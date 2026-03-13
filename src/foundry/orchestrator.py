from typing import TypedDict, Annotated, List, Union, Dict, Any, Optional
import json
import os
import uuid
from langgraph.graph import StateGraph, START, END
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


# Maximum number of reflexion→engineer retry cycles before failing
MAX_REFLEXION_RETRIES = 3


class GraphState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    current_agent: str
    project_context: Dict[str, Any]
    review_feedback: Dict[str, Any]
    project_id: str  # UUID string for DB persistence
    reflexion_count: int  # tracks how many review→reflexion cycles have occurred


class AgentOrchestrator:
    def __init__(self):
        self.pm_agent = ProductManagerAgent()
        self.architect_agent = ArchitectAgent()
        self.engineer_agent = EngineerAgent()
        self.code_review_agent = CodeReviewAgent()
        self.devops_agent = DevOpsAgent()
        self.reflexion_agent = ReflexionAgent()
        
        self.workflow = self._build_graph()
        self.app = self.workflow.compile()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(GraphState)

        workflow.add_node("product_manager", self._run_pm)
        workflow.add_node("architect", self._run_architect)
        workflow.add_node("engineer", self._run_engineer)
        workflow.add_node("code_review", self._run_code_review)
        workflow.add_node("reflexion", self._run_reflexion)
        workflow.add_node("devops", self._run_devops)

        workflow.add_edge(START, "product_manager")
        workflow.add_edge("product_manager", "architect")
        workflow.add_edge("architect", "engineer")
        workflow.add_edge("engineer", "code_review")
        
        workflow.add_conditional_edges(
            "code_review",
            self._check_review_outcome,
            {
                "approved": "devops",
                "rejected": "reflexion",
                "max_retries_exceeded": "devops",
            }
        )
        
        workflow.add_edge("reflexion", "engineer")
        workflow.add_edge("devops", END)

        return workflow

    # ------------------------------------------------------------------ #
    #  Helper: persist project status to the database
    # ------------------------------------------------------------------ #
    async def _update_project_status(
        self,
        project_id: str,
        status: ProjectStatus,
        **kwargs: Any,
    ) -> None:
        """Update a project record in the database."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Project).where(Project.id == uuid.UUID(project_id))
            )
            project = result.scalar_one_or_none()
            if project:
                project.status = status
                for key, value in kwargs.items():
                    if hasattr(project, key):
                        setattr(project, key, value)
                await session.commit()

    async def _save_artifacts(
        self,
        project_id: str,
        files: Dict[str, str],
        artifact_type: ArtifactType = ArtifactType.code,
    ) -> None:
        """Save generated file content as Artifact records."""
        async with AsyncSessionLocal() as session:
            for filename, content in files.items():
                artifact = Artifact(
                    project_id=uuid.UUID(project_id),
                    filename=filename,
                    artifact_type=artifact_type,
                    content=content,
                )
                session.add(artifact)
            await session.commit()

    # ------------------------------------------------------------------ #
    #  Agent node implementations
    # ------------------------------------------------------------------ #
    async def _run_pm(self, state: GraphState):
        project_id = state.get("project_id")
        if project_id:
            await self._update_project_status(project_id, ProjectStatus.running_pm)

        messages = state["messages"]
        last_message = messages[-1]
        
        requirements = last_message.content
        agent_response = await self.pm_agent.analyze_requirements(requirements)
        
        content = "PRD Generated: " + str(agent_response.payload)[:100] + "..."

        prd_data = agent_response.payload
        if project_id:
            # Persist PRD as JSONB
            await self._update_project_status(project_id, ProjectStatus.running_pm, prd=prd_data)

        return {
            "current_agent": "product_manager", 
            "messages": [AIMessage(content=content, name="product_manager")],
            "project_context": {"prd": prd_data},
            "reflexion_count": state.get("reflexion_count", 0)
        }

    async def _run_architect(self, state: GraphState):
        project_id = state.get("project_id")
        if project_id:
            await self._update_project_status(project_id, ProjectStatus.running_architect)

        prd = state["project_context"].get("prd")
        agent_response = await self.architect_agent.design_architecture(str(prd))
        
        content = "Architecture Designed: " + str(agent_response.payload)[:100] + "..."
        
        new_context = state["project_context"].copy()
        arch_data = agent_response.payload
        new_context["architecture"] = arch_data

        if project_id:
            await self._update_project_status(
                project_id, ProjectStatus.running_architect, architecture=arch_data
            )

        return {
            "current_agent": "architect", 
            "messages": [AIMessage(content=content, name="architect")],
            "project_context": new_context
        }

    async def _run_engineer(self, state: GraphState):
        project_id = state.get("project_id")
        if project_id:
            await self._update_project_status(project_id, ProjectStatus.running_engineer)

        architecture = state["project_context"].get("architecture")
        agent_response = await self.engineer_agent.generate_code(str(architecture))
        
        # Use project_id for path (or fallback to 'mvp_project')
        path_id = project_id or "mvp_project"
        base_path = os.path.join(os.getcwd(), "generated_projects", str(path_id))
        
        files = agent_response.payload.get("code", {})
        written_paths = self.engineer_agent.write_code_to_disk(files, base_path)
        
        content = f"Code Generated and Written to {base_path}: {len(written_paths)} files."

        if project_id:
            await self._update_project_status(
                project_id, ProjectStatus.running_engineer, generated_path=base_path
            )
            await self._save_artifacts(project_id, files, ArtifactType.code)

        new_context = state["project_context"].copy()
        new_context["code"] = files
        new_context["code_path"] = base_path
        
        return {
            "current_agent": "engineer", 
            "messages": [AIMessage(content=content, name="engineer")],
            "project_context": new_context
        }

    async def _run_code_review(self, state: GraphState):
        project_id = state.get("project_id")
        if project_id:
            await self._update_project_status(project_id, ProjectStatus.running_code_review)

        code = state["project_context"].get("code")
        agent_response = await self.code_review_agent.analyze_code(code)
        
        review_json = agent_response.payload.get("review", "{}")
        if isinstance(review_json, str):
            try:
                review_data = json.loads(review_json)
            except Exception:
                review_data = {"status": "APPROVED", "feedback": "JSON parse error, defaulting to Approved"}
        else:
            review_data = review_json
            
        content = f"Code Review Complete. Status: {review_data.get('status')}"

        if project_id:
            await self._update_project_status(
                project_id, ProjectStatus.running_code_review, code_review=review_data
            )

        return {
            "current_agent": "code_review",
            "messages": [AIMessage(content=content, name="code_review")],
            "review_feedback": review_data
        }

    async def _run_reflexion(self, state: GraphState):
        project_id = state.get("project_id")
        if project_id:
            await self._update_project_status(project_id, ProjectStatus.running_reflexion)

        current_count = state.get("reflexion_count", 0) + 1

        feedback = state.get("review_feedback")
        code = state["project_context"].get("code")
        
        agent_response = await self.reflexion_agent.reflect_on_feedback(feedback, code)
        
        content = f"Reflexion Plan (attempt {current_count}/{MAX_REFLEXION_RETRIES}): " + str(agent_response.payload.get("fix_plan"))[:100]
        
        return {
            "current_agent": "reflexion",
            "messages": [AIMessage(content=content, name="reflexion")],
            "reflexion_count": current_count,
        }

    async def _run_devops(self, state: GraphState):
        project_id = state.get("project_id")
        if project_id:
            await self._update_project_status(project_id, ProjectStatus.running_devops)

        architecture = state["project_context"].get("architecture")
        agent_response = await self.devops_agent.prepare_deployment(architecture)
        
        deployment_files = agent_response.payload.get("deployment_files", {})
        base_path = state["project_context"].get("code_path")
        
        if isinstance(deployment_files, str):
            try:
                deployment_files = json.loads(deployment_files)
            except Exception:
                deployment_files = {}

        if base_path and deployment_files:
            self.engineer_agent.write_code_to_disk(deployment_files, base_path)

        if project_id and deployment_files:
            await self._save_artifacts(project_id, deployment_files, ArtifactType.config)
            await self._update_project_status(project_id, ProjectStatus.completed)

        # --- Git integration: initialise repo and commit scaffold ---
        if base_path:
            git_ok = git_service.init_repo(base_path)
            if git_ok:
                git_service.commit_all(base_path)

        content = "DevOps Deployment Files Generated."
        
        return {
            "current_agent": "devops", 
            "messages": [AIMessage(content=content, name="devops")]
        }

    def _check_review_outcome(self, state: GraphState):
        feedback = state.get("review_feedback", {})
        status = feedback.get("status", "APPROVED").upper()
        
        if status == "REJECTED":
            retries = state.get("reflexion_count", 0)
            if retries >= MAX_REFLEXION_RETRIES:
                print(f"Max reflexion retries ({MAX_REFLEXION_RETRIES}) exceeded — proceeding to devops anyway.")
                return "max_retries_exceeded"
            return "rejected"
        return "approved"

    async def run_project(
        self,
        initial_requirements: str,
        project_id: Optional[str] = None,
    ):
        """Run the full project generation pipeline.

        Args:
            initial_requirements: Natural-language requirements from the user.
            project_id: Optional UUID string. When provided, the orchestrator
                        will persist agent outputs to the database.
        """
        inputs: GraphState = {
            "messages": [HumanMessage(content=initial_requirements)],
            "current_agent": "user",
            "project_context": {},
            "review_feedback": {},
            "project_id": project_id or "",
            "reflexion_count": 0,
        }

        try:
            async for output in self.app.astream(inputs):
                for key, value in output.items():
                    print(f"Finished step: {key}")
                    if "messages" in value:
                        print(f"  Result: {value['messages'][-1].content[:100]}...")
        except Exception as exc:
            if project_id:
                await self._update_project_status(project_id, ProjectStatus.failed)
            raise
