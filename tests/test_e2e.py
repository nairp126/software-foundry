"""End-to-end tests for the Autonomous Software Foundry pipeline.

Uses an in-process ASGI client (no live server required) with mocked
database and Redis dependencies so the full test suite runs without
external services.

Coverage:
  - Health / root endpoints
  - Project CRUD (create, read, list, delete)
  - Multi-language project creation (python, javascript, typescript, java)
  - Pipeline status transitions
  - Artifact retrieval
  - Approval workflow (approve, reject, no-pending 404)
  - Agent control (pause, resume, cancel)
  - API key management (create, list, deactivate, delete)
  - Orchestrator unit-level: language read, success/failure status, state merge
  - Error handling (404, 422, invalid UUID)
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime

from httpx import AsyncClient, ASGITransport
from foundry.main import app


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _uuid():
    return uuid.uuid4()


def _project_row(
    *,
    id=None,
    name="Test Project",
    description=None,
    requirements="Build something.",
    status="created",
    language="python",
    framework=None,
    prd=None,
    architecture=None,
    code_review=None,
    generated_path=None,
):
    """Return a MagicMock that looks like a Project ORM row."""
    m = MagicMock()
    m.id = id or _uuid()
    m.name = name
    m.description = description
    m.requirements = requirements
    m.status = MagicMock()
    m.status.value = status
    m.language = language
    m.framework = framework
    m.prd = prd
    m.architecture = architecture
    m.code_review = code_review
    m.generated_path = generated_path
    m.created_at = datetime(2026, 1, 1, 12, 0, 0)
    m.updated_at = datetime(2026, 1, 1, 12, 0, 0)
    return m


def _artifact_row(*, id=None, project_id=None, filename="main.py", artifact_type="code", content="# code"):
    m = MagicMock()
    m.id = id or _uuid()
    m.project_id = project_id or _uuid()
    m.filename = filename
    m.artifact_type = MagicMock()
    m.artifact_type.value = artifact_type
    m.content = content
    m.created_at = datetime(2026, 1, 1, 12, 0, 0)
    return m


def _approval_row(*, id=None, project_id=None, stage="plan", status="pending", reviewer_comment=None):
    m = MagicMock()
    m.id = id or _uuid()
    m.project_id = project_id or _uuid()
    m.stage = stage
    m.status = MagicMock()
    m.status.value = status
    m.reviewer_comment = reviewer_comment
    m.created_at = datetime(2026, 1, 1, 12, 0, 0)
    return m


def _api_key_row(*, id=None, name="Test Key", key_prefix="sk-test", is_active=True,
                 expires_at=None, last_used_at=None, rate_limit_per_minute=60):
    m = MagicMock()
    m.id = id or _uuid()
    m.name = name
    m.key_prefix = key_prefix
    m.is_active = is_active
    m.expires_at = expires_at
    m.last_used_at = last_used_at
    m.rate_limit_per_minute = rate_limit_per_minute
    m.created_at = datetime(2026, 1, 1, 12, 0, 0)
    return m


def _mock_db_session(scalar_one_or_none=None, scalars_all=None):
    """Build a mock AsyncSession that returns the given values."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_one_or_none
    result.scalars.return_value.all.return_value = scalars_all or []
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


from foundry.database import get_db
from contextlib import asynccontextmanager


@asynccontextmanager
async def _override_db(session):
    """Context manager that overrides the get_db dependency for the duration of a test."""
    async def _get_override():
        yield session

    app.dependency_overrides[get_db] = _get_override
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 1. Health / Root
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_root_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert "name" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# 2. Project CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_project_returns_201():
    project = _project_row(name="Calc App", requirements="Build a calculator.")
    session = _mock_db_session()

    async def fake_refresh(obj):
        obj.id = project.id
        obj.created_at = project.created_at
        obj.updated_at = project.updated_at
        obj.status = project.status

    session.refresh = fake_refresh

    async with _override_db(session):
        with patch("foundry.main._run_project_background", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/projects", json={
                    "name": "Calc App",
                    "requirements": "Build a calculator.",
                    "language": "python",
                })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Calc App"
    assert data["status"] == "created"


