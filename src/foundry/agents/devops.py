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
        try:
            from foundry.tools.knowledge_graph_tools import KnowledgeGraphTools
            self.kg_tools = KnowledgeGraphTools()
        except ImportError:
            self.kg_tools = None

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
            entry_point = message.payload.get("entry_point", "main.py")
            return await self.prepare_deployment(architecture, code_repo, language, project_id, entry_point)
        return None

    async def prepare_deployment(
        self,
        architecture: Dict[str, Any],
        code_repo: Optional[Dict[str, str]] = None,
        language: str = "python",
        project_id: Optional[str] = None,
        entry_point: str = "main.py"
    ) -> AgentMessage:
        """
        Generates deployment configurations (Dockerfile, docker-compose.yml, etc).
        """
        base_image = self._select_base_image(language, code_repo)

        # 1. Context Extraction (Req 21.1 / BUG-DEV-1)
        file_list = []
        deps_content = ""
        if code_repo:
            file_list = list(code_repo.keys())
            # Try to resolve entry point deterministically
            from foundry.tools.import_resolver import ImportResolver
            entry_point = ImportResolver.discover_entry_point(code_repo)
            
            # Try to find dependency files for better Docker layer caching
            dep_files = ["requirements.txt", "package.json", "pom.xml", "build.gradle"]
            for f in dep_files:
                if f in code_repo:
                    deps_content += f"\nFILE: {f}\n{code_repo[f][:1000]}\n"

        # 2. KG Grounding (Fix: Blind Tool Access)
        kg_project_context = ""
        if self.kg_tools and project_id:
            try:
                kg_project_context = await self.kg_tools.get_project_summary_for_generation(project_id)
            except Exception as e:
                logger.warning(f"DevOps KG context retrieval failed: {e}")

        system_prompt = f"""You are an expert DevOps Engineer.
        {kg_project_context}

        CRITICAL: Use the provided File List and Dependency Context to ensure the Dockerfile 
        correctly handles the project structure and dependency management for {language}.
        The resolved ENTRY POINT for this application is: {entry_point}
        
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
        
        Entry Point: {entry_point}
        
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
            # DETERMINISTIC FALLBACK: If LLM failed, generate basic but correct deployment files
        if "error" in deployment_data:
            logger.warning("LLM-based deployment generation failed. Using deterministic fallback.")
            dep_install = "pip install --no-cache-dir -r requirements.txt" if language == "python" else "npm install"
            dep_file = "requirements.txt" if language == "python" else "package.json"
            run_cmd = f'["python", "{entry_point}"]' if language == "python" else f'["node", "{entry_point}"]'
            
            deployment_data = {
                "Dockerfile": (
                    f"FROM {base_image}\n"
                    f"WORKDIR /app\n"
                    f"COPY {dep_file} .\n"
                    f"RUN {dep_install}\n"
                    f"COPY . .\n"
                    f"EXPOSE 8000\n"
                    f"CMD {run_cmd}\n"
                ),
                "docker-compose.yml": (
                    f"version: '3.8'\n"
                    f"services:\n"
                    f"  app:\n"
                    f"    build: .\n"
                    f"    ports:\n"
                    f"      - '8000:8000'\n"
                    f"    env_file:\n"
                    f"      - .env\n"
                ),
                ".dockerignore": (
                    "venv/\n.venv/\n__pycache__/\n*.pyc\n.git/\n"
                    ".env\nnode_modules/\n.pytest_cache/\n"
                ),
                ".env.example": (
                    "# Application Environment Variables\n"
                    "APP_ENV=production\n"
                    "APP_PORT=8000\n"
                    "DATABASE_URL=sqlite:///data.db\n"
                ),
                "explanation": "Deterministic fallback — LLM JSON generation failed."
            }

        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.ORCHESTRATOR,
            message_type=MessageType.TASK,
            payload=deployment_data,
        )
