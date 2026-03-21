from typing import TypedDict, Annotated, List, Union, Dict, Any, Optional
import json
import os
import uuid
import logging
import asyncio
import re
from datetime import datetime
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from sqlalchemy import select

from foundry.agents.base import AgentType, AgentMessage, MessageType
from foundry.agents import (
    ProductManagerAgent,
    ArchitectAgent,
    EngineerAgent,
    DevOpsAgent,
    CodeReviewAgent,
    ReflexionAgent
)
from foundry.database import AsyncSessionLocal
from foundry.models.project import Project, ProjectStatus
from foundry.models.artifact import Artifact, ArtifactType
from foundry.services.git_service import git_service
from foundry.services.knowledge_graph import KnowledgeGraphService
from foundry.graph.ingestion import ingestion_pipeline
from foundry.config import settings

logger = logging.getLogger(__name__)

# Maximum number of reflexion→engineer retry cycles before failing
MAX_REFLEXION_RETRIES = 3


class GraphState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    current_agent: str
    project_context: Dict[str, Any]
    review_feedback: Dict[str, Any]
    project_id: str  # UUID string for DB persistence
    reflexion_count: int  # tracks how many review→reflexion cycles have occurred
    success_flag: bool  # tracks if the code was successfully deployed
    language: str  # project language, e.g. "python", "javascript", "java"
    framework: str  # project framework, e.g. "fastapi", "express", "spring"