@pytest.mark.asyncio
async def test_create_project_missing_requirements_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/projects", json={"name": "Bad"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_missing_name_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/projects", json={"requirements": "Do something."})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_project_by_id():
    project = _project_row(name="My Project", status="running_engineer")
    session = _mock_db_session(scalar_one_or_none=project)

    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/projects/{project.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My Project"
    assert data["status"] == "running_engineer"


@pytest.mark.asyncio
async def test_get_project_not_found_returns_404():
    session = _mock_db_session(scalar_one_or_none=None)
    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/projects/{_uuid()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_projects_returns_list():
    projects = [_project_row(name=f"P{i}") for i in range(3)]
    session = _mock_db_session(scalars_all=projects)

    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_delete_project_returns_204():
    project = _project_row()
    session = _mock_db_session(scalar_one_or_none=project)

    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.delete(f"/projects/{project.id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_nonexistent_project_returns_404():
    session = _mock_db_session(scalar_one_or_none=None)
    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.delete(f"/projects/{_uuid()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_uuid_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/projects/not-a-uuid")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 3. Multi-Language Project Creation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language,framework", [
    ("python", "fastapi"),
    ("javascript", "express"),
    ("typescript", "express"),
    ("java", "spring"),
])
@pytest.mark.asyncio
async def test_create_project_for_language(language, framework):
    project = _project_row(language=language, framework=framework)

    async def fake_refresh(obj):
        obj.id = project.id
        obj.created_at = project.created_at
        obj.updated_at = project.updated_at
        obj.status = project.status

    session = _mock_db_session()
    session.refresh = fake_refresh

    async with _override_db(session):
        with patch("foundry.main._run_project_background", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/projects", json={
                    "name": f"{language.title()} App",
                    "requirements": f"Build a REST API in {language}.",
                    "language": language,
                    "framework": framework,
                })
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# 4. Pipeline Status Transitions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", [
    "created", "running_pm", "running_architect", "running_engineer",
    "running_code_review", "running_reflexion", "running_devops",
    "completed", "failed",
])
@pytest.mark.asyncio
async def test_project_status_is_returned_correctly(status):
    project = _project_row(status=status)
    session = _mock_db_session(scalar_one_or_none=project)

    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/projects/{project.id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == status


# ---------------------------------------------------------------------------
# 5. Artifact Retrieval
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_artifacts_empty_for_new_project():
    project = _project_row()
    # First execute call returns the project, second returns empty artifacts
    session = AsyncMock()
    proj_result = MagicMock()
    proj_result.scalar_one_or_none.return_value = project
    artifact_result = MagicMock()
    artifact_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(side_effect=[proj_result, artifact_result])

    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/projects/{project.id}/artifacts")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_artifacts_returns_stored_artifacts():
    project = _project_row()
    artifacts = [
        _artifact_row(project_id=project.id, filename="prd.md", artifact_type="documentation"),
        _artifact_row(project_id=project.id, filename="main.py", artifact_type="code"),
        _artifact_row(project_id=project.id, filename="code_review.json", artifact_type="review"),
    ]
    session = AsyncMock()
    proj_result = MagicMock()
    proj_result.scalar_one_or_none.return_value = project
    artifact_result = MagicMock()
    artifact_result.scalars.return_value.all.return_value = artifacts
    session.execute = AsyncMock(side_effect=[proj_result, artifact_result])

    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/projects/{project.id}/artifacts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    filenames = {a["filename"] for a in data}
    assert filenames == {"prd.md", "main.py", "code_review.json"}


@pytest.mark.asyncio
async def test_artifact_response_has_required_fields():
    project = _project_row()
    artifact = _artifact_row(project_id=project.id, filename="architecture.md", artifact_type="documentation")
    session = AsyncMock()
    proj_result = MagicMock()
    proj_result.scalar_one_or_none.return_value = project
    artifact_result = MagicMock()
    artifact_result.scalars.return_value.all.return_value = [artifact]
    session.execute = AsyncMock(side_effect=[proj_result, artifact_result])

    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/projects/{project.id}/artifacts")
    item = resp.json()[0]
    for field in ("id", "filename", "artifact_type", "content", "created_at"):
        assert field in item


@pytest.mark.asyncio
async def test_get_artifacts_for_nonexistent_project_returns_404():
    session = _mock_db_session(scalar_one_or_none=None)
    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/projects/{_uuid()}/artifacts")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. Approval Workflow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_approval_returns_none_when_no_approval():
    session = _mock_db_session(scalar_one_or_none=None)
    project = _project_row()
    # First call returns project (not used by this endpoint), second returns None
    session.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=MagicMock(return_value=None)
    ))
    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/projects/{_uuid()}/approval")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_get_approval_returns_pending_approval():
    approval = _approval_row(stage="plan", status="pending")
    session = _mock_db_session(scalar_one_or_none=approval)
    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/projects/{_uuid()}/approval")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["stage"] == "plan"


