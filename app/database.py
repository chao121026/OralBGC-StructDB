from contextlib import contextmanager
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from .config import get_settings

def get_engine() -> Engine:
    db = get_settings().resolve_db()
    if not db.exists():
        raise RuntimeError("Configured read-only SQLite database is unavailable")
    uri = f"file:{db.as_posix()}?mode=ro"
    return create_engine("sqlite://", future=True, creator=lambda: sqlite3.connect(uri, uri=True))

@contextmanager
def db_connect():
    engine = get_engine()
    with engine.connect() as conn:
        yield conn

def table_exists(conn, name: str) -> bool:
    return bool(conn.execute(text("select 1 from sqlite_master where type='table' and name=:n"), {"n": name}).first())
