"""Add language and framework columns to projects table.

Revision ID: 470bc123d458
Revises: 460bc123d457
Create Date: 2026-03-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "470bc123d458"
down_revision = "460bc123d457"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "language",
            sa.String(50),
            nullable=False,
            server_default="python",
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "framework",
            sa.String(100),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "framework")
    op.drop_column("projects", "language")
