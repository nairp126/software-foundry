from typing import Dict, Any, Optional
import json
import re
from datetime import datetime
from foundry.agents.base import Agent, AgentType, AgentMessage, MessageType
from foundry.llm.factory import LLMProviderFactory
from foundry.llm.base import LLMMessage
from foundry.utils.parsing import extract_json_from_text
from foundry.config import settings
import logging

logger = logging.getLogger(__name__)

class ArchitectAgent(Agent):
    """
    Architect Agent responsible for system design and technology selection.
    """

    def _extract_json(self, content: str) -> Dict[str, Any]:
        """Robuster JSON extraction using utility."""
        parsed = extract_json_from_text(content)
        if isinstance(parsed, dict):
            return parsed
            
        # Fallback if parsing fails
        return {
            "project_name": "Architecture Draft",
            "tech_stack": {"backend": "Target Framework", "language": "Target Language"},
            "file_structure": ["src/main.py"],
            "raw_content": content[:500] if content else ""
        }

    def _normalize_json(self, content: str) -> str:
        """Kept for backward internal compatibility; preferred _extract_json."""
        data = self._extract_json(content)
        return json.dumps(data)

    def __init__(self, model_name: Optional[str] = None):
        model_name = model_name or settings.ollama_model_name
        super().__init__(AgentType.ARCHITECT, model_name)
        self.llm = LLMProviderFactory.create_provider(model_name=model_name)
        
        # Knowledge Graph integration for architecture decisions
        try:
            from foundry.tools.knowledge_graph_tools import KnowledgeGraphTools
            self.kg_tools = KnowledgeGraphTools()
        except ImportError:
            self.kg_tools = None

    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.message_type == MessageType.TASK:
            prd = message.payload.get("prd", "")
            requirements = message.payload.get("requirements", "")
            language = message.payload.get("language", "python")
            framework = message.payload.get("framework", "")
            project_id = message.payload.get("project_id", "unknown")
            feedback = message.payload.get("feedback", "")
            existing_architecture = message.payload.get("existing_architecture", "")
            if not prd:
                return None
            return await self.design_architecture(
                prd, requirements, language, framework, project_id, 
                existing_architecture=existing_architecture, 
                feedback=feedback
            )
        return None

    async def design_architecture(
        self, 
        prd_content: str, 
        requirements: str = "", 
        language: str = "python", 
        framework: str = "", 
        project_id: str = "unknown",
        existing_architecture: Any = None,
        feedback: str = ""
    ) -> AgentMessage:
        """
        Design system architecture based on PRD.
        """
        from foundry.utils.language_config import get_language_config
        lang_config = get_language_config(language)
        lang_name = lang_config.name.title()
        web_framework = framework or (lang_config.web_frameworks[0] if lang_config.web_frameworks else "")
        coding_standard = lang_config.coding_standard

        # Fetch architectural patterns from KG if available (Fix ARCH-Patterns)
        kg_context = ""
        if self.kg_tools:
            try:
                patterns = await self.kg_tools.get_successful_patterns(language, web_framework)
                if patterns:
                    kg_context = "\nPAST SUCCESSFUL PATTERNS FROM KG:\n"
                    for p in patterns:
                        snippet = (p.get("code_snippet") or "")[:300]
                        kg_context += f"- [{p.get('name')}] {p.get('description')}\n  Snippet: {snippet}\n"
            except Exception as e:
                logger.warning(f"Failed to fetch patterns from KG: {e}")

        grounding_anchor = f"\nABSOLUTE DOMAIN: {requirements}\n" if requirements else ""
        system_prompt = (
            f"You are an expert {lang_name} System Architect.{grounding_anchor}\n"
            f"{kg_context}\n"
            f"Design a robust, scalable system architecture based on the provided PRD.\n\n"
            f"Target language: {lang_name}\n"
            f"Preferred framework: {web_framework}\n"
            f"Coding standard: {coding_standard}\n\n"
            "The Architecture Design should include:\n"
            "1. High-Level Architecture (Monolith vs Microservices, Client/Server)\n"
            "2. Technology Stack Selection (use the target language and framework above)\n"
            "3. Database Schema Design (Entities and Relationships)\n"
            "4. API Interface Definition (Endpoints)\n"
            f"5. File Structure (use {lang_config.extensions[0]} extensions for source files)\n\n"
            "Return the result as a JSON object strictly following this template:\n"
            "{\n"
            '  "high_level_design": "Overall system pattern",\n'
            '  "tech_stack": {"backend": "...", "database": "..."},\n'
            '  "data_model": [{"entity": "Name", "attributes": ["attr1"]}],\n'
            '  "api_endpoints": [{"path": "/...", "method": "GET", "description": "..."}],\n'
            '  "file_structure": ["path/to/file.ext"]\n'
            "}"
        )

        user_prompt = f"Design the architecture for the following PRD:\n\n{prd_content}"
        
        if feedback and existing_architecture:
            user_prompt = f"""
            The user has REJECTED the previous architecture design. 
            Update the existing architecture based on the user's feedback.

            USER FEEDBACK:
            {feedback}

            EXISTING ARCHITECTURE:
            {json.dumps(existing_architecture, indent=2) if isinstance(existing_architecture, dict) else str(existing_architecture)}

            PRD FOR CONTEXT:
            {prd_content}
            """

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]

        # Two-pass validation: self-correct once if the output looks wrong, then validate again
        architecture_content = ""
        for attempt in range(2):
            response = await self.llm.generate(messages, temperature=0.2)
            architecture_content = response.content
            try:
                # Use robust extraction
                arch_dict = self._extract_json(architecture_content)
                # Schema Validation & Auto-fix
                arch_dict = self._validate_and_fix_arch_schema(arch_dict, language, web_framework)
                architecture_content = json.dumps(arch_dict, indent=2)
                break
            except Exception:
                if attempt == 1:
                    # Final fallback
                    architecture_content = self._language_fallback_architecture(prd_content, language, lang_name, web_framework)
                else:
                    # Trigger self-correction
                    messages.append(LLMMessage(role="assistant", content=architecture_content))
                    messages.append(LLMMessage(
                        role="user",
                        content=(
                            f"The previous response was not valid JSON. "
                            f"Please rewrite the architecture as a valid JSON object for a "
                            f"{lang_name} project using {web_framework}."
                        )
                    ))

        # Apply sanitization ONLY to cross-language legacy overrides (Cross-Lang Gate)
        # If it's a Python project, we may want to ensure we don't accidentally leak Node logic
        # if the Architect got confused, but we must NOT do this for other languages.
        if language.lower() == "python":
            architecture_content = self._sanitize_architecture_for_engineer(architecture_content)

        # Parse final architecture to dictionary for the Engineer (HIGH-ARCH-2)
        final_arch_dict = self._extract_json(architecture_content)

        # KG: store architecture decision (Req 16.3)
        if self.kg_tools:
            try:
                from foundry.services.knowledge_graph import knowledge_graph_service
                await knowledge_graph_service.store_architecture_decision(
                    project_id=project_id,
                    title=f"Architecture for {lang_name} project",
                    decision=architecture_content[:3000],
                    rationale=f"Generated by ArchitectAgent using {web_framework}",
                    language=language,
                    framework=web_framework,
                )
                # KG: store as a reusable pattern (Req 16.5)
                await knowledge_graph_service.store_pattern(
                    project_id=project_id,
                    name=final_arch_dict.get("high_level_design") or f"Standard {lang_name} {web_framework} Pattern",
                    description=f"Architecture pattern for {lang_name} using {web_framework}",
                    language=language,
                    code_snippet=architecture_content[:2000],
                )
            except Exception as e:
                logger.warning(f"Architect Agent KG store failed: {e}")

        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.ENGINEER,
            message_type=MessageType.TASK,
            payload={
                "architecture": final_arch_dict, 
                "prd": prd_content,
                "language": language,
                "framework": web_framework,
                "project_id": project_id
            }
        )

    async def _architect_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Node for Architect agent. Kept for LangGraph."""
        return {}

    def _validate_and_fix_arch_schema(self, arch: Dict[str, Any], language: str, framework: str) -> Dict[str, Any]:
        """Ensures the architecture has critical fields for the engineer."""
        required_fields = {
            "high_level_design": "Standard monolothic architecture",
            "tech_stack": {"language": language, "framework": framework},
            "data_model": [],
            "api_endpoints": [],
            "file_structure": []
        }
        
        for field, default in required_fields.items():
            if field not in arch or not arch[field]:
                arch[field] = default
        
        # If file_structure is empty, try to hallucinate a basic one based on tech stack
        if not arch["file_structure"]:
            ext = ".py" if language.lower() == "python" else ".js"
            arch["file_structure"] = [f"src/main{ext}", f"src/models{ext}", "requirements.txt" if language.lower() == "python" else "package.json"]
            
        return arch

    def _sanitize_architecture_for_engineer(self, arch_str: str) -> str:
        """Translates JS terms for Python-only projects."""
        replacements = {
            "React": "Python/Jinja2", "Next.js": "FastAPI", "node.js": "Python",
            "TypeScript": "Python", "JavaScript": "Python", "npm install": "pip install",
            "package.json": "requirements.txt", "webpack": "Python build", "vite": "uvicorn",
            "express": "FastAPI", "Express": "FastAPI", "Vue": "Python/HTMX",
            "Mongoose": "SQLAlchemy", "MongoDB": "PostgreSQL"
        }
        for js_term, py_term in replacements.items():
            arch_str = re.sub(re.escape(js_term), py_term, arch_str, flags=re.IGNORECASE)
        arch_str = re.sub(r'\.(js|ts|jsx|tsx|css|html)\b', '.py', arch_str)
        return arch_str

    def _language_fallback_architecture(self, prd: str, language: str = "python", lang_name: str = "Python", web_framework: str = "fastapi") -> str:
        """Generate a language-aware fallback architecture when LLM output is unparseable."""
        from foundry.utils.language_config import get_language_config
        lang_config = get_language_config(language)
        ext = lang_config.extensions[0]
        package_file = lang_config.package_file
        return (
            '{\n'
            f'  "projectName": "{lang_name} Fallback Project",\n'
            f'  "techStack": {{"backend": "{web_framework}", "language": "{lang_name}"}},\n'
            f'  "fileStructure": {{"src": ["main{ext}", "models{ext}", "utils{ext}"], "root": ["{package_file}", "README.md"]}}\n'
            '}'
        )

    def _python_fallback_architecture(self, prd: str) -> str:
        return self._language_fallback_architecture(prd, "python", "Python", "fastapi")

    async def organize_file_structure(self, architecture: Dict[str, Any], tech_stack: Dict[str, str]) -> Dict[str, Any]:
        """
        Generate file structure following best practices for the selected technology stack.
        
        Args:
            architecture: System architecture design
            tech_stack: Selected technology stack (frontend, backend, database, etc.)
            
        Returns:
            Dictionary containing file structure with paths and descriptions
        """
        system_prompt = """You are an expert in software project organization and best practices.
        Generate a comprehensive file structure that follows industry best practices for the given technology stack.
        
        Consider:
        - Separation of concerns (MVC, Clean Architecture, etc.)
        - Configuration management (environment files, config directories)
        - Testing structure (unit, integration, e2e tests)
        - Documentation placement (README, API docs, architecture docs)
        - Build and deployment files (Dockerfile, CI/CD configs)
        - Code organization patterns specific to the framework/language
        
        Return a JSON object with this structure:
        {
            "root_structure": {
                "directories": [
                    {
                        "path": "src/",
                        "purpose": "Main source code directory",
                        "subdirectories": [...]
                    }
                ],
                "files": [
                    {
                        "path": "README.md",
                        "purpose": "Project documentation",
                        "template": "basic"
                    }
                ]
            },
            "conventions": {
                "naming": "kebab-case for files, PascalCase for classes",
                "structure_pattern": "Feature-based organization",
                "test_location": "Co-located with source files"
            }
        }
        """
        
        user_prompt = f"""Generate file structure for:
        
