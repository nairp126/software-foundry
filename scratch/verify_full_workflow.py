import asyncio
import os
import uuid
import logging
import sys

# Add src to path
sys.path.append(os.path.abspath("src"))

from foundry.orchestrator import AgentOrchestrator
from foundry.database import init_db, AsyncSessionLocal
from foundry.models.project import Project, ProjectStatus
from foundry.models.approval import ApprovalRequest, ApprovalStatus
from foundry.config import settings
from sqlalchemy import select

# Configure logging to see the "Graph-First" and "Surgical Context" messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Force engineering and KG logs to DEBUG to see retrieval details
logging.getLogger("foundry.agents.engineer").setLevel(logging.DEBUG)
logging.getLogger("foundry.services.knowledge_graph").setLevel(logging.DEBUG)

async def automate_approval(project_id: str):
    """Automatically approve any pending architecture gate."""
    while True:
        async with AsyncSessionLocal() as session:
            # Check for pending approval requests
            res = await session.execute(
                select(Project).where(Project.id == project_id)
            )
            project = res.scalar_one_or_none()
            
            if project and project.status == ProjectStatus.paused:
                print(f"DEBUG: Found paused project {project_id}. Approving architecture...")
                # Find the pending approval request
                res_app = await session.execute(
                    select(ApprovalRequest)
                    .where(ApprovalRequest.project_id == project_id)
                    .where(ApprovalRequest.status == ApprovalStatus.pending)
                )
                approval = res_app.scalar_one_or_none()
                if approval:
                    approval.status = ApprovalStatus.approved
                    approval.reviewer_comment = "Automated approval for E2E verification."
                    await session.commit()
                    print("DEBUG: Architecture approved.")
                    return True
            
            if project and project.status in (ProjectStatus.completed, ProjectStatus.failed):
                return False
                
        await asyncio.sleep(2)

async def run_verification():
    print("Starting E2E Verification: Gym Management API")
    
    # Connect to Redis
    from foundry.redis_client import redis_client
    await redis_client.connect()
    print(f"Redis connected: {redis_client.is_connected}")
    
    await init_db()
    
    project_id = str(uuid.uuid4())
    requirements = """
    Create a Gym Management System.
    1. src/models.py: Define User (id, name, email) and Membership (id, user_id, type).
    2. src/schemas.py: Pydantic schemas for the above models.
    3. src/main.py: FastAPI app with endpoints to register a user and assign a membership.
    Ensure strict separation of concerns and valid Python package structure.
    """
    
    # Create the project record
    async with AsyncSessionLocal() as session:
        project = Project(
            id=project_id,
            name="Gym Management API",
            description="E2E Verification Project",
            requirements=requirements,
            status=ProjectStatus.created,
            language="python"
        )
        session.add(project)
        await session.commit()
    
    orchestrator = AgentOrchestrator()
    
    # Run loop to handle pauses
    current_node = None
    while True:
        print(f"DEBUG: Starting/Resuming orchestrator from {current_node or 'START'}")
        # orchestrator.run returns True if it finished (reached END or PAUSED)
        success = await orchestrator.run(
            project_id=project_id,
            initial_prompt=requirements,
            resume_from=current_node
        )
        
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(Project).where(Project.id == project_id))
            project = res.scalar_one_or_none()
            if not project:
                print("ERROR: Project record disappeared.")
                break
                
            print(f"DEBUG: Pipeline yield. Current Status: {project.status}")
            
            if project.status == ProjectStatus.completed:
                print("SUCCESS: Pipeline completed.")
                break
            elif project.status == ProjectStatus.failed:
                print("FAILURE: Pipeline failed.")
                break
            elif project.status == ProjectStatus.paused:
                # Automate approval and then resume
                await automate_approval(project_id)
                current_node = "engineer" # Resume from engineer node
            else:
                # Something else happened?
                print(f"DEBUG: Unexpected status {project.status}. Stopping.")
                break

if __name__ == "__main__":
    asyncio.run(run_verification())
