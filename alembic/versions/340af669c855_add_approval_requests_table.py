"""add approval_requests table

Revision ID: 340af669c855
Revises: 15a78862f63e
Create Date: 2026-02-25 11:36:55.644653

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '340af669c855'
down_revision = '15a78862f63e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Let SQLAlchemy create the enum type automatically
    op.create_table('approval_requests',
    sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('stage', sa.String(length=64), nullable=False),
    sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='approval_status'), server_default='pending', nullable=False),
    sa.Column('reviewer_comment', sa.Text(), nullable=True),
    sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_approval_requests_project_id'), 'approval_requests', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_approval_requests_project_id'), table_name='approval_requests')
    op.drop_table('approval_requests')
