import json
import logging
from typing import Dict, Any, Optional
from foundry.agents.base import Agent, AgentType, AgentMessage, MessageType
from foundry.llm.base import LLMMessage
from foundry.llm.factory import LLMProviderFactory

logger = logging.getLogger(__name__)

# Base Docker images per language (Req 21.2)
BASE_IMAGES = {
    "python": "python:3.11-slim",
    "javascript": "node:20-alpine",
    "typescript": "node:20-alpine",
    "java": "eclipse-temurin:21-jre-alpine",
}


class DevOpsAgent(Agent):
    def __init__(self, model_name: Optional[str] = None):
        super().__init__(AgentType.DEVOPS, model_name)
        self.llm = LLMProviderFactory.create_provider(model_name=self.model_name)

    def _select_base_image(self, language: str, code_repo: Optional[Dict[str, str]] = None) -> str:
        """Select the correct base Docker image for the given language.

        Falls back to Language_Config when code_repo is empty (Req 21.3).
        """
        lang_key = (language or "python").lower().strip()
        image = BASE_IMAGES.get(lang_key)
        if image:
            return image
        # Unknown language — fall back via Language_Config
        try:
            from foundry.utils.language_config import get_language_config
            image = get_language_config(lang_key).get("base_image", "python:3.11-slim")
            logger.warning("Unknown language %r — falling back to base image %r from Language_Config.", language, image)
            return image
        except Exception:
            return "python:3.11-slim"

    async def process_message(self, message: AgentMessage) -> AgentMessage:
        if message.message_type == MessageType.TASK:
            architecture = message.payload.get("architecture")
            code_repo = message.payload.get("code_repo")
            language = message.payload.get("language", "python")
            return await self.prepare_deployment(architecture, code_repo, language)
        return None

    async def prepare_deployment(
        self,
        architecture: Dict[str, Any],
        code_repo: Optional[Dict[str, str]] = None,
        language: str = "python",
    ) -> AgentMessage:
        """
        Generates deployment configurations (Dockerfile, docker-compose.yml).

        Reads code_repo to determine the correct base image and build steps (Req 21.1).
        Selects base image by language (Req 21.2).
        Falls back to Language_Config when code_repo is empty (Req 21.3).
        """
        if not code_repo:
            logger.warning("DevOpsAgent.prepare_deployment: code_repo is empty — falling back to Language_Config base image.")

        base_image = self._select_base_image(language, code_repo)

        system_prompt = f"""You are an expert DevOps Engineer.
        Your goal is to generate the necessary deployment configuration files for the project.

        The project is written in {language}. Use the following base Docker image: {base_image}

        Generate:
        1. `Dockerfile`: For the application using the base image above.
        2. `docker-compose.yml`: For the application and its dependencies (e.g., database, redis).

        Return the result as a JSON object where keys are filenames and values are file content.
        Example:
        {{
            "Dockerfile": "FROM {base_image}...",
            "docker-compose.yml": "version: '3.8'..."
        }}
        """

        user_prompt = f"Here is the system architecture:\n\n{architecture}"
        if code_repo:
            # Provide a brief summary of the repo structure for context
            file_list = ", ".join(list(code_repo.keys())[:10])
            user_prompt += f"\n\nProject files: {file_list}"

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]

        response = await self.llm.generate(messages, temperature=0.2, json_mode=True)

        deployment_data = response.content
        if isinstance(deployment_data, str):
            try:
                deployment_data = deployment_data.replace("```json", "").replace("```", "").strip()
                deployment_data = json.loads(deployment_data)
            except Exception:
                deployment_data = {}

        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.ENGINEER,
            message_type=MessageType.TASK,
            payload=deployment_data,
        )
