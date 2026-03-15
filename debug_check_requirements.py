import asyncio
from sqlalchemy import select
from foundry.database import AsyncSessionLocal
from foundry.models.project import Project
import sys

async def check(project_id):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            print(f"Name: {project.name}")
            print(f"Requirements: {project.requirements}")
        else:
            print("Project Not Found")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(check(sys.argv[1]))
    else:
        print("Usage: python debug_check_requirements.py <project_id>")
