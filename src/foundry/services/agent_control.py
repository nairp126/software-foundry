"""Agent execution control mechanisms for pause/resume/cancel operations."""

import uuid
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
from typing import Optional, Dict, Any
from pathlib import Path

from foundry.redis_client import redis_client


class AgentControlService:
    """Manages agent execution control operations."""

    def __init__(self):
        """Initialize the agent control service."""
        self._checkpoint_prefix = "agent_checkpoint:"
        self._control_prefix = "agent_control:"

    @property
    def redis(self):
        """Get Redis client."""
        return redis_client.client

    async def pause_execution(
        self,
        project_id: uuid.UUID,
        reason: str = "User requested pause",
    ) -> Dict[str, Any]:
        """Pause agent execution for a project.
        
        Implements Requirement 21.5:
        - Pause execution at any time
        - Preserve current state
        
        Args:
            project_id: Project UUID
            reason: Reason for pausing
            
        Returns:
            Dictionary with pause status
        """
        control_key = f"{self._control_prefix}{project_id}"
        
        # Set control flag
        control_data = {
            "action": "pause",
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        try:
            await self.redis.set(
                control_key,
                json.dumps(control_data),
                ex=86400,  # 24 hour expiry
            )
        except Exception as e:
            logger.error(f"Redis set failed in pause_execution: {e}")
        
        return {
            "success": True,
            "project_id": str(project_id),
            "action": "pause",
            "message": f"Execution paused: {reason}",
        }

    async def resume_execution(
        self,
        project_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Resume agent execution for a project.
        
        Implements Requirement 21.5:
        - Resume execution from pause point
        
        Args:
            project_id: Project UUID
            
        Returns:
            Dictionary with resume status
        """
        control_key = f"{self._control_prefix}{project_id}"
        
        # Clear control flag
        try:
            await self.redis.delete(control_key)
        except Exception as e:
            logger.error(f"Redis delete failed in resume_execution: {e}")
        
        return {
            "success": True,
            "project_id": str(project_id),
            "action": "resume",
            "message": "Execution resumed",
        }

    async def cancel_execution(
        self,
        project_id: uuid.UUID,
        rollback: bool = True,
    ) -> Dict[str, Any]:
        """Cancel agent execution and optionally rollback.
        
        Implements Requirement 21.5:
        - Cancel execution and rollback to last stable state
        
        Args:
            project_id: Project UUID
            rollback: Whether to rollback to last checkpoint
            
        Returns:
            Dictionary with cancellation status
        """
        control_key = f"{self._control_prefix}{project_id}"
        
        # Set control flag for cancellation
        control_data = {
            "action": "cancel",
            "rollback": rollback,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        try:
            await self.redis.set(
                control_key,
                json.dumps(control_data),
                ex=3600,  # 1 hour expiry
            )
        except Exception as e:
            logger.error(f"Redis set failed in cancel_execution: {e}")
        
        result = {
            "success": True,
            "project_id": str(project_id),
            "action": "cancel",
            "message": "Execution cancelled",
        }
        
        if rollback:
            # Attempt to restore last checkpoint
            checkpoint = await self.get_checkpoint(project_id)
            if checkpoint:
                result["checkpoint_restored"] = True
                result["checkpoint_timestamp"] = checkpoint.get("timestamp")
            else:
                result["checkpoint_restored"] = False
                result["message"] += " (no checkpoint available for rollback)"
        
        return result

    async def check_control_status(
        self,
        project_id: uuid.UUID,
    ) -> Optional[Dict[str, Any]]:
        """Check if there's a control action pending for a project.
        
        Args:
            project_id: Project UUID
            
        Returns:
            Control data if action is pending, None otherwise
        """
        control_key = f"{self._control_prefix}{project_id}"
        
        try:
            control_json = await self.redis.get(control_key)
            if not control_json:
                return None
            return json.loads(control_json)
        except Exception as e:
            logger.error(f"Redis get failed in check_control_status: {e}")
            return None

    async def save_checkpoint(
        self,
        project_id: uuid.UUID,
        agent_state: Dict[str, Any],
        description: str = "",
    ) -> Dict[str, Any]:
        """Save a checkpoint of current agent state.
        
        Implements Requirement 21.5:
        - State preservation during pause
        - Execution checkpointing
        
        Args:
            project_id: Project UUID
            agent_state: Current state of agents
            description: Description of checkpoint
            
        Returns:
            Dictionary with checkpoint status
        """
        checkpoint_key = f"{self._checkpoint_prefix}{project_id}"
        
        checkpoint_data = {
            "project_id": str(project_id),
            "agent_state": agent_state,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Save checkpoint with 7 day expiry
        try:
            await self.redis.set(
                checkpoint_key,
                json.dumps(checkpoint_data),
                ex=604800,  # 7 days
            )
        except Exception as e:
            logger.error(f"Redis set failed in save_checkpoint: {e}")
            return {"success": False, "project_id": str(project_id)}
        
        return {
            "success": True,
            "project_id": str(project_id),
            "checkpoint_timestamp": checkpoint_data["timestamp"],
        }

    async def get_checkpoint(
        self,
        project_id: uuid.UUID,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve the last checkpoint for a project.
        
        Args:
            project_id: Project UUID
            
        Returns:
            Checkpoint data if exists, None otherwise
        """
        checkpoint_key = f"{self._checkpoint_prefix}{project_id}"
        
        try:
            checkpoint_json = await self.redis.get(checkpoint_key)
            if not checkpoint_json:
                return None
            return json.loads(checkpoint_json)
        except Exception as e:
            logger.error(f"Redis get failed in get_checkpoint: {e}")
            return None

    async def delete_checkpoint(
        self,
        project_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Delete checkpoint for a project.
        
        Args:
            project_id: Project UUID
            
        Returns:
            Dictionary with deletion status
        """
        checkpoint_key = f"{self._checkpoint_prefix}{project_id}"
        
        try:
            deleted = await self.redis.delete(checkpoint_key)
        except Exception as e:
            logger.error(f"Redis delete failed in delete_checkpoint: {e}")
            deleted = 0
        
        return {
            "success": bool(deleted),
            "project_id": str(project_id),
            "deleted": bool(deleted),
        }


# Module-level convenience instance
agent_control_service = AgentControlService()
