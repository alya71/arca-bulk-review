"""Recompute every chunk embedding with the configured embedding model (after switching providers).
Usage: python scripts/reembed.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import pool  # noqa: E402
from app.llm import EMBED_MODEL, embed  # noqa: E402


def main() -> None:
    pool.open()
    with pool.connection() as conn:
        chunks = conn.execute("SELECT id, coalesce(section_path, '') AS sp, text FROM chunks ORDER BY id").fetchall()
        vectors = embed([f"{c['sp']}\n{c['text']}" for c in chunks])
        with conn.transaction():
            for c, v in zip(chunks, vectors):
                conn.execute("UPDATE chunks SET embedding=%s::vector WHERE id=%s", (str(v), c["id"]))
    pool.close()
    print(f"re-embedded {len(chunks)} chunks with {EMBED_MODEL}")


if __name__ == "__main__":
    main()
