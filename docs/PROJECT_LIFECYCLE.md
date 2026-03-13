# Project Lifecycle Management

The Project Lifecycle Management system provides comprehensive control over project creation, management, and deletion within the Autonomous Software Foundry.

## Overview

The system implements **Requirement 19** from the design specification, providing:

- **Project Creation** with unique ID generation and directory structure initialization
- **Project Listing** with metadata including resource usage and cost estimates
- **Project Deletion** with confirmation, cleanup, and resource deallocation

## Features

### 1. Project Creation (Requirement 19.1)

When creating a project, the system:

- Generates a unique UUID for the project
- Creates an isolated Knowledge Graph namespace (`project:{id}:*`)
- Initializes a Git repository with `.gitignore`
- Sets up a standard project directory structure:
  - `src/` - Source code
  - `tests/` - Test files
  - `docs/` - Documentation
  - `config/` - Configuration files
  - `README.md` - Project documentation

**Example:**

```python
from foundry.services.project_service import project_service
from foundry.database import AsyncSessionLocal

async with AsyncSessionLocal() as session:
    project = await project_service.create_project(
        session=session,
        name="My Project",
        requirements="Build a web application",
        description="Optional description"
    )
    await session.commit()
    
    print(f"Project ID: {project.id}")
    print(f"Project Path: {project.generated_path}")
```

### 2. Project Retrieval

Retrieve a specific project by its UUID:

```python
project = await project_service.get_project(
    session=session,
    project_id=project_uuid
)

if project:
    print(f"Found project: {project.name}")
else:
    print("Project not found")
```

### 3. Project Listing (Requirement 19.7)

List all projects with comprehensive metadata:

```python
projects = await project_service.list_projects(session=session)

for project_meta in projects:
    print(f"Name: {project_meta['name']}")
    print(f"Status: {project_meta['status']}")
    print(f"Created: {project_meta['created_at']}")
    print(f"Disk Usage: {project_meta['resource_usage']['disk_space_mb']} MB")
    print(f"Monthly Cost: ${project_meta['estimated_monthly_cost']}")
```

**Filter by Status:**

```python
from foundry.models.project import ProjectStatus

created_projects = await project_service.list_projects(
    session=session,
    status=ProjectStatus.created
)
```

### 4. Project Deletion (Requirement 19.6)

Delete a project with explicit confirmation and comprehensive cleanup:

```python
result = await project_service.delete_project(
    session=session,
    project_id=project_uuid,
    confirmed=True  # Required for safety
)
await session.commit()

if result["success"]:
    print("Project deleted successfully")
    print(f"Steps completed: {result['steps_completed']}")
else:
    print(f"Deletion failed: {result['message']}")
```

**Deletion Process:**

1. **CDK Destroy** - Removes cloud resources (stubbed for MVP)
2. **Knowledge Graph Cleanup** - Deletes all project nodes (stubbed for MVP)
3. **File System Cleanup** - Removes all local project files
4. **Database Cleanup** - Deletes the project record

**Safety Features:**

- Requires explicit `confirmed=True` parameter
- Returns detailed status of each cleanup step
- Reports any errors encountered during deletion

## Architecture

### Service Layer

The `ProjectService` class (`src/foundry/services/project_service.py`) provides:

- **Async/await** support for all operations
- **Session management** - Caller controls transaction boundaries
- **Error handling** - Graceful degradation with detailed error reporting
- **Extensibility** - Stubbed methods for future Neo4j and CDK integration

### Database Model

The `Project` model (`src/foundry/models/project.py`) includes:

- **UUID primary key** - Globally unique project identifiers
- **Status tracking** - Lifecycle state management
- **Timestamps** - Creation and modification tracking
- **JSONB fields** - Flexible storage for agent outputs
- **Relationships** - Cascade deletion for related artifacts

### Directory Structure

Projects are stored in `generated_projects/{project_id}/`:

```
generated_projects/
└── {project-uuid}/
    ├── .git/
    ├── .gitignore
    ├── README.md
    ├── src/
    ├── tests/
    ├── docs/
    └── config/
```

## Resource Tracking

### Disk Space

The system calculates actual disk usage by walking the project directory tree:

```python
resource_usage = {
    "disk_space_mb": 12.5,  # Actual size in MB
    "knowledge_graph_nodes": 0,  # To be implemented
    "active_agents": 0  # To be implemented
}
```

