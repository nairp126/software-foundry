"""add projects and artifacts

Revision ID: 15a78862f63e
Revises: 
Create Date: 2026-02-25 00:02:30.948390

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '15a78862f63e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Let SQLAlchemy create the enum types automatically
    op.create_table('projects',
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('requirements', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('created', 'running_pm', 'running_architect', 'running_engineer', 'running_code_review', 'running_reflexion', 'running_devops', 'completed', 'failed', name='project_status'), server_default='created', nullable=False),
    sa.Column('prd', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('architecture', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('code_review', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('generated_path', sa.String(length=512), nullable=True),
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projects_name'), 'projects', ['name'], unique=False)
    op.create_table('artifacts',
    sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('filename', sa.String(length=512), nullable=False),
    sa.Column('artifact_type', sa.Enum('code', 'config', 'documentation', 'diagram', 'log', name='artifact_type'), nullable=False),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_artifacts_project_id'), 'artifacts', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_artifacts_project_id'), table_name='artifacts')
    op.drop_table('artifacts')
    op.drop_index(op.f('ix_projects_name'), table_name='projects')
    op.drop_table('projects')
