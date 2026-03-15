"""add review and devops to artifact_type enum

Revision ID: 480bc123d459
Revises: 470bc123d458
Create Date: 2026-03-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '480bc123d459'
down_revision = '470bc123d458'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires ALTER TYPE ... ADD VALUE outside of a transaction
    op.execute("ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'review'")
    op.execute("ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'devops'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; downgrade is a no-op
    pass
