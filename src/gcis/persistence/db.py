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
        if database_url.startswith("sqlite"):
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
    return engine

_engine = None
_SessionLocal = None

def _run_alembic_upgrade(engine):
    """Run alembic upgrade head — production migrations (no create_all fallback)."""
    try:
        from alembic.config import Config
        from alembic import command
        # ensure models are imported so autogenerate target knows tables, but for upgrade we just need alembic
        from gcis.persistence import models  # noqa: F401
        ini_path = Path(__file__).resolve().parents[3] / "alembic.ini"
        if not ini_path.exists():
            return False
        cfg = Config(str(ini_path))
        # force url to current engine
        try:
            url_str = str(engine.url)
        except Exception:
            url_str = engine.url.render_as_string(hide_password=False)
        cfg.set_main_option("sqlalchemy.url", url_str)
        command.upgrade(cfg, "head")
        return True
    except Exception as e:
        # In test/offline, raise for visibility but don't silently create_all
        print(f"[db] alembic upgrade failed: {e}")
        return False

def init_db(database_url: str | None = None):
    global _engine, _SessionLocal
    _engine = get_engine(database_url)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    # Production migrations via alembic — no create_all fallback
    # For :memory: and tests, alembic upgrade will create tables as well
    from gcis.persistence import models  # noqa: F401  ensure Base metadata knows tables
    _run_alembic_upgrade(_engine)
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

def preflight_alembic_version(engine=None) -> dict:
    """Phase8 check: DB alembic_version must be at head; else NOT_READY."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from sqlalchemy import text as sa_text
        eng = engine or get_engine_singleton()
        # current version in DB
        with eng.connect() as conn:
            try:
                res = conn.execute(sa_text("SELECT version_num FROM alembic_version"))
                current = res.scalar()
            except Exception:
                current = None
        ini_path = Path(__file__).resolve().parents[3] / "alembic.ini"
        cfg = Config(str(ini_path))
        script = ScriptDirectory.from_config(cfg)
        head = script.get_current_head()
        ok = (current == head and current is not None)
        return {"current": current, "head": head, "ok": ok, "at_head": ok}
    except Exception as e:
        return {"current": None, "head": None, "ok": False, "error": str(e)}
