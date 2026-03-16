from typing import Dict, Any, Optional, List
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
            self.kg_tools = KnowledgeGraphTools()
        except ImportError:
            self.kg_tools = None
        
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

        {context}
        
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

        # Step 1: Plan file structure
        file_structure = await self._plan_file_structure(architecture_content, prd_content, language=graph_state_language or "python")

        # Step 2: Detect language from GraphState
        language = self._detect_language(architecture_content, graph_state_language)
        lang_config = get_language_config(language)

        # Step 3: Generate code for each file sequentially for stability
        generated_files = {}
        files_to_generate = self._parse_file_list(file_structure)
        files_to_generate = files_to_generate[:5]  # Support slightly larger MVPs

        for i, filename in enumerate(files_to_generate):
            logger.info(f"Generating content for {filename} ({i+1}/{len(files_to_generate)})...")

            # KG: inject project summary into EVERY file's prompt (Req 16.1 / 19.3)
            kg_project_summary = ""
            if self.kg_tools:
                try:
                    kg_project_summary = await self.kg_tools.get_project_summary_for_generation(project_id)
                except Exception as e:
                    logger.warning(f"KG project summary retrieval failed: {e}")

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

        # Standardize extensions and cleanup
        final_repo = {}
        for filename, content in generated_files.items():
            f_clean = filename.strip()
            # ONLY rename if the language is python AND we have a mismatch
            if language == "python" and not f_clean.endswith(".py") and "." in f_clean:
                # Basic safety: if it's clearly a code file but not .py, rename it
                name_part, ext_part = os.path.splitext(f_clean)
                if ext_part.lower() in ['.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs']:
                    f_clean = name_part + ".py"
            
            final_repo[f_clean] = content

        test_files = await self.generate_tests(final_repo, language)
        quality_result = await self.run_quality_gates(final_repo, language, "/tmp/project")
        integration_report = self._validate_component_integration(final_repo)

        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.CODE_REVIEW,
            message_type=MessageType.TASK,
            payload={
                "code_repo": final_repo,
                "code": final_repo,
                "tests": test_files,
                "file_structure": file_structure,
                "integration_report": integration_report,
                "quality_gates": quality_result,
                "language": language
            }
        )
    
    async def _plan_file_structure(self, architecture: str, prd: str = "", language: str = "python") -> str:
        from foundry.utils.language_config import get_language_config
        lang_config = get_language_config(language)
        ext = lang_config.extensions[0]
        lang_name = lang_config.name.title()

        system_prompt = (
            f"You are an expert {lang_name} Engineer.\n"
            f"Plan the file structure for a project based on the following architecture.\n\n"
            f"Use {ext} extensions for source files.\n"
            "Return ONLY a JSON list of file paths "
            f'(e.g. ["src/main{ext}", "src/utils{ext}", "README.md"]).'
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

    def _parse_file_list(self, response_content: str) -> List[str]:
        """
        Parses the Architect's file structure output into a flat list of paths.
        Language-aware: only renames extensions for Python projects.
        """
        try:
            # Cleanup and parse
            content = response_content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "")
            
            # Use JSON loads to handle the possibly nested structure
            raw_structure = json.loads(content)
            
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
                filtered_paths.append(clean_p)
                
            return filtered_paths
        except Exception as e:
            logger.error(f"Error parsing file list: {e}. Falling back to default.")
            return ["main.py", "requirements.txt", "README.md"]

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
                    # If value is a leaf (filename or string mapping), use the key as the path
                    # Some architectures use {"main.js": "Main entry point"}, we want "main.js"
                    # Others use {"src": {"main.js": "..."}}, we want "src/main.js"
                    paths.append(new_path)
        elif isinstance(structure, list):
            for item in structure:
                if isinstance(item, (dict, list)):
                    paths.extend(self._flatten_file_structure(item, current_path))
                else:
                    paths.append(os.path.join(current_path, item) if current_path else item)
        elif isinstance(structure, str):
            paths.append(os.path.join(current_path, structure) if current_path else structure)
        
        # Deduplicate and normalize
        return list(set(p.replace("\\", "/") for p in paths if p))

    def _detect_language(self, architecture_content: str, graph_state_language: str = "") -> str:
        """Detect language from GraphState first, then fall back to architecture content."""
        if graph_state_language and graph_state_language.strip():
            return graph_state_language.lower().strip()
        
        # Fallback: simple inspection of architecture string
        if "java" in architecture_content.lower(): return "java"
        if "javascript" in architecture_content.lower() or "node.js" in architecture_content.lower(): return "javascript"
        if "typescript" in architecture_content.lower(): return "typescript"
        
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
    ) -> str:
        """
        Generate file content with coding standards and security measures.
        Supports incremental repair if existing_version is provided.
        """
        coding_standard = self.CODING_STANDARDS.get(language, "industry best practices")
        
        # KG Context Integration
        kg_context = ""
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
                    kg_surgical_context = await self.kg_tools.get_surgical_context(
                        project_id=project_id,
                        dependency_names=dep_names
                    )
                except Exception as e:
                    logger.warning(f"GraphRAG retrieval failed, falling back to truncation: {e}")

            if kg_surgical_context:
                # GraphRAG path: Use precise, structured context from the KG
                context_str = kg_surgical_context
            else:
                # FALLBACK: KG has no data yet (first generation pass).
                # Use truncated raw code as a safety net.
                context_str = "\n\nCRITICAL CONTEXT - PREVIOUSLY GENERATED FILES IN THIS SESSION:\n"
                context_str += "You MUST ensure the new file is fully compatible with the frameworks, imports, naming conventions, and logic used in these files. Do NOT hallucinate conflicting frameworks.\n"
                for prev_file, prev_code in previously_generated.items():
                    truncated_code = prev_code
                    if len(prev_code) > 2000:
                        truncated_code = f"... [TRUNCATED] ...\n{prev_code[-2000:]}"
                    context_str += f"\n--- {prev_file} ---\n```python\n{truncated_code}\n```\n"

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
    
    def _clean_code(self, content: str) -> str:
        """
        Strips Markdown code blocks and other non-code text from LLM response.
        Prioritizes content between backticks and strips common trailing chatter.
        """
        if not content:
            return ""
            
        # 1. Try to extract content between the first and last backticks
        # Use greedy match for the outermost blocks
        match = re.search(r'```(?:[a-zA-Z]*)\n?(.*?)\n?```', content, re.DOTALL)
        if match:
            clean_content = match.group(1).strip()
        else:
            # 2. Fallback: just strip any leading/trailing backticks and spaces
            clean_content = content.replace('```', '').strip()
        
        # 3. Aggressive chatter stripping for common LLM closing phrases
        chatter_patterns = [
            r'\n\nThis solution follows the specified architecture.*$',
            r'\n\nI hope this helps.*$',
            r'\n\nLet me know if you need anything else.*$',
            r'\n\nRequirements met:.*$',
        ]
        for pattern in chatter_patterns:
            clean_content = re.sub(pattern, '', clean_content, flags=re.DOTALL | re.IGNORECASE).strip()
            
        return clean_content

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
        
        # Select test framework
        framework = self.test_generator.select_framework(language, tech_stack)
        
        # Sequential test generation for stability
        for filename, code in code_files.items():
            if filename.endswith(('.txt', '.md', '.json', '.yml', '.yaml')):
                continue
            
            try:
                test_code = await self.test_generator.generate_unit_tests(
                    code, filename, language, framework
                )
                test_filename = self.test_generator.get_test_filename(filename, framework)
                test_files[test_filename] = test_code
            except Exception as e:
                logger.warning(f"Failed to generate tests for {filename}: {e}")
        
        return test_files


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
