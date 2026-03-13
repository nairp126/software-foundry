"""Demo of project lifecycle management functionality."""

import asyncio
from foundry.database import AsyncSessionLocal
from foundry.services.project_service import project_service


async def demo_project_lifecycle():
    """Demonstrate project lifecycle operations."""
    
    print("=== Project Lifecycle Management Demo ===\n")
    
    async with AsyncSessionLocal() as session:
        # 1. Create a new project
        print("1. Creating a new project...")
        project = await project_service.create_project(
            session=session,
            name="E-Commerce Platform",
            requirements="Build a full-stack e-commerce platform with user authentication, product catalog, shopping cart, and payment integration",
            description="Modern e-commerce solution with React frontend and FastAPI backend"
        )
        await session.commit()
        
        print(f"   ✓ Project created with ID: {project.id}")
        print(f"   ✓ Project directory: {project.generated_path}")
        print(f"   ✓ Status: {project.status.value}\n")
        
        # 2. Get project details
        print("2. Retrieving project details...")
        retrieved_project = await project_service.get_project(
            session=session,
            project_id=project.id
        )
        print(f"   ✓ Retrieved project: {retrieved_project.name}")
        print(f"   ✓ Created at: {retrieved_project.created_at}\n")
        
        # 3. List all projects
        print("3. Listing all projects...")
        projects = await project_service.list_projects(session=session)
        print(f"   ✓ Total projects: {len(projects)}")
        for proj in projects:
            print(f"     - {proj['name']} ({proj['status']})")
            print(f"       Disk usage: {proj['resource_usage']['disk_space_mb']} MB")
            print(f"       Estimated cost: ${proj['estimated_monthly_cost']}/month")
        print()
        
        # 4. Create another project
        print("4. Creating another project...")
        project2 = await project_service.create_project(
            session=session,
            name="Task Management App",
            requirements="Build a task management application with kanban boards",
        )
        await session.commit()
        print(f"   ✓ Second project created with ID: {project2.id}\n")
        
        # 5. List projects filtered by status
        print("5. Listing projects by status...")
        from foundry.models.project import ProjectStatus
        created_projects = await project_service.list_projects(
            session=session,
            status=ProjectStatus.created
        )
        print(f"   ✓ Projects with 'created' status: {len(created_projects)}\n")
        
        # 6. Delete a project (with confirmation)
        print("6. Deleting a project...")
        result = await project_service.delete_project(
            session=session,
            project_id=project2.id,
            confirmed=True
        )
        await session.commit()
        
        if result["success"]:
            print(f"   ✓ Project deleted successfully")
            print(f"   ✓ Steps completed: {', '.join(result['steps_completed'])}")
        else:
            print(f"   ✗ Deletion failed: {result['message']}")
        
        if result.get("errors"):
            print(f"   ⚠ Errors encountered: {result['errors']}")
        print()
        
        # 7. Verify deletion
        print("7. Verifying deletion...")
        deleted_project = await project_service.get_project(
            session=session,
            project_id=project2.id
        )
        if deleted_project is None:
            print("   ✓ Project successfully removed from database\n")
        else:
            print("   ✗ Project still exists in database\n")
        
        # 8. Final project list
        print("8. Final project list...")
        final_projects = await project_service.list_projects(session=session)
        print(f"   ✓ Remaining projects: {len(final_projects)}")
        for proj in final_projects:
            print(f"     - {proj['name']} (ID: {proj['id']})")
        print()
        
        print("=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(demo_project_lifecycle())
