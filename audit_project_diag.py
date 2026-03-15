
import asyncio
from sqlalchemy import select
from foundry.database import AsyncSessionLocal
from foundry.models.project import Project
from foundry.models.artifact import Artifact
import json

async def audit_project(project_id):
    async with AsyncSessionLocal() as session:
        # Get project info
        stmt = select(Project).where(Project.id == project_id)
        result = await session.execute(stmt)
        project = result.scalar_one_or_none()
        
        if not project:
            print(f"Project {project_id} not found.")
            return

        print(f"--- Project Audit: {project_id} ---")
        print(f"Name: {project.name}")
        print(f"Original Requirements: {project.requirements}")
        print(f"Final Status: {project.status}")
        print("\n--- PRD (Product Manager Output) ---")
        print(json.dumps(project.prd, indent=2) if project.prd else "No PRD in DB")
        
        print("\n--- Architecture (Architect Output) ---")
        print(json.dumps(project.architecture, indent=2) if project.architecture else "No Architecture in DB")

        # Get all artifacts
        stmt = select(Artifact).where(Artifact.project_id == project_id)
        result = await session.execute(stmt)
        artifacts = result.scalars().all()
        
        print("\n--- Artifacts Recorded ---")
        for art in artifacts:
            print(f"- {art.filename} ({art.artifact_type})")
            if art.filename == "architecture.md":
                print(f"\n[FULL ARCHITECTURE CONTENT]:\n{art.content}\n")

        print("\n--- Code Review Feedbacks ---")
        # Check if code review artifact exists
        for art in artifacts:
            if art.filename == "code_review.json":
                print(art.content)

if __name__ == "__main__":
    import sys
    pid = "c3c53472-9d5a-4fb1-ad03-920ce9c5eba0"
    if len(sys.argv) > 1:
        pid = sys.argv[1]
    asyncio.run(audit_project(pid))
