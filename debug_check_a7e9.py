import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

from sqlalchemy import select
from foundry.database import AsyncSessionLocal
from foundry.models.project import Project

async def check():
    async with AsyncSessionLocal() as s:
        p = await s.get(Project, "a7e927ef-3ba0-43a0-a947-ed9c6b953260")
        if p:
            print(f"DB NAME: {p.name}")
            print(f"DB REQS: {p.requirements}")
        else:
            print("Project NOT FOUND in DB.")

if __name__ == "__main__":
    asyncio.run(check())