### Cost Estimation

Monthly cost estimation is currently stubbed (returns `0.0`) and will be implemented when:

- Cloud resources are actually provisioned
- DevOps agent integration is complete
- Cost tracking infrastructure is in place

## Future Enhancements

### Phase 2 Features (Deferred from MVP)

1. **Project Pausing** (Requirement 19.2)
   - Serialize complete project state
   - Suspend agent execution
   - Preserve Knowledge Graph snapshot

2. **Project Resumption** (Requirement 19.3)
   - Restore project state from serialized data
   - Resume agents from last checkpoint
   - Reload Knowledge Graph context

3. **Project Cloning** (Requirement 19.4)
   - Copy codebase and configuration
   - Duplicate Knowledge Graph relationships
   - Generate new unique project ID

4. **Project Archival** (Requirement 19.5)
   - Compress all project artifacts
   - Export Knowledge Graph data
   - Move to long-term storage
   - Optional cloud resource teardown

5. **Project Export** (Requirement 19.9)
   - Create portable archive (.tar.gz or .zip)
   - Include code, config, docs, and KG export
   - Support import on other foundry instances

### Integration Points

1. **Neo4j Knowledge Graph**
   - Implement `_delete_knowledge_graph_nodes()`
   - Add namespace isolation (`project:{id}:*`)
   - Track component relationships

2. **AWS CDK Integration**
   - Implement `_destroy_cloud_resources()`
   - Execute `cdk destroy --force`
   - Track provisioned resources

3. **Resource Quotas** (Requirement 19.8)
   - Enforce maximum concurrent projects
   - Limit Knowledge Graph nodes per project
   - Cap disk space per project
   - Monitor cloud spend per project

## Testing

Comprehensive test coverage in `tests/test_project_service.py`:

- ✅ Project creation with unique IDs
- ✅ Directory structure initialization
- ✅ Git repository initialization
- ✅ Project retrieval (existing and non-existent)
- ✅ Project listing with metadata
- ✅ Status filtering
- ✅ Resource usage tracking
- ✅ Deletion with confirmation requirement
- ✅ File system cleanup
- ✅ Database record removal
- ✅ CDK destroy integration (stubbed)
- ✅ Knowledge Graph cleanup (stubbed)
- ✅ Unique directory paths for multiple projects

Run tests:

```bash
pytest tests/test_project_service.py -v
```

## Example Usage

See `examples/project_lifecycle_demo.py` for a complete demonstration of all lifecycle operations.

## API Integration

The project service is designed to be integrated with the FastAPI backend:

```python
from fastapi import APIRouter, Depends
from foundry.database import get_db
from foundry.services.project_service import project_service

router = APIRouter()

@router.post("/projects")
async def create_project(
    name: str,
    requirements: str,
    session: AsyncSession = Depends(get_db)
):
    project = await project_service.create_project(
        session=session,
        name=name,
        requirements=requirements
    )
    return {"project_id": str(project.id), "status": project.status.value}

@router.get("/projects")
async def list_projects(session: AsyncSession = Depends(get_db)):
    return await project_service.list_projects(session=session)

@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    confirmed: bool,
    session: AsyncSession = Depends(get_db)
):
    return await project_service.delete_project(
        session=session,
        project_id=UUID(project_id),
        confirmed=confirmed
    )
```

## Security Considerations

1. **Confirmation Required** - Deletion requires explicit confirmation to prevent accidental data loss
2. **Path Validation** - Project paths are generated internally to prevent directory traversal
3. **Transaction Safety** - All database operations use transactions for atomicity
4. **Error Isolation** - Errors in one cleanup step don't prevent other steps from executing

## Performance

- **Async Operations** - All I/O operations are asynchronous for better concurrency
- **Efficient Queries** - Database queries use indexes on UUID and status fields
- **Lazy Loading** - Resource usage calculated on-demand during listing
- **Connection Pooling** - Database connections managed by SQLAlchemy pool

## Troubleshooting

### Project Creation Fails

- Check database connectivity
- Verify `generated_projects/` directory is writable
- Ensure Git is installed and accessible

### Deletion Incomplete

- Check the `errors` array in the deletion result
- Verify file system permissions
- Review logs for detailed error messages

### Resource Usage Incorrect

- Ensure project directory exists
- Check file system permissions for directory traversal
- Verify no symbolic links causing calculation issues
