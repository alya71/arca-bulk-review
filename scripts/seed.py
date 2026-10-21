"""Ingest every synthetic PDF. Re-running is a no-op thanks to content hashing."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import init_db, pool  # noqa: E402
from app.ingest import ingest_pdf  # noqa: E402

if __name__ == "__main__":
    init_db()
    for f in sorted((ROOT / "data" / "synthetic").glob("*.pdf")):
        doc_id = ingest_pdf(f.read_bytes(), f.name, actor="seed")
        print(f"{doc_id:>3}  {f.name}")
    pool.close()
