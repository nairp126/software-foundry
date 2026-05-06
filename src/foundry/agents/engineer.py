from typing import Dict, Any, Optional, List, Tuple
import json
import os
import re
import asyncio
import logging
from foundry.agents.base import Agent, AgentType, AgentMessage, MessageType
from foundry.llm.factory import LLMProviderFactory
from foundry.llm.base import LLMMessage
from foundry.testing.test_generator import TestGenerator, TestFramework
from foundry.testing.quality_gates import QualityGates
from foundry.graph.ingestion import IngestionPipeline
from foundry.tools.import_resolver import ImportResolver
from foundry.config import settings
from foundry.metrics import SurgicalContextMetrics, MetricsCollector
import time


logger = logging.getLogger(__name__)

class EngineerAgent(Agent):
    """
    Engineering Agent responsible for code generation with code quality and security measures.
    
    Implements:
    - Consistent naming conventions and coding standards enforcement
    - Error handling and input validation generation
    - Security best practices integration
    - Component integration and dependency management
    """
    
    # Language-specific coding standards
    CODING_STANDARDS = {
        "python": "PEP 8",
        "javascript": "ESLint Standard",
        "typescript": "ESLint + TypeScript Strict",
        "java": "Google Java Style",
        "go": "Effective Go",
        "rust": "Rust Style Guide",
    }
    
    # Security patterns to enforce
    SECURITY_PATTERNS = {
        "input_validation": True,
        "sql_injection_prevention": True,
        "xss_protection": True,
        "secure_authentication": True,
        "input_sanitization": True,
        "error_message_sanitization": True,
    }
    
    # Fix 2: Comprehensive JS Detection Regex
    JS_PATTERNS = re.compile(
        r'\b(const |let |var |require\(|import React|express\(\)|module\.exports|'
        r'export default|npm install|\.then\(|\.catch\(|document\.|window\.|'
        r'addEventListener|async function\s+\w+\s*\(|=>\s*\{|\.jsx?["\'])',
        re.MULTILINE | re.IGNORECASE
    )

    def _has_js_leakage(self, code: str) -> bool:
        """Returns True if the code contains JavaScript-specific syntax."""
        return bool(self.JS_PATTERNS.search(code))

    def __init__(self, model_name: Optional[str] = None):
        super().__init__(AgentType.ENGINEER, model_name)
        self.llm = LLMProviderFactory.create_provider(model_name=self.model_name)
        self.test_generator = TestGenerator(self.model_name)
        self.quality_gates = QualityGates()
        
        # Knowledge Graph integration for context-aware code generation
        try:
            from foundry.tools.knowledge_graph_tools import KnowledgeGraphTools
            if settings.enable_kg:
                self.kg_tools = KnowledgeGraphTools()
                self.ingestion_pipeline = IngestionPipeline()
            else:
                logger.info("KG integration disabled via configuration.")
                self.kg_tools = None
                self.ingestion_pipeline = None
        except ImportError:
            self.kg_tools = None
            self.ingestion_pipeline = None
        
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.message_type == MessageType.TASK:
            architecture = message.payload.get("architecture", "")
            prd = message.payload.get("prd", "")
            requirements = message.payload.get("requirements", "")
            fix_instructions = message.payload.get("fix_instructions", "")
            existing_code = message.payload.get("existing_code", {})
            graph_state_language = message.payload.get("language", "")

            if not architecture:
                return None
            return await self.generate_code(
                architecture, prd, requirements, fix_instructions, existing_code,
                message.payload.get("project_id", "current"),
                graph_state_language=graph_state_language,
            )
        return None

    async def _request_code_generation(self, filename: str, architecture: str, language: str, coding_standard: str, prd: str = "", requirements: str = "", context: str = "", fix_instructions: str = "", existing_version: str = None) -> str:
        """
        Internal method for code generation prompting.
        """
        # Fix L: Domain Grounding
        grounding_anchor = f"\nABSOLUTE DOMAIN: {requirements}\n" if requirements else ""
        
        # Root Cause 2 & 3 Fix: Inject project manifest/responsibility mapping
        project_manifest = ""
        if context:
            project_manifest = f"\nPROJECT STRUCTURE & RESPONSIBILITIES:\n{context}\n"
        
        # Fix: Architectural Guardrails - Inject mandatory imports
        required_imports_str = ""
        if context and "REQUIRED_IMPORTS:" in context:
            try:
                # Extract the imports specific to this file from the context block
                required_imports_str = f"\nCRITICAL: The Architect has mandated these specific imports for {filename}:\n{context.split('REQUIRED_IMPORTS:')[1].split('---')[0]}\nYou MUST include these at the top of the file.\n"
            except (IndexError, ValueError):
                logger.warning(f"Failed to parse required imports from context for {filename}")

        system_prompt = f"""You are an expert Software Engineer.{grounding_anchor}
        Your goal is to write high-quality, professional-grade code for the file: {filename}

        Language: {language}
        Coding Standard: {coding_standard}

        Requirements:
        - Follow {coding_standard} coding standards
        - Apply security best practices throughout
        - Include input validation for all external inputs
        - Add comprehensive error handling with try/except blocks
        - Use environment variables for secrets, never hardcode credentials
        - Write clean, readable, well-documented code
        - MANDATORY: Include comprehensive unit tests for all logic. Place tests in a 'tests/' directory.
        - SEPARATION OF CONCERNS: Do NOT redefine models, schemas, or database logic already defined in other files. Import them instead.
        - CRITICAL: Every function MUST contain real implementation logic. Using 'pass', 'TODO', or empty function bodies is STRICTLY FORBIDDEN.
        - COMPLETENESS CHECK: Before finishing each file, verify that EVERY function has a return statement or produces a side-effect. No function should be a no-op.
        - SYNTAX CHECK: Ensure the code is syntactically correct for {language}. Verify all 'if', 'for', 'while', 'def', and 'class' blocks are properly indented and have a body.
        {required_imports_str}

        {project_manifest}
        
        CRITICAL: Return ONLY the raw code for {filename}. 
        Do NOT include any introduction, explanations, or conclusions after the code.
        Do NOT include markdown fences in your internal logic, although your outer response should be a single clean code block.
        """

        if fix_instructions:
            user_prompt = f"Fix the following issues in {filename}:\n{fix_instructions}\n\nExisting code:\n{existing_version or ''}\n\nArchitecture:\n{architecture}"
        else:
            user_prompt = f"Generate the file {filename} for this architecture:\n{architecture}"
            if prd:
                user_prompt += f"\n\nProduct Requirements:\n{prd}"

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]
        response = await self.llm.generate(messages, temperature=0.2)
        return self._clean_code(response.content)
    async def generate_code(self, architecture_content: str, prd_content: str = "", requirements: str = "", fix_instructions: str = "", existing_code: Dict[str, str] = None, project_id: str = "current", graph_state_language: str = "") -> AgentMessage:
        """
        Generate code based on architecture with quality and security measures.
        """
        from foundry.utils.language_guards import detect_language_mismatch
        from foundry.utils.language_config import get_language_config

        # Step 1: Detect language from GraphState (Priority)
        language = self._detect_language(architecture_content, graph_state_language)
        lang_config = get_language_config(language)

        # Step 2: Plan file structure with detected language
        file_structure = await self._plan_file_structure(architecture_content, prd_content, language=language)

        # Step 3: Generate code for each file sequentially for stability
        generated_files = {}
        files_to_generate = self._parse_file_list(file_structure)
        
        # Initialize metrics collector
        self._metrics_collector = MetricsCollector(project_id)
        
        # Root Cause 1 Fix: Raise file cap to 50 to accommodate larger projects (Req 20.3)
        files_to_generate = files_to_generate[:50]  

        for i, file_obj in enumerate(files_to_generate):
            if isinstance(file_obj, dict):
                filename = file_obj.get("path", "")
                contract = file_obj.get("contract", "Implement according to standard architecture.")
            else:
                filename = str(file_obj)
                contract = "Implement according to standard architecture."
            
            if not filename: continue
            
            logger.info(f"Generating content for {filename} ({i+1}/{len(files_to_generate)})...")

            # KG: inject project summary and internal symbols into EVERY file's prompt (Req 16.1 / 19.3)
            kg_project_summary = ""
            if self.kg_tools:
                try:
                    kg_project_summary = await self.kg_tools.get_project_summary_for_generation(project_id)
                    
                    # Surgical Context Injection: Extract keywords from contract
                    keywords = []
                    if contract:
                        # Extract CamelCase and Snake_Case words as potential symbols
                        keywords = re.findall(r'\b[A-Z][a-zA-Z0-9]*\b|\b[a-z][a-z0-9_]*\b', contract)
                        # Filter out common English words and small words
                        stop_words = {'the', 'and', 'use', 'for', 'with', 'from', 'import', 'class', 'function', 'method'}
                        keywords = [kw for kw in keywords if len(kw) > 3 and kw.lower() not in stop_words]
                    
                    # ADDED: Explicit SURGICAL import recommendations from KG
                    kg_project_summary += await self.kg_tools.get_relevant_symbols(project_id, keywords)
                    
                    # Layered Architecture Guard Injection
                    layer_info = "\nARCHITECTURAL LAYER CONSTRAINTS:\n"
                    if "models" in filename or "schema" in filename:
                        layer_info += "- This is a CORE LAYER file. Do NOT import from services, routes, or main.\n"
                    elif "database" in filename:
                        layer_info += "- This is a PERSISTENCE LAYER file. Only import from models.\n"
                    elif "route" in filename or "app.py" in filename:
                        layer_info += "- This is an INTERFACE LAYER file. You may import models, schemas, and database.\n"
                    kg_project_summary += layer_info
                    
                except Exception as e:
                    logger.warning(f"KG project summary retrieval failed: {e}")

            # Inject required_imports from architecture into the context
            # Use basename matching to be flexible with paths (e.g., src/database.py matches database.py)
            required_imports = []
            if isinstance(architecture_content, dict):
                req_map = architecture_content.get("required_imports", {})
                base_filename = os.path.basename(filename)
                
                # Try exact match first, then basename match
                if filename in req_map:
                    required_imports = req_map[filename]
                elif base_filename in req_map:
                    required_imports = req_map[base_filename]
            
            if required_imports:
                kg_project_summary += f"\nREQUIRED_IMPORTS:\n" + "\n".join(required_imports) + "\n---"

            # Surgical Context Injection: Track efficiency for patent metrics
            current_metric = SurgicalContextMetrics(file_path=filename)
            
            code = await self._generate_file_content(
                filename,
                architecture_content,
                language,
                generated_files,
                prd_content,
                requirements,
                fix_instructions,
                existing_code.get(filename) if existing_code else None,
                project_id,
                kg_project_summary=kg_project_summary,
                file_contract=contract,
                metric=current_metric
            )

            # 3-Attempt Language-Aware Recovery Loop
            for attempt in range(3):
                if detect_language_mismatch(code, language):
                    logger.warning(f"Language mismatch in {filename} (attempt {attempt + 1}). Recovering...")
                    code = await self._recover_with_correct_language(filename, code, architecture_content, language)
                else:
                    break
            else:
                # All 3 attempts failed — generate a minimal stub
                logger.critical(f"All recovery attempts failed for {filename}. Generating stub.")
                code = (
                    f"# Auto-stub: generation failed for {filename}.\n"
                    f"raise NotImplementedError('{filename} requires manual implementation')\n"
                )

            generated_files[filename] = code
            
            # STUB DETECTION: Reject files with empty function bodies
            if language == "python":
                stubs = self._detect_stub_functions(code, filename)
                if stubs and not filename.endswith("__init__.py"):
                    logger.warning(f"Stub functions detected in {filename}: {stubs}. Re-generating with enforcement.")
                    code = await self._generate_file_content(
                        filename, architecture_content, language, generated_files,
                        prd_content, requirements + "\nCRITICAL: The previous generation contained empty function bodies (pass statements). You MUST implement the actual logic this time.",
                        "", existing_code.get(filename) if existing_code else None,
                        project_id
                    )
                    generated_files[filename] = code
                    
            if self.kg_tools and filename.endswith('.py'):
                from foundry.utils.code_fixer import apply_deterministic_fixes
                code = apply_deterministic_fixes(code, filename)
                generated_files[filename] = code

            # INCREMENTAL INGESTION (Graph-First Strategy)
            if self.ingestion_pipeline:
                try:
                    ingest_start = time.time()
                    ingest_stats = await self.ingestion_pipeline.ingest_source(
                        code=generated_files[filename],
                        file_path=filename,
                        project_id=project_id
                    )
                    current_metric.ingestion_latency_ms = (time.time() - ingest_start) * 1000
                    current_metric.symbols_resolved = ingest_stats.get("functions_created", 0) + ingest_stats.get("classes_created", 0)
                    logger.info(f"Successfully ingested {filename} into Knowledge Graph.")
                except Exception as e:
                    logger.warning(f"Failed to ingest {filename} into KG: {e}")

            # Collect metrics
            if hasattr(self, "_metrics_collector") and self._metrics_collector:
                self._metrics_collector.add_metric(current_metric)

        # Ensure structural integrity (__init__.py files)
        if language == "python":
            generated_files = self._ensure_init_files(generated_files)

        # Standardize extensions and cleanup
        final_repo = {}
        for filename, content in generated_files.items():
            f_clean = filename.strip()
            # ONLY rename if the language is python AND we have a mismatch
            if language == "python" and not f_clean.endswith(".py") and "." in f_clean:
                name_part, ext_part = os.path.splitext(f_clean)
                if ext_part.lower() in ['.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs']:
                    f_clean = name_part + ".py"
            
            # Structural Enforcement: All code files starting with test_ should be in tests/
            if (f_clean.startswith("test_") or f_clean.endswith("_test.py")) and not f_clean.startswith("tests/"):
                f_clean = f"tests/{f_clean}"
                
            final_repo[f_clean] = content

        # Step 4: Generate tests and merge them into the repository
        test_files = await self.generate_tests(final_repo, language)
        for t_name, t_content in test_files.items():
            # Ensure tests from generator also go to tests/
            t_clean = t_name.strip()
            if not t_clean.startswith("tests/"):
                t_clean = f"tests/{t_clean}"
            final_repo[t_clean] = t_content

        # Step 5: Ensure dependency manifest exists
        manifest_files = ["requirements.txt", "package.json", "go.mod", "pom.xml", "build.gradle"]
        if not any(m in final_repo for m in manifest_files):
            logger.info("Dependency manifest missing. Generating fallback...")
            manifest_name, manifest_content = await self._generate_dependency_manifest(final_repo, language)
            if manifest_name:
                final_repo[manifest_name] = manifest_content

        # Flush metrics
        if self._metrics_collector:
            report_path = self._metrics_collector.flush()
            if report_path:
                logger.info(f"Patent metrics flushed to: {report_path}")

        quality_result = await self.run_quality_gates(final_repo, language, "/tmp/project")
        integration_report = self._validate_component_integration(final_repo)
        
        # New: Import Resolution Pre-flight (Fix: Quality Gap 2)
        if language == "python":
            logger.info("Running Import Resolution pre-flight...")
            resolver = ImportResolver(final_repo)
            resolution_report = resolver.resolve_all()
            if resolution_report.get("missing_internal_imports") or resolution_report.get("syntax_errors"):
                 logger.warning(f"Import Resolution found issues: {resolution_report}")
                 integration_report["import_resolution"] = resolution_report

        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.CODE_REVIEW,
            message_type=MessageType.TASK,
            payload={
                "code_repo": final_repo,
                "code": final_repo,
                "tests": {k: v for k, v in final_repo.items() if k.startswith("tests/")},
                "file_structure": list(final_repo.keys()),
                "integration_report": integration_report,
                "quality_gates": quality_result,
                "language": language
            }
        )

    def _ensure_init_files(self, code_files: Dict[str, str]) -> Dict[str, str]:
        """Ensures all directories in the project have __init__.py files."""
        new_files = code_files.copy()
        dirs_to_check = set()
        
        for filename in code_files.keys():
            path_parts = filename.replace("\\", "/").split("/")
            # Add all parent directories
            for i in range(1, len(path_parts)):
                dirs_to_check.add("/".join(path_parts[:i]))
        
        for d in dirs_to_check:
            if not d or d == ".": continue
            init_file = f"{d}/__init__.py"
            if init_file not in new_files:
                logger.info(f"Injecting missing structural file: {init_file}")
                new_files[init_file] = "# Structural initialization\n"
        
        # Check root as well if src exists
        if "src" in dirs_to_check and "src/__init__.py" not in new_files:
             new_files["src/__init__.py"] = "# Structural initialization\n"
             
        return new_files
    
    async def _plan_file_structure(self, architecture: str, prd: str = "", language: str = "python") -> str:
        from foundry.utils.language_config import get_language_config
        lang_config = get_language_config(language)
        ext = lang_config.extensions[0]
        lang_name = lang_config.name.title()

        system_prompt = (
            f"You are an expert {lang_name} Engineer.\n"
            f"Plan the file structure for a project based on the following architecture.\n\n"
            f"Use {ext} extensions for source files.\n"
            f"MANDATORY: You MUST include a dependency manifest file ('requirements.txt' for Python, 'package.json' for JS/TS).\n"
            f"MANDATORY: You MUST include a 'README.md' and a '.env.example'.\n"
            "Return ONLY a JSON object with a 'files' array, where each item has a 'path' and a strictly defined 'contract' describing what logic MUST and MUST NOT go into that file to ensure proper separation of concerns (e.g. no models in routers). "
            f'(e.g. {{"files": [{{"path": "requirements.txt", "contract": "Dependencies"}}, {{"path": "src/main{ext}", "contract": "Flask routing only. MUST import models from src.models. DO NOT define database models here."}}]}}).'
        )

        user_prompt = f"Architecture:\n{architecture}"
        if prd:
            user_prompt += f"\n\nProduct Requirements (PRD):\n{prd}"
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        response = await self.llm.generate(messages, temperature=0.1)
        return response.content

    def _parse_file_list(self, response_content: str) -> List[Dict[str, str]]:
        """
        Parses the Architect's file structure output into a list of file contracts.
        Language-aware: only renames extensions for Python projects.
        """
        try:
            # Cleanup and parse
            content = response_content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "")
            
            # Use JSON loads to handle the possibly nested structure
            raw_structure = json.loads(content)
            
            if isinstance(raw_structure, dict) and "files" in raw_structure:
                file_contracts = []
                for item in raw_structure["files"]:
                    if "path" in item:
                        # Language-aware correction
                        clean_p = item["path"].strip()
                        if not clean_p: continue
                        if clean_p.endswith("/") or clean_p in ["src", "lib", "tests", "docs", "bin"]:
                            continue
                        if "." not in os.path.basename(clean_p) and clean_p != "Dockerfile":
                            continue
                        if (clean_p.startswith("test_") or "_test." in clean_p) and not clean_p.startswith("tests/"):
                            clean_p = f"tests/{clean_p}"
                        
                        file_contracts.append({
                            "path": clean_p,
                            "contract": item.get("contract", "Implement according to standard architecture.")
                        })
                
                # Check if valid results were extracted
                if file_contracts:
                    # De-duplicate while preserving order
                    seen = set()
                    unique_contracts = []
                    for c in file_contracts:
                        if c["path"] not in seen:
                            unique_contracts.append(c)
                            seen.add(c["path"])
                    return unique_contracts

            # LEGACY FALLBACK
            # RECURSIVE FLATTENING: Ensure we catch nested files like src/components/App.js
            flat_paths = self._flatten_file_structure(raw_structure)
            
            # Filter out directories: entries that don't have an extension or match common dir names
            filtered_paths = []
            for p in flat_paths:
                clean_p = p.strip()
                if not clean_p: continue
                # Skip if it ends with / or matches common dirs or has no dot
                if clean_p.endswith("/") or clean_p in ["src", "lib", "tests", "docs", "bin"]:
                    continue
                if "." not in os.path.basename(clean_p) and clean_p != "Dockerfile":
                    continue
                # Structural Enforcement: All test files must reside in tests/ (Req 15.2)
                if (clean_p.startswith("test_") or "_test." in clean_p) and not clean_p.startswith("tests/"):
                    clean_p = f"tests/{clean_p}"
                    
                filtered_paths.append(clean_p)
                
            # DE-DUPLICATION and Priority Protection
            seen = set()
            unique_paths = []
            for p in filtered_paths:
                if p not in seen:
                    unique_paths.append({"path": p, "contract": "Implement according to standard architecture."})
                    seen.add(p)
            
            return unique_paths
        except Exception as e:
            logger.error(f"Error parsing file list: {e}. Falling back to default.")
            return [
                {"path": "main.py", "contract": "Implement according to standard architecture."}, 
                {"path": "requirements.txt", "contract": "Dependencies"}, 
                {"path": "README.md", "contract": "Project documentation"}
            ]

    def _flatten_file_structure(self, structure: Any, current_path: str = "") -> List[str]:
        """
        Recursively flattens nested dictionaries/lists into project paths.
        """
        paths = []
        if isinstance(structure, dict):
            for key, value in structure.items():
                # Join key to path
                new_path = os.path.join(current_path, key) if current_path else key
                if isinstance(value, (dict, list)):
                    # Recurse if value is a sub-structure
                    paths.extend(self._flatten_file_structure(value, new_path))
                else:
                    paths.append(new_path)
        elif isinstance(structure, list):
            for item in structure:
                if isinstance(item, (dict, list)):
                    paths.extend(self._flatten_file_structure(item, current_path))
                else:
                    paths.append(os.path.join(current_path, item) if current_path else item)
        elif isinstance(structure, str):
            paths.append(os.path.join(current_path, structure) if current_path else structure)
        
        # Root Cause 2 Fix: Preserve order using a list-based deduplication
        seen = set()
        ordered_paths = []
        for p in paths:
            norm_p = p.replace("\\", "/").strip("/")
            if norm_p and norm_p not in seen:
                seen.add(norm_p)
                ordered_paths.append(norm_p)
        
        return ordered_paths

    def _detect_language(self, architecture_content: str, graph_state_language: str = "") -> str:
        """Detect language from GraphState first, then fall back to architecture content."""
        if graph_state_language and graph_state_language.strip():
            return graph_state_language.lower().strip()
        
        # Fallback: inspection of architecture content
        arch_str = str(architecture_content).lower()
        if "java" in arch_str: return "java"
        if "node" in arch_str or "javascript" in arch_str or "express" in arch_str: return "javascript"
        if "typescript" in arch_str or " ts " in arch_str: return "typescript"
        if "rust" in arch_str or " cargo " in arch_str: return "rust"
        if " go " in arch_str or "golang" in arch_str: return "go"
        
        return "python"

    async def _generate_file_content(
        self, 
        filename: str, 
        architecture: str, 
        language: str, 
        previously_generated: Dict[str, str] = None, 
        prd: str = "", 
        requirements: str = "", # Fix L
        fix_instructions: str = "",
        existing_version: str = None,
        project_id: str = "current",
        kg_project_summary: str = "",
        file_contract: str = "",
        metric: Optional[SurgicalContextMetrics] = None
    ) -> str:
        """
        Generate file content with coding standards and security measures.
        Supports incremental repair if existing_version is provided.
        """
        coding_standard = self.CODING_STANDARDS.get(language, "industry best practices")
        
        # KG Context Integration
        kg_context = ""
        if file_contract:
            kg_context += f"\n\nCRITICAL ARCHITECTURAL CONTRACT FOR {filename}:\n{file_contract}\nYou MUST strictly adhere to this boundary. Do not implement logic that belongs in another file.\n"

        if self.kg_tools and fix_instructions:
            try:
                # Try to get context for the component we are fixing
                # We use the filename as a proxy for the module/component name
                component_name = os.path.basename(filename).split('.')[0]
                context_data = await self.kg_tools.get_component_context(
                    project_id=project_id,
                    component_name=component_name
                )
                kg_context = f"\n\nKNOWLEDGE GRAPH CONTEXT (Dependency & Impact Analysis):\n{self.kg_tools.format_for_llm(context_data)}\n"
            except Exception as e:
                logger.warning(f"KG Context retrieval failed: {e}")

        context_str = ""
        if previously_generated:
            # GraphRAG FIRST: Try to get surgical context from the Knowledge Graph
            # This provides ONLY the specific dependencies this file needs,
            # instead of dumping ALL previously generated code.
            kg_surgical_context = ""
            if self.kg_tools:
                try:
                    # Extract dependency names from the file list
                    dep_names = [os.path.splitext(os.path.basename(f))[0] 
                                 for f in previously_generated.keys()]
                    
                    retrieval_start = time.time()
                    kg_surgical_context = await self.kg_tools.get_surgical_context(
                        project_id=project_id,
                        dependency_names=dep_names
                    )
                    if metric:
                        metric.kg_retrieval_latency_ms = (time.time() - retrieval_start) * 1000
                except Exception as e:
                    logger.warning(f"GraphRAG retrieval failed, falling back to truncation: {e}")

            if kg_surgical_context:
                # GraphRAG path: Use precise, structured context from the KG
                context_str = f"\n\nKNOWLEDGE GRAPH CONTEXT (Related Symbols & Definitions):\n{kg_surgical_context}\n"
                if metric:
                    metric.path_used = "kg_surgical"
                    metric.kg_context_tokens = len(kg_surgical_context.split())
            else:
                # FALLBACK: Inject truncated content of key files for cross-file coherence
                context_str = "\n\nCRITICAL CONTEXT - PREVIOUSLY GENERATED FILES:\n"
                context_str += "You MUST import from and be compatible with these files. Do NOT redefine their classes/functions.\n\n"
                fallback_tokens = 0
                for prev_file, prev_content in previously_generated.items():
                    # Extract signatures to provide full visibility into the project's interface
                    signatures = self._extract_signatures(prev_content)
                    context_str += f"--- {prev_file} (Interface) ---\n{signatures}\n\n"
                    fallback_tokens += len(signatures.split())
                
                if metric:
                    metric.path_used = "fallback_truncation"
                    metric.fallback_context_tokens = fallback_tokens

        code = await self._request_code_generation(
            filename, 
            architecture, 
            language, 
            coding_standard, 
            prd, 
            requirements, # Fix L
            context_str + kg_project_summary, 
            fix_instructions, 
            existing_version
        )
        
        return code
    
    def _detect_stub_functions(self, code: str, filename: str) -> List[str]:
        """Detect functions that are just stubs (pass, ..., NotImplementedError)."""
        stub_patterns = [
            r'def\s+\w+\([^)]*\).*:\s*\n\s+(pass|\.\.\.)\s*$',
            r'def\s+\w+\([^)]*\).*:\s*\n\s+#.*\n\s+(pass|\.\.\.)\s*$',
            r'def\s+\w+\([^)]*\).*:\s*\n\s+"""[^"]*"""\s*\n\s+(pass|\.\.\.)\s*$',
        ]
        stubs = []
        for pattern in stub_patterns:
            matches = re.finditer(pattern, code, re.MULTILINE)
            for match in matches:
                stubs.append(match.group(0)[:80])
        return stubs

    def _clean_code(self, content: str) -> str:
        from foundry.utils.code_fixer import clean_llm_markdown
        return clean_llm_markdown(content)
    
    def _extract_signatures(self, code: str) -> str:
        """Extract function and class signatures from Python code."""
        signatures = []
        # Match class definitions
        class_matches = re.finditer(r'class\s+(\w+)(?:\(([^)]*)\))?\s*:', code)
        for m in class_matches:
            signatures.append(f"class {m.group(1)}({m.group(2) or ''}): ...")
            
        # Match async and normal function definitions
        func_matches = re.finditer(r'(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([^:]+))?\s*:', code)
        for m in func_matches:
            ret = f" -> {m.group(3).strip()}" if m.group(3) else ""
            signatures.append(f"def {m.group(1)}({m.group(2).strip()}){ret}: ...")
            
        return "\n".join(signatures) if signatures else "# [No signatures found or not Python]"

    async def _recover_with_correct_language(self, filename: str, dirty_code: str, architecture: str, target_language: str = "python") -> str:
        """Recover a file generated in the wrong language using Language_Guards."""
        from foundry.utils.language_guards import recover_prompt
        prompt = recover_prompt(filename, dirty_code, target_language, architecture)
        messages = [LLMMessage(role="user", content=prompt)]
        response = await self.llm.generate(messages, temperature=0.1)
        return self._clean_code(response.content)
    
    def write_code_to_disk(self, code_files: Dict[str, str], base_path: str) -> List[str]:
        """
        Writes the generated code files to the specified base path.
        """
        written_files = []
        if not os.path.exists(base_path):
            os.makedirs(base_path)
            
        for filename, content in code_files.items():
            # Handle subdirectories in filenames
            # Normalize path separators
            filename = filename.replace("\\", "/")
            full_path = os.path.join(base_path, *filename.split("/"))
            directory = os.path.dirname(full_path)
            
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
                
            # Clean up code blocks using unified method
            clean_content = self._clean_code(content)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(clean_content)
                
            written_files.append(full_path)
            
        return written_files
    
    def _clean_code(self, content: str) -> str:
        from foundry.utils.code_fixer import clean_llm_markdown
        return clean_llm_markdown(content)

    def _detect_language(self, architecture_content: str, graph_state_language: str = "") -> str:
        """Detect language from GraphState first, then fall back to architecture content."""
        if graph_state_language and graph_state_language.strip():
            return graph_state_language.lower().strip()
        
        # Fallback: inspection of architecture content
        arch_str = str(architecture_content).lower()
        if "java" in arch_str: return "java"
        if "node" in arch_str or "javascript" in arch_str or "express" in arch_str: return "javascript"
        if "typescript" in arch_str or " ts " in arch_str: return "typescript"
        if "rust" in arch_str or " cargo " in arch_str: return "rust"
        return "python"  # Restrict to Python only as per user requirements
    async def _enhance_code_quality(self, code: str, filename: str, language: str) -> str:
        """
        Enhance code quality by validating and improving coding standards.
        """
        # Check for basic quality issues
        issues = []
        
        # Check for hardcoded credentials (basic patterns)
        if self._contains_hardcoded_secrets(code):
            issues.append("hardcoded_credentials")
        
        # Check for missing error handling
        if not self._has_error_handling(code, language):
            issues.append("missing_error_handling")
        
        # If issues found, request improvements
        if issues:
            code = await self._request_code_improvements(code, filename, language, issues)
        
        return code
    
    def _contains_hardcoded_secrets(self, code: str) -> bool:
        """
        Detect potential hardcoded secrets in code.
        """
        # Common patterns for hardcoded secrets
        secret_patterns = [
            r'password\s*=\s*["\'][^"\']{8,}["\']',
            r'api[_-]?key\s*=\s*["\'][^"\']{20,}["\']',
            r'secret\s*=\s*["\'][^"\']{20,}["\']',
            r'token\s*=\s*["\'][^"\']{20,}["\']',
            r'aws[_-]?access[_-]?key',
            r'private[_-]?key\s*=\s*["\']'
        ]
        
        for pattern in secret_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True
        
        return False
    
    def _has_error_handling(self, code: str, language: str) -> bool:
        """
        Check if code contains error handling mechanisms.
        """
        error_handling_patterns = {
            "python": [r'try:', r'except', r'raise'],
            "javascript": [r'try\s*{', r'catch', r'throw'],
            "typescript": [r'try\s*{', r'catch', r'throw'],
            "java": [r'try\s*{', r'catch', r'throws'],
            "go": [r'if\s+err\s*!=\s*nil', r'error'],
            "rust": [r'Result<', r'Option<', r'\?', r'unwrap']
        }
        
        patterns = error_handling_patterns.get(language, [r'try', r'catch', r'error'])
        
        # For small files (< 50 lines), error handling might not be needed
        if len(code.split('\n')) < 50:
            return True
        
        return any(re.search(pattern, code, re.IGNORECASE) for pattern in patterns)
    
    async def _request_code_improvements(self, code: str, filename: str, language: str, issues: List[str]) -> str:
        """
        Request LLM to improve code based on identified issues.
        """
        issue_descriptions = {
            "hardcoded_credentials": "Remove hardcoded credentials and replace with environment variables",
            "missing_error_handling": "Add comprehensive error handling with try-catch blocks"
        }
        
        improvements_needed = "\n".join([f"- {issue_descriptions.get(issue, issue)}" for issue in issues])
        
        coding_standard = self.CODING_STANDARDS.get(language, "industry best practices")
        system_prompt = f"""You are an expert {language.title()} Quality Engineer.
        Improve the provided code based on the instructions.
        Follow {coding_standard} standards.
        
        Return ONLY the updated code without any explanations.
        """
        
        user_prompt = f"File: {filename}\nLanguage: {language}\n\nImprovements needed:\n{improvements_needed}\n\nCode:\n{code}"
        
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        response = await self.llm.generate(messages, temperature=0.1)
        return response.content
    
    def _validate_component_integration(self, code_files: Dict[str, str]) -> Dict[str, Any]:
        """
        Validate that components integrate properly with correct imports and dependencies.
        """
        report = {
            "status": "valid",
            "issues": [],
            "dependencies": [],
            "imports": {}
        }
        
        # Extract imports from each file
        for filename, code in code_files.items():
            imports = self._extract_imports(code, filename)
            report["imports"][filename] = imports
            
            # Check for common integration issues
            if self._has_circular_dependencies(report["imports"]):
                report["issues"].append("Potential circular dependencies detected")
                report["status"] = "warning"
        
        # Extract dependencies
        for filename, code in code_files.items():
            if "requirements.txt" in filename or "package.json" in filename:
                deps = self._extract_dependencies(code, filename)
                report["dependencies"].extend(deps)
        
        return report
    
    def _extract_imports(self, code: str, filename: str) -> List[str]:
        """
        Extract import statements from code.
        """
        imports = []
        if not code:
            return imports
        
        # Python imports
        if filename.endswith('.py'):
            import_patterns = [
                r'^import\s+(\S+)',
                r'^from\s+(\S+)\s+import'
            ]
            for pattern in import_patterns:
                matches = re.findall(pattern, code, re.MULTILINE)
                imports.extend(matches)
        
        # JavaScript/TypeScript imports
        elif any(filename.endswith(ext) for ext in ['.js', '.ts', '.jsx', '.tsx']):
            import_patterns = [
                r'import\s+.*\s+from\s+["\']([^"\']+)["\']',
                r'require\(["\']([^"\']+)["\']\)'
            ]
            for pattern in import_patterns:
                matches = re.findall(pattern, code)
                imports.extend(matches)
        
        return imports
    
    def _has_circular_dependencies(self, imports_map: Dict[str, List[str]]) -> bool:
        """
        Simple check for circular dependencies (basic implementation).
        """
        # This is a simplified check - a full implementation would need graph analysis
        # For now, just check if any file imports another file that imports it back
        for file1, imports1 in imports_map.items():
            for file2, imports2 in imports_map.items():
                if file1 != file2:
                    # Check if file1 imports file2 and file2 imports file1
                    file1_base = os.path.splitext(os.path.basename(file1))[0]
                    file2_base = os.path.splitext(os.path.basename(file2))[0]
                    
                    if file2_base in str(imports1) and file1_base in str(imports2):
                        return True
        
        return False
    
    def _extract_dependencies(self, code: str, filename: str) -> List[str]:
        """
        Extract dependencies from package files.
        """
        dependencies = []
        
        if "requirements.txt" in filename:
            # Python dependencies
            lines = code.split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Extract package name (before ==, >=, etc.)
                    dep = re.split(r'[=<>!]', line)[0].strip()
                    if dep:
                        dependencies.append(dep)
        
        elif "package.json" in filename:
            # JavaScript/TypeScript dependencies
            try:
                package_data = json.loads(code)
                if "dependencies" in package_data:
                    dependencies.extend(package_data["dependencies"].keys())
                if "devDependencies" in package_data:
                    dependencies.extend(package_data["devDependencies"].keys())
            except json.JSONDecodeError:
                pass
        
        return dependencies

    async def generate_tests(
        self, code_files: Dict[str, str], language: str, tech_stack: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Generate unit tests for all code files.
        
        Args:
            code_files: Dictionary of filename -> code content
            language: Programming language
            tech_stack: Optional technology stack details
            
        Returns:
            Dictionary of test filename -> test code
        """
        test_files = {}
        
        # 1. GENERATE GLOBAL MOCKS (Phase 3 Optimization)
        shared_mocks = ""
        if language == "python":
            mocks_filename, shared_mocks = await self._generate_global_mocks(code_files, language)
            if mocks_filename and shared_mocks:
                test_files[mocks_filename] = shared_mocks
        
        # Select test framework
        framework = self.test_generator.select_framework(language, tech_stack)
        
        # Sequential test generation for stability
        for filename, code in code_files.items():
            if filename.endswith(('.txt', '.md', '.json', '.yml', '.yaml')) or "mocks.py" in filename:
                continue
            
            try:
                test_code = await self.test_generator.generate_unit_tests(
                    code, filename, language, framework, shared_mocks=shared_mocks
                )
                test_filename = self.test_generator.get_test_filename(filename, framework)
                test_files[test_filename] = test_code
            except Exception as e:
                logger.warning(f"Failed to generate tests for {filename}: {e}")
        
        return test_files

    async def _generate_global_mocks(self, code_files: Dict[str, str], language: str) -> Tuple[str, str]:
        """Generates a centralized mocks file based on the project structure."""
        if language != "python":
            return "", ""
            
        system_prompt = (
            f"You are an expert {language} QA Engineer. Analyze the provided project files "
            f"and generate a single, comprehensive 'tests/mocks.py' file containing mocks for ALL "
            f"external dependencies (databases, APIs, third-party services) and complex internal services.\n"
            "This file will be used by ALL unit tests. Ensure mocks are robust and reusable."
        )
        
        # Summary of files to help mock generation
        file_summary = "\n".join([f"- {f}" for f in code_files.keys()])
        user_prompt = f"Project Files:\n{file_summary}\n\nGenerate tests/mocks.py content ONLY."
        
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        try:
            response = await self.llm.generate(messages, temperature=0.1)
            mock_content = self._clean_code(response.content)
            return "tests/mocks.py", mock_content
        except Exception as e:
            logger.error(f"Failed to generate global mocks: {e}")
            return "", ""


    async def run_quality_gates(
        self, code_files: Dict[str, str], language: str, project_path: str
    ) -> Dict[str, Any]:
        """
        Run quality gates on generated code.
        
        Args:
            code_files: Dictionary of filename -> code content
            language: Programming language
            project_path: Path to project directory
            
        Returns:
            Dictionary with quality gate results
        """
        try:
            result = await self.quality_gates.run_quality_gates(code_files, language, project_path)
            
            return {
                "passed": result.passed,
                "linting_passed": result.linting_passed,
                "type_checking_passed": result.type_checking_passed,
                "security_passed": result.security_passed,
                "summary": result.summary,
                "lint_issues_count": len(result.lint_issues),
                "type_issues_count": len(result.type_issues),
                "security_issues_count": len(result.security_issues),
            }
        except Exception as e:
            logger.error(f"Quality gates failed: {e}")
            return {
                "passed": False,
                "error": str(e),
                "summary": f"Quality gates execution failed: {e}",
            }
    async def _generate_dependency_manifest(self, code_repo: Dict[str, str], language: str) -> Tuple[str, str]:
        """Scans imports and generates a fallback dependency manifest."""
        import re
        
        manifest_name = "requirements.txt"
        if language == "javascript" or language == "typescript":
            manifest_name = "package.json"
        elif language == "go":
            manifest_name = "go.mod"
        
        system_prompt = (
            f"You are a DevOps expert. Based on the provided code filenames and their imports, "
            f"generate a standard {manifest_name} file for this {language} project.\n"
            "Include ALL necessary third-party libraries. Use generic versions if not sure.\n"
            "Return ONLY the file content, no markdown blocks."
        )
        
        # Collect imports to help the LLM
        import_summary = []
        for filename, content in code_repo.items():
            if language == "python" and filename.endswith(".py"):
                imports = re.findall(r"^(?:from|import) (\w+)", content, re.MULTILINE)
                import_summary.append(f"{filename}: {', '.join(set(imports))}")
            elif (language == "javascript" or language == "typescript") and filename.endswith((".js", ".ts", ".jsx", ".tsx")):
                imports = re.findall(r"(?:import|require)\(?['\"]([^'\".]+)", content)
                import_summary.append(f"{filename}: {', '.join(set(imports))}")

        user_prompt = f"Scanned Imports:\n" + "\n".join(import_summary[:50]) # Cap for context
        
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        try:
            response = await self.llm.generate(messages, temperature=0.1)
            return manifest_name, response.content.strip()
        except Exception as e:
            logger.error(f"Failed to generate fallback manifest: {e}")
            return "", ""
