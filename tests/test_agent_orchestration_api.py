"""Tests for agent orchestration API endpoints."""

import pytest
from uuid import uuid4

from foundry.models.project import Project, ProjectStatus


@pytest.mark.asyncio
class TestAgentOrchestrationEndpoints:
    """Test agent orchestration control endpoints."""

    async def test_get_agent_status(self, client, db_session):
        """Test getting agent status for a project."""
        # Create test project
        project = Project(
            name="Test Project",
            requirements="Build a test app",
            status=ProjectStatus.running_engineer,
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        
        response = await client.get(f"/projects/{project.id}/agent/status")
        assert response.status_code == 200
        data = response.json()
        
        assert data["project_id"] == str(project.id)
        assert data["status"] == "running_engineer"
        assert data["current_agent"] == "engineer"
        assert data["is_paused"] is False

    async def test_get_agent_status_not_found(self, client):
        """Test getting status for non-existent project."""
        fake_id = uuid4()
        response = await client.get(f"/projects/{fake_id}/agent/status")
        assert response.status_code == 404

    async def test_pause_agent_execution(self, client, db_session):
        """Test pausing agent execution."""
        # Create running project
        project = Project(
            name="Test Project",
            requirements="Build a test app",
            status=ProjectStatus.running_engineer,
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        
        response = await client.post(
            f"/projects/{project.id}/agent/pause",
            json={"reason": "Testing pause functionality"},
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["action"] == "pause"
        assert "Testing pause functionality" in data["message"]
        
        # Verify project status updated
        await db_session.refresh(project)
        assert project.status == ProjectStatus.paused

    async def test_pause_already_paused_project(self, client, db_session):
        """Test pausing an already paused project."""
        # Create paused project
        project = Project(
            name="Test Project",
            requirements="Build a test app",
            status=ProjectStatus.paused,
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        
        response = await client.post(
            f"/projects/{project.id}/agent/pause",
            json={},
        )
        assert response.status_code == 400
        assert "already paused" in response.json()["detail"]

    async def test_resume_agent_execution(self, client, db_session):
        """Test resuming agent execution."""
        # Create paused project
        project = Project(
            name="Test Project",
            requirements="Build a test app",
            status=ProjectStatus.paused,
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        
        response = await client.post(f"/projects/{project.id}/agent/resume")
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["action"] == "resume"
        
        # Verify project status updated
        await db_session.refresh(project)
        assert project.status != ProjectStatus.paused

    async def test_resume_not_paused_project(self, client, db_session):
        """Test resuming a project that isn't paused."""
        # Create running project
        project = Project(
            name="Test Project",
            requirements="Build a test app",
            status=ProjectStatus.running_engineer,
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        
        response = await client.post(f"/projects/{project.id}/agent/resume")
        assert response.status_code == 400
        assert "not paused" in response.json()["detail"]

    async def test_cancel_agent_execution(self, client, db_session):
        """Test canceling agent execution."""
        # Create running project
        project = Project(
            name="Test Project",
            requirements="Build a test app",
            status=ProjectStatus.running_engineer,
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        
        response = await client.post(
            f"/projects/{project.id}/agent/cancel",
            json={"rollback": True},
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["action"] == "cancel"
        
        # Verify project status updated to failed
        await db_session.refresh(project)
        assert project.status == ProjectStatus.failed

    async def test_cancel_without_rollback(self, client, db_session):
        """Test canceling without rollback."""
        # Create running project
        project = Project(
            name="Test Project",
            requirements="Build a test app",
            status=ProjectStatus.running_engineer,
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        
        response = await client.post(
            f"/projects/{project.id}/agent/cancel",
            json={"rollback": False},
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data.get("checkpoint_restored") is None or data["checkpoint_restored"] is False


@pytest.mark.asyncio
class TestAgentStatusHelper:
    """Test helper functions for agent status."""

    def test_get_current_agent_from_status(self):
        """Test extracting agent name from project status."""
        from foundry.main import _get_current_agent_from_status
        
        assert _get_current_agent_from_status(ProjectStatus.running_pm) == "product_manager"
        assert _get_current_agent_from_status(ProjectStatus.running_architect) == "architect"
        assert _get_current_agent_from_status(ProjectStatus.running_engineer) == "engineer"
        assert _get_current_agent_from_status(ProjectStatus.running_code_review) == "code_review"
        assert _get_current_agent_from_status(ProjectStatus.running_reflexion) == "reflexion"
        assert _get_current_agent_from_status(ProjectStatus.running_devops) == "devops"
        assert _get_current_agent_from_status(ProjectStatus.created) is None
        assert _get_current_agent_from_status(ProjectStatus.completed) is None
