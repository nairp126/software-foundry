import json
import re
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
    "go": "golang:1.21-alpine",
    "rust": "rust:1.75-slim",
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
            image = get_language_config(lang_key).base_image
            logger.warning("Unknown language %r — falling back to base image %r from Language_Config.", language, image)
            return image
        except Exception:
            return "python:3.11-slim"

    async def process_message(self, message: AgentMessage) -> AgentMessage:
        if message.message_type == MessageType.TASK:
            architecture = message.payload.get("architecture")
            code_repo = message.payload.get("code_repo")
            language = message.payload.get("language", "python")
            project_id = message.payload.get("project_id")
            return await self.prepare_deployment(architecture, code_repo, language, project_id)
        return None

    async def prepare_deployment(
        self,
        architecture: Dict[str, Any],
        code_repo: Optional[Dict[str, str]] = None,
        language: str = "python",
        project_id: Optional[str] = None
    ) -> AgentMessage:
        """
        Generates deployment configurations (Dockerfile, docker-compose.yml, etc).
        """
        base_image = self._select_base_image(language, code_repo)

        # Context Extraction (Req 21.1 / BUG-DEV-1)
        file_list = []
        deps_content = ""
        if code_repo:
            file_list = list(code_repo.keys())
            # Try to find dependency files for better Docker layer caching
            dep_files = ["requirements.txt", "package.json", "pom.xml", "build.gradle"]
            for f in dep_files:
                if f in code_repo:
                    deps_content += f"\nFILE: {f}\n{code_repo[f][:1000]}\n"

        system_prompt = f"""You are an expert DevOps Engineer.
        Generate deployment configuration files for a {language} project.
        
        BASE IMAGE: {base_image}
        
        CRITICAL: Use the provided File List and Dependency Context to ensure the Dockerfile 
        correctly handles the project structure and dependency management for {language}.
        
        You MUST generate the following files:
        1. `Dockerfile`: Optimized for production (multi-stage build if applicable).
        2. `docker-compose.yml`: For the app + dependencies (DB, Redis, etc) from architecture.
        3. `.dockerignore`: To exclude venv, node_modules, .git, etc.
        4. `.env.example`: Template for environment variables.

        Return ONLY a JSON object. 
        IMPORTANT: All internal double quotes (e.g., in Docker CMD or ENTRYPOINT) MUST be escaped with a backslash (\\\").
        
        Example Output:
        {{
            \"Dockerfile\": \"FROM python:3.11\\nCMD [\\\"python\\\", \\\"app.py\\\"]\",
            \"docker-compose.yml\": \"...\",
            \".dockerignore\": \"...\",
            \".env.example\": \"...\",
            \"explanation\": \"...\"
        }}
        """

        user_prompt = f"""
        Architecture: {json.dumps(architecture, indent=2)}
        
        Files in Repository: {", ".join(file_list)}
        
        Dependency Context:
        {deps_content}
        """

        max_retries = 2
        attempt_num = 0
        deployment_data = {}
        
        while attempt_num < max_retries:
            attempt_num += 1
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt)
            ]
            
            if attempt_num > 1:
                messages.append(LLMMessage(
                    role="user", 
                    content="CRITICAL: Your previous response was not valid JSON. Return ONLY the requested JSON object without any preamble or markdown code blocks backticks."
                ))

            response = await self.llm.generate(messages, temperature=0.2, json_mode=True)
            
            # Robust JSON Parsing (BUG-DEV-2)
            try:
                content = response.content
                if not content:
                    raise ValueError("Empty response from LLM")
                    
                if "```" in content:
                    content = re.sub(r'```[a-z]*\n|```', '', content).strip()
                
                if isinstance(content, str):
                    deployment_data = json.loads(content)
                else:
                    deployment_data = content
                    
                logger.info(f"DevOpsAgent successfully generated {len(deployment_data.keys())} files on attempt {attempt_num}.")
                break # Success
            except json.JSONDecodeError as je:
                logger.error(f"DevOps Agent JSON syntax error on attempt {attempt_num} at line {je.lineno} col {je.colno}: {je.msg}")
                if attempt_num == max_retries:
                    deployment_data = {
                        "error": f"JSON syntax error: {str(je)}",
                        "raw_response": response.content[:1000] if response else "No response"
                    }
            except Exception as e:
                logger.error(f"DevOps Agent failed to parse deployment JSON on attempt {attempt_num}: {e}")
                if attempt_num == max_retries:
                    deployment_data = {
                        "error": f"General parsing failure: {str(e)}",
                        "raw_response": response.content[:1000] if response else "No response"
                    }

        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.ORCHESTRATOR,
            message_type=MessageType.TASK,
            payload=deployment_data,
        )
