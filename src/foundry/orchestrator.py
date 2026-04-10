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
from foundry.vcs.git_manager import GitManager, CommitType
from foundry.services.knowledge_graph import KnowledgeGraphService
from foundry.graph.ingestion import ingestion_pipeline
from foundry.config import settings
from foundry.services.agent_control import agent_control_service


class AgentControlInterrupt(Exception):
    """Base exception for agent control interrupts."""
    def __init__(self, project_id: str, action: str, reason: str = ""):
        self.project_id = project_id
        self.action = action
        self.reason = reason
        super().__init__(f"Agent execution {action} for project {project_id}: {reason}")


class AgentPauseInterrupt(AgentControlInterrupt):
    """Exception raised when agent execution is paused."""
    def __init__(self, project_id: str, reason: str = "User requested pause"):
        super().__init__(project_id, "paused", reason)


class AgentCancelInterrupt(AgentControlInterrupt):
    """Exception raised when agent execution is cancelled."""
    def __init__(self, project_id: str, reason: str = "User requested cancellation"):
        super().__init__(project_id, "cancelled", reason)

logger = logging.getLogger(__name__)

# Maximum number of reflexion→engineer retry cycles before failing
MAX_REFLEXION_RETRIES = 3


def merge_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Reducer for merging dictionaries in GraphState."""
    new_dict = (left or {}).copy()
    new_dict.update(right or {})
    return new_dict


class GraphState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    current_agent: str
    project_context: Annotated[Dict[str, Any], merge_dicts]
    review_feedback: Annotated[Dict[str, Any], merge_dicts]
    project_id: str  # UUID string for DB persistence
    reflexion_count: int  # tracks how many review→reflexion cycles have occurred
    success_flag: bool  # tracks if the code was successfully deployed
    language: str  # project language, e.g. "python", "javascript", "java"
    framework: str  # project framework, e.g. "fastapi", "express", "spring"
    resume_from: Optional[str]  # Optional node to resume from


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

    def _route_entry(self, state: GraphState) -> str:
        """Determines the start node of the graph."""
        if state.get("resume_from"):
            return state["resume_from"]
        return "product_manager"

    def _build_graph(self) -> StateGraph:
        """Construct the LangGraph workflow."""
        workflow = StateGraph(GraphState)

        # Define nodes
        workflow.add_node("product_manager", self._pm_node)
        workflow.add_node("architect", self._architect_node)
        workflow.add_node("architect_approval", self._approval_node)
        workflow.add_node("engineer", self._engineer_node)
        workflow.add_node("code_review", self._code_review_node)
        workflow.add_node("reflexion", self._reflexion_node)
        workflow.add_node("devops", self._devops_node)

        # Define edges
        workflow.add_conditional_edges(START, self._route_entry)
        workflow.add_edge("product_manager", "architect")
        
        # Approval gate after architecture (Audit 7.2)
        workflow.add_conditional_edges(
            "architect",
            self._should_proceed_to_approval,
            {
                "approve": "architect_approval",
                "direct": "engineer"
            }
        )
        
        workflow.add_conditional_edges(
            "architect_approval",
            self._check_approval_status,
            {
                "proceed": "engineer",
                "wait": END # In a real system, this would wait for a trigger
            }
        )
        
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
        if redis_client.is_connected:
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
        await self._check_control(project_id)
        await self._update_project_status(project_id, ProjectStatus.running_pm)
        await self._publish_status_update(project_id, ProjectStatus.running_pm, "Starting requirements analysis...")
        
        # PRE-SEED KG WITH PROJECT NODE (Critical for relational linking)
        try:
            await self.kg_service.client.connect()
            await self.kg_service.create_project(
                project_id=project_id,
                name=f"Project {project_id[:8]}",
                metadata={"status": "initializing"}
            )
        except Exception as e:
            logger.warning(f"Failed to pre-seed project in KG: {e}")
        
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
        prd = response.payload.get("prd") if response and isinstance(response.payload, dict) else None
        
        # Parse PRD if it's a JSON string
        prd = self._parse_json_field(prd)
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
            
            # SEED KG WITH REQUIREMENTS
            try:
                if prd:
                    await self.kg_service.client.connect()
                    await self.kg_service.store_requirement(
                        project_id=state["project_id"],
                        text=prd if isinstance(prd, str) else json.dumps(prd),
                        source_agent="ProductManager"
                    )
            except Exception as e:
                logger.warning(f"Failed to seed requirements in KG: {e}")
                
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
        await self._check_control(project_id)
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
        architecture = response.payload.get("architecture") if response and isinstance(response.payload, dict) else None
        
        # Parse Architecture if it's a JSON string
        architecture = self._parse_json_field(architecture)
        
        # Save Architecture to project model
        await self._update_project_fields(state["project_id"], {"architecture": architecture})
    
        # Store Architecture artifact
        if architecture:
            await self._store_artifact(
                state["project_id"], 
                "architecture.md", 
                architecture, 
                ArtifactType.documentation,
                state.get("language", "python")
            )
            
            # SEED KG WITH ARCHITECTURE DECISIONS
            try:
                if architecture:
                    await self.kg_service.client.connect()
                    # Store as a monolithic architecture node for context
                    await self.kg_service.store_architecture_decision(
                        project_id=state["project_id"],
                        title="System Architecture",
                        decision=architecture if isinstance(architecture, str) else json.dumps(architecture),
                        rationale="Initial design from ArchitectAgent",
                        language=state.get("language", "python"),
                        framework=state.get("framework", "")
                    )
            except Exception as e:
                logger.warning(f"Failed to seed architecture in KG: {e}")
                
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
        await self._check_control(project_id)
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
            
        # TRACK GENERATED CODE IN GIT
        try:
            project_path = os.path.join(settings.generated_projects_path, state["project_id"])
            git_manager = GitManager(project_path)
            # Initialize repo right before committing just in case
            git_manager.initialize_repository()
            git_manager.create_commit(
                commit_type=CommitType.FEAT,
                description=f"Engineer generated codebase for {state.get('language', 'python')} project",
                scope="engineer"
            )
            logger.info(f"Committed generated code to Git for project {state['project_id']}")
        except Exception as e:
            logger.error(f"Git commit failed for project {state['project_id']}: {e}")
            
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
                project_path=project_path,
                language=state.get("language", "python")
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
                "prd": prd,
                "entry_point": payload["entry_point"]
            }
        }

    async def _code_review_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for Code Review agent."""
        project_id = state["project_id"]
        await self._check_control(project_id)
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
        review_results = response.payload if response else None
        review_results = self._parse_json_field(review_results)
        
        if not isinstance(review_results, dict):
            review_results = {"status": "REJECTED", "feedback": "Invalid review format", "approved": False}

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
            "project_context": {**state["project_context"]},
            "review_feedback": review_results
        }

    async def _reflexion_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for Reflexion engine (self-healing)."""
        project_id = state["project_id"]
        await self._check_control(project_id)
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
        await self._check_control(project_id)
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
                "project_id": state["project_id"],
                "entry_point": state["project_context"].get("entry_point", "app.py")
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
        # Fix boundary check (BUG-ORCH-4 / Audit 7.2)
        if state.get("reflexion_count", 0) >= MAX_REFLEXION_RETRIES:
            return "fail"
        
        return "fix"

    async def _approval_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for handling architectural approval."""
        project_id = state["project_id"]
        
        # Check if project was already approved (manual override)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()
            if project and project.status == ProjectStatus.running_engineer:
                return {"messages": [AIMessage(content="Design already approved. Skipping node.")]}

        # Create ApprovalRequest
        from foundry.models.approval import ApprovalRequest, ApprovalType, ApprovalStatus
        import uuid
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(ApprovalRequest).where(
                        ApprovalRequest.project_id == uuid.UUID(project_id),
                        ApprovalRequest.status == ApprovalStatus.pending
                    )
                )
                if not result.scalar_one_or_none():
                    approval = ApprovalRequest(
                        project_id=uuid.UUID(project_id),
                        request_type=ApprovalType.plan,
                        stage="architecture",
                        status=ApprovalStatus.pending,
                        content={"architecture": state["project_context"].get("architecture", "")}
                    )
                    session.add(approval)
                    await session.commit()
            except Exception as e:
                logger.error(f"Failed to create ApprovalRequest: {e}")

        await self._update_project_status(project_id, ProjectStatus.paused)
        await self._publish_status_update(project_id, ProjectStatus.paused, "Architectural design pending review.")
        
        return {
            "messages": [AIMessage(content="Waiting for architectural approval...")],
            "project_context": {"pending_approval": True}
        }

    def _should_proceed_to_approval(self, state: GraphState) -> str:
        """Decide if we should enter the approval node based on policy."""
        # For now, we only enter if policy is STRICT. In production, check DB.
        # This is a placeholder for the logic mentioned in audit.
        return "approve" # Default to approval for safety as per hardening goal

    async def _check_approval_status(self, state: GraphState) -> str:
        """Check if the user has approved the design."""
        project_id = state["project_id"]
        from foundry.models.approval import ApprovalRequest, ApprovalStatus
        import uuid
        
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(ApprovalRequest).where(
                        ApprovalRequest.project_id == uuid.UUID(project_id),
                        ApprovalRequest.stage == "architecture"
                    ).order_by(ApprovalRequest.created_at.desc())
                )
                approval = result.scalar_one_or_none()
                
                if not approval:
                    return "proceed"
                
                if approval.status == ApprovalStatus.approved:
                    return "proceed"
                
                # If pending or rejected, exit the graph
                return "wait"
            except Exception as e:
                logger.error(f"Error checking approval status: {e}")
                return "wait"

    # JSONB column names that must always be stored as dicts, never strings
    _JSONB_FIELDS = {"prd", "architecture", "code_review"}

    async def _update_project_fields(self, project_id: str, fields: Dict[str, Any]):
        """Update multiple fields on a project record.
        
        Automatically parses JSON strings for JSONB columns to prevent
        Pydantic ValidationErrors when the API reads them back.
        """
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(Project).where(Project.id == project_id)
                )
                project = result.scalar_one_or_none()
                if project:
                    for key, value in fields.items():
                        # Auto-parse JSON strings for JSONB columns
                        if key in self._JSONB_FIELDS and isinstance(value, str):
                            value = self._parse_json_field(value)
                        setattr(project, key, value)
                    await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to update fields for project {project_id}: {e}")

    async def _update_project_status(self, project_id: str, status: ProjectStatus):
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(Project).where(Project.id == project_id)
                )
                project = result.scalar_one_or_none()
                if project:
                    project.status = status
                    project.updated_at = datetime.utcnow()
                    await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to update status for project {project_id}: {e}")

    async def _check_control(self, project_id: str):
        """Check for pending control actions and raise interrupts if needed."""
        import uuid
        try:
            status = await agent_control_service.check_control_status(uuid.UUID(project_id))
            if not status:
                return
            
            action = status.get("action")
            reason = status.get("reason", "No reason provided")
            
            if action == "pause":
                logger.info(f"Execution PAUSED for project {project_id}: {reason}")
                raise AgentPauseInterrupt(project_id, reason)
            elif action == "cancel":
                logger.info(f"Execution CANCELLED for project {project_id}: {reason}")
                raise AgentCancelInterrupt(project_id, reason)
        except (AgentPauseInterrupt, AgentCancelInterrupt):
            raise
        except Exception as e:
            logger.warning(f"Error checking control status for {project_id}: {e}")
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

    def _parse_json_field(self, field_value: Any) -> Any:
        """Safely parse a field into a dictionary if it is a JSON string."""
        if not field_value:
            return None
        if isinstance(field_value, str):
            try:
                # Basic cleaning of markdown backticks if present
                cleaned = field_value.replace("```json", "").replace("```", "").strip()
                if not cleaned:
                    return None
                return json.loads(cleaned)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON field: {field_value[:100]}...")
                return None
        return field_value

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
        
        # Handle non-string content (e.g., dicts from structured responses)
        if isinstance(content, (dict, list)):
            content = json.dumps(content, indent=2)
        elif content is None:
            content = ""

        # CLEANING: Strip markdown backticks for code files
        if artifact_type == ArtifactType.code and isinstance(content, str):
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

    async def run(self, project_id: str, initial_prompt: str, resume_from: Optional[str] = None):
        """Run the orchestration graph for a project."""
        # Read lang, framework, prd, arch from the project record
        project_language = "python"
        project_framework = ""
        project_prd = ""
        project_architecture = ""
        
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(Project).where(Project.id == project_id)
                )
                project = result.scalar_one_or_none()
                if project:
                    project_language = getattr(project, "language", "python") or "python"
                    project_framework = getattr(project, "framework", "") or ""
                    project_prd = getattr(project, "prd", "") or ""
                    project_architecture = getattr(project, "architecture", "") or ""
            except Exception as e:
                logger.warning(f"Could not read project data: {e}")

        # Ensure we have a mock prompt if resuming without one
        safe_prompt = initial_prompt if initial_prompt else "Resume execution"
        
        initial_state = {
            "messages": [HumanMessage(content=safe_prompt)],
            "current_agent": "product_manager",
            "project_context": {
                "prd": project_prd,
                "architecture": project_architecture
            },
            "review_feedback": {},
            "project_id": project_id,
            "reflexion_count": 0,
            "success_flag": False,
            "language": project_language,
            "framework": project_framework,
            "resume_from": resume_from
        }
        
        # Use project_id as thread_id for LangGraph checkpointer
        config = {"configurable": {"thread_id": project_id}}
        
        try:
            final_state = initial_state
            last_yield_time = float(datetime.utcnow().timestamp())
            
            logger.critical(f"STARTING GRAPH ASTREAM FOR PROJECT {project_id}")
            async for output in self.graph.astream(initial_state, config):
                logger.critical(f"ASTREAM YIELDED: {output.keys() if isinstance(output, dict) else output}")
                current_time = float(datetime.utcnow().timestamp())
                for key, value in output.items():
                    logger.debug(f"Graph node {key} finished")
                    duration = float(current_time - last_yield_time)
                    
                    try:
                        await self._log_execution(project_id, key, "COMPLETED", last_yield_time, duration)
                    except Exception as e:
                        logger.warning(f"Failed to log execution: {e}")
                        
                    final_state = {**final_state, **value}
                last_yield_time = current_time
                
            logger.critical(f"GRAPH ASTREAM COMPLETED. FINAL STATE SUCCESS FLAG: {final_state.get('success_flag')}")
            if final_state.get("success_flag"):
                await self._update_project_status(project_id, ProjectStatus.completed)
                await self._publish_status_update(project_id, ProjectStatus.completed, "Generation and deployment successful.")
                logger.info(f"Project {project_id} completed successfully.")
            else:
                # Check if we naturally paused for approval, if so, do not fail
                async with AsyncSessionLocal() as session:
                    res = await session.execute(select(Project).where(Project.id == project_id))
                    p = res.scalar_one_or_none()
                    if p and p.status == ProjectStatus.paused:
                        logger.info(f"Project {project_id} is paused for approval, correctly suspending stream.")
                    else:
                        await self._update_project_status(project_id, ProjectStatus.failed)
                        await self._publish_status_update(project_id, ProjectStatus.failed, "Project failed during execution.")
                        logger.warning(f"Project {project_id} ended without reaching successful deployment. Final State keys: {final_state.keys()}")
            return True
        except AgentPauseInterrupt as e:
            # When paused, we don't mark as failed in the graph flow
            # The API level already set status to PAUSED
            logger.info(f"Orchestration paused for {project_id}")
            await self._publish_status_update(project_id, ProjectStatus.paused, f"Execution paused: {e.reason}")
            return True
        except AgentCancelInterrupt as e:
            logger.info(f"Orchestration cancelled for {project_id}")
            await self._update_project_status(project_id, ProjectStatus.failed)
            await self._publish_status_update(project_id, ProjectStatus.failed, f"Execution cancelled: {e.reason}")
            return True
        except Exception as e:
            logger.error(f"Orchestrator failed: {e}", exc_info=True)
            await self._update_project_status(project_id, ProjectStatus.failed)
            return False
