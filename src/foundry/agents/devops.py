from typing import Dict, Any
from foundry.agents.base import Agent, AgentType, AgentMessage, MessageType
from foundry.llm.base import LLMMessage
from foundry.llm.factory import LLMProviderFactory

class DevOpsAgent(Agent):
    def __init__(self):
        super().__init__(AgentType.DEVOPS)
        self.llm = LLMProviderFactory.create_provider(model_name=self.model_name)

    async def process_message(self, message: AgentMessage) -> AgentMessage:
        if message.message_type == MessageType.TASK:
            architecture = message.payload.get("architecture")
            return await self.prepare_deployment(architecture)
        return None

    async def prepare_deployment(self, architecture: Dict[str, Any]) -> AgentMessage:
        """
        Generates deployment configurations (Dockerfile, docker-compose.yml) based on architecture.
        """
        system_prompt = """You are an expert DevOps Engineer.
        Your goal is to generate the necessary deployment configuration files for the project.
        
        Based on the architecture provided, generate:
        1.  `Dockerfile`: For the application.
        2.  `docker-compose.yml`: For the application and its dependencies (e.g., database, redis).
        
        Return the result as a JSON object where keys are filenames and values are file content.
        Example:
        {
            "Dockerfile": "FROM python:3.9...",
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
        
        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.ENGINEER,  # Feedback loop or End
            message_type=MessageType.TASK,
            payload={"deployment_files": response.content}
        )
