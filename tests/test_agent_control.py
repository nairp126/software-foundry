"""Unit tests for agent control service."""

import pytest
import uuid
import json
from datetime import datetime

from foundry.services.agent_control import agent_control_service


class TestAgentControlService:
    """Test agent control service functionality."""

    @pytest.mark.asyncio
    async def test_pause_execution(self, redis_client):
        """Test pausing agent execution."""
        project_id = uuid.uuid4()
        
        result = await agent_control_service.pause_execution(
            project_id,
            reason="Testing pause",
        )
        
        assert result["success"] is True
        assert result["action"] == "pause"
        assert "paused" in result["message"].lower()
        
        # Verify control status
        status = await agent_control_service.check_control_status(project_id)
        assert status is not None
        assert status["action"] == "pause"
        assert status["reason"] == "Testing pause"

    @pytest.mark.asyncio
    async def test_resume_execution(self, redis_client):
        """Test resuming agent execution."""
        project_id = uuid.uuid4()
        
        # First pause
        await agent_control_service.pause_execution(project_id)
        
        # Then resume
        result = await agent_control_service.resume_execution(project_id)
        
        assert result["success"] is True
        assert result["action"] == "resume"
        
        # Verify control status cleared
        status = await agent_control_service.check_control_status(project_id)
        assert status is None

    @pytest.mark.asyncio
    async def test_cancel_execution(self, redis_client):
        """Test cancelling agent execution."""
        project_id = uuid.uuid4()
        
        result = await agent_control_service.cancel_execution(
            project_id,
            rollback=False,
        )
        
        assert result["success"] is True
        assert result["action"] == "cancel"
        
        # Verify control status
        status = await agent_control_service.check_control_status(project_id)
        assert status is not None
        assert status["action"] == "cancel"
        assert status["rollback"] is False

    @pytest.mark.asyncio
    async def test_cancel_with_rollback(self, redis_client):
        """Test cancelling with rollback when checkpoint exists."""
        project_id = uuid.uuid4()
        
        # Save a checkpoint first
        agent_state = {
            "current_agent": "engineer",
            "progress": 50,
        }
        await agent_control_service.save_checkpoint(
            project_id,
            agent_state,
            description="Mid-execution checkpoint",
        )
        
        # Cancel with rollback
        result = await agent_control_service.cancel_execution(
            project_id,
            rollback=True,
        )
        
        assert result["success"] is True
        assert result["checkpoint_restored"] is True

    @pytest.mark.asyncio
    async def test_save_and_get_checkpoint(self, redis_client):
        """Test saving and retrieving checkpoints."""
        project_id = uuid.uuid4()
        
        agent_state = {
            "current_agent": "architect",
            "completed_steps": ["requirements", "design"],
            "next_step": "code_generation",
        }
        
        # Save checkpoint
        save_result = await agent_control_service.save_checkpoint(
            project_id,
            agent_state,
            description="Architecture complete",
        )
        
        assert save_result["success"] is True
        
        # Retrieve checkpoint
        checkpoint = await agent_control_service.get_checkpoint(project_id)
        
        assert checkpoint is not None
        assert checkpoint["agent_state"]["current_agent"] == "architect"
        assert checkpoint["description"] == "Architecture complete"
        assert "timestamp" in checkpoint

    @pytest.mark.asyncio
    async def test_delete_checkpoint(self, redis_client):
        """Test deleting a checkpoint."""
        project_id = uuid.uuid4()
        
        # Save checkpoint
        agent_state = {"test": "data"}
        await agent_control_service.save_checkpoint(project_id, agent_state)
        
        # Delete checkpoint
        result = await agent_control_service.delete_checkpoint(project_id)
        
        assert result["success"] is True
        assert result["deleted"] is True
        
        # Verify checkpoint is gone
        checkpoint = await agent_control_service.get_checkpoint(project_id)
        assert checkpoint is None

    @pytest.mark.asyncio
    async def test_check_control_status_no_action(self, redis_client):
        """Test checking control status when no action is pending."""
        project_id = uuid.uuid4()
        
        status = await agent_control_service.check_control_status(project_id)
        
        assert status is None
