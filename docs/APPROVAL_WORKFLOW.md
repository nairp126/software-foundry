# Approval Workflow System

## Overview

The Approval Workflow System provides human-in-the-loop controls for the Autonomous Software Foundry, allowing users to maintain oversight and control over the autonomous development process. The system implements a comprehensive approval mechanism with timeout handling, pause/resume functionality, and configurable approval policies.

## Features

### 1. Approval Request Management

- **Create Approval Requests**: Generate approval requests with detailed context including:
  - Phantom file tree showing files to be created/modified
  - Technology stack and dependencies
  - Cloud resources with cost estimates
  - Estimated time to completion
  
- **Approval Types**:
  - `plan`: Approve project plan before execution
  - `deployment`: Approve deployment before production
  - `cost_override`: Approve when costs exceed thresholds
  - `security_review`: Approve when security issues detected
  - `component`: Approve individual components (strict mode)

- **User Response Options**:
  - `approve`: Proceed with execution
  - `reject`: Discard and regenerate
  - `approve_with_changes`: Apply modifications and proceed
  - `edit`: Modify plan inline (handled as approve_with_changes)

### 2. Approval Policies

Three approval policy modes are supported:

#### Autonomous Mode
- **Use Case**: Development and testing environments
- **Behavior**: No approvals required, fully autonomous execution
- **Risk**: High - suitable only for non-production environments

#### Standard Mode (Default)
- **Use Case**: Most production deployments
- **Behavior**: Requires approval for:
  - Project plan before execution
  - Deployment before production
- **Risk**: Medium - balanced control and automation

#### Strict Mode
- **Use Case**: High-security or regulated environments
- **Behavior**: Requires approval for:
  - Project plan
  - Each major component before implementation
  - Deployment before production
- **Risk**: Low - maximum oversight and control

### 3. Timeout Handling

- **Configurable Timeouts**: Set timeout duration (default: 60 minutes)
- **Auto-Cancellation**: Pending approvals automatically timeout after configured duration
- **Background Processing**: Celery task processes expired approvals periodically
- **Status Tracking**: Approval status transitions to `timeout` when expired

### 4. Agent Execution Control

#### Pause Execution
- Pause agent execution at any time
- Preserves current state in Redis
- Allows review of progress before continuing

#### Resume Execution
- Resume from exact pause point
- Restores agent state from checkpoint
- Continues execution seamlessly

#### Cancel Execution
- Cancel execution with optional rollback
- Rollback to last stable checkpoint
- Clean up resources and state

#### Checkpointing
- Automatic state preservation
- 7-day checkpoint retention
- Supports recovery and rollback

## Architecture

### Database Schema

```sql
-- Approval Requests Table
CREATE TABLE approval_requests (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    request_type approval_type NOT NULL,
    status approval_status NOT NULL DEFAULT 'pending',
    content JSONB NOT NULL,
    estimated_cost FLOAT,
    timeout_at TIMESTAMP,
    responded_at TIMESTAMP,
    response JSONB,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

-- Indexes
CREATE INDEX ix_approval_requests_project_id ON approval_requests(project_id);
CREATE INDEX ix_approval_requests_status ON approval_requests(status);

-- Enums
CREATE TYPE approval_type AS ENUM (
    'plan', 'deployment', 'cost_override', 'security_review', 'component'
);

CREATE TYPE approval_status AS ENUM (
    'pending', 'approved', 'rejected', 'timeout', 'cancelled'
);

CREATE TYPE approval_policy AS ENUM (
    'autonomous', 'standard', 'strict'
);
```

### Redis State Management

```
# Control Flags
agent_control:{project_id} -> {
    "action": "pause|resume|cancel",
    "reason": "...",
    "timestamp": "..."
}

# Checkpoints
agent_checkpoint:{project_id} -> {
    "project_id": "...",
    "agent_state": {...},
    "description": "...",
    "timestamp": "..."
}
```

## Usage Examples

### Creating an Approval Request

```python
from foundry.services.approval_service import approval_service
from foundry.models.approval import (
    ApprovalRequestCreate,
    ApprovalContent,
    ApprovalType,
)

# Create approval content
content = ApprovalContent(
    description="Deploy new feature",
    phantom_file_tree={
        "src": {
            "api": {"routes.py": "file"},
            "frontend": {"App.tsx": "file"},
        }
    },
    technology_stack={
        "backend": "FastAPI",
        "frontend": "React",
    },
    cloud_resources=[
        {"type": "EC2", "instance_type": "t3.micro", "cost": 8.50}
    ],
    estimated_time="30 minutes",
)

# Create approval request
request_data = ApprovalRequestCreate(
    project_id=str(project_id),
    request_type=ApprovalType.plan,
    content=content,
    estimated_cost=8.50,
    timeout_minutes=60,
)

approval = await approval_service.create_approval_request(
    session,
    request_data,
)
```

