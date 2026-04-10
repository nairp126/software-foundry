"""Approval workflow model for human-in-the-loop gates."""

import enum
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, Text, ForeignKey, Enum as SAEnum, Float, DateTime, JSON, UUID
from sqlalchemy.orm import relationship
from pydantic import BaseModel as PydanticBaseModel, Field

from foundry.database import Base
from foundry.models.base import BaseModel


class ApprovalStatus(str, enum.Enum):
    """Lifecycle of an approval request."""
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    timeout = "timeout"
    cancelled = "cancelled"


class ApprovalType(str, enum.Enum):
    """Type of approval request."""
    plan = "plan"
    deployment = "deployment"
    cost_override = "cost_override"
    security_review = "security_review"
    component = "component"


class ApprovalPolicy(str, enum.Enum):
    """Approval policy modes."""
    autonomous = "autonomous"  # No approvals required (dev/test only)
    standard = "standard"      # Approve plan + deployment
    strict = "strict"          # Approve plan + components + deployment


class ApprovalRequest(BaseModel, Base):
    """A gate that pauses the pipeline until a human makes a decision."""
    __tablename__ = "approval_requests"

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_type = Column(
        SAEnum(ApprovalType, name="approval_type", create_constraint=True),
        nullable=False,
        doc="Type of approval being requested",
    )
    status = Column(
        SAEnum(ApprovalStatus, name="approval_status", create_constraint=True),
        nullable=False,
        default=ApprovalStatus.pending,
        server_default=ApprovalStatus.pending.value,
        index=True,
    )
    content = Column(
        JSON,
        nullable=False,
        doc="Approval content including phantom file tree, tech stack, resources, etc.",
    )
    estimated_cost = Column(
        Float,
        nullable=True,
        doc="Estimated monthly cost in USD for cloud resources",
    )
    timeout_at = Column(
        DateTime,
        nullable=True,
        doc="When this approval request should auto-cancel",
    )
    stage = Column(
        String(64),
        nullable=True,
        doc="Pipeline stage this approval belongs to (e.g. 'plan', 'deployment')",
    )
    reviewer_comment = Column(
        Text,
        nullable=True,
        doc="Comment left by the reviewer when approving or rejecting",
    )
    responded_at = Column(
        DateTime,
        nullable=True,
        doc="When the user responded to this approval",
    )
    response = Column(
        JSON,
        nullable=True,
        doc="User response including decision, modifications, and reason",
    )

    # Relationships
    project = relationship("Project", backref="approval_requests")

    def __repr__(self) -> str:
        return f"<ApprovalRequest project={self.project_id} type={self.request_type.value} status={self.status.value}>"

    def is_expired(self) -> bool:
        """Check if this approval request has expired."""
        if self.timeout_at is None:
            return False
        return datetime.utcnow() >= self.timeout_at

    def can_respond(self) -> bool:
        """Check if this approval can still be responded to."""
        return self.status == ApprovalStatus.pending and not self.is_expired()


# Pydantic models for API validation

class ApprovalContent(PydanticBaseModel):
    """Content structure for approval requests."""
    phantom_file_tree: Optional[Dict[str, Any]] = Field(
        None,
        description="Tree structure showing files to be created/modified",
    )
    technology_stack: Optional[Dict[str, str]] = Field(
        None,
        description="Technologies and versions to be used",
    )
    dependencies: Optional[list[str]] = Field(
        None,
        description="Dependencies to be installed",
    )
    cloud_resources: Optional[list[Dict[str, Any]]] = Field(
        None,
        description="Cloud resources to be provisioned with cost estimates",
    )
    estimated_time: Optional[str] = Field(
        None,
        description="Estimated time to completion",
    )
    description: Optional[str] = Field(
        None,
        description="Human-readable description of what's being approved",
    )


class ApprovalResponse(PydanticBaseModel):
    """User response to an approval request."""
    decision: str = Field(
        ...,
        description="User decision: approve, edit, reject, approve_with_changes",
    )
    modifications: Optional[Dict[str, Any]] = Field(
        None,
        description="User modifications to the plan (for edit/approve_with_changes)",
    )
    reason: Optional[str] = Field(
        None,
        description="User's reason for the decision",
    )


class ApprovalRequestCreate(PydanticBaseModel):
    """Request to create an approval."""
    project_id: str = Field(..., description="Project UUID")
    request_type: ApprovalType = Field(..., description="Type of approval")
    content: ApprovalContent = Field(..., description="Approval content")
    estimated_cost: Optional[float] = Field(None, description="Estimated monthly cost")
    timeout_minutes: Optional[int] = Field(
        60,
        description="Minutes until auto-cancel (default 60)",
    )
