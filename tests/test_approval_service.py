"""Unit tests for approval service."""

import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.models.approval import (
    ApprovalRequest,
    ApprovalStatus,
    ApprovalType,
    ApprovalPolicy,
    ApprovalContent,
    ApprovalResponse,
    ApprovalRequestCreate,
)
from foundry.models.project import Project, ProjectStatus
from foundry.services.approval_service import approval_service


@pytest.fixture
async def test_project(db_session: AsyncSession):
    """Create a test project."""
    project = Project(
        name="Test Project",
        description="Test project for approval tests",
        requirements="Build a test app",
        status=ProjectStatus.created,
        approval_policy=ApprovalPolicy.standard,
    )
    db_session.add(project)
    await db_session.flush()
    return project


class TestApprovalService:
    """Test approval service functionality."""

    @pytest.mark.asyncio
    async def test_create_approval_request(self, db_session: AsyncSession, test_project: Project):
        """Test creating an approval request."""
        content = ApprovalContent(
            description="Test approval request",
            phantom_file_tree={"src": {"main.py": "file"}},
            technology_stack={"python": "3.11"},
        )
        
        request_data = ApprovalRequestCreate(
            project_id=str(test_project.id),
            request_type=ApprovalType.plan,
            content=content,
            estimated_cost=10.50,
            timeout_minutes=30,
        )
        
        approval = await approval_service.create_approval_request(db_session, request_data)
        
        assert approval.id is not None
        assert approval.project_id == test_project.id
        assert approval.request_type == ApprovalType.plan
        assert approval.status == ApprovalStatus.pending
        assert approval.estimated_cost == 10.50
        assert approval.timeout_at is not None
        assert approval.content["description"] == "Test approval request"

    @pytest.mark.asyncio
    async def test_get_approval_request(self, db_session: AsyncSession, test_project: Project):
        """Test retrieving an approval request."""
        content = ApprovalContent(description="Test approval")
        request_data = ApprovalRequestCreate(
            project_id=str(test_project.id),
            request_type=ApprovalType.deployment,
            content=content,
        )
        
        created = await approval_service.create_approval_request(db_session, request_data)
        retrieved = await approval_service.get_approval_request(db_session, created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.request_type == ApprovalType.deployment

    @pytest.mark.asyncio
    async def test_list_pending_approvals(self, db_session: AsyncSession, test_project: Project):
        """Test listing pending approvals."""
        # Create multiple approval requests
        for i in range(3):
            content = ApprovalContent(description=f"Test approval {i}")
            request_data = ApprovalRequestCreate(
                project_id=str(test_project.id),
                request_type=ApprovalType.plan,
                content=content,
            )
            await approval_service.create_approval_request(db_session, request_data)
        
        pending = await approval_service.list_pending_approvals(db_session, test_project.id)
        
        assert len(pending) == 3
        assert all(a.status == ApprovalStatus.pending for a in pending)

    @pytest.mark.asyncio
    async def test_respond_to_approval_approve(self, db_session: AsyncSession, test_project: Project):
        """Test approving an approval request."""
        content = ApprovalContent(description="Test approval")
        request_data = ApprovalRequestCreate(
            project_id=str(test_project.id),
            request_type=ApprovalType.plan,
            content=content,
        )
        
        approval = await approval_service.create_approval_request(db_session, request_data)
        
        response = ApprovalResponse(
            decision="approve",
            reason="Looks good",
        )
        
        result = await approval_service.respond_to_approval(db_session, approval.id, response)
        
        assert result["success"] is True
        assert result["status"] == "approved"
        
        # Verify database update
        updated = await approval_service.get_approval_request(db_session, approval.id)
        assert updated.status == ApprovalStatus.approved
        assert updated.responded_at is not None

    @pytest.mark.asyncio
    async def test_respond_to_approval_reject(self, db_session: AsyncSession, test_project: Project):
        """Test rejecting an approval request."""
        content = ApprovalContent(description="Test approval")
        request_data = ApprovalRequestCreate(
            project_id=str(test_project.id),
            request_type=ApprovalType.deployment,
            content=content,
        )
        
        approval = await approval_service.create_approval_request(db_session, request_data)
        
        response = ApprovalResponse(
            decision="reject",
            reason="Needs changes",
        )
        
        result = await approval_service.respond_to_approval(db_session, approval.id, response)
        
        assert result["success"] is True
        assert result["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_respond_to_approval_with_changes(self, db_session: AsyncSession, test_project: Project):
        """Test approving with modifications."""
        content = ApprovalContent(description="Test approval")
        request_data = ApprovalRequestCreate(
            project_id=str(test_project.id),
            request_type=ApprovalType.plan,
            content=content,
        )
        
        approval = await approval_service.create_approval_request(db_session, request_data)
        
        response = ApprovalResponse(
            decision="approve_with_changes",
            modifications={"tech_stack": {"python": "3.12"}},
            reason="Updated Python version",
        )
        
        result = await approval_service.respond_to_approval(db_session, approval.id, response)
        
        assert result["success"] is True
        assert result["status"] == "approved"
        
        updated = await approval_service.get_approval_request(db_session, approval.id)
        assert updated.response["modifications"]["tech_stack"]["python"] == "3.12"

    @pytest.mark.asyncio
    async def test_cancel_approval(self, db_session: AsyncSession, test_project: Project):
        """Test cancelling an approval request."""
        content = ApprovalContent(description="Test approval")
        request_data = ApprovalRequestCreate(
            project_id=str(test_project.id),
            request_type=ApprovalType.plan,
            content=content,
        )
        
        approval = await approval_service.create_approval_request(db_session, request_data)
        
        result = await approval_service.cancel_approval(
            db_session,
            approval.id,
            reason="User cancelled",
        )
        
        assert result["success"] is True
        assert result["status"] == "cancelled"
        
        updated = await approval_service.get_approval_request(db_session, approval.id)
        assert updated.status == ApprovalStatus.cancelled

    @pytest.mark.asyncio
    async def test_process_expired_approvals(self, db_session: AsyncSession, test_project: Project):
        """Test auto-cancelling expired approvals."""
        # Create an expired approval
        content = ApprovalContent(description="Expired approval")
        request_data = ApprovalRequestCreate(
            project_id=str(test_project.id),
            request_type=ApprovalType.plan,
            content=content,
            timeout_minutes=0,  # Immediate timeout
        )
        
        approval = await approval_service.create_approval_request(db_session, request_data)
        
        # Manually set timeout to past
        approval.timeout_at = datetime.utcnow() - timedelta(minutes=1)
        await db_session.flush()
        
        # Process expired approvals
        result = await approval_service.process_expired_approvals(db_session)
        
        assert result["success"] is True
        assert result["expired_count"] == 1
        assert str(approval.id) in result["approval_ids"]
        
        # Verify status updated
        updated = await approval_service.get_approval_request(db_session, approval.id)
        assert updated.status == ApprovalStatus.timeout

    @pytest.mark.asyncio
    async def test_cannot_respond_to_expired_approval(self, db_session: AsyncSession, test_project: Project):
        """Test that expired approvals cannot be responded to."""
        content = ApprovalContent(description="Test approval")
        request_data = ApprovalRequestCreate(
            project_id=str(test_project.id),
            request_type=ApprovalType.plan,
            content=content,
            timeout_minutes=0,
        )
        
        approval = await approval_service.create_approval_request(db_session, request_data)
        approval.timeout_at = datetime.utcnow() - timedelta(minutes=1)
        await db_session.flush()
        
        response = ApprovalResponse(decision="approve")
        result = await approval_service.respond_to_approval(db_session, approval.id, response)
        
        assert result["success"] is False
        assert "cannot be responded to" in result["message"].lower()

    def test_should_request_approval_autonomous(self):
        """Test approval policy logic for autonomous mode."""
        assert not approval_service.should_request_approval(
            ApprovalPolicy.autonomous, ApprovalType.plan
        )
        assert not approval_service.should_request_approval(
            ApprovalPolicy.autonomous, ApprovalType.deployment
        )

    def test_should_request_approval_standard(self):
        """Test approval policy logic for standard mode."""
        assert approval_service.should_request_approval(
            ApprovalPolicy.standard, ApprovalType.plan
        )
        assert approval_service.should_request_approval(
            ApprovalPolicy.standard, ApprovalType.deployment
        )
        assert not approval_service.should_request_approval(
            ApprovalPolicy.standard, ApprovalType.component
        )

    def test_should_request_approval_strict(self):
        """Test approval policy logic for strict mode."""
        assert approval_service.should_request_approval(
            ApprovalPolicy.strict, ApprovalType.plan
        )
        assert approval_service.should_request_approval(
            ApprovalPolicy.strict, ApprovalType.component
        )
        assert approval_service.should_request_approval(
            ApprovalPolicy.strict, ApprovalType.deployment
        )

    def test_approval_request_is_expired(self):
        """Test approval expiration check."""
        approval = ApprovalRequest(
            project_id=uuid.uuid4(),
            request_type=ApprovalType.plan,
            status=ApprovalStatus.pending,
            content={},
            timeout_at=datetime.utcnow() - timedelta(minutes=1),
        )
        
        assert approval.is_expired() is True
        
        approval.timeout_at = datetime.utcnow() + timedelta(minutes=10)
        assert approval.is_expired() is False
        
        approval.timeout_at = None
        assert approval.is_expired() is False

    def test_approval_request_can_respond(self):
        """Test approval response eligibility."""
        approval = ApprovalRequest(
            project_id=uuid.uuid4(),
            request_type=ApprovalType.plan,
            status=ApprovalStatus.pending,
            content={},
            timeout_at=datetime.utcnow() + timedelta(minutes=10),
        )
        
        assert approval.can_respond() is True
        
        # Cannot respond if approved
        approval.status = ApprovalStatus.approved
        assert approval.can_respond() is False
        
        # Cannot respond if expired
        approval.status = ApprovalStatus.pending
        approval.timeout_at = datetime.utcnow() - timedelta(minutes=1)
        assert approval.can_respond() is False
