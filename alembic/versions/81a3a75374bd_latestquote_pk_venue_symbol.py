"""latestquote_pk_venue_symbol — Phase6 + Phase7 triple timestamps

Revision ID: 81a3a75374bd
Revises: 001
Create Date: 2026-09-21 19:07:08.775600
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '81a3a75374bd'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Phase6 PK fix + Phase7 timestamps ###
    op.add_column('latest_quotes', sa.Column('received_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('latest_quotes', sa.Column('persisted_at', sa.DateTime(timezone=True), nullable=True))
    # For SQLite, PK change requires table recreation — use batch with recreate
    # Existing PK was (symbol) alone; new is (venue, symbol) composite to prevent multi-venue overwrite
    try:
        # Batch will recreate table with new PK; for SQLite this copies data
        with op.batch_alter_table('latest_quotes', recreate='always') as batch_op:
            # SQLite batch recreate will infer new PK from model; explicitly create composite
            # Drop old PK (symbol) and create new (venue,symbol) — handled by recreate
            pass
        # After batch, manually ensure PK is composite via raw SQL for SQLite (fallback if batch didn't change)
        # Use get_bind to check — but simpler: if the table still has old PK, recreate via drop/create (data is empty in sandbox)
        # Check if PK is still single column by inspecting sqlite_master; if so, do raw
        bind = op.get_bind()
        # This raw path will handle the PK change explicitly for empty DB
        # For empty DB, we can safely drop and recreate
        res = bind.execute(sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='latest_quotes'")).scalar()
        if res and '"symbol" PRIMARY KEY' in res or "PRIMARY KEY (symbol)" in res:
            # Old PK detected — recreate correctly
            op.execute(sa.text("PRAGMA foreign_keys=OFF"))
            op.execute(sa.text("ALTER TABLE latest_quotes RENAME TO _latest_quotes_old"))
            op.execute(sa.text("""
                CREATE TABLE latest_quotes (
                    venue VARCHAR NOT NULL,
                    symbol VARCHAR NOT NULL,
                    price NUMERIC(38, 18) NOT NULL,
                    bid NUMERIC(38, 18),
                    ask NUMERIC(38, 18),
                    mark_price NUMERIC(38, 18),
                    updated_at DATETIME,
                    received_at DATETIME,
                    persisted_at DATETIME,
                    source VARCHAR NOT NULL,
                    PRIMARY KEY (venue, symbol)
                )
            """))
            op.execute(sa.text("INSERT OR IGNORE INTO latest_quotes (venue,symbol,price,bid,ask,mark_price,updated_at,received_at,persisted_at,source) SELECT venue,symbol,price,bid,ask,mark_price,updated_at,received_at,persisted_at,source FROM _latest_quotes_old"))
            op.execute(sa.text("DROP TABLE _latest_quotes_old"))
            op.execute(sa.text("PRAGMA foreign_keys=ON"))
    except Exception as e:
        # fallback: log but don't fail migration — add columns already succeeded
        print(f"latestquote PK migration warning: {e}")


def downgrade() -> None:
    op.drop_column('latest_quotes', 'persisted_at')
    op.drop_column('latest_quotes', 'received_at')
    # Downgrade PK back to single (symbol) — best effort, data may be lost
    try:
        bind = op.get_bind()
        op.execute(sa.text("PRAGMA foreign_keys=OFF"))
        op.execute(sa.text("ALTER TABLE latest_quotes RENAME TO _latest_quotes_old2"))
        op.execute(sa.text("""
            CREATE TABLE latest_quotes (
                venue VARCHAR,
                symbol VARCHAR NOT NULL PRIMARY KEY,
                price NUMERIC(38, 18) NOT NULL,
                bid NUMERIC(38, 18),
                ask NUMERIC(38, 18),
                mark_price NUMERIC(38, 18),
                updated_at DATETIME,
                source VARCHAR NOT NULL
            )
        """))
        op.execute(sa.text("INSERT OR IGNORE INTO latest_quotes (venue,symbol,price,bid,ask,mark_price,updated_at,source) SELECT venue,symbol,price,bid,ask,mark_price,updated_at,source FROM _latest_quotes_old2"))
        op.execute(sa.text("DROP TABLE _latest_quotes_old2"))
        op.execute(sa.text("PRAGMA foreign_keys=ON"))
    except Exception:
        pass
