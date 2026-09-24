"""Phase9: universe_sync_state cursor/latency"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
revision: str = 'b8c7d6e5f4a3'
down_revision: Union[str, None] = 'a7f3c9d1e2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    op.create_table('universe_sync_state',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('last_cursor', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_latency_ms', sa.Integer(), nullable=True),
        sa.Column('last_venue', sa.String(), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("INSERT INTO universe_sync_state (id, run_count, error_count) VALUES (1,0,0)")
def downgrade() -> None:
    op.drop_table('universe_sync_state')