@pytest.mark.asyncio
async def test_approve_pending_approval():
    from foundry.models.approval import ApprovalStatus
    approval = _approval_row(status="pending")
    session = _mock_db_session(scalar_one_or_none=approval)

    # After commit+refresh the endpoint reads approval.status.value — make it return the real enum value
    async def fake_refresh(obj):
        obj.status = ApprovalStatus.approved

    session.refresh = fake_refresh

    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"/projects/{_uuid()}/approve", json={"comment": "LGTM"})
    assert resp.status_code == 200
    assert resp.json()["reviewer_comment"] == "LGTM"


@pytest.mark.asyncio
async def test_approve_when_no_pending_returns_404():
    session = _mock_db_session(scalar_one_or_none=None)
    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"/projects/{_uuid()}/approve", json={})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reject_pending_approval():
    from foundry.models.approval import ApprovalStatus
    approval = _approval_row(status="pending")
    project = _project_row()
    # First execute → approval, second execute → project (for status update)
    session = AsyncMock()
    approval_result = MagicMock(scalar_one_or_none=MagicMock(return_value=approval))
    project_result = MagicMock(scalar_one_or_none=MagicMock(return_value=project))
    session.execute = AsyncMock(side_effect=[approval_result, project_result])
    session.commit = AsyncMock()

    async def fake_refresh(obj):
        if hasattr(obj, "status") and not isinstance(obj.status, ApprovalStatus):
            obj.status = ApprovalStatus.rejected

    session.refresh = fake_refresh

    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"/projects/{_uuid()}/reject", json={"comment": "Not ready"})
    assert resp.status_code == 200
    assert resp.json()["reviewer_comment"] == "Not ready"


@pytest.mark.asyncio
async def test_reject_when_no_pending_returns_404():
    session = _mock_db_session(scalar_one_or_none=None)
    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"/projects/{_uuid()}/reject", json={})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 7. Agent Control
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_agent_status_for_running_project():
    from foundry.models.project import ProjectStatus
    project = _project_row(status="running_engineer")
    project.status = ProjectStatus.running_engineer
    session = _mock_db_session(scalar_one_or_none=project)

    with patch("foundry.main.agent_control_service.check_control_status", new_callable=AsyncMock, return_value=None), \
         patch("foundry.main.agent_control_service.get_checkpoint", new_callable=AsyncMock, return_value=None):
        async with _override_db(session):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get(f"/projects/{project.id}/agent/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running_engineer"
    assert data["current_agent"] == "engineer"
    assert data["is_paused"] is False


@pytest.mark.asyncio
async def test_get_agent_status_not_found():
    session = _mock_db_session(scalar_one_or_none=None)
    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/projects/{_uuid()}/agent/status")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_pause_running_project():
    from foundry.models.project import ProjectStatus
    project = _project_row(status="running_architect")
    project.status = ProjectStatus.running_architect
    session = _mock_db_session(scalar_one_or_none=project)

    pause_result = {"success": True, "project_id": str(project.id), "action": "pause", "message": "Paused"}
    with patch("foundry.main.agent_control_service.pause_execution", new_callable=AsyncMock, return_value=pause_result):
        async with _override_db(session):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(f"/projects/{project.id}/agent/pause", json={"reason": "Testing"})
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["action"] == "pause"


@pytest.mark.asyncio
async def test_pause_already_paused_returns_400():
    from foundry.models.project import ProjectStatus
    project = _project_row(status="paused")
    project.status = ProjectStatus.paused
    session = _mock_db_session(scalar_one_or_none=project)

    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"/projects/{project.id}/agent/pause", json={})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_resume_paused_project():
    from foundry.models.project import ProjectStatus
    project = _project_row(status="paused")
    project.status = ProjectStatus.paused
    session = _mock_db_session(scalar_one_or_none=project)

    resume_result = {"success": True, "project_id": str(project.id), "action": "resume", "message": "Resumed"}
    with patch("foundry.main.agent_control_service.resume_execution", new_callable=AsyncMock, return_value=resume_result):
        async with _override_db(session):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(f"/projects/{project.id}/agent/resume")
    assert resp.status_code == 200
    assert resp.json()["action"] == "resume"


