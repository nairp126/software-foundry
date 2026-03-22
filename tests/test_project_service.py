"""Tests for project lifecycle management service."""

import os
import shutil
import uuid
import pytest
from pathlib import Path

from foundry.models.project import Project, ProjectStatus
from foundry.services.project_service import ProjectService


@pytest.fixture
def test_projects_dir(tmp_path):
    """Create a temporary directory for test projects."""
    import stat
    projects_dir = tmp_path / "test_projects"
    projects_dir.mkdir()
    yield str(projects_dir)
    # Cleanup
    if projects_dir.exists():
        def remove_readonly(func, path, _):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(projects_dir, onerror=remove_readonly)


@pytest.fixture
def project_service(test_projects_dir):
    """Create a project service instance with test directory."""
    return ProjectService(base_projects_dir=test_projects_dir)


@pytest.mark.asyncio
async def test_create_project_generates_unique_id(db_session, project_service):
    """Test that project creation generates a unique UUID."""
    project = await project_service.create_project(
        session=db_session,
        name="Test Project",
        requirements="Build a web app",
        description="Test description",
    )
    
    assert project.id is not None
    assert isinstance(project.id, uuid.UUID)
    assert project.name == "Test Project"
    assert project.requirements == "Build a web app"
    assert project.description == "Test description"
    assert project.status == ProjectStatus.created


@pytest.mark.asyncio
async def test_create_project_initializes_directory_structure(db_session, project_service):
    """Test that project creation sets up proper directory structure."""
    project = await project_service.create_project(
        session=db_session,
        name="Test Project",
        requirements="Build a web app",
    )
    
    project_dir = project.generated_path
    assert project_dir is not None
    assert os.path.exists(project_dir)
    
    # Check standard subdirectories
    assert os.path.exists(os.path.join(project_dir, "src"))
    assert os.path.exists(os.path.join(project_dir, "tests"))
    assert os.path.exists(os.path.join(project_dir, "docs"))
    assert os.path.exists(os.path.join(project_dir, "config"))
    
    # Check README exists
    assert os.path.exists(os.path.join(project_dir, "README.md"))


@pytest.mark.asyncio
async def test_create_project_initializes_git_repository(db_session, project_service):
    """Test that project creation initializes a Git repository."""
    project = await project_service.create_project(
        session=db_session,
        name="Test Project",
        requirements="Build a web app",
    )
    
    project_dir = project.generated_path
    git_dir = os.path.join(project_dir, ".git")
    
    assert os.path.exists(git_dir)
    assert os.path.isdir(git_dir)
    
    # Check .gitignore exists
    gitignore_path = os.path.join(project_dir, ".gitignore")
    assert os.path.exists(gitignore_path)


@pytest.mark.asyncio
async def test_get_project_returns_existing_project(db_session, project_service):
    """Test retrieving an existing project by ID."""
    created_project = await project_service.create_project(
        session=db_session,
        name="Test Project",
        requirements="Build a web app",
    )
    
    retrieved_project = await project_service.get_project(
        session=db_session,
        project_id=created_project.id,
    )
    
    assert retrieved_project is not None
    assert retrieved_project.id == created_project.id
    assert retrieved_project.name == created_project.name


@pytest.mark.asyncio
async def test_get_project_returns_none_for_nonexistent(db_session, project_service):
    """Test that getting a non-existent project returns None."""
    fake_id = uuid.uuid4()
    project = await project_service.get_project(
        session=db_session,
        project_id=fake_id,
    )
    
    assert project is None


@pytest.mark.asyncio
async def test_list_projects_returns_all_projects(db_session, project_service):
    """Test listing all projects with metadata."""
    # Create multiple projects
    project1 = await project_service.create_project(
        session=db_session,
        name="Project 1",
        requirements="Build app 1",
    )
    
    project2 = await project_service.create_project(
        session=db_session,
        name="Project 2",
        requirements="Build app 2",
    )
    
    projects = await project_service.list_projects(session=db_session)
    
    assert len(projects) >= 2
    
    # Check metadata structure
    for project_meta in projects:
        assert "id" in project_meta
        assert "name" in project_meta
        assert "status" in project_meta
        assert "created_at" in project_meta
        assert "updated_at" in project_meta
        assert "resource_usage" in project_meta
        assert "estimated_monthly_cost" in project_meta


@pytest.mark.asyncio
async def test_list_projects_filters_by_status(db_session, project_service):
    """Test filtering projects by status."""
    project = await project_service.create_project(
        session=db_session,
        name="Test Project",
        requirements="Build a web app",
    )
    
    # List only created projects
    projects = await project_service.list_projects(
        session=db_session,
        status=ProjectStatus.created,
    )
    
    assert len(projects) >= 1
    assert all(p["status"] == "created" for p in projects)


