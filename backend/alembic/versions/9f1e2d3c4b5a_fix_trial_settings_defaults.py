"""Fix trial_settings defaults and existing production values

The original add_free_trial_models migration seeded trial_settings with
duration_days=2, max_trials_per_month=2 - which never matched the actual
business rule (3-day trial, 1 trial per Telegram ID per calendar month)
enforced everywhere else (TrialSetting model defaults, get_trial_settings()
fallback, request_free_trial() fallback). Any database that already ran
that migration is still sitting on the wrong values.

This migration:
  1. Fixes the column server_defaults going forward (for any fresh DB that
     runs the full chain, or any row inserted via raw SQL without going
     through the ORM).
  2. Directly corrects any existing row(s) in trial_settings so the
     database - the actual source of truth at runtime - matches the
     3-day / 1-per-month rule exactly, regardless of what was seeded
     before.

Revision ID: 9f1e2d3c4b5a
Revises: 513209c2dab3
Create Date: 2026-08-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f1e2d3c4b5a'
down_revision = '513209c2dab3'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Correct the server_defaults on the columns themselves.
    op.alter_column(
        'trial_settings', 'duration_days',
        existing_type=sa.Integer(),
        server_default='3',
    )
    op.alter_column(
        'trial_settings', 'max_trials_per_month',
        existing_type=sa.Integer(),
        server_default='1',
    )

    # 2. Force existing rows to the correct production values. The database
    # is the source of truth for this setting - not hardcoded defaults in
    # the app - so any row left over from the old 2/2 seed must be fixed
    # directly rather than relying on someone remembering to edit it via
    # the admin UI.
    op.execute(
        "UPDATE trial_settings SET duration_days = 3 WHERE duration_days = 2"
    )
    op.execute(
        "UPDATE trial_settings SET max_trials_per_month = 1 WHERE max_trials_per_month = 2"
    )

    # 3. If, for whatever reason, no row exists yet in this database, seed
    # the correct one now so the app never falls back to in-code defaults.
    op.execute(
        """
        INSERT INTO trial_settings (enabled, duration_days, max_trials_per_month, allow_existing_customers, trial_plan_name)
        SELECT true, 3, 1, false, 'Trial EA'
        WHERE NOT EXISTS (SELECT 1 FROM trial_settings)
        """
    )


def downgrade():
    op.alter_column(
        'trial_settings', 'duration_days',
        existing_type=sa.Integer(),
        server_default='2',
    )
    op.alter_column(
        'trial_settings', 'max_trials_per_month',
        existing_type=sa.Integer(),
        server_default='2',
    )
