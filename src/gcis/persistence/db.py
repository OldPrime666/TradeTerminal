from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

class Base(DeclarativeBase):
    pass

def get_engine(database_url: str | None = None):
    from gcis.core.config import get_config
    if database_url is None:
        cfg = get_config()
        database_url = cfg.get("database", {}).get("url", "sqlite:///var/gcis.db")
        # Ensure var directory exists for sqlite
        if database_url.startswith("sqlite"):
            # extract path
            path = database_url.split("///")[-1].split("?")[0]
            if path and path != ":memory:":
                p = Path(path)
                if not p.is_absolute():
                    p = Path(__file__).resolve().parents[3] / p
                p.parent.mkdir(parents=True, exist_ok=True)
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True, future=True)
    # For postgres, ensure we can handle timestamptz; for sqlite, no need
    return engine

_engine = None
_SessionLocal = None

def init_db(database_url: str | None = None):
    global _engine, _SessionLocal
    _engine = get_engine(database_url)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    # create tables lazily via models import
    from gcis.persistence import models  # noqa: F401
    Base.metadata.create_all(bind=_engine)
    return _engine

def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()

def get_engine_singleton():
    global _engine
    if _engine is None:
        init_db()
    return _engine