Architecture:
{json.dumps(architecture, indent=2)}

Technology Stack:
{json.dumps(tech_stack, indent=2)}
"""
        
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        response = await self.llm.generate(messages, temperature=0.5)
        
        try:
            result = json.loads(response.content)
            # Ensure conventions is never empty — populate defaults if missing or empty
            if not result.get("conventions"):
                result["conventions"] = {
                    "naming": "snake_case for files, PascalCase for classes",
                    "structure_pattern": "Feature-based organization",
                    "test_location": "Co-located with source files",
                }
            return result
        except json.JSONDecodeError:
            return {
                "root_structure": {"directories": [], "files": []},
                "conventions": {
                    "naming": "snake_case for files, PascalCase for classes",
                    "structure_pattern": "Feature-based organization",
                    "test_location": "Co-located with source files",
                },
            }

    async def document_architectural_decisions(
        self, 
        architecture: Dict[str, Any], 
        tech_stack: Dict[str, str],
        requirements: str
    ) -> Dict[str, Any]:
        """
        Create architectural decision documentation with rationale and trade-offs.
        
        Args:
            architecture: System architecture design
            tech_stack: Selected technology stack
            requirements: Original requirements from PRD
            
        Returns:
            Dictionary containing architectural decision records (ADRs)
        """
        system_prompt = """You are an expert software architect documenting architectural decisions.
        Create comprehensive Architectural Decision Records (ADRs) following the standard format.
        
        For each major decision, document:
        1. Context: What is the issue we're addressing?
        2. Decision: What is the change we're proposing/doing?
        3. Rationale: Why did we choose this approach?
        4. Consequences: What are the positive and negative outcomes?
        5. Alternatives Considered: What other options were evaluated?
        6. Trade-offs: What are we optimizing for vs sacrificing?
        
        Return a JSON array of ADRs with this structure:
        {
            "decisions": [
                {
                    "id": "ADR-001",
                    "title": "Database Choice",
                    "status": "accepted",
                    "context": "Need to store relational data for the application...",
                    "decision": "Use PostgreSQL for data persistence",
                    "rationale": "Strong consistency, relational features, and team familiarity.",
                    "consequences": {
                        "positive": ["Reliability", "ACID compliance"],
                        "negative": ["Slightly higher setup complexity"]
                    },
                    "alternatives": ["SQLite", "MongoDB"],
                    "trade_offs": {
                        "optimizing_for": ["Data integrity", "Scalability"],
                        "sacrificing": ["Initial development speed"]
                    }
                }
            ]
        }
        """
        
        user_prompt = f"""Document architectural decisions for:

