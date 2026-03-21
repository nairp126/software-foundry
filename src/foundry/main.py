"""FastAPI application entry point."""

import asyncio
import subprocess
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any, List, Optional, Set
from uuid import UUID, uuid4
from datetime import datetime, timedelta

from fastapi import (
    FastAPI,
    BackgroundTasks,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    Request,
    Depends,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select, func

from foundry.config import settings
from foundry.redis_client import redis_client
from foundry.orchestrator import AgentOrchestrator
from foundry.database import AsyncSessionLocal, get_db
from foundry.models.project import Project, ProjectStatus
from sqlalchemy.ext.asyncio import AsyncSession
from foundry.models.artifact import Artifact, ArtifactType
from foundry.models.approval import ApprovalRequest, ApprovalStatus
from foundry.models.api_key import APIKey
from foundry.middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    get_api_key,
    require_api_key,
)
from foundry.services.agent_control import agent_control_service
from foundry.services.knowledge_graph import knowledge_graph_service
from foundry.api.schemas import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectListItem,
    ArtifactResponse,
    ApprovalResponse,
    ApprovalDecision,
    AgentStatusResponse,
    AgentControlRequest,
    AgentControlResponse,
    APIKeyCreateRequest,
    APIKeyResponse,
    APIKeyCreateResponse,
    ErrorResponse,
    ValidationErrorResponse,
    ValidationErrorDetail,
)


# ------------------------------------------------------------------ #
#  Application
# ------------------------------------------------------------------ #


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    await redis_client.connect()
    
    # Initialize Knowledge Graph
    try:
        await knowledge_graph_service.initialize()
        print("Knowledge Graph initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize Knowledge Graph: {e}")
        print("Application will continue without Knowledge Graph support")
    
    # Check for pending migrations
    try:
        # Run alembic check to see if migrations are up to date
        # Note: In a production environment, you might want to run 'upgrade head'
        # but for safety we just check and log here.
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "check"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            print(f"WARNING: Database migrations are not up to date!\n{result.stderr or result.stdout}")
        else:
            print("Database migrations are up to date.")
    except Exception as e:
        print(f"Warning: Could not check migration status: {e}")
    
    yield
    await knowledge_graph_service.disconnect()
    await redis_client.disconnect()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    default_limit=60,  # 60 requests per minute
    window_seconds=60,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ #
