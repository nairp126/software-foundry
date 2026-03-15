"""Celery tasks for approval workflow background processing."""

from celery import shared_task
from foundry.celery_app import app
from foundry.database import AsyncSessionLocal
from foundry.services.approval_service import approval_service


@app.task(name="foundry.tasks.process_expired_approvals")
def process_expired_approvals_task():
    """Background task to process expired approval requests.
    
    This task should be scheduled to run periodically (e.g., every 5 minutes)
    to auto-cancel approval requests that have exceeded their timeout.
    
    Implements Requirement 21.9:
    - Auto-cancel pending approvals after timeout
    """
    import asyncio
    
    async def _process():
        async with AsyncSessionLocal() as session:
            result = await approval_service.process_expired_approvals(session)
            await session.commit()
            return result
    
    # Run the async function
    result = asyncio.run(_process())
    
    return {
        "task": "process_expired_approvals",
        "expired_count": result.get("expired_count", 0),
        "approval_ids": result.get("approval_ids", []),
    }
