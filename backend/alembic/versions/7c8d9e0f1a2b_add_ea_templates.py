"""Add ea_templates table for web-admin EA source/version management

Revision ID: 7c8d9e0f1a2b
Revises: 9f1e2d3c4b5a
Create Date: 2026-08-17 00:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c8d9e0f1a2b'
down_revision = '9f1e2d3c4b5a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ea_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('version_label', sa.String(), nullable=True),
        sa.Column('filename', sa.String(), nullable=True),
        sa.Column('source_code', sa.Text(), nullable=True),
        sa.Column('file_size', sa.Integer(), server_default='0', nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='0', nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('uploaded_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ea_templates_id'), 'ea_templates', ['id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_ea_templates_id'), table_name='ea_templates')
    op.drop_table('ea_templates')