class AgentOrchestrator:
    """Manages the autonomous software development lifecycle using LangGraph."""
    # Fix 5: Master JS Detection Regex (Final Write-Time Gate)
    JS_PATTERNS = re.compile(
        r'\b(const |let |var |require\(|import React|express\(\)|module\.exports|'
        r'export default|npm install|\.then\(|\.catch\(|document\.|window\.|'
        r'addEventListener|async function\s+\w+\s*\(|=>\s*\{|\.jsx?["\'])',
        re.MULTILINE | re.IGNORECASE
    )

    def __init__(self, model_name: Optional[str] = None):
        self.pm_agent = ProductManagerAgent()
        self.architect_agent = ArchitectAgent()
        self.engineer_agent = EngineerAgent()
        self.devops_agent = DevOpsAgent()
        self.code_review_agent = CodeReviewAgent()
        self.reflexion_agent = ReflexionAgent()
        self.kg_service = KnowledgeGraphService()
        self._checkpointer = MemorySaver()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Construct the LangGraph workflow."""
        workflow = StateGraph(GraphState)

        # Define nodes
        workflow.add_node("product_manager", self._pm_node)
        workflow.add_node("architect", self._architect_node)
        workflow.add_node("engineer", self._engineer_node)
        workflow.add_node("code_review", self._code_review_node)
        workflow.add_node("reflexion", self._reflexion_node)
        workflow.add_node("devops", self._devops_node)

        # Define edges
        workflow.add_edge(START, "product_manager")
        workflow.add_edge("product_manager", "architect")
        workflow.add_edge("architect", "engineer")
        workflow.add_edge("engineer", "code_review")

        # Conditional path after code review
        workflow.add_conditional_edges(
            "code_review",
            self._should_continue_from_review,
            {
                "approve": "devops",
                "fix": "reflexion",
                "fail": END
            }
        )

        # From reflexion back to engineer for fixing
        workflow.add_edge("reflexion", "engineer")

        # End after devops
        workflow.add_edge("devops", END)

        return workflow.compile(checkpointer=self._checkpointer)

    async def _publish_status_update(self, project_id: str, status: ProjectStatus, message: str = ""):
        """Publish status update to Redis for real-time WebSocket broadcasting."""
        from foundry.redis_client import redis_client
        if redis_client.client:
            event_data = {
                "type": "status_update",
                "status": status.value,
                "project_id": project_id,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }
            channel = f"foundry:project:{project_id}"
            await redis_client.client.publish(channel, json.dumps(event_data))

    async def _pm_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for Product Manager agent."""
        project_id = state["project_id"]
        await self._update_project_status(project_id, ProjectStatus.running_pm)
        await self._publish_status_update(project_id, ProjectStatus.running_pm, "Starting requirements analysis...")
        
        # Get the latest message from the history if any
        user_prompt = state["messages"][-1].content if state["messages"] else ""
        logger.info(f"PM Node processing requirements: {user_prompt[:50]}...")
        
        message = AgentMessage(
            sender=AgentType.PRODUCT_MANAGER,
            recipient=AgentType.PRODUCT_MANAGER,
            message_type=MessageType.TASK,
            payload={
                "project_id": state["project_id"],
                "prompt": user_prompt,
                "requirements": user_prompt # Fix L: Direct Anchor
            }
        )
        
        response = await self.pm_agent.process_message(message)
        prd = response.payload.get("prd", "") if response else ""
        
        # Save PRD to project model
        await self._update_project_fields(state["project_id"], {"prd": prd})
        
        # Store PRD artifact
        if prd:
            await self._store_artifact(
                state["project_id"], 
                "prd.md", 
                prd, 
                ArtifactType.documentation,
                state.get("language", "python")
            )
            
        return {
            "messages": [AIMessage(content=f"PRD generated:\n{prd}")],
            "project_context": {
                **state["project_context"],
                "prd": prd,
                "requirements": state.get("requirements", "") or state["project_context"].get("requirements", "")
            },
            "language": state.get("language", "python")
        }

    async def _architect_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for Architect agent."""
        project_id = state["project_id"]
        await self._update_project_status(project_id, ProjectStatus.running_architect)
        await self._publish_status_update(project_id, ProjectStatus.running_architect, "Designing system architecture...")
        
        prd = state["project_context"].get("prd", "")
        requirements = state.get("requirements", "") # Fix L
        message = AgentMessage(
            sender=AgentType.PRODUCT_MANAGER,
            recipient=AgentType.ARCHITECT,
            message_type=MessageType.TASK,
            payload={
                "prd": prd,
                "requirements": requirements,
                "language": state.get("language", "python"),
                "framework": state.get("framework", ""),
                "project_id": state["project_id"],
            }
        )
        
        response = await self.architect_agent.process_message(message)
        architecture = response.payload.get("architecture", "") if response else ""
        
        # Save architecture to project model
        await self._update_project_fields(project_id, {"architecture": architecture})
        
        # Store Architecture artifact
        if architecture:
            await self._store_artifact(
                state["project_id"], 
                "architecture.md", 
                architecture, 
                ArtifactType.documentation,
                state.get("language", "python")
            )
            
        return {
            "messages": [AIMessage(content=f"Architecture designed:\n{architecture}")],
            "project_context": {
                **state["project_context"],
                "architecture": architecture,
                "prd": prd,
                "requirements": state["project_context"].get("requirements", "")
            }
        }

    async def _engineer_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for Engineer agent."""
        project_id = state["project_id"]
        await self._update_project_status(project_id, ProjectStatus.running_engineer)
        await self._publish_status_update(project_id, ProjectStatus.running_engineer, "Generating codebase...")
        
        architecture = state["project_context"].get("architecture", "")
        prd = state["project_context"].get("prd", "")
        
        # If we came from reflexion, we might have specific fixes to apply
        reflexion_feedback = state.get("review_feedback", {}).get("reflexion_fix", "")
        existing_code = state["project_context"].get("code_repo", {})
        
        payload = {
            "architecture": architecture,
            "prd": prd,
            "requirements": state.get("requirements", ""),
            "fix_instructions": reflexion_feedback,
            "existing_code": existing_code,
            "project_id": state["project_id"],
            "entry_point": "main.py",
            "language": state.get("language", "python"),
            "framework": state.get("framework", ""),
        }
        
        message = AgentMessage(
            sender=AgentType.ARCHITECT,
            recipient=AgentType.ENGINEER,
            message_type=MessageType.TASK,
            payload=payload
        )
        
        response = await self.engineer_agent.process_message(message)
        code_repo = {}
        if response and response.payload:
            code_repo = response.payload.get("code_repo") or response.payload.get("code") or {}
        
        # Store code artifacts
        for file_path, content in code_repo.items():
            await self._store_artifact(
                state["project_id"],
                file_path,
                content,
                ArtifactType.code,
                state.get("language", "python")
            )
            
        # Store test artifacts
        test_files = response.payload.get("tests", {}) if response and response.payload else {}
        for file_path, content in test_files.items():
            await self._store_artifact(
                state["project_id"],
                file_path,
                content,
                ArtifactType.code, # Or create ArtifactType.test if preferred, for now using code
                state.get("language", "python")
            )
            
        # EARLY INGESTION: Ingest into Knowledge Graph after first generation or repair
        try:
            project_path = os.path.join(settings.generated_projects_path, state["project_id"])
            
            # Extract project name from PRD if available
            project_name = "New Project"
            if prd and isinstance(prd, str):
                name_match = re.search(r'# Project Name:\s*(.*)', prd) or re.search(r'"project_name":\s*"(.*)"', prd)
                if name_match:
                    project_name = name_match.group(1).strip()
            
            await ingestion_pipeline.ingest_project(
                project_id=state["project_id"],
                project_name=f"{project_name} ({state.get('language', 'python')})",
                project_path=project_path
            )
            logger.info(f"Project {state['project_id']} successfully ingested/updated in KG")
        except Exception as e:
            logger.error(f"Early KG ingestion failed: {e}")

        return {
            "messages": [AIMessage(content=f"Code generated for {len(code_repo)} files.")],
            "project_context": {
                **state["project_context"], 
                "code_repo": code_repo, 
                "architecture": architecture, 
                "prd": prd
            }
        }

    async def _code_review_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for Code Review agent."""
        project_id = state["project_id"]
        await self._update_project_status(project_id, ProjectStatus.running_code_review)
        await self._publish_status_update(project_id, ProjectStatus.running_code_review, "Analyzing generated code...")

        code_repo = state["project_context"].get("code_repo", {})
        language = state.get("language", "python")

        message = AgentMessage(
            sender=AgentType.ENGINEER,
            recipient=AgentType.CODE_REVIEW,
            message_type=MessageType.TASK,
            payload={
                "code_repo": code_repo,
                "project_id": state["project_id"],
                "language": language,
            }
        )

        response = await self.code_review_agent.process_message(message)
        review_results = response.payload if response else {"status": "REJECTED", "feedback": "Review failed"}

        is_approved = review_results.get("status") == "APPROVED"
        review_results["approved"] = is_approved

        # Save code review to project model
        await self._update_project_fields(state["project_id"], {"code_review": review_results})
        
        # Store review as artifact
        await self._store_artifact(
            state["project_id"],
            "code_review.json",
            json.dumps(review_results, indent=2),
            ArtifactType.review,
            state.get("language", "python")
        )

        return {
            "messages": [AIMessage(content=f"Code review completed. Status: {review_results.get('status')}")],
            "review_feedback": review_results
        }

    async def _reflexion_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for Reflexion engine (self-healing)."""
        project_id = state["project_id"]
        await self._update_project_status(project_id, ProjectStatus.running_reflexion)
        await self._publish_status_update(project_id, ProjectStatus.running_reflexion, "Starting self-healing loop...")
        
        code_repo = state["project_context"].get("code_repo", {})
        language = state.get("language", "python")
        
        # EXECUTION SANDBOX: Run the code before asking for a fix
        from foundry.services.sandbox_service import sandbox_service
        from foundry.config import settings
        
        # Determine the host path for the sandbox mount
        # If running in Docker, we use the HOST_GENERATED_PROJECTS_PATH
        # If running locally, we use the local generated_projects_path
        base_path = settings.host_generated_projects_path or os.path.abspath(settings.generated_projects_path)
        project_host_path = os.path.join(base_path, project_id)
        
        logger.info(f"Running sandbox execution for project {project_id}")
        execution_results = await sandbox_service.execute_project(
            project_id=project_id,
            project_path=project_host_path,
            language=language
        )
        
        # Use "feedback" instead of "comments" (BUG-ORCH-2)
        review_feedback = state["review_feedback"]
        review_comments = review_feedback.get("feedback") or review_feedback.get("comments", "")
        
        # Enrich feedback with real execution logs
        enriched_feedback = f"{review_comments}\n\n### REAL EXECUTION LOGS\n"
        if execution_results["success"]:
            enriched_feedback += "Execution Succeeded.\n"
        else:
            enriched_feedback += f"Execution Failed with exit code {execution_results['exit_code']}.\n"
        
        enriched_feedback += f"STDOUT:\n{execution_results['stdout']}\n"
        enriched_feedback += f"STDERR:\n{execution_results['stderr']}\n"
        
        message = AgentMessage(
            sender=AgentType.CODE_REVIEW,
            recipient=AgentType.REFLEXION,
            message_type=MessageType.TASK,
            payload={
                "task_type": "execute_and_fix",
                "code_repo": code_repo,
                "feedback": enriched_feedback,
                "issues": state["review_feedback"].get("issues", []),
                "project_id": project_id,
                "execution_results": execution_results
            }
        )
        
        response = await self.reflexion_agent.process_message(message)
        reflexion_fix = response.payload.get("fix_plan", "") if response else ""
        updated_code_repo = response.payload.get("code_repo", code_repo) if response else code_repo
        
        return {
            "messages": [AIMessage(content=f"Reflexion analysis complete. Execution success: {execution_results['success']}")],
            "project_context": {
                **state["project_context"], 
                "code_repo": updated_code_repo
            },
            "review_feedback": {
                **state["review_feedback"], 
                "reflexion_fix": reflexion_fix
            },
            "reflexion_count": state.get("reflexion_count", 0) + 1
        }

    async def _devops_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for DevOps agent."""
        project_id = state["project_id"]
        await self._update_project_status(project_id, ProjectStatus.running_devops)
        await self._publish_status_update(project_id, ProjectStatus.running_devops, "Preparing deployment configuration...")
        
        code_repo = state["project_context"].get("code_repo", {})
        architecture = state["project_context"].get("architecture", "")
        
        message = AgentMessage(
            sender=AgentType.ENGINEER,
            recipient=AgentType.DEVOPS,
            message_type=MessageType.TASK,
            payload={
                "code_repo": code_repo,
                "architecture": architecture,
                "language": state.get("language", "python"),
                "project_id": state["project_id"]
            }
        )
        
        response = await self.devops_agent.process_message(message)
        deployment_results = response.payload if response else {}
        
        # Store deployment files as artifacts
        for filename, content in deployment_results.items():
            if filename == "explanation":
                continue
            
            # Ensure content is string (Fix TypeError ORCH)
            artifact_content = content
            if not isinstance(content, str):
                artifact_content = json.dumps(content, indent=2)

            await self._store_artifact(
                state["project_id"],
                filename,
                artifact_content,
                ArtifactType.devops,
                state.get("language", "python")
            )
        
        # After successful generation and deployment
        # KG Ingestion already happened in Engineer node for early context availability
        
        # REMOVED: Redundant status update. 'run' method handles final status.
        
        return {
            "messages": [AIMessage(content="DevOps and deployment tasks completed.")],
            "project_context": {**state["project_context"], "deployment": deployment_results},
            "success_flag": True
        }

    def _should_continue_from_review(self, state: GraphState) -> str:
        """Route the workflow based on code review results."""
        review = state["review_feedback"]
        
        if review.get("approved", False):
            return "approve"
        
        # If not approved, check if we should try reflexion or just fail
        # Fix boundary check (BUG-ORCH-4)
        if state.get("reflexion_count", 0) >= MAX_REFLEXION_RETRIES:
            return "fail"
        
        return "fix"

    async def _update_project_fields(self, project_id: str, fields: Dict[str, Any]):
        """Update multiple fields on a project record."""
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(Project).where(Project.id == project_id)
                )
                project = result.scalar_one_or_none()
                if project:
                    for key, value in fields.items():
                        setattr(project, key, value)
                    await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to update fields for project {project_id}: {e}")

    async def _update_project_status(self, project_id: str, status: ProjectStatus):
        """Update project status in database."""
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(Project).where(Project.id == project_id)
                )
                project = result.scalar_one_or_none()
                if project:
                    project.status = status
                    await session.commit()
            except Exception as e:
                logger.error(f"Failed to update project status: {e}")
                await session.rollback()

    async def _log_execution(
        self,
        project_id: str,
        agent_type: str,
        status: str,
        start_time: Optional[int] = None,
        duration: Optional[float] = None,
        error: Optional[str] = None
    ):
        """Log an agent execution record."""
        from foundry.models.execution import AgentExecution
        async with AsyncSessionLocal() as session:
            try:
                execution = AgentExecution(
                    project_id=project_id,
                    agent_type=agent_type,
                    status=status,
                    start_time=start_time,
                    duration_seconds=duration,
                    error_message=error
                )
                session.add(execution)
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to log agent execution: {e}")

    async def _store_artifact(self, project_id: str, name: str, content: str, artifact_type: ArtifactType, language: str = "python"):
        """Store generated artifact in database and filesystem."""
        # Save to filesystem
        project_dir = os.path.join(settings.generated_projects_path, project_id)
        os.makedirs(project_dir, exist_ok=True)
        
        file_path = os.path.join(project_dir, name)
        # Handle subdirectories in artifact name
        dir_part = os.path.dirname(file_path)
        if dir_part:
            os.makedirs(dir_part, exist_ok=True)
        
        # CLEANING: Strip markdown backticks for code files
        if artifact_type == ArtifactType.code:
            content = content.replace("```python", "").replace("```javascript", "").replace("```js", "").replace("```", "").strip()

            # Use the actual project language (Fix ORCH-1b)
            project_language = language.lower()
            
            # The language gate only applies when the target language is python
            if project_language == "python" and name.lower().endswith(".py"):
                if bool(self.JS_PATTERNS.search(content)):
                    logger.critical(f"FINAL GATE BLOCKED: JS leakage detected in Python file {name}. Substituting stub.")
                    content = "# BLOCKED: JavaScript leakage detected during final save.\n# Manual implementation required.\n"
        
        # Update path after possible name change
        file_path = os.path.join(project_dir, name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        # Save to database
        async with AsyncSessionLocal() as session:
            try:
                # Upsert logic: check for existing artifact with same name in this project
                result = await session.execute(
                    select(Artifact).where(
                        Artifact.project_id == project_id,
                        Artifact.filename == name
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    existing.content = content
                    existing.language = language
                    existing.updated_at = datetime.utcnow()
                else:
                    artifact = Artifact(
                        project_id=project_id,
                        filename=name,
                        content=content,
                        artifact_type=artifact_type,
                        language=language
                    )
                    session.add(artifact)
                
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to store artifact record: {e}")
                await session.rollback()

    async def run(self, project_id: str, initial_prompt: str):
        """Run the orchestration graph for a project."""
        # Read language and framework from the project record
        project_language = "python"
        project_framework = ""
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(Project).where(Project.id == project_id)
                )
                project = result.scalar_one_or_none()
                if project:
                    project_language = getattr(project, "language", "python") or "python"
                    project_framework = getattr(project, "framework", "") or ""
            except Exception as e:
                logger.warning(f"Could not read project language/framework: {e}")

        initial_state = {
            "messages": [HumanMessage(content=initial_prompt)],
            "current_agent": "product_manager",
            "project_context": {},
            "review_feedback": {},
            "project_id": project_id,
            "reflexion_count": 0,
            "success_flag": False,
            "language": project_language,
            "framework": project_framework,
        }
        
        # Use project_id as thread_id for LangGraph checkpointer
        config = {"configurable": {"thread_id": project_id}}
        
        try:
            final_state = initial_state
            async for output in self.graph.astream(initial_state, config):
                # We can emit logs or events here for real-time tracking
                for key, value in output.items():
                    logger.debug(f"Graph node {key} finished")
                    # Update final_state with the latest values from the node output
                    final_state = {**final_state, **value}
                    
            if final_state.get("success_flag"):
                await self._update_project_status(project_id, ProjectStatus.completed)
                await self._publish_status_update(project_id, ProjectStatus.completed, "Generation and deployment successful.")
                logger.info(f"Project {project_id} completed successfully.")
            else:
                await self._update_project_status(project_id, ProjectStatus.failed)
                await self._publish_status_update(project_id, ProjectStatus.failed, "Project failed during execution.")
                logger.warning(f"Project {project_id} ended without reaching successful deployment.")
            return True
        except Exception as e:
            logger.error(f"Orchestrator failed: {e}", exc_info=True)
            await self._update_project_status(project_id, ProjectStatus.failed)
            return False