### Responding to an Approval

```python
from foundry.models.approval import ApprovalResponse

# Approve
response = ApprovalResponse(
    decision="approve",
    reason="Plan looks good",
)

result = await approval_service.respond_to_approval(
    session,
    approval_id,
    response,
)

# Approve with changes
response = ApprovalResponse(
    decision="approve_with_changes",
    modifications={"tech_stack": {"python": "3.12"}},
    reason="Updated Python version",
)

# Reject
response = ApprovalResponse(
    decision="reject",
    reason="Needs redesign",
)
```

### Pausing and Resuming Execution

```python
from foundry.services.agent_control import agent_control_service

# Pause execution
result = await agent_control_service.pause_execution(
    project_id,
    reason="Need to review progress",
)

# Check control status
status = await agent_control_service.check_control_status(project_id)
if status and status["action"] == "pause":
    print("Execution is paused")

# Resume execution
result = await agent_control_service.resume_execution(project_id)
```

### Saving and Restoring Checkpoints

```python
# Save checkpoint
agent_state = {
    "current_agent": "engineer",
    "completed_steps": ["requirements", "design"],
    "progress": 50,
}

await agent_control_service.save_checkpoint(
    project_id,
    agent_state,
    description="Engineering 50% complete",
)

# Restore checkpoint
checkpoint = await agent_control_service.get_checkpoint(project_id)
if checkpoint:
    agent_state = checkpoint["agent_state"]
    # Resume from checkpoint
```

## Background Tasks

### Approval Timeout Processing

A Celery task runs periodically to process expired approvals:

```python
# Configure in celery beat schedule
from celery.schedules import crontab

app.conf.beat_schedule = {
    'process-expired-approvals': {
        'task': 'foundry.tasks.process_expired_approvals',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}
```

## API Integration

The approval workflow system is designed to integrate with the FastAPI backend:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from foundry.database import get_db
from foundry.services.approval_service import approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])

@router.post("/")
async def create_approval(
    request: ApprovalRequestCreate,
    session: AsyncSession = Depends(get_db),
):
    """Create a new approval request."""
    approval = await approval_service.create_approval_request(session, request)
    return approval

@router.post("/{approval_id}/respond")
async def respond_to_approval(
    approval_id: str,
    response: ApprovalResponse,
    session: AsyncSession = Depends(get_db),
):
    """Respond to an approval request."""
    result = await approval_service.respond_to_approval(
        session,
        UUID(approval_id),
        response,
    )
    return result

@router.get("/pending")
async def list_pending_approvals(
    project_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    """List pending approval requests."""
    project_uuid = UUID(project_id) if project_id else None
    approvals = await approval_service.list_pending_approvals(
        session,
        project_uuid,
    )
    return approvals
```

## Testing

The approval workflow system includes comprehensive tests:

- **Unit Tests**: `tests/test_approval_service.py`, `tests/test_agent_control.py`
- **Integration Tests**: `tests/test_approval_workflow_integration.py`

Run tests:
```bash
pytest tests/test_approval_service.py -v
pytest tests/test_agent_control.py -v
pytest tests/test_approval_workflow_integration.py -v
```

## Requirements Validation

This implementation satisfies the following requirements from Requirement 21:

- ✅ **21.1**: Four-phase workflow with explicit transitions
- ✅ **21.2**: Approval presentation with phantom file tree, tech stack, resources, costs
- ✅ **21.3**: User review options (approve, edit, reject, approve with changes)
- ✅ **21.4**: Approval policies (autonomous, standard, strict)
- ✅ **21.5**: Agent execution controls (pause, resume, cancel with rollback)
- ✅ **21.9**: Auto-cancel pending approvals after timeout

## Future Enhancements

- WebSocket notifications for real-time approval updates
- VS Code extension integration for in-IDE approval UI
- Approval history and audit trail
- Multi-user approval workflows (require N approvals)
- Approval templates for common scenarios
- Cost threshold auto-pause integration
- Security issue auto-block integration
