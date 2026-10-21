"""Ingest: raw bytes → blob store → words + chunks + tags + embeddings. Idempotent by content hash."""
import hashlib
import logging

from pgvector.psycopg import register_vector

from ..db import BLOB_DIR, audit, pool
from ..llm import embed
from .parse_pymupdf import parse_pdf
from .tag import tag

log = logging.getLogger(__name__)


def ingest_pdf(data: bytes, filename: str, actor: str = "system") -> int:
    sha = hashlib.sha256(data).hexdigest()
    with pool.connection() as conn:
        row = conn.execute("SELECT id, status FROM documents WHERE sha256=%s", (sha,)).fetchone()
        if row and row["status"] == "ingested":
            return row["id"]

    (BLOB_DIR / f"{sha}.pdf").write_bytes(data)  # keep the original, untouched
    parsed = parse_pdf(data)
    full_text = " ".join(w.text for w in parsed.words)
    tags = tag(filename, full_text)
    title = parsed.chunks[0].section_path or parsed.chunks[0].text[:120] if parsed.chunks else filename
    try:
        vectors = embed([f"{c.section_path}\n{c.text}" for c in parsed.chunks]) if parsed.chunks else []
    except Exception as e:  # embeddings are an optimization for search; never block ingest on them
        log.warning("embedding failed for %s: %s", filename, e)
        vectors = [None] * len(parsed.chunks)

    with pool.connection() as conn, conn.transaction():
        register_vector(conn)
        doc_id = conn.execute(
            """INSERT INTO documents(sha256, filename, doc_type, product, ectd_section, title, page_count, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'ingested')
               ON CONFLICT (sha256) DO UPDATE SET status='ingested', doc_type=EXCLUDED.doc_type,
                 product=EXCLUDED.product, ectd_section=EXCLUDED.ectd_section, title=EXCLUDED.title
               RETURNING id""",
            (sha, filename, tags["doc_type"], tags["product"], tags["ectd_section"], title, parsed.page_count),
        ).fetchone()["id"]
        conn.execute("DELETE FROM words WHERE doc_id=%s", (doc_id,))
        conn.execute("DELETE FROM chunks WHERE doc_id=%s", (doc_id,))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO words(doc_id, idx, page, text, x0, y0, x1, y1) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                [(doc_id, w.idx, w.page, w.text, w.x0, w.y0, w.x1, w.y1) for w in parsed.words],
            )
            cur.executemany(
                """INSERT INTO chunks(doc_id, ord, section_path, text, page_start, page_end, word_start, word_end, embedding)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                [(doc_id, c.ord, c.section_path, c.text, c.page_start, c.page_end, c.word_start, c.word_end, v)
                 for c, v in zip(parsed.chunks, vectors)],
            )
        audit(conn, actor, "ingest", f"document:{doc_id}",
              {"filename": filename, "sha256": sha, "parser": "pymupdf", "chunks": len(parsed.chunks), **tags})
    return doc_id