Requirements:
{requirements}

Architecture:
{json.dumps(architecture, indent=2)}

Technology Stack:
{json.dumps(tech_stack, indent=2)}

Focus on major decisions like:
- Architecture pattern choice (monolith vs microservices)
- Technology stack selections
- Database choice
- API design approach
- Deployment strategy
"""
        
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        response = await self.llm.generate(messages, temperature=0.6)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"decisions": []}

    async def track_rationale_and_tradeoffs(
        self,
        decision_id: str,
        decision_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Track detailed rationale and trade-offs for a specific architectural decision.
        
        Args:
            decision_id: Unique identifier for the decision
            decision_context: Context information about the decision
            
        Returns:
            Dictionary containing detailed rationale and trade-off analysis
        """
        system_prompt = """You are an expert at analyzing architectural trade-offs.
        Provide a detailed analysis of the rationale and trade-offs for the given decision.
        
        Consider:
        - Performance implications
        - Scalability considerations
        - Maintainability impact
        - Cost implications (development and operational)
        - Team expertise and learning curve
        - Time-to-market impact
        - Security considerations
        - Flexibility for future changes
        
        Return a JSON object with this structure:
        {
            "decision_id": "ADR-001",
            "rationale": {
                "primary_drivers": ["Performance", "Scalability"],
                "detailed_reasoning": "Detailed explanation...",
                "supporting_evidence": ["Benchmark data", "Industry practices"]
            },
            "trade_offs": {
                "dimensions": [
                    {
                        "dimension": "Performance",
                        "impact": "positive",
                        "score": 8,
                        "explanation": "Optimized for high throughput..."
                    },
                    {
                        "dimension": "Complexity",
                        "impact": "negative",
                        "score": -3,
                        "explanation": "Introduces additional operational overhead..."
                    }
                ],
                "overall_assessment": "Net positive with manageable complexity",
                "risk_factors": ["Operational complexity", "Team learning curve"]
            },
            "future_implications": {
                "enables": ["Horizontal scaling", "Independent deployments"],
                "constrains": ["Requires distributed tracing", "More complex debugging"]
            }
        }
        """
        
        user_prompt = f"""Analyze rationale and trade-offs for:

Decision ID: {decision_id}

Context:
{json.dumps(decision_context, indent=2)}
"""
        
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        response = await self.llm.generate(messages, temperature=0.6)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {
                "decision_id": decision_id,
                "rationale": {},
                "trade_offs": {},
                "future_implications": {}
            }

    async def generate_comprehensive_design(self, prd_content: str) -> Dict[str, Any]:
        """
        Generate a comprehensive design including architecture, file structure, and ADRs.
        
        Args:
            prd_content: Product Requirements Document content
            
        Returns:
            Complete design package with all documentation
        """
        # First, generate the base architecture
        architecture_message = await self.design_architecture(prd_content)
        architecture = architecture_message.payload.get("architecture", {})
        
        # Parse architecture if it's a string
        if isinstance(architecture, str):
            try:
                # CLEANING: Strip markdown backticks
                architecture = architecture.replace("```json", "").replace("```", "").strip()
                architecture = json.loads(architecture)
            except json.JSONDecodeError:
                architecture = {"raw": architecture}
        
        # Extract tech stack from architecture
        tech_stack = architecture.get("technology_stack", {})
        
        # Generate file structure
        file_structure = await self.organize_file_structure(architecture, tech_stack)
        
        # Generate architectural decision records
        adrs = await self.document_architectural_decisions(architecture, tech_stack, prd_content)
        
        # Compile comprehensive design
        comprehensive_design = {
            "architecture": architecture,
            "file_structure": file_structure,
            "architectural_decisions": adrs,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "agent": str(self.agent_type),
                "model": self.model_name
            }
        }
        
        return comprehensive_design