@pytest.mark.asyncio
async def test_resume_non_paused_returns_400():
    from foundry.models.project import ProjectStatus
    project = _project_row(status="running_engineer")
    project.status = ProjectStatus.running_engineer
    session = _mock_db_session(scalar_one_or_none=project)

    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"/projects/{project.id}/agent/resume")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cancel_running_project():
    from foundry.models.project import ProjectStatus
    project = _project_row(status="running_devops")
    project.status = ProjectStatus.running_devops
    session = _mock_db_session(scalar_one_or_none=project)

    cancel_result = {"success": True, "project_id": str(project.id), "action": "cancel", "message": "Cancelled"}
    with patch("foundry.main.agent_control_service.cancel_execution", new_callable=AsyncMock, return_value=cancel_result):
        async with _override_db(session):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(f"/projects/{project.id}/agent/cancel", json={"rollback": True})
    assert resp.status_code == 200
    assert resp.json()["action"] == "cancel"


@pytest.mark.asyncio
async def test_cancel_not_found_returns_404():
    session = _mock_db_session(scalar_one_or_none=None)
    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"/projects/{_uuid()}/agent/cancel", json={})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 8. API Key Management
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_api_key_returns_201():
    from foundry.models.api_key import APIKey
    key_value = "sk-testapikey1234567890"
    key_row = _api_key_row(name="My Key", key_prefix="sk-test")
    session = _mock_db_session()
    session.refresh = AsyncMock(side_effect=lambda obj: None)

    with patch.object(APIKey, "generate_key", return_value=key_value), \
         patch.object(APIKey, "hash_key", return_value="hashed"), \
         patch.object(APIKey, "get_key_prefix", return_value="sk-test"):
        async with _override_db(session):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api-keys", json={"name": "My Key"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Key"
    assert "key" in data
    assert data["key"] == key_value


@pytest.mark.asyncio
async def test_create_api_key_missing_name_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api-keys", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_api_keys():
    keys = [_api_key_row(name=f"Key {i}") for i in range(3)]
    session = _mock_db_session(scalars_all=keys)

    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api-keys")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    for item in data:
        assert "key" not in item  # actual key never returned in list


