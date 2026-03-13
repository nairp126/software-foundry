"""Integration tests for approval workflow system."""

import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.models.project import Project, ProjectStatus
from foundry.models.approval import (
    ApprovalType,
    ApprovalPolicy,
    ApprovalContent,
    ApprovalResponse,
    ApprovalRequestCreate,
)
from foundry.services.approval_service import approval_service
from foundry.services.agent_control import agent_control_service


@pytest.fixture
async def test_project(db_session: AsyncSession):
    """Create a test project."""
    project = Project(
        name="Integration Test Project",
        description="Test project for approval workflow integration",
        requirements="Build a test app with approval workflow",
        status=ProjectStatus.created,
        approval_policy=ApprovalPolicy.standard,
    )
    db_session.add(project)
    await db_session.flush()
    return project


class TestApprovalWorkflowIntegration:
    """Integration tests for complete approval workflow."""

    @pytest.mark.asyncio
    async def test_complete_approval_workflow(
        self,
        db_session: AsyncSession,
        redis_client,
        test_project: Project,
    ):
        """Test complete approval workflow from request to response."""
        # Step 1: Create approval request
        content = ApprovalContent(
            description="Deploy new feature",
            phantom_file_tree={
                "src": {
                    "api": {"routes.py": "file", "models.py": "file"},
                    "frontend": {"App.tsx": "file"},
                }
            },
            technology_stack={
                "backend": "FastAPI",
                "frontend": "React",
                "database": "PostgreSQL",
            },
            dependencies=["fastapi", "sqlalchemy", "react"],
            cloud_resources=[
                {"type": "EC2", "instance_type": "t3.micro", "cost": 8.50},
                {"type": "RDS", "instance_type": "db.t3.micro", "cost": 15.00},
            ],
            estimated_time="30 minutes",
        )
        
        request_data = ApprovalRequestCreate(
            project_id=str(test_project.id),
            request_type=ApprovalType.plan,
            content=content,
            estimated_cost=23.50,
            timeout_minutes=60,
        )
        
        approval = await approval_service.create_approval_request(db_session, request_data)
        assert approval.status.value == "pending"
        
        # Step 2: User reviews and approves
        response = ApprovalResponse(
            decision="approve",
            reason="Plan looks good, proceed with execution",
        )
        
        result = await approval_service.respond_to_approval(
            db_session,
            approval.id,
            response,
        )
        
        assert result["success"] is True
        assert result["status"] == "approved"
        
        # Step 3: Verify approval is no longer pending
        pending = await approval_service.list_pending_approvals(
            db_session,
            test_project.id,
        )
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_approval_with_pause_resume(
        self,
        db_session: AsyncSession,
        redis_client,
        test_project: Project,
    ):
        """Test approval workflow with execution pause and resume."""
        # Create approval and approve it
        content = ApprovalContent(description="Test feature")
        request_data = ApprovalRequestCreate(
            project_id=str(test_project.id),
            request_type=ApprovalType.plan,
            content=content,
        )
        
        approval = await approval_service.create_approval_request(db_session, request_data)
        
        response = ApprovalResponse(decision="approve")
        await approval_service.respond_to_approval(db_session, approval.id, response)
        
        # Simulate execution starting
        agent_state = {
            "current_agent": "engineer",
            "progress": 30,
        }
        await agent_control_service.save_checkpoint(
            test_project.id,
            agent_state,
            description="Engineering in progress",
        )
        
        # User pauses execution
        pause_result = await agent_control_service.pause_execution(
            test_project.id,
            reason="Need to review progress",
        )
        assert pause_result["success"] is True
        
        # Verify pause status
        control_status = await agent_control_service.check_control_status(test_project.id)
        assert control_status["action"] == "pause"
        
        # User resumes execution
        resume_result = await agent_control_service.resume_execution(test_project.id)
        assert resume_result["success"] is True
        
        # Verify control cleared
        control_status = await agent_control_service.check_control_status(test_project.id)
        assert control_status is None
        
        # Checkpoint should still exist
        checkpoint = await agent_control_service.get_checkpoint(test_project.id)
        assert checkpoint is not None
        assert checkpoint["agent_state"]["progress"] == 30

    @pytest.mark.asyncio
    async def test_approval_rejection_workflow(
        self,
        db_session: AsyncSession,
        redis_client,
        test_project: Project,
    ):
        """Test approval rejection and regeneration workflow."""
        # Create approval request
        content = ApprovalContent(
            description="Initial plan",
            technology_stack={"backend": "Django"},
        )
        
        request_data = ApprovalRequestCreate(
            project_id=str(test_project.id),
            request_type=ApprovalType.plan,
            content=content,
        )
        
        approval = await approval_service.create_approval_request(db_session, request_data)
        
        # User rejects
        response = ApprovalResponse(
            decision="reject",
            reason="Prefer FastAPI over Django",
        )
        
        result = await approval_service.respond_to_approval(
            db_session,
            approval.id,
            response,
        )
        
        assert result["success"] is True
        assert result["status"] == "rejected"
        
        # Create new approval with modifications
        new_content = ApprovalContent(
            description="Updated plan",
            technology_stack={"backend": "FastAPI"},
        )
        
        new_request_data = ApprovalRequestCreate(
            project_id=str(test_project.id),
            request_type=ApprovalType.plan,
            content=new_content,
        )
        
        new_approval = await approval_service.create_approval_request(
            db_session,
            new_request_data,
        )
        
        # User approves new plan
        approve_response = ApprovalResponse(decision="approve")
        approve_result = await approval_service.respond_to_approval(
            db_session,
            new_approval.id,
            approve_response,
        )
        
        assert approve_result["success"] is True
        assert approve_result["status"] == "approved"

    @pytest.mark.asyncio
    async def test_approval_timeout_workflow(
        self,
        db_session: AsyncSession,
        redis_client,
        test_project: Project,
    ):
        """Test approval timeout and auto-cancellation."""
        # Create approval with immediate timeout
        content = ApprovalContent(description="Time-sensitive approval")
        request_data = ApprovalRequestCreate(
            project_id=str(test_project.id),
            request_type=ApprovalType.deployment,
            content=content,
            timeout_minutes=0,
        )
        
        approval = await approval_service.create_approval_request(db_session, request_data)
        
        # Manually expire it
        approval.timeout_at = datetime.utcnow() - timedelta(seconds=1)
        await db_session.flush()
        
        # Process expired approvals
        result = await approval_service.process_expired_approvals(db_session)
        
        assert result["expired_count"] == 1
        assert str(approval.id) in result["approval_ids"]
        
        # Verify approval is now timed out
        updated = await approval_service.get_approval_request(db_session, approval.id)
        assert updated.status.value == "timeout"

    @pytest.mark.asyncio
    async def test_policy_enforcement(
        self,
        db_session: AsyncSession,
        redis_client,
    ):
        """Test approval policy enforcement across different modes."""
        # Test autonomous mode
        autonomous_project = Project(
            name="Autonomous Project",
            requirements="Test autonomous mode",
            approval_policy=ApprovalPolicy.autonomous,
        )
        db_session.add(autonomous_project)
        await db_session.flush()
        
        # No approvals should be required
        assert not approval_service.should_request_approval(
            ApprovalPolicy.autonomous,
            ApprovalType.plan,
        )
        assert not approval_service.should_request_approval(
            ApprovalPolicy.autonomous,
            ApprovalType.deployment,
        )
        
        # Test standard mode
        standard_project = Project(
            name="Standard Project",
            requirements="Test standard mode",
            approval_policy=ApprovalPolicy.standard,
        )
        db_session.add(standard_project)
        await db_session.flush()
        
        # Plan and deployment should require approval
        assert approval_service.should_request_approval(
            ApprovalPolicy.standard,
            ApprovalType.plan,
        )
        assert approval_service.should_request_approval(
            ApprovalPolicy.standard,
            ApprovalType.deployment,
        )
        # Components should not
        assert not approval_service.should_request_approval(
            ApprovalPolicy.standard,
            ApprovalType.component,
        )
        
        # Test strict mode
        strict_project = Project(
            name="Strict Project",
            requirements="Test strict mode",
            approval_policy=ApprovalPolicy.strict,
        )
        db_session.add(strict_project)
        await db_session.flush()
        
        # All approval types should be required
        assert approval_service.should_request_approval(
            ApprovalPolicy.strict,
            ApprovalType.plan,
        )
        assert approval_service.should_request_approval(
            ApprovalPolicy.strict,
            ApprovalType.component,
        )
        assert approval_service.should_request_approval(
            ApprovalPolicy.strict,
            ApprovalType.deployment,
        )
