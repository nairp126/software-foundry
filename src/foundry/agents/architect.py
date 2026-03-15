from typing import Dict, Any, Optional
import json
import re
from datetime import datetime
from foundry.agents.base import Agent, AgentType, AgentMessage, MessageType
from foundry.llm.factory import LLMProviderFactory
from foundry.llm.base import LLMMessage
from foundry.config import settings

class ArchitectAgent(Agent):
    """
    Architect Agent responsible for system design and technology selection.
    """

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
            requirements = message.payload.get("requirements", "") # Fix L
            if not prd:
                return None
            return await self.design_architecture(prd, requirements)
        return None

    async def design_architecture(self, prd_content: str, requirements: str = "") -> AgentMessage:
        """
        Design system architecture based on PRD.
        """
        # Fix L: System-level Grounding
        grounding_anchor = f"\nABSOLUTE DOMAIN: {requirements}\n" if requirements else ""
        system_prompt = f"""You are an expert System Architect.{grounding_anchor}
        Your goal is to design a robust, scalable system architecture based on the provided Product Requirements Document (PRD).

        ABSOLUTE SYSTEM REQUIREMENT: You are a PYTHON-ONLY ARCHITECT. 
        YOU ARE PROHIBITED FROM SUGGESTING ANY NON-PYTHON TECHNOLOGIES.

        MANDATORY TECH STACK (ONLY USE THESE):
        - Backend: FastAPI, Flask, or Django (Python 3.11+)
        - Web Server: Uvicorn or Gunicorn
        - Database: PostgreSQL, Redis, or DynamoDB (using Python clients like boto3 or psycopg2)
        - UI/Frontend: If UI is needed, suggest Jinja2 templates, HTMX, or server-side rendering logic in Python.

        STRICTLY PROHIBITED (DO NOT USE):
        - NO Node.js, NO Express.
        - NO React, NO Vue, NO Angular.
        - NO NPM, NO Yarn.
        - NO JavaScript or TypeScript libraries.

        The Architecture Design should include:
        1. High-Level Architecture (Monolith vs Microservices, Client/Server)
        2. Technology Stack Selection (Must be strictly Python-based)
        3. Database Schema Design (Entities and Relationships)
        4. API Interface Definition (Endpoints)
        5. File Structure (Must use strictly .py extensions)

        Return the result as a JSON object.
        """

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"Design the architecture for the following PRD:\n\n{prd_content}")
        ]

        # MULTI-PASS VALIDATION: Ensure the architecture is strictly Pythonic
        valid_architecture = False
        attempts = 0
        architecture_content = ""
        
        while not valid_architecture and attempts < 2:
            attempts += 1
            response = await self.llm.generate(messages, temperature=0.2)
            architecture_content = response.content
            
            if not self._is_non_python_stack(architecture_content):
                valid_architecture = True
            else:
                print(f"CRITICAL: Non-Python architecture detected (Attempt {attempts}). Triggering Self-Correction...")
                # Update messages for correction pass
                correction_prompt = f"CRITICAL ERROR: You suggested a non-Python tech stack. REWRITE this design to be 100% PYTHON (FastAPI/Flask/SQL). ABSOLUTELY NO Node, React, or JS.\n\nInvalid Design:\n{architecture_content}"
                messages.append(LLMMessage(role="assistant", content=architecture_content))
                messages.append(LLMMessage(role="user", content=correction_prompt))

        # Final Hard-Fail: If still JS after attempts, use fallback
        if not valid_architecture:
            print("Architect Self-Correction failed. Using Hardened Python Fallback Template.")
            architecture_content = self._python_fallback_architecture(prd_content)

        # Fix 1: Final sanitization pass to translate any remaining terms
        architecture_content = self._sanitize_architecture_for_engineer(architecture_content)

        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.ENGINEER,
            message_type=MessageType.TASK,
            payload={"architecture": architecture_content, "prd": prd_content}
        )

    def _is_non_python_stack(self, content: str) -> bool:
        """Checks if the architecture contains forbidden technologies."""
        forbidden = ["node.js", "express.js", "react.js", "npm ", "yarn ", "mongodb", "next.js", "typescript"]
        lower_content = content.lower()
        return any(f in lower_content for f in forbidden)

    async def _self_correct_architecture(self, dirty_arch: str, prd: str) -> str:
        """Forces the Architect to rewrite the design using Python."""
        system_prompt = """CRITICAL ERROR: You suggested a non-Python tech stack (Node/React/JS). 
        You MUST rewrite this design to be 100% PYTHON-BASED.
        - Use FastAPI or Flask for Backend.
        - Use PostgreSQL or Redis for Database.
        - Use Jinja2/HTMX for UI (if needed).
        - Use strictly .py extensions.
        - ABSOLUTELY NO JavaScript, Node, or React.
        """
        user_prompt = f"Original PRD:\n{prd}\n\nInvalid Non-Python Design to fix:\n{dirty_arch}"
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        response = await self.llm.generate(messages, temperature=0.1)
        return response.content

    def _sanitize_architecture_for_engineer(self, arch_str: str) -> str:
        """
        Translates JS terms and FORCE-RENAMES extensions inside the arch JSON.
        """
        # 1. Term replacements
        replacements = {
            "React": "Python/Jinja2", "Next.js": "FastAPI", "node.js": "Python",
            "TypeScript": "Python", "JavaScript": "Python", "npm install": "pip install",
            "package.json": "requirements.txt", "webpack": "Python build", "vite": "uvicorn",
            "express": "FastAPI", "Express": "FastAPI", "Vue": "Python/HTMX",
            "Mongoose": "SQLAlchemy", "MongoDB": "PostgreSQL"
        }
        for js_term, py_term in replacements.items():
            arch_str = re.sub(re.escape(js_term), py_term, arch_str, flags=re.IGNORECASE)
        
        # 2. Path/Extension replacements: Force ".js" to ".py" inside the JSON
        arch_str = re.sub(r'\.(js|ts|jsx|tsx|css|html)\b', '.py', arch_str)
        
        return arch_str

    def _python_fallback_architecture(self, prd: str) -> str:
        return f"""
{{
  "projectName": "Python Fallback Project",
  "techStack": {{ "backend": "FastAPI", "database": "SQLite", "language": "Python 3.11" }},
  "fileStructure": {{ "src": ["main.py", "models.py", "utils.py"], "root": ["requirements.txt", "README.md"] }}
}}
"""

    def _is_non_python_stack(self, content: str) -> bool:
        """Expanded case-insensitive forbidden list."""
        forbidden = [
            "node.js", "express.js", "react.js", "npm ", "yarn ", "mongodb", "next.js", 
            "typescript", "vue.js", "angular", "webpack", "vite", ".jsx", ".tsx", 
            "package.json", "node_modules", "javascript", "react-dom", "react-router",
            "nodejs", "expressjs", "reactjs", "nextjs", "vuejs"
        ]
        lower_content = content.lower()
        if any(f in lower_content for f in forbidden):
            return True
        # Final check for ".js" or ".ts" extensions in the text
        if re.search(r'\.(js|ts|jsx|tsx)\b', lower_content):
            return True
        return False

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
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"root_structure": {"directories": [], "files": []}, "conventions": {}}

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
                    "title": "Selection of React for Frontend",
                    "status": "accepted",
                    "context": "Need a modern, component-based UI framework...",
                    "decision": "Use React with TypeScript for frontend development",
                    "rationale": "Large ecosystem, strong typing, team expertise...",
                    "consequences": {
                        "positive": ["Fast development", "Rich ecosystem"],
                        "negative": ["Learning curve for new developers"]
                    },
                    "alternatives": ["Vue.js", "Angular", "Svelte"],
                    "trade_offs": {
                        "optimizing_for": ["Developer productivity", "Maintainability"],
                        "sacrificing": ["Bundle size", "Initial learning curve"]
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


