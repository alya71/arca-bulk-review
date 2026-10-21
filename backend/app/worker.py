"""Queue worker. Postgres is the queue: claim with FOR UPDATE SKIP LOCKED and a lease,
so any number of worker processes can run, and a crashed worker's task is re-claimed
once its lease expires. Run: python -m app.worker"""
import json
import logging
import os
import threading
import time
import traceback

from .db import audit, init_db, pool
from .extract.run import run_task
from .llm import get_provider

log = logging.getLogger("worker")
CONCURRENCY = int(os.environ.get("WORKER_CONCURRENCY", "2"))  # per process; global cap = this × replicas
MAX_ATTEMPTS = 3
LEASE = os.environ.get("TASK_LEASE", "5 minutes")  # > p99 task time; re-runs are idempotent anyway

CLAIM_SQL = f"""
UPDATE tasks SET status='running', attempts=attempts+1, locked_until=now() + interval '{LEASE}'
WHERE id = (
  SELECT id FROM tasks
  WHERE (status='queued' AND run_after <= now()) OR (status='running' AND locked_until < now())
  ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1)
RETURNING *"""


def claim():
    with pool.connection() as conn:
        return conn.execute(CLAIM_SQL).fetchone()


def process(task: dict) -> None:
    with pool.connection() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id=%s", (task["job_id"],)).fetchone()
        provider = get_provider(job["model"])  # the job pins model + prompt version, not the worker
        review = conn.execute("SELECT * FROM reviews WHERE id=%s", (job["review_id"],)).fetchone()
        doc = conn.execute("SELECT * FROM documents WHERE id=%s", (task["doc_id"],)).fetchone()
        questions = conn.execute("SELECT * FROM questions WHERE review_id=%s ORDER BY ord", (review["id"],)).fetchall()
        cells = run_task(conn, provider, job, review, doc, questions)

        with conn.transaction():  # idempotent: re-running a task replaces its cells
            conn.execute("DELETE FROM cells WHERE job_id=%s AND doc_id=%s", (job["id"], doc["id"]))
            for c in cells:
                cell_id = conn.execute(
                    "INSERT INTO cells(job_id, doc_id, question_id, value, status) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                    (job["id"], doc["id"], c["question_id"], json.dumps(c["value"]), c["status"])).fetchone()["id"]
                for ci in c["citations"]:
                    conn.execute(
                        """INSERT INTO citations(cell_id, doc_id, chunk_id, quote, verified, match_score, page, rects)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (cell_id, ci["doc_id"], ci["chunk_id"], ci["quote"], ci["verified"], ci["match_score"],
                         ci["rects"][0]["page"] if ci["rects"] else None, json.dumps(ci["rects"])))
            conn.execute("UPDATE tasks SET status='done', error=NULL, locked_until=NULL WHERE id=%s", (task["id"],))
            audit(conn, "worker", "extract", f"task:{task['id']}",
                  {"job_id": job["id"], "doc_id": doc["id"], "model": provider.model,
                   "prompt_version": job["prompt_version"],
                   "statuses": {c["question_id"]: c["status"] for c in cells}})
        finish_job_if_done(conn, job["id"])


def fail(task: dict, err: str) -> None:
    with pool.connection() as conn:
        if task["attempts"] >= MAX_ATTEMPTS:
            conn.execute("UPDATE tasks SET status='failed', error=%s, locked_until=NULL WHERE id=%s", (err, task["id"]))
        else:  # exponential backoff
            conn.execute(
                """UPDATE tasks SET status='queued', error=%s, locked_until=NULL,
                   run_after = now() + make_interval(secs => 5 * power(2, attempts)) WHERE id=%s""",
                (err, task["id"]))
        finish_job_if_done(conn, task["job_id"])


def finish_job_if_done(conn, job_id: int) -> None:
    conn.execute(
        """UPDATE jobs SET finished_at=now(),
             status = CASE WHEN EXISTS (SELECT 1 FROM tasks WHERE job_id=%(j)s AND status='failed') THEN 'failed' ELSE 'done' END
           WHERE id=%(j)s AND finished_at IS NULL
             AND NOT EXISTS (SELECT 1 FROM tasks WHERE job_id=%(j)s AND status IN ('queued','running'))""",
        {"j": job_id})


def loop(n: int) -> None:
    while True:
        task = claim()
        if not task:
            time.sleep(1)
            continue
        log.info("[%d] task %s (job %s, doc %s, attempt %s)", n, task["id"], task["job_id"], task["doc_id"], task["attempts"])
        t0 = time.time()
        try:
            process(task)
            log.info("[%d] task %s done in %.1fs", n, task["id"], time.time() - t0)
        except Exception as e:
            log.error("[%d] task %s failed: %s", n, task["id"], e)
            fail(task, f"{e}\n{traceback.format_exc()[-1500:]}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    init_db()
    threads = [threading.Thread(target=loop, args=(i,), daemon=True) for i in range(CONCURRENCY)]
    for t in threads:
        t.start()
    log.info("worker started with concurrency=%d", CONCURRENCY)
    for t in threads:
        t.join()
