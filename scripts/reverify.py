"""Re-check every stored citation with the current (exact-match) verifier.

Fills in source_text, downgrades any citation that no longer matches exactly, and
recomputes cell status (an answer with no verified quote is 'unverified').
Usage: python scripts/reverify.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import pool  # noqa: E402
from app.extract.verify import locate, rects_for  # noqa: E402


def main() -> None:
    pool.open()
    words: dict[int, list[dict]] = {}
    kept = dropped = 0
    with pool.connection() as conn, conn.transaction():
        for c in conn.execute("SELECT id, doc_id, quote, verified FROM citations ORDER BY id").fetchall():
            if c["doc_id"] not in words:
                words[c["doc_id"]] = conn.execute(
                    "SELECT idx, page, text, x0, y0, x1, y1 FROM words WHERE doc_id=%s ORDER BY idx", (c["doc_id"],)).fetchall()
            ws = words[c["doc_id"]]
            m = locate(c["quote"], ws)
            if c["verified"] and not m:
                dropped += 1
                print(f"  citation {c['id']}: no exact match, now unverified: {c['quote'][:90]!r}")
            kept += bool(m)
            rects = rects_for(ws, m.word_start, m.word_end) if m else []
            conn.execute("UPDATE citations SET verified=%s, match_score=%s, source_text=%s, rects=%s::jsonb, page=%s WHERE id=%s",
                         (m is not None, m.score if m else None, m.text if m else None,
                          json.dumps(rects), rects[0]["page"] if rects else None, c["id"]))
        changed = conn.execute(
            """UPDATE cells c SET status = CASE WHEN EXISTS (SELECT 1 FROM citations ci WHERE ci.cell_id=c.id AND ci.verified)
                                               THEN 'answered' ELSE 'unverified' END
               WHERE c.status IN ('answered', 'unverified') RETURNING c.id""").rowcount
    pool.close()
    print(f"{kept} citations verified exactly, {dropped} downgraded; {changed} answered/unverified cells re-evaluated")


if __name__ == "__main__":
    main()
