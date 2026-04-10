"""Project model for persisting generated projects."""

import enum
from sqlalchemy import Column, String, Text, Enum as SAEnum, ForeignKey, JSON
from sqlalchemy.orm import relationship

from foundry.database import Base
from foundry.models.base import BaseModel
from foundry.models.approval import ApprovalPolicy


class ProjectStatus(str, enum.Enum):
    """Status of a project through the generation lifecycle."""
    created = "created"
    running_pm = "running_pm"
    running_architect = "running_architect"
    running_engineer = "running_engineer"
    running_code_review = "running_code_review"
    running_reflexion = "running_reflexion"
    running_devops = "running_devops"
    paused = "paused"
    completed = "completed"
    failed = "failed"


class Project(BaseModel, Base):
    """Persisted project record."""
    __tablename__ = "projects"

    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    requirements = Column(Text, nullable=False)
    status = Column(
        SAEnum(ProjectStatus, name="project_status", create_constraint=True),
        nullable=False,
        default=ProjectStatus.created,
        server_default=ProjectStatus.created.value,
    )
    
    # Approval policy configuration
    approval_policy = Column(
        SAEnum(ApprovalPolicy, name="approval_policy", create_constraint=True),
        nullable=False,
        default=ApprovalPolicy.standard,
        server_default=ApprovalPolicy.standard.value,
        doc="Approval policy for this project",
    )

    # Multi-language support
    language = Column(String(50), nullable=False, default="python", server_default="python")
    framework = Column(String(100), nullable=True)

    # Agent outputs stored as JSON for flexibility
    prd = Column(JSON, nullable=True)
    architecture = Column(JSON, nullable=True)
    code_review = Column(JSON, nullable=True)
    generated_path = Column(String(512), nullable=True)

    # Relationships
    artifacts = relationship("Artifact", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project {self.name} ({self.status.value})>"
