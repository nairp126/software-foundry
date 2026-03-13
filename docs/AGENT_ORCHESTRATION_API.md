# Agent Orchestration API Guide

## Overview

The Agent Orchestration API provides real-time control over agent execution, allowing you to pause, resume, cancel, and monitor agent progress during project generation.

## Key Concepts

### Agent Lifecycle States

Projects progress through various agent states:
- `created`: Initial state
- `running_pm`: Product Manager agent analyzing requirements
- `running_architect`: Architect agent designing system
- `running_engineer`: Engineering agent generating code
- `running_code_review`: Code Review agent analyzing quality
- `running_reflexion`: Reflexion engine fixing errors
- `running_devops`: DevOps agent provisioning infrastructure
- `paused`: Execution paused by user
- `completed`: Successfully finished
- `failed`: Execution failed or cancelled

### Checkpoints

The system automatically saves checkpoints during execution, allowing you to:
- Resume from the exact point of interruption
- Rollback to the last stable state
- Recover from failures

## API Endpoints

### Get Agent Status

Get the current execution status of a project.

**Endpoint**: `GET /projects/{project_id}/agent/status`

**Response**:
```json
{
  "project_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "running_engineer",
  "current_agent": "engineer",
  "progress": null,
  "is_paused": false,
  "checkpoint_available": true
}
```

**Fields**:
- `project_id`: UUID of the project
- `status`: Current project status
- `current_agent`: Name of the currently executing agent
- `progress`: Progress information (future enhancement)
- `is_paused`: Whether execution is paused
- `checkpoint_available`: Whether a checkpoint exists for rollback

**Example**:
```bash
curl -X GET http://localhost:8000/projects/{project_id}/agent/status \
  -H "X-API-Key: your_api_key"
```

### Pause Agent Execution

Pause the currently running agent, preserving state for later resumption.

**Endpoint**: `POST /projects/{project_id}/agent/pause`

**Request Body**:
```json
{
  "reason": "Need to review architecture before proceeding"
}
```

**Parameters**:
- `reason` (optional): Explanation for pausing

**Response**:
```json
{
  "success": true,
  "project_id": "123e4567-e89b-12d3-a456-426614174000",
  "action": "pause",
  "message": "Execution paused: Need to review architecture before proceeding"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/projects/{project_id}/agent/pause \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"reason": "Need to review architecture"}'
```

**Use Cases**:
- Review generated architecture before code generation
- Check cost estimates before deployment
- Verify security scan results
- Manual intervention required

### Resume Agent Execution

Resume a paused project from its last checkpoint.

**Endpoint**: `POST /projects/{project_id}/agent/resume`

**Response**:
```json
{
  "success": true,
  "project_id": "123e4567-e89b-12d3-a456-426614174000",
  "action": "resume",
  "message": "Execution resumed"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/projects/{project_id}/agent/resume \
  -H "X-API-Key: your_api_key"
```

**Behavior**:
- Restores agent state from checkpoint
- Continues execution from pause point
- Updates project status to appropriate running state

### Cancel Agent Execution

Cancel execution and optionally rollback to the last checkpoint.

**Endpoint**: `POST /projects/{project_id}/agent/cancel`

**Request Body**:
```json
{
  "rollback": true
}
```

**Parameters**:
- `rollback` (optional, default: true): Whether to restore last checkpoint

**Response**:
```json
{
  "success": true,
  "project_id": "123e4567-e89b-12d3-a456-426614174000",
  "action": "cancel",
  "message": "Execution cancelled",
  "checkpoint_restored": true,
  "checkpoint_timestamp": "2024-01-15T10:30:00Z"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/projects/{project_id}/agent/cancel \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"rollback": true}'
```

**Use Cases**:
- Stop execution due to incorrect requirements
- Cancel after detecting issues
- Abort before expensive cloud provisioning
- Emergency stop

## Usage Patterns

### Pattern 1: Review Before Proceeding

```python
import requests
import time

api_key = "your_api_key"
headers = {"X-API-Key": api_key}
base_url = "http://localhost:8000"

# Create project
response = requests.post(
    f"{base_url}/projects",
    headers=headers,
    json={
        "name": "My Project",
        "requirements": "Build a REST API"
    }
)
project_id = response.json()["id"]

# Monitor until architect completes
while True:
    status = requests.get(
        f"{base_url}/projects/{project_id}/agent/status",
        headers=headers
    ).json()
    
    if status["current_agent"] == "architect":
        # Pause to review architecture
        requests.post(
            f"{base_url}/projects/{project_id}/agent/pause",
            headers=headers,
            json={"reason": "Review architecture"}
        )
        break
    
    time.sleep(5)

# Review architecture...
architecture = requests.get(
    f"{base_url}/projects/{project_id}",
    headers=headers
).json()["architecture"]

print("Architecture:", architecture)

# Resume if approved
user_input = input("Approve architecture? (y/n): ")
if user_input.lower() == "y":
    requests.post(
        f"{base_url}/projects/{project_id}/agent/resume",
        headers=headers
    )
else:
    requests.post(
        f"{base_url}/projects/{project_id}/agent/cancel",
        headers=headers,
        json={"rollback": True}
    )
```

