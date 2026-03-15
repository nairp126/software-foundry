"""Artifact model for persisting generated files and outputs."""

import enum
from sqlalchemy import Column, String, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from foundry.database import Base
from foundry.models.base import BaseModel


class ArtifactType(str, enum.Enum):
    """Type of generated artifact."""
    code = "code"
    config = "config"
    documentation = "documentation"
    diagram = "diagram"
    log = "log"
    review = "review"
    devops = "devops"


class Artifact(BaseModel, Base):
    """A single generated file or output belonging to a project."""
    __tablename__ = "artifacts"

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename = Column(String(512), nullable=False)
    artifact_type = Column(
        SAEnum(ArtifactType, name="artifact_type", create_constraint=True),
        nullable=False,
        default=ArtifactType.code,
    )
    content = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="artifacts")

    def __repr__(self) -> str:
        return f"<Artifact {self.filename} ({self.artifact_type.value})>"
