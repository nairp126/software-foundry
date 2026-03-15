from typing import TypedDict, Annotated, List, Union, Dict, Any, Optional
import json
import os
import uuid
import logging
import asyncio
import re
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
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

        return workflow.compile()

    async def _pm_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for Product Manager agent."""
        await self._update_project_status(state["project_id"], ProjectStatus.running_pm)
        
        # Get the latest message from the history if any
        user_prompt = state["messages"][-1].content if state["messages"] else ""
        logger.info(f"PM Node processing requirements: {user_prompt[:50]}...")
        
        message = AgentMessage(
            sender=AgentType.PRODUCT_MANAGER,
            recipient=AgentType.PRODUCT_MANAGER,
            message_type=MessageType.TASK,
            payload={
                "prompt": user_prompt,
                "requirements": user_prompt # Fix L: Direct Anchor
            }
        )
        
        response = await self.pm_agent.process_message(message)
        prd = response.payload.get("prd", "") if response else ""
        
        # Store PRD artifact
        if prd:
            await self._store_artifact(
                state["project_id"], 
                "prd.md", 
                prd, 
                ArtifactType.documentation
            )
            
        return {
            "messages": [AIMessage(content=f"PRD generated:\n{prd}")],
            "project_context": {
                "prd": prd,
                "requirements": state.get("requirements", "") # Persist for next nodes
            }
        }

    async def _architect_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for Architect agent."""
        await self._update_project_status(state["project_id"], ProjectStatus.running_architect)
        
        prd = state["project_context"].get("prd", "")
        requirements = state.get("requirements", "") # Fix L
        message = AgentMessage(
            sender=AgentType.PRODUCT_MANAGER,
            recipient=AgentType.ARCHITECT,
            message_type=MessageType.TASK,
            payload={
                "prd": prd,
                "requirements": requirements
            }
        )
        
        response = await self.architect_agent.process_message(message)
        architecture = response.payload.get("architecture", "") if response else ""
        
        # Store Architecture artifact
        if architecture:
            await self._store_artifact(
                state["project_id"], 
                "architecture.md", 
                architecture, 
                ArtifactType.documentation
            )
            
        return {
            "messages": [AIMessage(content=f"Architecture designed:\n{architecture}")],
            "project_context": {
                "architecture": architecture, 
                "prd": prd,
                "requirements": state.get("requirements", "") # Persist for next nodes
            }
        }

    async def _engineer_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for Engineer agent."""
        await self._update_project_status(state["project_id"], ProjectStatus.running_engineer)
        
        architecture = state["project_context"].get("architecture", "")
        prd = state["project_context"].get("prd", "")
        
        # If we came from reflexion, we might have specific fixes to apply
        reflexion_feedback = state.get("review_feedback", {}).get("reflexion_fix", "")
        existing_code = state["project_context"].get("code_repo", {})
        
        payload = {
            "architecture": architecture,
            "prd": prd,
            "requirements": state.get("requirements", ""), # Fix L
            "fix_instructions": reflexion_feedback,
            "existing_code": existing_code,
            "project_id": state["project_id"],
            "entry_point": "main.py"
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
                ArtifactType.code
            )
            
        # EARLY INGESTION: Ingest into Knowledge Graph after first generation or repair
        try:
            project_path = os.path.join(settings.generated_projects_path, state["project_id"])
            await ingestion_pipeline.ingest_project(
                project_id=state["project_id"],
                project_name=f"Python Project {state['project_id'][:8]}",
                project_path=project_path
            )
            logger.info(f"Project {state['project_id']} successfully ingested/updated in KG")
        except Exception as e:
            logger.error(f"Early KG ingestion failed: {e}")

        return {
            "messages": [AIMessage(content=f"Code generated for {len(code_repo)} files.")],
            "project_context": {"code_repo": code_repo, "architecture": architecture, "prd": prd}
        }

    async def _code_review_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for Code Review agent."""
        await self._update_project_status(state["project_id"], ProjectStatus.running_code_review)
        
        code_repo = state["project_context"].get("code_repo", {})
        
        message = AgentMessage(
            sender=AgentType.ENGINEER,
            recipient=AgentType.CODE_REVIEW,
            message_type=MessageType.TASK,
            payload={
                "code_repo": code_repo,
                "project_id": state["project_id"]
            }
        )
        
        response = await self.code_review_agent.process_message(message)
        review_results = response.payload if response else {"status": "REJECTED", "feedback": "Review failed"}
        
        # Bridge status/approved fields for LangGraph routing
        is_approved = review_results.get("status") == "APPROVED"
        
        # FAIL-SAFE: Re-verify that no JS leaked into an "APPROVED" review
        if is_approved:
            patterns = ["const ", "require(", "import React", "express()", "module.exports", "export default"]
            for file_path, content in code_repo.items():
                if any(p in content for p in patterns):
                    is_approved = False
                    review_results["status"] = "REJECTED"
                    review_results["feedback"] = "REVIEWER FAIL-SAFE: JS leakage detected in approved repo. Rejecting for Python rewrite."
                    break

        review_results["approved"] = is_approved
        
        # Store review as artifact
        await self._store_artifact(
            state["project_id"],
            "code_review.json",
            json.dumps(review_results, indent=2),
            ArtifactType.review
        )
        
        return {
            "messages": [AIMessage(content=f"Code review completed. Status: {review_results.get('status')}")],
            "review_feedback": review_results
        }

    async def _reflexion_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for Reflexion engine (self-healing)."""
        await self._update_project_status(state["project_id"], ProjectStatus.running_reflexion)
        
        code_repo = state["project_context"].get("code_repo", {})
        review_comments = state["review_feedback"].get("comments", "")
        
        message = AgentMessage(
            sender=AgentType.CODE_REVIEW,
            recipient=AgentType.REFLEXION,
            message_type=MessageType.TASK,
            payload={
                "task_type": "execute_and_fix",
                "code_repo": code_repo,
                "feedback": review_comments,
                "project_id": state["project_id"]
            }
        )
        
        response = await self.reflexion_agent.process_message(message)
        reflexion_fix = response.payload.get("fix_plan", "") if response else ""
        
        return {
            "messages": [AIMessage(content=f"Reflexion analysis complete. Fix plan generated.")],
            "review_feedback": {**state["review_feedback"], "reflexion_fix": reflexion_fix},
            "reflexion_count": state.get("reflexion_count", 0) + 1
        }

    async def _devops_node(self, state: GraphState) -> Dict[str, Any]:
        """Node for DevOps agent."""
        await self._update_project_status(state["project_id"], ProjectStatus.running_devops)
        
        code_repo = state["project_context"].get("code_repo", {})
        architecture = state["project_context"].get("architecture", "")
        
        message = AgentMessage(
            sender=AgentType.ENGINEER,
            recipient=AgentType.DEVOPS,
            message_type=MessageType.TASK,
            payload={
                "code_repo": code_repo,
                "architecture": architecture
            }
        )
        
        response = await self.devops_agent.process_message(message)
        deployment_results = response.payload if response else {}
        
        # Store deployment files as artifacts
        for filename, content in deployment_results.items():
            await self._store_artifact(
                state["project_id"],
                filename,
                content,
                ArtifactType.devops
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
        if state.get("reflexion_count", 0) < MAX_REFLEXION_RETRIES:
            return "fix"
        
        return "fail"

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

    async def _store_artifact(self, project_id: str, name: str, content: str, artifact_type: ArtifactType):
        """Store generated artifact in database and filesystem."""
        # Save to filesystem
        project_dir = os.path.join(settings.generated_projects_path, project_id)
        os.makedirs(project_dir, exist_ok=True)
        
        file_path = os.path.join(project_dir, name)
        # Handle subdirectories in artifact name
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # CLEANING: Strip markdown backticks for code files
        if artifact_type == ArtifactType.code:
            content = content.replace("```python", "").replace("```javascript", "").replace("```js", "").replace("```", "").strip()
            
            # Fix 5: Master Write-Time Gate
            # 1. Block forbidden extensions entirely
            forbidden_exts = ['.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.php', '.html', '.css']
            if any(name.lower().endswith(ext) for ext in forbidden_exts):
                logger.critical(f"MASTER GATE BLOCKED forbidden extension: {name}. Substituting error stub.")
                content = f"# BLOCKED: Forbidden file type {name} detected in Python project.\n"
                # Optionally rename to .py to prevent sandbox breakage
                if not name.endswith(".py"):
                    name = os.path.splitext(name)[0] + ".py"
            
            # 2. Block JS content in Python files
            if name.endswith(".py") and bool(self.JS_PATTERNS.search(content)):
                logger.critical(f"FINAL GATE BLOCKED: JS leakage detected in {name}. Substituting error stub.")
                content = f"# BLOCKED: JavaScript leakage detected during final save.\n# Manual implementation required.\n"
        
        # Update path after possible name change
        file_path = os.path.join(project_dir, name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        # Save to database
        async with AsyncSessionLocal() as session:
            try:
                artifact = Artifact(
                    project_id=project_id,
                    filename=name,
                    content=content,
                    artifact_type=artifact_type
                )
                session.add(artifact)
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to store artifact record: {e}")
                await session.rollback()

    async def run(self, project_id: str, initial_prompt: str):
        """Run the orchestration graph for a project."""
        initial_state = {
            "messages": [HumanMessage(content=initial_prompt)],
            "current_agent": "product_manager",
            "project_context": {},
            "review_feedback": {},
            "project_id": project_id,
            "reflexion_count": 0,
            "success_flag": False
        }
        
        try:
            final_state = initial_state
            async for output in self.graph.astream(initial_state):
                # We can emit logs or events here for real-time tracking
                for key, value in output.items():
                    logger.debug(f"Graph node {key} finished")
                    # Update final_state with the latest values from the node output
                    final_state = {**final_state, **value}
                    
            if final_state.get("success_flag"):
                await self._update_project_status(project_id, ProjectStatus.completed)
                logger.info(f"Project {project_id} completed successfully.")
            else:
                await self._update_project_status(project_id, ProjectStatus.failed)
                logger.warning(f"Project {project_id} ended without reaching successful deployment.")
            return True
        except Exception as e:
            logger.error(f"Orchestrator failed: {e}", exc_info=True)
            await self._update_project_status(project_id, ProjectStatus.failed)
            return False