#  Error Handlers
# ------------------------------------------------------------------ #

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed response."""
    errors = []
    for error in exc.errors():
        errors.append(
            ValidationErrorDetail(
                loc=error["loc"],
                msg=error["msg"],
                type=error["type"],
            )
        )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ValidationErrorResponse(
            detail=errors,
            error_code="validation_error",
            timestamp=datetime.utcnow(),
        ).model_dump(mode="json"),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with standardized format."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            error_code=f"http_{exc.status_code}",
            timestamp=datetime.utcnow(),
            path=str(request.url),
        ).model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            detail="Internal server error" if not settings.debug else str(exc),
            error_code="internal_error",
            timestamp=datetime.utcnow(),
            path=str(request.url),
        ).model_dump(mode="json"),
    )


# ------------------------------------------------------------------ #
#  Background runner
# ------------------------------------------------------------------ #

async def _run_project_background(project_id: str, requirements: str) -> None:
    """Background task that drives the orchestrator pipeline."""
    try:
        # Fix K: Instantiate fresh orchestrator for every project to avoid memory contamination
        orchestrator = AgentOrchestrator()
        await orchestrator.run(project_id=str(project_id), initial_prompt=requirements)
    except Exception as exc:
        print(f"[ERROR] Project {project_id} failed: {exc}")


# ------------------------------------------------------------------ #
#  Endpoints
# ------------------------------------------------------------------ #

@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


# ---- Projects ---- #

@app.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    request: ProjectCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(require_api_key),
):
    """Create a new project and start generation in the background."""

    project = Project(
        name=request.name,
        description=request.description,
        requirements=request.requirements,
        status=ProjectStatus.created,
        language=request.language or "python",
        framework=request.framework,
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)
    project_id = str(project.id)
    response = ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        requirements=project.requirements,
        status=project.status.value,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )

    background_tasks.add_task(_run_project_background, project_id, request.requirements)
    return response


@app.get("/projects", response_model=List[ProjectListItem])
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(require_api_key),
):
    """List all projects with pagination."""
    result = await db.execute(
        select(Project)
        .order_by(Project.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    projects = result.scalars().all()
    return [
        ProjectListItem(
            id=p.id,
            name=p.name,
            status=p.status.value,
            created_at=p.created_at,
        )
        for p in projects
    ]


@app.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID, 
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(require_api_key),
):
    """Get full project details by ID."""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        requirements=project.requirements,
        status=project.status.value,
        prd=project.prd,
        architecture=project.architecture,
        code_review=project.code_review,
        generated_path=project.generated_path,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@app.get("/projects/{project_id}/artifacts", response_model=List[ArtifactResponse])
async def get_project_artifacts(
    project_id: UUID, 
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(require_api_key),
):
    """Get all generated artifacts for a project."""
    # Verify project exists
    proj = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Artifact)
        .where(Artifact.project_id == project_id)
        .order_by(Artifact.created_at)
    )
    artifacts = result.scalars().all()
    return [
        ArtifactResponse(
            id=a.id,
            filename=a.filename,
            artifact_type=a.artifact_type.value,
            content=a.content,
            created_at=a.created_at,
        )
        for a in artifacts
    ]


@app.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: UUID, 
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(require_api_key),
):
    """Delete a project and all its artifacts."""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()


# ---- Approval Workflow ---- #

@app.get("/projects/{project_id}/approval", response_model=Optional[ApprovalResponse])
async def get_approval_status(
    project_id: UUID, 
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(require_api_key),
):
    """Get the latest approval request for a project."""
    result = await db.execute(
        select(ApprovalRequest)
        .where(ApprovalRequest.project_id == project_id)
        .order_by(ApprovalRequest.created_at.desc())
        .limit(1)
    )
    approval = result.scalar_one_or_none()
    if not approval:
        return None
    return ApprovalResponse(
        id=approval.id,
        project_id=approval.project_id,
        stage=approval.stage,
        status=approval.status.value,
        reviewer_comment=approval.reviewer_comment,
        created_at=approval.created_at,
    )


@app.post("/projects/{project_id}/approve", response_model=ApprovalResponse)
async def approve_project(
    project_id: UUID, 
    decision: ApprovalDecision, 
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(require_api_key),
):
    """Approve the pending gate for a project."""
    result = await db.execute(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.project_id == project_id,
            ApprovalRequest.status == ApprovalStatus.pending,
        )
        .order_by(ApprovalRequest.created_at.desc())
        .limit(1)
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="No pending approval found")

    approval.status = ApprovalStatus.approved
    approval.reviewer_comment = decision.comment
    await db.commit()
    await db.refresh(approval)

    return ApprovalResponse(
        id=approval.id,
        project_id=approval.project_id,
        stage=approval.stage,
        status=approval.status.value,
        reviewer_comment=approval.reviewer_comment,
        created_at=approval.created_at,
    )


@app.post("/projects/{project_id}/reject", response_model=ApprovalResponse)
async def reject_project(
    project_id: UUID, 
    decision: ApprovalDecision, 
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(require_api_key),
):
    """Reject the pending gate for a project."""
    result = await db.execute(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.project_id == project_id,
            ApprovalRequest.status == ApprovalStatus.pending,
        )
        .order_by(ApprovalRequest.created_at.desc())
        .limit(1)
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="No pending approval found")

    approval.status = ApprovalStatus.rejected
    approval.reviewer_comment = decision.comment
    await db.commit()
    await db.refresh(approval)

    # Also mark the project as FAILED
    proj_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = proj_result.scalar_one_or_none()
    if project:
        project.status = ProjectStatus.failed
        await db.commit()

    return ApprovalResponse(
        id=approval.id,
        project_id=approval.project_id,
        stage=approval.stage,
        status=approval.status.value,
        reviewer_comment=approval.reviewer_comment,
        created_at=approval.created_at,
    )


# ---- Agent Orchestration ---- #

@app.get("/projects/{project_id}/agent/status", response_model=AgentStatusResponse)
async def get_agent_status(
    project_id: UUID, 
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(require_api_key),
):
    """Get current agent execution status for a project."""
    # Verify project exists
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check control status
    control_status = await agent_control_service.check_control_status(project_id)
    is_paused = bool(control_status and control_status.get("action") == "pause")
    
    # Check checkpoint availability
    checkpoint = await agent_control_service.get_checkpoint(project_id)
    
    return AgentStatusResponse(
        project_id=project_id,
        status=project.status.value,
        current_agent=_get_current_agent_from_status(project.status),
        progress=None,  # TODO: Implement progress tracking
        is_paused=is_paused,
        checkpoint_available=checkpoint is not None,
    )


@app.post("/projects/{project_id}/agent/pause", response_model=AgentControlResponse)
async def pause_agent_execution(
    project_id: UUID,
    request: AgentControlRequest,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(require_api_key),
):
    """Pause agent execution for a project."""
    # Verify project exists
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if already paused
    if project.status == ProjectStatus.paused:
        raise HTTPException(status_code=400, detail="Project is already paused")
    
    # Pause execution
    pause_result = await agent_control_service.pause_execution(
        project_id,
        reason=request.reason or "User requested pause",
    )
    
    # Update project status
    project.status = ProjectStatus.paused
    await db.commit()
    
    return AgentControlResponse(**pause_result)


@app.post("/projects/{project_id}/agent/resume", response_model=AgentControlResponse)
async def resume_agent_execution(
    project_id: UUID, 
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(require_api_key),
):
    """Resume agent execution for a project."""
    # Verify project exists
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if paused
    if project.status != ProjectStatus.paused:
        raise HTTPException(status_code=400, detail="Project is not paused")
    
    # Resume execution
    resume_result = await agent_control_service.resume_execution(project_id)
    
    # Update project status (restore to appropriate running state)
    # TODO: Restore to the correct running state from checkpoint
    project.status = ProjectStatus.created
    await db.commit()
    
    return AgentControlResponse(**resume_result)


@app.post("/projects/{project_id}/agent/cancel", response_model=AgentControlResponse)
async def cancel_agent_execution(
    project_id: UUID,
    request: AgentControlRequest,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(require_api_key),
):
    """Cancel agent execution and optionally rollback."""
    # Verify project exists
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Cancel execution
    cancel_result = await agent_control_service.cancel_execution(
        project_id,
        rollback=request.rollback if request.rollback is not None else True,
    )
    
    # Update project status
    project.status = ProjectStatus.failed
    await db.commit()
    
    return AgentControlResponse(**cancel_result)


# ---- API Key Management ---- #

@app.post("/api-keys", response_model=APIKeyCreateResponse, status_code=201)
async def create_api_key(
    request: APIKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(require_api_key),
):
    """Create a new API key.
    
    Note: The actual key is only returned once during creation.
    Store it securely as it cannot be retrieved later.
    """
    # Generate new key
    key = APIKey.generate_key()
    key_hash = APIKey.hash_key(key)
    key_prefix = APIKey.get_key_prefix(key)
    
    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
    
    # Create API key record
    api_key = APIKey(
        name=request.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        expires_at=expires_at,
        rate_limit_per_minute=request.rate_limit_per_minute or 60,
    )
    
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    
    return APIKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key=key,  # Only time the actual key is returned
        key_prefix=api_key.key_prefix,
        expires_at=api_key.expires_at,
        rate_limit_per_minute=api_key.rate_limit_per_minute,
        created_at=api_key.created_at,
    )


@app.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List all API keys (without the actual key values)."""
    result = await db.execute(
        select(APIKey)
        .order_by(APIKey.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    api_keys = result.scalars().all()
    return [
        APIKeyResponse(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            is_active=k.is_active,
            expires_at=k.expires_at,
            last_used_at=k.last_used_at,
            rate_limit_per_minute=k.rate_limit_per_minute,
            created_at=k.created_at,
        )
        for k in api_keys
    ]


@app.delete("/api-keys/{key_id}", status_code=204)
async def delete_api_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete an API key."""
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    await db.delete(api_key)
    await db.commit()


@app.patch("/api-keys/{key_id}/deactivate", response_model=APIKeyResponse)
async def deactivate_api_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Deactivate an API key without deleting it."""
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    api_key.is_active = False
    await db.commit()
    await db.refresh(api_key)
    
    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
            is_active=api_key.is_active,
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at,
            rate_limit_per_minute=api_key.rate_limit_per_minute,
            created_at=api_key.created_at,
        )


# ---- Helper Functions ---- #

def _get_current_agent_from_status(status: ProjectStatus) -> Optional[str]:
    """Extract current agent name from project status."""
    status_to_agent = {
        ProjectStatus.running_pm: "product_manager",
        ProjectStatus.running_architect: "architect",
        ProjectStatus.running_engineer: "engineer",
        ProjectStatus.running_code_review: "code_review",
        ProjectStatus.running_reflexion: "reflexion",
        ProjectStatus.running_devops: "devops",
    }
    return status_to_agent.get(status)


# ---- WebSocket Real-Time Updates ---- #

# Track active WebSocket connections per project
_ws_connections: Dict[str, Set[WebSocket]] = {}


@app.websocket("/ws/projects/{project_id}")
async def project_websocket(websocket: WebSocket, project_id: UUID):
    """WebSocket endpoint for real-time project status updates."""
    await websocket.accept()
    key = str(project_id)
    if key not in _ws_connections:
        _ws_connections[key] = set()
    _ws_connections[key].add(websocket)

    try:
        while True:
            # Poll project status every 2 seconds and push updates
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Project).where(Project.id == project_id)
                )
                project = result.scalar_one_or_none()
                if project:
                    await websocket.send_json({
                        "type": "status_update",
                        "status": project.status.value,
                        "updated_at": project.updated_at.isoformat(),
                    })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        _ws_connections[key].discard(websocket)
        if not _ws_connections[key]:
            del _ws_connections[key]
