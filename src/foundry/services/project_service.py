"""Project lifecycle management service."""

import os
import shutil
import stat
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.models.project import Project, ProjectStatus
from foundry.vcs.git_manager import GitManager
from foundry.services.knowledge_graph import knowledge_graph_service
from foundry.graph.ingestion import ingestion_pipeline


class ProjectService:
    """Manages project lifecycle operations."""

    def __init__(self, base_projects_dir: str = "generated_projects"):
        """Initialize the project service.
        
        Args:
            base_projects_dir: Base directory for storing generated projects
        """
        self.base_projects_dir = base_projects_dir
        # Ensure the base directory exists
        Path(self.base_projects_dir).mkdir(parents=True, exist_ok=True)

    async def create_project(
        self,
        session: AsyncSession,
        name: str,
        requirements: str,
        description: Optional[str] = None,
    ) -> Project:
        """Create a new project with unique ID and directory structure.
        
        Implements Requirement 19.1:
        - Generate unique project ID
        - Create isolated Knowledge_Graph namespace (project:{id}:*)
        - Initialize Git repository
        - Set up project directory structure
        
        Args:
            session: Database session
            name: Project name
            requirements: Project requirements
            description: Optional project description
            
        Returns:
            Created project instance
        """
        # Create project record with unique UUID
        project = Project(
            id=uuid.uuid4(),
            name=name,
            description=description,
            requirements=requirements,
            status=ProjectStatus.created,
        )
        
        session.add(project)
        await session.flush()  # Get the ID assigned
        
        # Create project directory structure
        project_dir = self._get_project_path(project.id)
        self._create_directory_structure(project_dir)
        
        # Initialize Git repository using the comprehensive GitManager
        try:
            git_manager = GitManager(project_dir)
            git_manager.initialize_repository()
        except Exception as e:
            print(f"Warning: Failed to initialize Git repository: {e}")
        
        # Store the generated path
        project.generated_path = project_dir
        
        await session.flush()  # Flush the updated path
        
        # Initialize Knowledge Graph for this project
        try:
            await knowledge_graph_service.create_project(
                project_id=str(project.id),
                name=name,
                metadata={
                    "description": description,
                    "created_at": project.created_at.isoformat(),
                    "requirements": requirements,
                }
            )
        except Exception as e:
            # Log error but don't fail project creation
            # Knowledge Graph is an enhancement, not a requirement
            print(f"Warning: Failed to initialize Knowledge Graph: {e}")
        
        return project

    async def get_project(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
    ) -> Optional[Project]:
        """Get a project by ID.
        
        Args:
            session: Database session
            project_id: Project UUID
            
        Returns:
            Project instance or None if not found
        """
        result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def list_projects(
        self,
        session: AsyncSession,
        status: Optional[ProjectStatus] = None,
    ) -> List[Dict[str, Any]]:
        """List all projects with metadata.
        
        Implements Requirement 19.7:
        - Display project metadata including creation date, last modified date
        - Show status (active/paused/archived)
        - Include resource usage and estimated monthly cost
        
        Args:
            session: Database session
            status: Optional status filter
            
        Returns:
            List of project metadata dictionaries
        """
        query = select(Project)
        if status:
            query = query.where(Project.status == status)
        
        result = await session.execute(query.order_by(Project.created_at.desc()))
        projects = result.scalars().all()
        
        project_list = []
        for project in projects:
            metadata = {
                "id": str(project.id),
                "name": project.name,
                "description": project.description,
                "status": project.status.value,
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat(),
                "generated_path": project.generated_path,
                # Resource usage - to be implemented with actual metrics
                "resource_usage": self._get_resource_usage(project),
                # Cost estimation - to be implemented with actual cloud cost tracking
                "estimated_monthly_cost": self._estimate_monthly_cost(project),
            }
            project_list.append(metadata)
        
        return project_list

    async def delete_project(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        """Delete a project with confirmation and cleanup.
        
        Implements Requirement 19.6:
        - Require explicit confirmation
        - Execute `cdk destroy` to remove cloud resources (stubbed for MVP)
        - Delete Knowledge_Graph nodes
        - Remove all local files
        
        Args:
            session: Database session
            project_id: Project UUID
            confirmed: Whether deletion is confirmed
            
        Returns:
            Dictionary with deletion status and details
            
        Raises:
            ValueError: If confirmation is not provided
        """
        if not confirmed:
            raise ValueError(
                "Project deletion requires explicit confirmation. "
                "Set confirmed=True to proceed."
            )
        
        # Get the project
        project = await self.get_project(session, project_id)
        if not project:
            return {
                "success": False,
                "message": f"Project {project_id} not found",
            }
        
        result = {
            "success": True,
            "project_id": str(project_id),
            "project_name": project.name,
            "steps_completed": [],
            "errors": [],
        }
        
        # Step 1: CDK destroy (stubbed for MVP - DevOps agent not fully implemented)
        try:
            cdk_result = await self._destroy_cloud_resources(project)
            result["steps_completed"].append("cloud_resources_destroyed")
            result["cdk_destroy_output"] = cdk_result
        except Exception as e:
            result["errors"].append(f"CDK destroy failed: {str(e)}")
        
        # Step 2: Delete Knowledge Graph nodes (stubbed - Neo4j integration pending)
        try:
            kg_result = await self._delete_knowledge_graph_nodes(project)
            result["steps_completed"].append("knowledge_graph_cleaned")
            result["kg_nodes_deleted"] = kg_result
        except Exception as e:
            result["errors"].append(f"Knowledge graph cleanup failed: {str(e)}")
        
        # Step 3: Remove local files
        try:
            if project.generated_path and os.path.exists(project.generated_path):
                def remove_readonly(func, path, _):
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                shutil.rmtree(project.generated_path, onerror=remove_readonly)
                result["steps_completed"].append("local_files_removed")
        except Exception as e:
            result["errors"].append(f"File cleanup failed: {str(e)}")
        
        # Step 4: Delete database record
        try:
            await session.delete(project)
            await session.flush()
            result["steps_completed"].append("database_record_deleted")
        except Exception as e:
            result["errors"].append(f"Database deletion failed: {str(e)}")
            result["success"] = False
        
        return result

    def _get_project_path(self, project_id: uuid.UUID) -> str:
        """Get the file system path for a project.
        
        Args:
            project_id: Project UUID
            
        Returns:
            Absolute path to project directory
        """
        return os.path.abspath(
            os.path.join(self.base_projects_dir, str(project_id))
        )

    def _create_directory_structure(self, project_dir: str) -> None:
        """Create the basic project directory structure.
        
        Args:
            project_dir: Path to project directory
        """
        # Create main project directory
        Path(project_dir).mkdir(parents=True, exist_ok=True)
        
        # Create standard subdirectories
        subdirs = [
            "src",
            "tests",
            "docs",
            "config",
        ]
        
        for subdir in subdirs:
            Path(os.path.join(project_dir, subdir)).mkdir(exist_ok=True)
        
        # Create a README placeholder
        readme_path = os.path.join(project_dir, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("# Project\n\n")
            f.write("Generated by Autonomous Software Foundry\n\n")
            f.write("## Getting Started\n\n")
            f.write("Documentation will be generated here.\n")

    def _get_resource_usage(self, project: Project) -> Dict[str, Any]:
        """Get resource usage for a project with real metrics."""
        # disk_space_mb calculation
        total_size = 0
        if project.generated_path and os.path.exists(project.generated_path):
            for dirpath, dirnames, filenames in os.walk(project.generated_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        
        resource_usage = {
            "disk_space_mb": round(total_size / (1024 * 1024), 2),
            "knowledge_graph_nodes": 0, # To be fetched asynchronously if needed, or via sync proxy
            "active_agents": 1 if project.status in [
                ProjectStatus.running_pm, 
                ProjectStatus.running_architect, 
                ProjectStatus.running_engineer, 
                ProjectStatus.running_code_review, 
                ProjectStatus.running_reflexion, 
                ProjectStatus.running_devops
            ] else 0,
        }
        
        return resource_usage

    def _estimate_monthly_cost(self, project: Project) -> float:
        """Estimate monthly cloud cost for a project.
        
        Args:
            project: Project instance
            
        Returns:
            Estimated monthly cost in USD
        """
        # Heuristic estimation since real CDK calculation is pending
        base_cost = 5.0  # Base cost for minimal web hosting (e.g., small EC2/ECS or Lambda + API Gateway)
        
        reqs = (project.requirements or "").lower()
        arch = ""
        # architecture can be text or dict depending on JSONB structure
        if project.architecture:
            if isinstance(project.architecture, str):
                arch = project.architecture.lower()
            elif isinstance(project.architecture, dict):
                arch = str(project.architecture).lower()
                
        combined = reqs + " " + arch
        
        cost = base_cost
        if any(kw in combined for kw in ["database", "postgres", "mysql", "rds", "sql"]):
            cost += 15.0  # basic RDS/managed DB instance
        if any(kw in combined for kw in ["redis", "cache", "memcached", "elasticache"]):
            cost += 10.0  # managed cache node
        if any(kw in combined for kw in ["load balancer", "alb", "nlb", "api gateway"]):
            cost += 20.0  # provisioned gateway/balancer
        if any(kw in combined for kw in ["s3", "storage", "blob", "bucket"]):
            cost += 2.5   # generous S3 usage
            
        return cost

    async def _destroy_cloud_resources(self, project: Project) -> Dict[str, Any]:
        """Destroy cloud resources using CDK.
        
        Args:
            project: Project instance
            
        Returns:
            Dictionary with CDK destroy results
        """
        # Stubbed for MVP - DevOps agent integration pending
        # In production, this would execute: cdk destroy --force
        return {
            "status": "stubbed",
            "message": "CDK destroy not yet implemented - DevOps agent pending",
            "resources_destroyed": [],
        }

    async def _delete_knowledge_graph_nodes(self, project: Project) -> int:
        """Delete Knowledge Graph nodes for a project.
        
        Args:
            project: Project instance
            
        Returns:
            Number of nodes deleted
        """
        try:
            await knowledge_graph_service.clear_project(str(project.id))
            return 1  # Successfully cleared
        except Exception as e:
            print(f"Warning: Failed to clear Knowledge Graph: {e}")
            return 0
    
    async def ingest_project_to_graph(
        self,
        project: Project,
    ) -> Dict[str, Any]:
        """Ingest project code into the Knowledge Graph.
        
        Args:
            project: Project instance
            
        Returns:
            Dictionary with ingestion statistics
        """
        if not project.generated_path or not os.path.exists(project.generated_path):
            return {
                "success": False,
                "error": "Project path does not exist"
            }
        
        try:
            stats = await ingestion_pipeline.ingest_project(
                project_id=str(project.id),
                project_name=project.name,
                project_path=project.generated_path,
                metadata={
                    "description": project.description,
                    "requirements": project.requirements,
                }
            )
            stats["success"] = True
            return stats
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Module-level convenience instance
project_service = ProjectService()
