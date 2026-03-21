"""Agent execution metrics and history models."""

import enum
from sqlalchemy import Column, String, Text, Integer, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from foundry.database import Base
from foundry.models.base import BaseModel


class AgentExecution(BaseModel, Base):
    """Execution record for a single agent node in the orchestrator pipeline."""
    __tablename__ = "agent_executions"

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_type = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False)
    
    # Timing and performance
    start_time = Column(Integer, nullable=True)  # Unix timestamp
    end_time = Column(Integer, nullable=True)    # Unix timestamp
    duration_seconds = Column(Float, nullable=True)
    
    # Resource usage
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    model_name = Column(String(100), nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    error_stack = Column(Text, nullable=True)
    
    # Context
    metadata_ = Column("metadata", JSON, nullable=True)

    # Relationships
    project = relationship("Project")

    def __repr__(self) -> str:
        return f"<AgentExecution {self.agent_type} for project {self.project_id} ({self.status})>"
