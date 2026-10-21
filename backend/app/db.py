import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql:///arca")
BLOB_DIR = Path(os.environ.get("BLOB_DIR", Path(__file__).resolve().parents[2] / "data" / "blobs"))

pool = ConnectionPool(DATABASE_URL, kwargs={"row_factory": dict_row, "autocommit": True}, open=False)


def init_db() -> None:
    BLOB_DIR.mkdir(parents=True, exist_ok=True)
    pool.open()
    sql = (Path(__file__).parent / "models.sql").read_text()
    with pool.connection() as conn:
        conn.execute(sql)


def audit(conn: psycopg.Connection, actor: str, action: str, entity: str, payload: dict) -> None:
    conn.execute(
        "INSERT INTO audit_log(actor, action, entity, payload) VALUES (%s, %s, %s, %s)",
        (actor, action, entity, json.dumps(payload)),
    )
