"""update approval workflow

Revision ID: 450bc123d456
Revises: 340af669c855
Create Date: 2026-02-25 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '450bc123d456'
down_revision = '340af669c855'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create new enum types
    op.execute("CREATE TYPE approval_type AS ENUM ('plan', 'deployment', 'cost_override', 'security_review', 'component')")
    op.execute("CREATE TYPE approval_policy AS ENUM ('autonomous', 'standard', 'strict')")
    
    # Update approval_status enum to include timeout and cancelled
    op.execute("ALTER TYPE approval_status ADD VALUE 'timeout'")
    op.execute("ALTER TYPE approval_status ADD VALUE 'cancelled'")
    
    # Drop old columns from approval_requests
    op.drop_column('approval_requests', 'stage')
    op.drop_column('approval_requests', 'reviewer_comment')
    
    # Add new columns to approval_requests
    op.add_column('approval_requests', sa.Column('request_type', sa.Enum('plan', 'deployment', 'cost_override', 'security_review', 'component', name='approval_type'), nullable=False, server_default='plan'))
    op.add_column('approval_requests', sa.Column('estimated_cost', sa.Float(), nullable=True))
    op.add_column('approval_requests', sa.Column('timeout_at', sa.DateTime(), nullable=True))
    op.add_column('approval_requests', sa.Column('responded_at', sa.DateTime(), nullable=True))
    op.add_column('approval_requests', sa.Column('response', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Rename context column to content
    op.alter_column('approval_requests', 'context', new_column_name='content', nullable=False)
    
    # Add index on status
    op.create_index(op.f('ix_approval_requests_status'), 'approval_requests', ['status'], unique=False)
    
    # Add approval_policy to projects table
    op.add_column('projects', sa.Column('approval_policy', sa.Enum('autonomous', 'standard', 'strict', name='approval_policy'), nullable=False, server_default='standard'))
    
    # Add paused status to project_status enum
    op.execute("ALTER TYPE project_status ADD VALUE 'paused'")


def downgrade() -> None:
    # Remove approval_policy from projects
    op.drop_column('projects', 'approval_policy')
    
    # Remove index
    op.drop_index(op.f('ix_approval_requests_status'), table_name='approval_requests')
    
    # Rename content back to context
    op.alter_column('approval_requests', 'content', new_column_name='context', nullable=True)
    
    # Remove new columns
    op.drop_column('approval_requests', 'response')
    op.drop_column('approval_requests', 'responded_at')
    op.drop_column('approval_requests', 'timeout_at')
    op.drop_column('approval_requests', 'estimated_cost')
    op.drop_column('approval_requests', 'request_type')
    
    # Add back old columns
    op.add_column('approval_requests', sa.Column('reviewer_comment', sa.Text(), nullable=True))
    op.add_column('approval_requests', sa.Column('stage', sa.String(length=64), nullable=False, server_default='unknown'))
    
    # Drop enum types
    op.execute("DROP TYPE approval_policy")
    op.execute("DROP TYPE approval_type")
    
    # Note: Cannot remove enum values from approval_status and project_status in PostgreSQL
    # Would require recreating the enum type
