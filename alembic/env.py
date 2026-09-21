from logging.config import fileConfig
import sys
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# this is the Alembic Config object, which provides access to the values within the .ini file
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add src to path for imports
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# import Base metadata from gcis
try:
    from gcis.persistence.db import Base  # noqa: F401,E402
    from gcis.persistence import models  # noqa: F401,E402  # ensure models imported so tables registered
    target_metadata = Base.metadata
except Exception as e:
    # fallback — will still allow stamp/upgrade but without autogenerate
    print(f"WARN alembic env.py could not import Base metadata: {e}")
    target_metadata = None

def _get_db_url():
    # Prefer GCIS config if available, else ini
    try:
        from gcis.core.config import get_config  # noqa: E402
        cfg = get_config()
        url = cfg.get("database", {}).get("url")
        if url:
            return url
    except Exception:
        pass
    return config.get_main_option("sqlalchemy.url")

def run_migrations_offline() -> None:
    url = _get_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    # override sqlalchemy.url before engine_from_config if we have config url
    db_url = _get_db_url()
    if db_url:
        config.set_main_option("sqlalchemy.url", db_url)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
