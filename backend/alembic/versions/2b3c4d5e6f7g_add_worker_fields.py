"""add_worker_fields

Revision ID: 2b3c4d5e6f7g
Revises: 1a2b3c4d5e6f
Create Date: 2026-08-08 17:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2b3c4d5e6f7g'
down_revision = '1a2b3c4d5e6f'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if mt5_id exists in orders
    if 'mt5_id' not in [c['name'] for c in inspector.get_columns('orders')]:
        op.add_column('orders', sa.Column('mt5_id', sa.String(), nullable=True))
        
    # Check if worker_id exists in compile_jobs
    compile_jobs_cols = [c['name'] for c in inspector.get_columns('compile_jobs')]
    if 'worker_id' not in compile_jobs_cols:
        op.add_column('compile_jobs', sa.Column('worker_id', sa.String(), nullable=True))
        op.add_column('compile_jobs', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
        op.add_column('compile_jobs', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
        op.add_column('compile_jobs', sa.Column('error_message', sa.Text(), nullable=True))
        op.add_column('compile_jobs', sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=True))

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'mt5_id' in [c['name'] for c in inspector.get_columns('orders')]:
        op.drop_column('orders', 'mt5_id')
        
    compile_jobs_cols = [c['name'] for c in inspector.get_columns('compile_jobs')]
    if 'worker_id' in compile_jobs_cols:
        op.drop_column('compile_jobs', 'worker_id')
        op.drop_column('compile_jobs', 'started_at')
        op.drop_column('compile_jobs', 'completed_at')
        op.drop_column('compile_jobs', 'error_message')
        op.drop_column('compile_jobs', 'attempt_count')
