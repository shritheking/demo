"""Add free trial models

Revision ID: 3b4c5d6e7f8g
Revises: 2b3c4d5e6f7g
Create Date: 2026-08-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3b4c5d6e7f8g'
down_revision = '2b3c4d5e6f7g'
branch_labels = None
depends_on = None


def upgrade():
    # Add license_type to licenses table
    op.add_column('licenses', sa.Column('license_type', sa.String(), server_default='paid', nullable=True))
    
    # Create trial_settings table
    op.create_table('trial_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default='1', nullable=True),
        # Business rule: 3-day trial, 1 trial per Telegram ID per calendar month.
        sa.Column('duration_days', sa.Integer(), server_default='3', nullable=True),
        sa.Column('max_trials_per_month', sa.Integer(), server_default='1', nullable=True),
        sa.Column('allow_existing_customers', sa.Boolean(), server_default='0', nullable=True),
        sa.Column('trial_plan_name', sa.String(), server_default='Trial EA', nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trial_settings_id'), 'trial_settings', ['id'], unique=False)

    # Create trial_activations table
    op.create_table('trial_activations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_user_id', sa.String(), nullable=True),
        sa.Column('mt5_id', sa.String(), nullable=True),
        sa.Column('license_id', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('month_key', sa.String(), nullable=True),
        sa.Column('status', sa.String(), server_default='active', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['license_id'], ['licenses.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trial_activations_id'), 'trial_activations', ['id'], unique=False)
    op.create_index(op.f('ix_trial_activations_month_key'), 'trial_activations', ['month_key'], unique=False)
    op.create_index(op.f('ix_trial_activations_mt5_id'), 'trial_activations', ['mt5_id'], unique=False)
    op.create_index(op.f('ix_trial_activations_telegram_user_id'), 'trial_activations', ['telegram_user_id'], unique=False)
    
    # We also need to seed the trial settings with a default row if not exists.
    # We can do this in the app logic or via a direct insert here.
    op.execute("INSERT INTO trial_settings (enabled, duration_days, max_trials_per_month, allow_existing_customers, trial_plan_name) VALUES (true, 3, 1, false, 'Trial EA')")

def downgrade():
    op.drop_index(op.f('ix_trial_activations_telegram_user_id'), table_name='trial_activations')
    op.drop_index(op.f('ix_trial_activations_mt5_id'), table_name='trial_activations')
    op.drop_index(op.f('ix_trial_activations_month_key'), table_name='trial_activations')
    op.drop_index(op.f('ix_trial_activations_id'), table_name='trial_activations')
    op.drop_table('trial_activations')
    
    op.drop_index(op.f('ix_trial_settings_id'), table_name='trial_settings')
    op.drop_table('trial_settings')
    
    op.drop_column('licenses', 'license_type')