### Pattern 2: Monitoring with Status Polling

```python
import requests
import time

def monitor_project(project_id, api_key):
    """Monitor project execution with status updates."""
    headers = {"X-API-Key": api_key}
    base_url = "http://localhost:8000"
    
    while True:
        status = requests.get(
            f"{base_url}/projects/{project_id}/agent/status",
            headers=headers
        ).json()
        
        print(f"Status: {status['status']}")
        print(f"Current Agent: {status['current_agent']}")
        print(f"Paused: {status['is_paused']}")
        print("-" * 40)
        
        if status["status"] in ["completed", "failed"]:
            break
        
        time.sleep(10)

# Usage
monitor_project("project-uuid", "your_api_key")
```

### Pattern 3: Emergency Stop

```python
import requests

def emergency_stop(project_id, api_key):
    """Immediately cancel execution with rollback."""
    headers = {"X-API-Key": api_key}
    
    response = requests.post(
        f"http://localhost:8000/projects/{project_id}/agent/cancel",
        headers=headers,
        json={"rollback": True}
    )
    
    result = response.json()
    print(f"Cancelled: {result['message']}")
    if result.get("checkpoint_restored"):
        print(f"Restored checkpoint from: {result['checkpoint_timestamp']}")

# Usage
emergency_stop("project-uuid", "your_api_key")
```

## WebSocket Real-Time Updates

For real-time status updates, use the WebSocket endpoint:

**Endpoint**: `ws://localhost:8000/ws/projects/{project_id}`

**Example**:
```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/projects/${projectId}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Status update:", data);
  // { type: "status_update", status: "running_engineer", updated_at: "..." }
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};
```

## Error Handling

### Project Not Found
```json
{
  "detail": "Project not found",
  "error_code": "http_404",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Invalid State Transition
```json
{
  "detail": "Project is already paused",
  "error_code": "http_400",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Cannot Resume Non-Paused Project
```json
{
  "detail": "Project is not paused",
  "error_code": "http_400",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Best Practices

### 1. Monitor Before Critical Operations
```python
# Check status before expensive operations
status = get_agent_status(project_id)
if status["current_agent"] == "devops":
    # Pause to review cost estimates
    pause_execution(project_id, "Review costs")
```

### 2. Use Checkpoints for Safety
```python
# Always enable rollback for cancellation
cancel_execution(project_id, rollback=True)
```

### 3. Provide Clear Reasons
```python
# Document why you're pausing
pause_execution(
    project_id,
    reason="Security scan found vulnerabilities - need manual review"
)
```

### 4. Handle State Transitions
```python
def safe_pause(project_id):
    """Safely pause execution with error handling."""
    status = get_agent_status(project_id)
    
    if status["is_paused"]:
        print("Already paused")
        return
    
    if status["status"] in ["completed", "failed"]:
        print("Cannot pause completed/failed project")
        return
    
    pause_execution(project_id)
```

## Integration with Approval Workflow

The agent orchestration API works seamlessly with the approval workflow:

```python
# 1. Monitor for approval requests
approval = get_approval_status(project_id)

if approval and approval["status"] == "pending":
    # 2. Execution is automatically paused
    print(f"Approval required for: {approval['stage']}")
    
    # 3. Review and approve/reject
    if user_approves():
        approve_project(project_id)
        # Execution resumes automatically
    else:
        reject_project(project_id)
        # Project marked as failed
```

## Troubleshooting

### Pause Not Taking Effect
- Check if project is in a pausable state
- Verify project is not already paused
- Ensure project hasn't completed or failed

### Resume Not Working
- Verify project is in paused state
- Check if checkpoint exists
- Review error logs for agent issues

### Checkpoint Not Available
- Checkpoints are created periodically
- Very new projects may not have checkpoints yet
- Check Redis connection for checkpoint storage

## API Reference Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/projects/{id}/agent/status` | Get agent execution status |
| POST | `/projects/{id}/agent/pause` | Pause agent execution |
| POST | `/projects/{id}/agent/resume` | Resume paused execution |
| POST | `/projects/{id}/agent/cancel` | Cancel execution with optional rollback |
| WS | `/ws/projects/{id}` | Real-time status updates |

## Related Documentation

- [Approval Workflow Guide](./APPROVAL_WORKFLOW.md)
- [API Authentication Guide](./API_AUTHENTICATION_GUIDE.md)
- [Project Lifecycle Management](./PROJECT_LIFECYCLE.md)
