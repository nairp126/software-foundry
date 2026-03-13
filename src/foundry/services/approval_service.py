"""Approval workflow service for human-in-the-loop controls."""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import select, and_
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


class ApprovalService:
    """Manages approval workflow operations."""

    async def create_approval_request(
        self,
        session: AsyncSession,
        request_data: ApprovalRequestCreate,
    ) -> ApprovalRequest:
        """Create a new approval request.
        
        Implements Requirements 21.1, 21.2:
        - Create approval request with type, content, cost estimates
        - Set timeout for auto-cancellation
        
        Args:
            session: Database session
            request_data: Approval request creation data
            
        Returns:
            Created approval request
        """
        # Calculate timeout
        timeout_at = None
        if request_data.timeout_minutes:
            timeout_at = datetime.utcnow() + timedelta(minutes=request_data.timeout_minutes)
        
        # Create approval request
        approval = ApprovalRequest(
            project_id=uuid.UUID(request_data.project_id),
            request_type=request_data.request_type,
            status=ApprovalStatus.pending,
            content=request_data.content.model_dump(),
            estimated_cost=request_data.estimated_cost,
            timeout_at=timeout_at,
        )
        
        session.add(approval)
        await session.flush()
        
        return approval

    async def get_approval_request(
        self,
        session: AsyncSession,
        approval_id: uuid.UUID,
    ) -> Optional[ApprovalRequest]:
        """Get an approval request by ID.
        
        Args:
            session: Database session
            approval_id: Approval request UUID
            
        Returns:
            Approval request or None if not found
        """
        result = await session.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
        )
        return result.scalar_one_or_none()

    async def list_pending_approvals(
        self,
        session: AsyncSession,
        project_id: Optional[uuid.UUID] = None,
    ) -> List[ApprovalRequest]:
        """List all pending approval requests.
        
        Args:
            session: Database session
            project_id: Optional project filter
            
        Returns:
            List of pending approval requests
        """
        query = select(ApprovalRequest).where(
            ApprovalRequest.status == ApprovalStatus.pending
        )
        
        if project_id:
            query = query.where(ApprovalRequest.project_id == project_id)
        
        result = await session.execute(query.order_by(ApprovalRequest.created_at))
        return list(result.scalars().all())

    async def respond_to_approval(
        self,
        session: AsyncSession,
        approval_id: uuid.UUID,
        response: ApprovalResponse,
    ) -> Dict[str, Any]:
        """Respond to an approval request.
        
        Implements Requirements 21.3, 21.4:
        - Handle user review options (approve, edit, reject, approve_with_changes)
        - Update approval state based on decision
        
        Args:
            session: Database session
            approval_id: Approval request UUID
            response: User response
            
        Returns:
            Dictionary with response status and details
        """
        approval = await self.get_approval_request(session, approval_id)
        
        if not approval:
            return {
                "success": False,
                "message": f"Approval request {approval_id} not found",
            }
        
        if not approval.can_respond():
            return {
                "success": False,
                "message": f"Approval request cannot be responded to (status: {approval.status.value})",
            }
        
        # Map decision to status
        decision_map = {
            "approve": ApprovalStatus.approved,
            "reject": ApprovalStatus.rejected,
            "approve_with_changes": ApprovalStatus.approved,
        }
        
        new_status = decision_map.get(response.decision)
        
        if not new_status:
            return {
                "success": False,
                "message": f"Invalid decision: {response.decision}",
            }
        
        # Update approval
        approval.status = new_status
        approval.responded_at = datetime.utcnow()
        approval.response = response.model_dump()
        
        await session.flush()
        
        return {
            "success": True,
            "approval_id": str(approval_id),
            "status": new_status.value,
            "decision": response.decision,
        }

    async def cancel_approval(
        self,
        session: AsyncSession,
        approval_id: uuid.UUID,
        reason: str = "User cancelled",
    ) -> Dict[str, Any]:
        """Cancel a pending approval request.
        
        Args:
            session: Database session
            approval_id: Approval request UUID
            reason: Cancellation reason
            
        Returns:
            Dictionary with cancellation status
        """
        approval = await self.get_approval_request(session, approval_id)
        
        if not approval:
            return {
                "success": False,
                "message": f"Approval request {approval_id} not found",
            }
        
        if approval.status != ApprovalStatus.pending:
            return {
                "success": False,
                "message": f"Cannot cancel approval in status: {approval.status.value}",
            }
        
        approval.status = ApprovalStatus.cancelled
        approval.responded_at = datetime.utcnow()
        approval.response = {"decision": "cancelled", "reason": reason}
        
        await session.flush()
        
        return {
            "success": True,
            "approval_id": str(approval_id),
            "status": ApprovalStatus.cancelled.value,
        }

    async def process_expired_approvals(
        self,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """Process expired approval requests and auto-cancel them.
        
        Implements Requirement 21.9:
        - Auto-cancel pending approvals after timeout
        
        Returns:
            Dictionary with processing results
        """
        # Find expired pending approvals
        result = await session.execute(
            select(ApprovalRequest).where(
                and_(
                    ApprovalRequest.status == ApprovalStatus.pending,
                    ApprovalRequest.timeout_at.isnot(None),
                    ApprovalRequest.timeout_at <= datetime.utcnow(),
                )
            )
        )
        expired_approvals = list(result.scalars().all())
        
        cancelled_count = 0
        for approval in expired_approvals:
            approval.status = ApprovalStatus.timeout
            approval.responded_at = datetime.utcnow()
            approval.response = {
                "decision": "timeout",
                "reason": "Approval request timed out",
            }
            cancelled_count += 1
        
        await session.flush()
        
        return {
            "success": True,
            "expired_count": cancelled_count,
            "approval_ids": [str(a.id) for a in expired_approvals],
        }

    def should_request_approval(
        self,
        policy: ApprovalPolicy,
        approval_type: ApprovalType,
    ) -> bool:
        """Determine if approval is required based on policy.
        
        Implements Requirement 21.4:
        - Autonomous: No approvals
        - Standard: Plan + Deployment
        - Strict: Plan + Components + Deployment
        
        Args:
            policy: Approval policy
            approval_type: Type of approval being checked
            
        Returns:
            True if approval is required
        """
        if policy == ApprovalPolicy.autonomous:
            return False
        
        if policy == ApprovalPolicy.standard:
            return approval_type in [ApprovalType.plan, ApprovalType.deployment]
        
        if policy == ApprovalPolicy.strict:
            return approval_type in [
                ApprovalType.plan,
                ApprovalType.component,
                ApprovalType.deployment,
            ]
        
        return False


# Module-level convenience instance
approval_service = ApprovalService()
