"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field


from foundry.models.approval import ApprovalPolicy


# ---- Project Schemas ---- #

class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    requirements: str = Field(..., min_length=1)
    description: Optional[str] = None
    language: Optional[str] = "python"
    framework: Optional[str] = None
    approval_policy: Optional[ApprovalPolicy] = Field(default=ApprovalPolicy.standard)


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    requirements: str
    status: str
    prd: Optional[Dict[str, Any]] = None
    architecture: Optional[Dict[str, Any]] = None
    code_review: Optional[Dict[str, Any]] = None
    generated_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListItem(BaseModel):
    id: UUID
    name: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- Artifact Schemas ---- #

class ArtifactResponse(BaseModel):
    id: UUID
    filename: str
    artifact_type: str
    content: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- Approval Schemas ---- #

class ApprovalResponse(BaseModel):
    id: UUID
    project_id: UUID
    stage: str
    status: str
    reviewer_comment: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    comment: Optional[str] = None


# ---- Agent Control Schemas ---- #

class AgentStatusResponse(BaseModel):
    project_id: UUID
    status: str
    current_agent: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None
    is_paused: bool = False
    checkpoint_available: bool = False


class AgentControlRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Reason for the action")
    rollback: Optional[bool] = Field(True, description="Whether to rollback on cancel")


class AgentControlResponse(BaseModel):
    success: bool
    project_id: str
    action: str
    message: str
    checkpoint_restored: Optional[bool] = None
    checkpoint_timestamp: Optional[str] = None


# ---- API Key Schemas ---- #

class APIKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Human-readable name")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="Days until expiration")
    rate_limit_per_minute: Optional[int] = Field(60, ge=1, le=1000, description="Max requests per minute")


class APIKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    rate_limit_per_minute: int
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyCreateResponse(BaseModel):
    """Response when creating a new API key - includes the actual key."""
    id: UUID
    name: str
    key: str = Field(..., description="The actual API key - save this, it won't be shown again")
    key_prefix: str
    expires_at: Optional[datetime]
    rate_limit_per_minute: int
    created_at: datetime


# ---- Error Schemas ---- #

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    path: Optional[str] = None


class ValidationErrorDetail(BaseModel):
    loc: List[str]
    msg: str
    type: str


class ValidationErrorResponse(BaseModel):
    detail: List[ValidationErrorDetail]
    error_code: str = "validation_error"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