@pytest.mark.asyncio
async def test_list_projects_includes_resource_usage(db_session, project_service):
    """Test that project listing includes resource usage metrics."""
    project = await project_service.create_project(
        session=db_session,
        name="Test Project",
        requirements="Build a web app",
    )
    
    projects = await project_service.list_projects(session=db_session)
    
    project_meta = next(p for p in projects if p["id"] == str(project.id))
    
    assert "resource_usage" in project_meta
    assert "disk_space_mb" in project_meta["resource_usage"]
    assert "knowledge_graph_nodes" in project_meta["resource_usage"]
    assert "active_agents" in project_meta["resource_usage"]
    
    # Should have some disk space from created files
    assert project_meta["resource_usage"]["disk_space_mb"] >= 0


@pytest.mark.asyncio
async def test_delete_project_requires_confirmation(db_session, project_service):
    """Test that project deletion requires explicit confirmation."""
    project = await project_service.create_project(
        session=db_session,
        name="Test Project",
        requirements="Build a web app",
    )
    
    with pytest.raises(ValueError, match="requires explicit confirmation"):
        await project_service.delete_project(
            session=db_session,
            project_id=project.id,
            confirmed=False,
        )


@pytest.mark.asyncio
async def test_delete_project_removes_local_files(db_session, project_service):
    """Test that project deletion removes all local files."""
    project = await project_service.create_project(
        session=db_session,
        name="Test Project",
        requirements="Build a web app",
    )
    
    project_dir = project.generated_path
    assert os.path.exists(project_dir)
    
    result = await project_service.delete_project(
        session=db_session,
        project_id=project.id,
        confirmed=True,
    )
    
    assert result["success"] is True
    assert "local_files_removed" in result["steps_completed"]
    assert not os.path.exists(project_dir)


@pytest.mark.asyncio
async def test_delete_project_removes_database_record(db_session, project_service):
    """Test that project deletion removes the database record."""
    project = await project_service.create_project(
        session=db_session,
        name="Test Project",
        requirements="Build a web app",
    )
    
    project_id = project.id
    
    result = await project_service.delete_project(
        session=db_session,
        project_id=project_id,
        confirmed=True,
    )
    
    assert result["success"] is True
    assert "database_record_deleted" in result["steps_completed"]
    
    # Verify project no longer exists
    deleted_project = await project_service.get_project(
        session=db_session,
        project_id=project_id,
    )
    assert deleted_project is None


@pytest.mark.asyncio
async def test_delete_project_handles_nonexistent_project(db_session, project_service):
    """Test that deleting a non-existent project returns appropriate result."""
    fake_id = uuid.uuid4()
    
    result = await project_service.delete_project(
        session=db_session,
        project_id=fake_id,
        confirmed=True,
    )
    
    assert result["success"] is False
    assert "not found" in result["message"]


@pytest.mark.asyncio
async def test_delete_project_includes_cdk_destroy_stub(db_session, project_service):
    """Test that project deletion includes CDK destroy step (stubbed for MVP)."""
    project = await project_service.create_project(
        session=db_session,
        name="Test Project",
        requirements="Build a web app",
    )
    
    result = await project_service.delete_project(
        session=db_session,
        project_id=project.id,
        confirmed=True,
    )
    
    assert "cdk_destroy_output" in result
    assert result["cdk_destroy_output"]["status"] == "stubbed"


@pytest.mark.asyncio
async def test_delete_project_includes_knowledge_graph_cleanup(db_session, project_service):
    """Test that project deletion includes knowledge graph cleanup (stubbed for MVP)."""
    project = await project_service.create_project(
        session=db_session,
        name="Test Project",
        requirements="Build a web app",
    )
    
    result = await project_service.delete_project(
        session=db_session,
        project_id=project.id,
        confirmed=True,
    )
    
    assert "kg_nodes_deleted" in result
    assert "knowledge_graph_cleaned" in result["steps_completed"]


@pytest.mark.asyncio
async def test_multiple_projects_have_unique_directories(db_session, project_service):
    """Test that multiple projects get unique directory paths."""
    project1 = await project_service.create_project(
        session=db_session,
        name="Project 1",
        requirements="Build app 1",
    )
    
    project2 = await project_service.create_project(
        session=db_session,
        name="Project 2",
        requirements="Build app 2",
    )
    
    assert project1.generated_path != project2.generated_path
    assert os.path.exists(project1.generated_path)
    assert os.path.exists(project2.generated_path)
