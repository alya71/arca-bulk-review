"""HTTP API. Identity is a plain X-User header for the demo (SSO in production);
every state change is written to audit_log with the actor."""
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .db import BLOB_DIR, audit, init_db, pool
from .extract.run import PROMPT_VERSION
from .ingest import ingest_pdf
from .llm import EMBED_MODEL, EXTRACT_MODEL, where_it_runs
from .presets import PRESETS
from .search import find_candidates


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield
    pool.close()


app = FastAPI(title="Bulk Review", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def user_of(x_user: str | None) -> str:
    return (x_user or "anonymous").strip() or "anonymous"


# ---------------------------------------------------------------- documents
@app.get("/api/documents")
def list_documents(doc_type: str | None = None):
    with pool.connection() as conn:
        q = "SELECT id, filename, doc_type, product, title, page_count, status, created_at FROM documents"
        return conn.execute(q + (" WHERE doc_type=%s" if doc_type else "") + " ORDER BY filename",
                            (doc_type,) if doc_type else ()).fetchall()


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...), x_user: str | None = Header(None)):
    data = await file.read()
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "only PDF files are supported")
    return {"id": ingest_pdf(data, file.filename or "upload.pdf", actor=user_of(x_user))}


@app.get("/api/documents/{doc_id}/file")
def document_file(doc_id: int):
    """The original raw file, byte-for-byte. Highlights are drawn on this, never on parsed text."""
    with pool.connection() as conn:
        d = conn.execute("SELECT sha256, filename FROM documents WHERE id=%s", (doc_id,)).fetchone()
    if not d:
        raise HTTPException(404)
    return FileResponse(BLOB_DIR / f"{d['sha256']}.pdf", media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{d["filename"]}"'})


# ---------------------------------------------------------------- reviews
@app.get("/api/presets")
def presets():
    return PRESETS


class QuestionIn(BaseModel):
    key: str
    prompt: str
    answer_type: str = "text"
    max_words: int | None = Field(None, ge=1)


class ReviewIn(BaseModel):
    name: str
    doc_filter: dict = {}
    reference_doc_id: int | None = None
    purpose: str | None = None
    questions: list[QuestionIn]


@app.post("/api/reviews")
def create_review(body: ReviewIn, x_user: str | None = Header(None)):
    if not body.questions:
        raise HTTPException(400, "at least one question is required")
    actor = user_of(x_user)
    with pool.connection() as conn, conn.transaction():
        rid = conn.execute(
            "INSERT INTO reviews(name, doc_filter, reference_doc_id, created_by, purpose) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (body.name, json.dumps(body.doc_filter), body.reference_doc_id, actor, body.purpose)).fetchone()["id"]
        for i, q in enumerate(body.questions):
            conn.execute("INSERT INTO questions(review_id, ord, key, prompt, answer_type, max_words) VALUES (%s,%s,%s,%s,%s,%s)",
                         (rid, i, q.key, q.prompt, q.answer_type, q.max_words))
        audit(conn, actor, "create_review", f"review:{rid}", body.model_dump())
    return {"id": rid}


@app.get("/api/reviews")
def list_reviews():
    with pool.connection() as conn:
        return conn.execute(
            """SELECT r.id, r.name, r.purpose, r.doc_filter->>'product' AS product, r.created_by, r.created_at,
                      (SELECT max(id) FROM jobs WHERE review_id=r.id) AS latest_job,
                      (SELECT count(*) FROM review_documents WHERE review_id=r.id) AS docs
               FROM reviews r ORDER BY r.id DESC LIMIT 20""").fetchall()


@app.get("/api/reviews/{rid}")
def get_review(rid: int):
    with pool.connection() as conn:
        r = conn.execute("SELECT * FROM reviews WHERE id=%s", (rid,)).fetchone()
        if not r:
            raise HTTPException(404)
        r["questions"] = conn.execute("SELECT * FROM questions WHERE review_id=%s ORDER BY ord", (rid,)).fetchall()
        r["documents"] = conn.execute(
            """SELECT d.id, d.filename, d.doc_type, d.product, rd.source FROM review_documents rd
               JOIN documents d ON d.id = rd.doc_id WHERE rd.review_id=%s ORDER BY d.filename""", (rid,)).fetchall()
        r["reference_doc"] = conn.execute("SELECT id, filename FROM documents WHERE id=%s",
                                          (r["reference_doc_id"],)).fetchone() if r["reference_doc_id"] else None
        r["jobs"] = conn.execute("SELECT * FROM jobs WHERE review_id=%s ORDER BY id DESC", (rid,)).fetchall()
        return r


@app.get("/api/reviews/{rid}/candidates")
def candidates(rid: int):
    with pool.connection() as conn:
        r = conn.execute("SELECT doc_filter FROM reviews WHERE id=%s", (rid,)).fetchone()
        if not r:
            raise HTTPException(404)
        f = r["doc_filter"]
        return find_candidates(conn, f.get("doc_type"), f.get("product"), f.get("query"))


class ConfirmIn(BaseModel):
    doc_ids: list[int]
    manual_ids: list[int] = []  # added by hand rather than proposed by search


@app.put("/api/reviews/{rid}/documents")
def confirm_documents(rid: int, body: ConfirmIn, x_user: str | None = Header(None)):
    actor = user_of(x_user)
    with pool.connection() as conn, conn.transaction():
        conn.execute("DELETE FROM review_documents WHERE review_id=%s", (rid,))
        for d in body.doc_ids:
            conn.execute("INSERT INTO review_documents(review_id, doc_id, source, added_by) VALUES (%s,%s,%s,%s)",
                         (rid, d, "manual" if d in body.manual_ids else "search", actor))
        audit(conn, actor, "confirm_documents", f"review:{rid}", body.model_dump())
    return {"count": len(body.doc_ids)}


@app.post("/api/reviews/{rid}/jobs")
def start_job(rid: int, x_user: str | None = Header(None)):
    actor = user_of(x_user)
    with pool.connection() as conn, conn.transaction():
        docs = conn.execute("SELECT doc_id FROM review_documents WHERE review_id=%s", (rid,)).fetchall()
        if not docs:
            raise HTTPException(400, "confirm the document set before running")
        jid = conn.execute(
            "INSERT INTO jobs(review_id, model, prompt_version, created_by) VALUES (%s,%s,%s,%s) RETURNING id",
            (rid, EXTRACT_MODEL, PROMPT_VERSION, actor)).fetchone()["id"]
        with conn.cursor() as cur:  # fan out: one task per document
            cur.executemany("INSERT INTO tasks(job_id, doc_id) VALUES (%s,%s)", [(jid, d["doc_id"]) for d in docs])
        audit(conn, actor, "start_job", f"job:{jid}",
              {"review_id": rid, "docs": len(docs), "model": EXTRACT_MODEL, "prompt_version": PROMPT_VERSION})
    return {"id": jid}


# ---------------------------------------------------------------- results
@app.get("/api/jobs/{jid}")
def get_job(jid: int):
    with pool.connection() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id=%s", (jid,)).fetchone()
        if not job:
            raise HTTPException(404)
        job["progress"] = conn.execute(
            "SELECT status, count(*) AS n FROM tasks WHERE job_id=%s GROUP BY status", (jid,)).fetchall()
        job["questions"] = conn.execute("SELECT * FROM questions WHERE review_id=%s ORDER BY ord",
                                        (job["review_id"],)).fetchall()
        job["rows"] = conn.execute(
            """SELECT t.doc_id, t.status AS task_status, t.error, d.filename, d.product, d.page_count
               FROM tasks t JOIN documents d ON d.id=t.doc_id WHERE t.job_id=%s ORDER BY d.filename""", (jid,)).fetchall()
        cells = conn.execute("SELECT * FROM cells WHERE job_id=%s", (jid,)).fetchall()
        cites = conn.execute(
            """SELECT ci.*, d.filename FROM citations ci JOIN cells c ON c.id=ci.cell_id
               JOIN documents d ON d.id=ci.doc_id WHERE c.job_id=%s ORDER BY ci.id""", (jid,)).fetchall()
        by_cell: dict[int, list] = {}
        for ci in cites:
            by_cell.setdefault(ci["cell_id"], []).append(ci)
        for c in cells:
            c["citations"] = by_cell.get(c["id"], [])
        job["cells"] = cells
        return job


class CellReviewIn(BaseModel):
    action: str  # accept | edit | flag
    value: list[str] | None = None
    note: str | None = None


@app.post("/api/cells/{cid}/review")
def review_cell(cid: int, body: CellReviewIn, x_user: str | None = Header(None)):
    if body.action not in ("accept", "edit", "flag"):
        raise HTTPException(400, "action must be accept, edit or flag")
    actor = user_of(x_user)
    if actor == "anonymous":  # a sign-off has to be attributable to a person
        raise HTTPException(400, "Enter your name in the Reviewer field before accepting, editing or flagging")
    state = {"accept": "accepted", "edit": "edited", "flag": "flagged"}[body.action]
    with pool.connection() as conn, conn.transaction():
        cell = conn.execute("SELECT c.*, j.model, j.prompt_version FROM cells c JOIN jobs j ON j.id=c.job_id "
                            "WHERE c.id=%s", (cid,)).fetchone()
        if not cell:
            raise HTTPException(404)
        new_value = cell["value"]
        if body.action == "edit":
            new_value = {**(cell["value"] or {}), "items": body.value or [], "edited_from": cell["value"]}
        conn.execute("UPDATE cells SET reviewer_state=%s, reviewer=%s, reviewed_at=now(), value=%s WHERE id=%s",
                     (state, actor, json.dumps(new_value), cid))
        audit(conn, actor, f"cell_{body.action}", f"cell:{cid}",
              {"before": cell["value"], "after": new_value, "note": body.note,
               "model": cell["model"], "prompt_version": cell["prompt_version"]})
    return {"reviewer_state": state}


@app.get("/api/system")
def system():
    """What the Security page shows: which model is configured and where document text goes."""
    return {"extract_model": EXTRACT_MODEL, "embed_model": EMBED_MODEL, "extract_host": where_it_runs(EXTRACT_MODEL),
            "embed_host": where_it_runs(EMBED_MODEL)}


@app.get("/api/audit")
def audit_log(entity: str | None = None, limit: int = 200):
    with pool.connection() as conn:
        if entity:
            return conn.execute("SELECT * FROM audit_log WHERE entity=%s ORDER BY id DESC LIMIT %s",
                                (entity, limit)).fetchall()
        return conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT %s", (limit,)).fetchall()
