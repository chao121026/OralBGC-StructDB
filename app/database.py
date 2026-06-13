from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from .config import get_settings

def get_engine() -> Engine:
    db = get_settings().resolve_db()
    db.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db}", future=True)

@contextmanager
def db_connect():
    engine = get_engine()
    with engine.connect() as conn:
        yield conn

def table_exists(conn, name: str) -> bool:
    return bool(conn.execute(text("select 1 from sqlite_master where type='table' and name=:n"), {"n": name}).first())