@pytest.mark.asyncio
async def test_deactivate_api_key():
    key_row = _api_key_row(is_active=True)
    session = _mock_db_session(scalar_one_or_none=key_row)
    session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "is_active", False))

    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.patch(f"/api-keys/{key_row.id}/deactivate")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_api_key_returns_204():
    key_row = _api_key_row()
    session = _mock_db_session(scalar_one_or_none=key_row)

    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.delete(f"/api-keys/{key_row.id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_nonexistent_api_key_returns_404():
    session = _mock_db_session(scalar_one_or_none=None)
    async with _override_db(session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.delete(f"/api-keys/{_uuid()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 9. Orchestrator Unit Tests
# ---------------------------------------------------------------------------

def test_orchestrator_state_merge_preserves_prior_keys():
    """State merge pattern: new keys added, old keys not dropped."""
    prior = {"prd": "some prd", "requirements": "build x", "extra": "keep me"}
    new_keys = {"architecture": "arch doc"}
    merged = {**prior, **new_keys}
    assert merged["prd"] == "some prd"
    assert merged["extra"] == "keep me"
    assert merged["architecture"] == "arch doc"


def test_orchestrator_reflexion_gate_fix_when_below_max():
    from foundry.orchestrator import AgentOrchestrator, MAX_REFLEXION_RETRIES
    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    for count in range(MAX_REFLEXION_RETRIES):
        state = {"review_feedback": {"approved": False}, "reflexion_count": count}
        assert orch._should_continue_from_review(state) == "fix"


def test_orchestrator_reflexion_gate_fail_at_max():
    from foundry.orchestrator import AgentOrchestrator, MAX_REFLEXION_RETRIES
    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    state = {"review_feedback": {"approved": False}, "reflexion_count": MAX_REFLEXION_RETRIES}
    assert orch._should_continue_from_review(state) == "fail"


def test_orchestrator_reflexion_gate_approve_when_approved():
    from foundry.orchestrator import AgentOrchestrator
    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    state = {"review_feedback": {"approved": True}, "reflexion_count": 0}
    assert orch._should_continue_from_review(state) == "approve"


def test_orchestrator_max_reflexion_retries_is_3():
    from foundry.orchestrator import MAX_REFLEXION_RETRIES
    assert MAX_REFLEXION_RETRIES == 3


@pytest.mark.asyncio
async def test_orchestrator_run_marks_completed_on_success():
    from foundry.orchestrator import AgentOrchestrator
    from foundry.models.project import ProjectStatus

    async def fake_astream(state):
        yield {"devops": {"success_flag": True, "project_context": {}, "messages": []}}

    mock_graph = MagicMock()
    mock_graph.astream = fake_astream

    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    orch.graph = mock_graph
    orch.kg_service = MagicMock()

    with patch.object(orch, "_update_project_status", new_callable=AsyncMock) as mock_update, \
         patch("foundry.orchestrator.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        project_mock = MagicMock()
        project_mock.language = "python"
        project_mock.framework = ""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = project_mock
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session_cls.return_value = mock_session

        result = await orch.run(project_id=str(_uuid()), initial_prompt="Build something.")

    assert result is True
    last_status = mock_update.call_args_list[-1][0][1]
    assert last_status == ProjectStatus.completed


@pytest.mark.asyncio
async def test_orchestrator_run_marks_failed_on_exception():
    from foundry.orchestrator import AgentOrchestrator
    from foundry.models.project import ProjectStatus

    mock_graph = MagicMock()
    mock_graph.astream = AsyncMock(side_effect=RuntimeError("boom"))

    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    orch.graph = mock_graph
    orch.kg_service = MagicMock()

    with patch.object(orch, "_update_project_status", new_callable=AsyncMock) as mock_update, \
         patch("foundry.orchestrator.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        project_mock = MagicMock()
        project_mock.language = "python"
        project_mock.framework = ""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = project_mock
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session_cls.return_value = mock_session

        result = await orch.run(project_id=str(_uuid()), initial_prompt="req")

    assert result is False
    last_status = mock_update.call_args_list[-1][0][1]
    assert last_status == ProjectStatus.failed


@pytest.mark.asyncio
async def test_orchestrator_reads_language_from_project():
    from foundry.orchestrator import AgentOrchestrator

    captured = {}

    async def fake_astream(state):
        captured.update(state)
        yield {"devops": {"success_flag": True, "project_context": {}, "messages": []}}

    mock_graph = MagicMock()
    mock_graph.astream = fake_astream

    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    orch.graph = mock_graph
    orch.kg_service = MagicMock()

    with patch.object(orch, "_update_project_status", new_callable=AsyncMock), \
         patch("foundry.orchestrator.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        project_mock = MagicMock()
        project_mock.language = "javascript"
        project_mock.framework = "express"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = project_mock
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session_cls.return_value = mock_session

        await orch.run(project_id=str(_uuid()), initial_prompt="Build a Node API.")

    assert captured.get("language") == "javascript"
    assert captured.get("framework") == "express"


