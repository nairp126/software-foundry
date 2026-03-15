from typing import Dict, Any, Optional
from foundry.agents.base import Agent, AgentType, AgentMessage, MessageType
from foundry.llm.base import LLMMessage
from foundry.llm.factory import LLMProviderFactory

class DevOpsAgent(Agent):
    def __init__(self, model_name: Optional[str] = None):
        super().__init__(AgentType.DEVOPS, model_name)
        self.llm = LLMProviderFactory.create_provider(model_name=self.model_name)

    async def process_message(self, message: AgentMessage) -> AgentMessage:
        if message.message_type == MessageType.TASK:
            architecture = message.payload.get("architecture")
            code_repo = message.payload.get("code_repo")
            return await self.prepare_deployment(architecture, code_repo)
        return None

    async def prepare_deployment(self, architecture: Dict[str, Any], code_repo: Optional[str] = None) -> AgentMessage:
        """
        Generates deployment configurations (Dockerfile, docker-compose.yml) based on architecture.
        """
        system_prompt = """You are an expert DevOps Engineer.
        Your goal is to generate the necessary deployment configuration files for the project.
        
        Based on the architecture provided (RESTRICTION: Project is ALWAYS Python-based):
        1.  `Dockerfile`: For the application using a Python base image (e.g., python:3.11-slim).
        2.  `docker-compose.yml`: For the application and its dependencies (e.g., database, redis).
        
        Return the result as a JSON object where keys are filenames and values are file content.
        Example:
        {
            "Dockerfile": "FROM python:3.11-slim...",
            "docker-compose.yml": "version: '3.8'..."
        }
        """

        user_prompt = f"Here is the system architecture:\n\n{architecture}"

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]

        # Use Qwen to generate the deployment files
        response = await self.llm.generate(messages, temperature=0.2, json_mode=True)
        
        # Ensure it's a dict
        deployment_data = response.content
        if isinstance(deployment_data, str):
            try:
                # CLEANING: Strip markdown backticks
                deployment_data = deployment_data.replace("```json", "").replace("```", "").strip()
                deployment_data = json.loads(deployment_data)
            except:
                deployment_data = {}

        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.ENGINEER,
            message_type=MessageType.TASK,
            payload=deployment_data
        )
