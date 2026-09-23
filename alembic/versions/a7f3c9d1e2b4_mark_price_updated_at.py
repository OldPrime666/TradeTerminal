"""mark_price_updated_at — Phase7 complete: separate mark freshness from price

Revision ID: a7f3c9d1e2b4
Revises: 81a3a75374bd
Create Date: 2026-09-22 08:45:00
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7f3c9d1e2b4'
down_revision: Union[str, None] = '81a3a75374bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add distinct mark_price event_time — separate from price updated_at (Phase7 complete)
    op.add_column('latest_quotes', sa.Column('mark_price_updated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('latest_quotes', 'mark_price_updated_at')
