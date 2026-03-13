# Approval Workflow Quick Start Guide

## Installation

The approval workflow system is included in the foundry core. Ensure you have:

1. PostgreSQL database running
2. Redis server running
3. Database migrations applied:
   ```bash
   python -m alembic upgrade head
   ```

## Quick Examples

### 1. Create an Approval Request

```python
from foundry.services.approval_service import approval_service
from foundry.models.approval import ApprovalRequestCreate, ApprovalContent, ApprovalType

content = ApprovalContent(
    description="Deploy new API endpoints",
    phantom_file_tree={"src": {"api": {"users.py": "file"}}},
    technology_stack={"backend": "FastAPI"},
    estimated_time="20 minutes",
)

request = ApprovalRequestCreate(
    project_id=str(project_id),
    request_type=ApprovalType.plan,
    content=content,
    estimated_cost=25.00,
    timeout_minutes=60,
)

approval = await approval_service.create_approval_request(session, request)
```

### 2. Respond to Approval

```python
from foundry.models.approval import ApprovalResponse

# Approve
response = ApprovalResponse(decision="approve", reason="LGTM")
result = await approval_service.respond_to_approval(session, approval_id, response)

# Reject
response = ApprovalResponse(decision="reject", reason="Needs redesign")
result = await approval_service.respond_to_approval(session, approval_id, response)

# Approve with changes
response = ApprovalResponse(
    decision="approve_with_changes",
    modifications={"tech_stack": {"python": "3.12"}},
    reason="Updated version",
)
result = await approval_service.respond_to_approval(session, approval_id, response)
```

### 3. Pause/Resume Execution

```python
from foundry.services.agent_control import agent_control_service

# Pause
await agent_control_service.pause_execution(project_id, reason="Review needed")

# Check status
status = await agent_control_service.check_control_status(project_id)

# Resume
await agent_control_service.resume_execution(project_id)
```

### 4. Save Checkpoints

```python
# Save checkpoint
agent_state = {"current_agent": "engineer", "progress": 75}
await agent_control_service.save_checkpoint(
    project_id,
    agent_state,
    description="Engineering 75% complete",
)

# Restore checkpoint
checkpoint = await agent_control_service.get_checkpoint(project_id)
agent_state = checkpoint["agent_state"]
```

## Approval Policies

Set policy when creating a project:

```python
from foundry.models.approval import ApprovalPolicy

project = Project(
    name="My Project",
    requirements="...",
    approval_policy=ApprovalPolicy.standard,  # or autonomous, strict
)
```

**Policy Behavior:**
- `autonomous`: No approvals (dev/test only)
- `standard`: Plan + Deployment approvals (default)
- `strict`: Plan + Components + Deployment approvals

## Background Tasks

Configure Celery Beat to process expired approvals:

```python
# In celery config
from celery.schedules import crontab

app.conf.beat_schedule = {
    'process-expired-approvals': {
        'task': 'foundry.tasks.process_expired_approvals',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}
```

## Testing

Run the approval workflow tests:

```bash
# All approval tests
pytest tests/test_approval_service.py tests/test_agent_control.py tests/test_approval_workflow_integration.py -v

# Run demo
python examples/approval_workflow_demo.py
```

## Common Patterns

### Check if Approval Required

```python
from foundry.services.approval_service import approval_service
from foundry.models.approval import ApprovalPolicy, ApprovalType

if approval_service.should_request_approval(
    project.approval_policy,
    ApprovalType.deployment,
):
    # Create approval request
    pass
else:
    # Proceed without approval
    pass
```

### Handle Timeout in Agent Loop

```python
# In agent execution loop
control_status = await agent_control_service.check_control_status(project_id)

if control_status:
    if control_status["action"] == "pause":
        # Save checkpoint and wait
        await agent_control_service.save_checkpoint(project_id, current_state)
        return  # Exit and wait for resume
    
    elif control_status["action"] == "cancel":
        # Rollback if requested
        if control_status.get("rollback"):
            checkpoint = await agent_control_service.get_checkpoint(project_id)
            # Restore state
        return  # Exit execution
```

## API Endpoints (Suggested)

```
POST   /api/approvals                    # Create approval
GET    /api/approvals/pending            # List pending
POST   /api/approvals/{id}/respond       # Respond
POST   /api/approvals/{id}/cancel        # Cancel

POST   /api/projects/{id}/pause          # Pause execution
POST   /api/projects/{id}/resume         # Resume execution
POST   /api/projects/{id}/cancel         # Cancel execution
```

## Troubleshooting

### Approval Not Auto-Cancelling
- Ensure Celery Beat is running
- Check `process_expired_approvals` task is scheduled
- Verify Redis connection

### Checkpoint Not Restoring
- Check Redis connection
- Verify checkpoint exists (7-day retention)
- Ensure project_id is correct

### Tests Failing
- Ensure PostgreSQL test database exists
- Ensure Redis is running
- Run migrations: `python -m alembic upgrade head`

## Next Steps

- Integrate with FastAPI endpoints
- Add WebSocket notifications
- Build VS Code extension UI
- Implement cost threshold auto-pause
- Add security issue auto-block

For detailed documentation, see `docs/APPROVAL_WORKFLOW.md`.
