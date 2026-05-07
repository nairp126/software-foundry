"""
Reflexion Engine: Self-healing system for automatic error detection and correction.

Implements the Execute → Analyze → Fix → Retry → Escalate workflow for code validation.
"""

from typing import Dict, Any, List, Optional
import json
import logging
import os
import re

from foundry.agents.base import Agent, AgentType, AgentMessage, MessageType
from foundry.llm.base import LLMMessage
from foundry.llm.factory import LLMProviderFactory
from foundry.testing.quality_gates import QualityGates
from foundry.sandbox.environment import (
    SandboxEnvironment,
    Sandbox,
    ExecutionResult,
    Code,
)
from foundry.sandbox.error_analysis import (
    ErrorAnalyzer,
    FixGenerator,
    ErrorAnalysis,
    CodeFix,
)
from foundry.tools.knowledge_graph_tools import KnowledgeGraphTools
from foundry.tools.import_resolver import ImportResolver
from foundry.utils.parsing import extract_json_from_text

logger = logging.getLogger(__name__)


class ReflexionEngine(Agent):
    """
    Self-healing system that automatically detects and corrects errors.
    
    Workflow:
    1. Execute: Run generated code in sandboxed environment
    2. Analyze: Capture errors, logs, and execution context
    3. Fix: Generate corrective modifications using error analysis
    4. Retry: Re-execute with fixes applied
    5. Escalate: Hand off to human if max retries exceeded
    """
    
    MAX_RETRY_ATTEMPTS = 2  # Reduced to allow orchestrator outer loop to handle escalation (BUG-REFX-3)
    
    def __init__(self, model_name: Optional[str] = None):
        super().__init__(AgentType.REFLEXION, model_name=model_name)
        self.llm = LLMProviderFactory.create_provider(model_name=self.model_name)
        self.sandbox_env = SandboxEnvironment()
        self.error_analyzer = ErrorAnalyzer()
        self.fix_generator = FixGenerator()
        self.quality_gates = QualityGates() # Added QualityGates initialization
        
        # Knowledge Graph integration
        try:
            self.kg_tools = KnowledgeGraphTools()
        except Exception:
            self.kg_tools = None
            
        # Stub recurrence tracking (Feature 4)
        self.stub_history = {} # Maps project_id:filename to recurrence count
        
    async def process_message(self, message: AgentMessage) -> AgentMessage:
        """Process incoming messages."""
        if message.message_type == MessageType.TASK:
            task_type = message.payload.get("task_type")
            
            if task_type == "execute_and_fix":
                # Execute code and automatically fix errors
                return await self.execute_and_fix(
                    code_repo=message.payload.get("code_repo") or message.payload.get("code"),
                    language=message.payload.get("language", "python"),
                    entry_point=message.payload.get("entry_point"),
                    dependencies=message.payload.get("dependencies", []),
                    feedback=message.payload.get("feedback"),
                    project_id=message.payload.get("project_id", "current")
                )
            elif task_type == "reflect_on_feedback":
                # Legacy: Handle code review feedback
                feedback = message.payload.get("feedback")
                code = message.payload.get("code")
                return await self.reflect_on_feedback(feedback, code)
        
        return None
    
    async def execute_code(
        self,
        code_repo: Dict[str, str],
        environment: SandboxEnvironment,
        language: str = "python",
        entry_point: str = "main.py",
        dependencies: Optional[List[str]] = None
    ) -> ExecutionResult:
        """
        Execute code in a sandboxed environment.
        """
        logger.info(f"Executing project in sandbox. Entry point: {entry_point}")
        
        # Create sandbox
        sandbox = await environment.create_sandbox(
            language=language,
            dependencies=dependencies or []
        )
        
        try:
            # Execute code
            result = await environment.execute_code(
                sandbox, 
                code_repo=code_repo,
                entry_point=entry_point
            )
            logger.info(
                f"Execution completed: success={result.success}, "
                f"exit_code={result.exit_code}, time={result.execution_time:.2f}s"
            )
            return result
        finally:
            # Always cleanup sandbox
            await environment.cleanup_sandbox(sandbox)
    
    async def analyze_errors(self, result: ExecutionResult) -> ErrorAnalysis:
        """
        Analyze execution errors and determine root cause.
        
        Args:
            result: Execution result with errors
            
        Returns:
            ErrorAnalysis with detailed analysis
        """
        logger.info(f"Analyzing errors: {len(result.errors)} error(s) found")
        
        error_message = result.stderr if result.stderr else "Unknown error"
        
        analysis = self.error_analyzer.analyze_error(
            error_message=error_message,
            stderr=result.stderr,
            exit_code=result.exit_code,
            code_content=""  # Will be provided by caller
        )
        
        logger.info(
            f"Error analysis: type={analysis.error_type}, "
            f"severity={analysis.severity}, root_cause={analysis.root_cause}"
        )
        
        return analysis
    
    async def analyze_impact_with_kg(
        self,
        project_id: str,
        component_name: str,
        error_analysis: ErrorAnalysis
    ) -> Dict[str, Any]:
        """
        Analyze the impact of an error using the Knowledge Graph.
        
        This provides "blast radius" analysis - what other components
        might be affected by this error or its fix.
        
        Args:
            project_id: Project identifier
            component_name: Name of the component with the error
            error_analysis: Error analysis results
            
        Returns:
            Impact analysis with affected components
        """
        logger.info(f"Analyzing impact for {component_name} using Knowledge Graph")
        
        try:
            await self.kg_tools.connect()
            
            # Get impact analysis from knowledge graph
            impact = await self.kg_tools.analyze_change_impact(
                project_id=project_id,
                component_name=component_name,
                max_depth=3
            )
            
            # Get callers of this component
            callers = await self.kg_tools.find_callers(
                project_id=project_id,
                function_name=component_name
            )
            
            # Get dependencies
            dependencies = await self.kg_tools.find_function_dependencies(
                project_id=project_id,
                function_name=component_name,
                max_depth=2
            )
            
            logger.info(
                f"Impact analysis: {len(impact.get('affected_components', []))} affected, "
                f"{len(callers)} callers, {len(dependencies)} dependencies"
            )
            
            return {
                "component": component_name,
                "error_type": error_analysis.error_type,
                "impact": impact,
                "callers": callers,
                "dependencies": dependencies,
                "blast_radius": len(impact.get("affected_components", [])),
                "risk_level": "high" if len(callers) > 5 else "medium" if len(callers) > 0 else "low"
            }
            
        except Exception as e:
            logger.warning(f"Knowledge Graph impact analysis failed: {e}")
            return {
                "component": component_name,
                "error": str(e),
                "blast_radius": 0,
                "risk_level": "unknown"
            }
        finally:
            await self.kg_tools.disconnect()
    
    async def generate_fixes(self, analysis: ErrorAnalysis, code_content: str) -> List[CodeFix]:
        """
        Generate code fixes based on error analysis.
        
        Args:
            analysis: Error analysis results
            code_content: Original code content
            
        Returns:
            List of CodeFix objects
        """
        logger.info("Generating fixes for errors")
        
        # Try rule-based fixes first
        fixes = self.fix_generator.generate_fixes(
            analysis=analysis,
            code_content=code_content,
            filename="main.py"
        )
        
        # If no rule-based fixes, use LLM
        if not fixes:
            logger.info("No rule-based fixes found, using LLM for fix generation")
            fixes = await self._generate_llm_fixes(analysis, code_content)
        
        logger.info(f"Generated {len(fixes)} fix(es)")
        return fixes
    
    async def _generate_llm_fixes(
        self, analysis: ErrorAnalysis, code_content: str, language: str = "python"
    ) -> List[CodeFix]:
        """Generate fixes using LLM (Fallback)."""
        system_prompt = f"""You are an expert code debugger and fixer.
        Analyze the error and provide corrected code for the {language} file.

        Provide ONLY the corrected code without any explanations or markdown formatting.
        """
        
        user_prompt = f"""
        Error Type: {analysis.error_type}
        Error Message: {analysis.error_message}
        Root Cause: {analysis.root_cause}
        
        Original Code:
        ```
        {code_content}
        ```
        
        Please provide the corrected code:
        """
        
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        response = await self.llm.generate(messages, temperature=0.3, agent_name="Reflexion")
        fixed_code = response.content.strip()
        
        # Clean markdown
        if "```" in fixed_code:
            fixed_code = re.sub(r'```[a-z]*\n|```', '', fixed_code).strip()
        
        return [
            CodeFix(
                fix_type="replace",
                target_file="main.py", # Fallback filename
                line_number=None,
                original_code=code_content,
                fixed_code=fixed_code,
                explanation=f"Fixed {analysis.error_type}: {analysis.root_cause}"
            )
        ]
    
    async def apply_fixes(self, code: Code, fixes: List[CodeFix]) -> Code:
        """
        Apply fixes to the code.
        
        Args:
            code: Original code
            fixes: List of fixes to apply
            
        Returns:
            Updated Code object
        """
        logger.info(f"Applying {len(fixes)} fix(es)")
        
        updated_content = code.content
        
        for fix in fixes:
            if fix.fix_type == "replace":
                updated_content = fix.fixed_code
            elif fix.fix_type == "insert":
                lines = updated_content.split("\n")
                if fix.line_number is not None and 0 <= fix.line_number <= len(lines):
                    lines.insert(fix.line_number, fix.fixed_code)
                    updated_content = "\n".join(lines)
            elif fix.fix_type == "delete":
                if fix.line_number is not None:
                    lines = updated_content.split("\n")
                    if 0 <= fix.line_number < len(lines):
                        del lines[fix.line_number]
                        updated_content = "\n".join(lines)
        
        return Code(
            content=updated_content,
            language=code.language,
            filename=code.filename,
            entry_point=code.entry_point
        )
    
    def should_escalate(self, attempt_count: int, error: ExecutionResult) -> bool:
        """
        Determine if error should be escalated to human intervention.
        
        Args:
            attempt_count: Number of retry attempts made
            error: Latest execution result
            
        Returns:
            True if should escalate, False otherwise
        """
        # Escalate if max retries exceeded
        if attempt_count >= self.MAX_RETRY_ATTEMPTS:
            logger.warning(f"Max retry attempts ({self.MAX_RETRY_ATTEMPTS}) exceeded")
            return True
        
        # Escalate for critical errors that can't be auto-fixed
        if "MemoryError" in error.stderr or "OutOfMemoryError" in error.stderr:
            logger.warning("Critical memory error detected, escalating")
            return True
        
        return False

    def _apply_fix_plan_to_repo(
        self,
        code_repo: Dict[str, str],
        fix_plan: Dict[str, Any]
    ) -> Dict[str, str]:
        """Apply per-file patches from fix_plan to code_repo.
        
        fix_plan shape: {"files": {"path/to/file.py": "...full corrected content..."}}
        Files not in fix_plan are left unchanged. Unparseable entries are skipped with a warning.
        """
        updated_repo = code_repo.copy()
        files_to_patch = fix_plan.get("files", {})
        
        if not isinstance(files_to_patch, dict):
            logger.warning("_apply_fix_plan_to_repo: fix_plan['files'] is not a dict, skipping patch")
            return updated_repo
        
        from foundry.utils.code_fixer import apply_deterministic_fixes
        
        for file_path, new_content in files_to_patch.items():
            if not isinstance(file_path, str) or not isinstance(new_content, str):
                logger.warning(f"_apply_fix_plan_to_repo: skipping unparseable entry for {file_path!r}")
                continue
            
            # Apply deterministic fixes to ensure Reflexion doesn't break boilerplate
            new_content = apply_deterministic_fixes(new_content, file_path)
            
            updated_repo[file_path] = new_content
            logger.debug(f"_apply_fix_plan_to_repo: patched {file_path}")
        
        return updated_repo

    async def execute_and_fix(
        self,
        code_repo: Dict[str, str],
        language: str = "python",
        entry_point: str = "main.py",
        dependencies: Optional[List[str]] = None,
        feedback: Optional[str] = None,
        project_id: str = "current"
    ) -> AgentMessage:
        """
        Execute code and automatically fix errors with retry logic.
        """
        if code_repo is None:
            code_repo = {}
        elif isinstance(code_repo, str):
            code_repo = {entry_point: code_repo}

        attempt = 0
        execution_history = []
        current_repo = code_repo.copy()
        
        # Extract dependencies from requirements.txt if present
        if not dependencies and "requirements.txt" in current_repo:
            try:
                req_content = current_repo["requirements.txt"]
                dependencies = [line.strip() for line in req_content.split('\n') 
                              if line.strip() and not line.startswith('#')]
                logger.info(f"Extracted {len(dependencies)} dependencies from requirements.txt")
            except Exception as e:
                logger.warning(f"Failed to extract dependencies: {e}")

        # 1. Entry Point Discovery (Fix: Blind pathing)
        if not entry_point or entry_point == "main.py":
            resolved_entry = ImportResolver.discover_entry_point(current_repo)
            if resolved_entry != entry_point:
                logger.info(f"Resolved entry point from {entry_point} to {resolved_entry}")
                entry_point = resolved_entry

        # Ensure quality tools are available for Python reflexion
        if language == "python":
            if not dependencies: dependencies = []
            for tool in ["bandit", "vulture"]:
                if tool not in dependencies: dependencies.append(tool)

        while attempt < self.MAX_RETRY_ATTEMPTS:
            attempt += 1
            logger.info(f"Execution attempt {attempt}/{self.MAX_RETRY_ATTEMPTS}")
            
            # Create a dedicated sandbox for this attempt to run multiple tools efficiently
            sandbox = await self.sandbox_env.create_sandbox(language, dependencies)
            try:
                # 1. Main Execution
                result = await self.sandbox_env.execute_code(sandbox, code_repo=current_repo, entry_point=entry_point)
                
                # 2. Pytest (if main passes)
                test_files = [f for f in current_repo.keys() if f.startswith("tests/") and f.endswith(".py")]
                if result.success and test_files and language == "python":
                    logger.info("Main execution passed. Running tests...")
                    test_result = await self.sandbox_env.execute_code(sandbox, command="python -m pytest tests/ --tb=short")
                    if not test_result.success:
                        logger.warning("Tests failed. Triggering fix.")
                        result = test_result
                        result.stderr = f"TEST FAILURES DETECTED:\n{test_result.stdout}\n{test_result.stderr}"

                # 3. Security Scan (Bandit)
                if result.success and language == "python":
                    logger.info("Running security scan (Bandit)...")
                    bandit_result = await self.sandbox_env.execute_code(sandbox, command="bandit -r . -f json")
                    try:
                        bandit_data = json.loads(bandit_result.stdout)
                        high_issues = [i for i in bandit_data.get("results", []) if i["issue_severity"] == "HIGH"]
                        if high_issues:
                            logger.warning(f"Security vulnerabilities found: {len(high_issues)}")
                            result.success = False
                            details = "\n".join([f"- {i['issue_text']} (Line {i['line_number']} in {i['filename']})" for i in high_issues[:5]])
                            result.stderr = f"SECURITY VULNERABILITY DETECTED:\n{details}\nYou must refactor to remove these high-severity risks."
                    except: pass

                # 4. Dead Code Scan (Vulture)
                if result.success and language == "python":
                    logger.info("Running dead code scan (Vulture)...")
                    vulture_result = await self.sandbox_env.execute_code(sandbox, command="vulture .")
                    dead_items = [l for l in vulture_result.stdout.splitlines() if l.strip()]
                    if len(dead_items) > 20:
                        logger.warning(f"Dead code threshold exceeded: {len(dead_items)}")
                        result.success = False
                        result.stderr = f"DEAD CODE THRESHOLD EXCEEDED ({len(dead_items)} items found).\n" + \
                                        "Please remove unused imports, functions, or variables to improve maintainability."
            finally:
                await self.sandbox_env.cleanup_sandbox(sandbox)

            execution_history.append({
                "attempt": attempt,
                "success": result.success,
                "exit_code": result.exit_code,
                "execution_time": result.execution_time,
            })
            
            # Check if execution (including quality gates) succeeded
            if result.success:
                # COMPLETENESS CHECK: Detect stub functions
                stub_files = self._find_stub_files(current_repo, language)
                if not stub_files:
                    # Clear stub history on success
                    for f in current_repo: self.stub_history.pop(f"{project_id}:{f}", None)
                    logger.info("Code executed successfully!")
                    return AgentMessage(
                        sender=self.agent_type,
                        recipient=AgentType.ENGINEER,
                        message_type=MessageType.RESPONSE,
                        payload={
                            "status": "success",
                            "code_repo": current_repo,
                            "fix_plan": "Self-healing loop succeeded in applying fixes.",
                            "result": {
                                "stdout": result.stdout,
                                "stderr": result.stderr,
                                "execution_time": result.execution_time,
                                "attempts": attempt,
                            },
                            "execution_history": execution_history,
                        }
                    )
                else:
                    logger.warning(f"Execution passed but {len(stub_files)} files contain stub functions: {list(stub_files.keys())}")
                    
                    # Track recurrence (Feature 4)
                    for f in stub_files:
                        key = f"{project_id}:{f}"
                        self.stub_history[key] = self.stub_history.get(key, 0) + 1
                        if self.stub_history[key] >= 2:
                            logger.error(f"STUB RECURRENCE DETECTED for {f}. Escalating severity.")
                            # Force failure and add persistent warning to result
                            result.stderr += f"\nCRITICAL: Recurring stub detected in {f}. STOP using placeholders!"

                    # PATENT-CRITICAL: _synthesize_semantic_failure converts a runtime-success
                    # state into a semantic failure signal using static analysis results alone.
                    result = self._synthesize_semantic_failure(stub_files, result)
            
            # Check if should escalate
            if self.should_escalate(attempt, result):
                logger.warning("Escalating to human intervention")
                return AgentMessage(
                    sender=self.agent_type,
                    recipient=AgentType.ENGINEER,
                    message_type=MessageType.ERROR,
                    payload={
                        "status": "escalated",
                        "reason": f"Failed after {attempt} attempts",
                        "last_error": {
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "exit_code": result.exit_code,
                        },
                        "execution_history": execution_history,
                    }
                )
            
            # Analyze errors
            analysis = await self.analyze_errors(result)
            
            # Enrich feedback with context
            error_context = f"Error: {analysis.error_message}\nRoot Cause: {analysis.root_cause}"
            if feedback:
                error_context += f"\nAdditional Context: {feedback}"

            # Step 4: Generate a structured Fix Plan
            
            error_file = None
            for file in current_repo:
                if file in analysis.error_message or file in analysis.root_cause:
                    error_file = file
                    break
            if not error_file:
                for file in current_repo:
                    if file.endswith('.py') and not file.startswith('test'):
                        error_file = file
                        break
            if not error_file and current_repo:
                error_file = list(current_repo.keys())[0]

            # Before generating a new fix, check KG for historical fixes
            historical_fix_applied = False
            if self.kg_tools:
                try:
                    from foundry.services.knowledge_graph import knowledge_graph_service
                    historical_fix = await knowledge_graph_service.get_error_fix(
                        error_type=analysis.error_type,
                        error_message=analysis.error_message,
                        language=language
                    )
                    if historical_fix and error_file:
                        logger.info(f"Found historical fix in KG for {analysis.error_type}")
                        # Apply the cached fix directly, skip LLM call
                        fix_plan_dict = {"files": {error_file: historical_fix}, "explanation": "Applied cached KG fix"}
                        current_repo = self._apply_fix_plan_to_repo(current_repo, fix_plan_dict)
                        historical_fix_applied = True
                        continue  # Skip to next execution attempt
                except Exception as e:
                    logger.warning(f"KG historical fix lookup failed: {e}")
            
            if historical_fix_applied:
                continue

            surgical_context = ""
            if self.kg_tools and error_file:
                try:
                    # Get only the imports/dependencies of the broken file from KG
                    dep_context = await self.kg_tools.get_component_context(
                        project_id=project_id,
                        component_name=os.path.splitext(os.path.basename(error_file))[0]
                    )
                    if dep_context:
                        surgical_context = self.kg_tools.format_for_llm(dep_context)
                except Exception as e:
                    logger.warning(f"KG surgical context failed: {e}")

            system_prompt = f"""You are a Lead Software Engineer. Resolve the following {language} execution error.
            
            Respond ONLY with a JSON fix plan in this format:
            {{
                "files": {{
                    "{error_file or 'filename.py'}": "...full corrected file content..."
                }},
                "explanation": "Short summary of the changes"
            }}
            """
            
            other_files = [f for f in current_repo if f != error_file]
            other_files_summary = ", ".join(other_files) if other_files else "None"
            
            user_prompt = f"""
            File that needs fixing: {error_file}
            ```python
            {current_repo.get(error_file, "") if error_file else ""}
            ```
            
            Other project files: {other_files_summary}
            
            KG Dependency Context:
            {surgical_context}
            
            Execution Failure:
            {error_context}
            """
            
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt)
            ]
            
            # Use lower temp for fix plans to ensure JSON validity
            response = await self.llm.generate(messages, temperature=0.2, json_mode=True, agent_name="Reflexion")
            try:
                # Clean and parse JSON using robust utility
                fix_plan_dict = extract_json_from_text(response.content)
                if not fix_plan_dict or not isinstance(fix_plan_dict, dict):
                    raise ValueError("Fix plan is missing or not a dictionary")
                
                # Apply the fixes to our repository (Self-healing!)
                current_repo = self._apply_fix_plan_to_repo(current_repo, fix_plan_dict)
                logger.info(f"Reflexion applied fix plan covering {len(fix_plan_dict.get('files', {}))} files.")
                
                # KG: store the error fix for future retrieval (Req 16.2)
                try:
                    from foundry.services.knowledge_graph import knowledge_graph_service
                    fixed_snippet = next(iter(fix_plan_dict.get("files", {}).values()), "")[:500]
                    await knowledge_graph_service.store_error_fix(
                        project_id=project_id,
                        error_type=analysis.error_type,
                        error_message=analysis.error_message,
                        fix_description=fix_plan_dict.get("explanation", "Auto-fix by ReflexionEngine"),
                        fixed_code=fixed_snippet,
                        language=language,
                    )
                except Exception as e:
                    logger.warning(f"Reflexion Agent KG store failed: {e}")
                
            except Exception as e:
                logger.error(f"Failed to apply reflexion fix plan: {e}")
                # FALLBACK: Try to extract code from markdown fences
                code_match = re.search(r'```(?:python)?\n(.*?)```', response.content, re.DOTALL)
                if code_match and error_file:
                    logger.info("JSON failed but extracted code from markdown. Applying directly.")
                    current_repo[error_file] = code_match.group(1).strip()
                else:
                    break  # No recovery possible

        # Max retries exceeded or parsing error
        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.ENGINEER,
            message_type=MessageType.TASK, # Return to engineer to let them decide next step
            payload={
                "status": "needs_fixes",
                "code_repo": current_repo,
                "fix_plan": (fix_plan_dict or {}).get("explanation", "Max retries reached") if 'fix_plan_dict' in locals() else "Unknown failure",
                "execution_history": execution_history,
                "error": error_context if 'error_context' in locals() else "Unknown failure"
            }
        )
        
        # Max retries exceeded
        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.ENGINEER,
            message_type=MessageType.ERROR,
            payload={
                "status": "failed",
                "reason": "Max retries exceeded",
                "execution_history": execution_history
            }
        )
    
    async def reflect_on_feedback(
        self, code_review: Dict[str, Any], original_code: Dict[str, str]
    ) -> AgentMessage:
        """
        Legacy method: Analyzes code review feedback and generates fix plan.
        
        This is kept for backward compatibility with the existing workflow.
        """
        issues = code_review.get("issues", [])

        # KG: fetch similar error fixes to enrich the prompt (Req 16.5)
        kg_similar_fixes = ""
        if self.kg_tools:
            try:
                error_type = code_review.get("error_type", "review_failure")
                language = code_review.get("language", "python")
                similar = await self.kg_tools.get_similar_error_fixes(error_type, language)
                if similar:
                    lines = ["\n\nSIMILAR PAST FIXES FROM KNOWLEDGE GRAPH:"]
                    for fix in similar:
                        lines.append(f"  [{fix.get('error_type')}] {fix.get('fix_description')}")
                    kg_similar_fixes = "\n".join(lines)
            except Exception as e:
                logger.warning(f"get_similar_error_fixes failed (non-blocking): {e}")

        system_prompt = """You are a Senior Lead Developer acting as a 'Reflexion' engine.
        The Code Reviewer has REJECTED the current implementation.
        
        Your job is to:
        1. Analyze the feedback and issues reported.
        2. Produce a JSON fix plan describing the corrected file contents.
        
        COMMON ARCHITECTURAL FIXES:
        - Missing Imports: If you see a NameError (e.g. 'Base', 'sessionmaker', 'Column'), you MUST add the missing imports.
        - FastAPI response_model: SQLAlchemy models CANNOT be used directly as response_models. You MUST define a Pydantic schema (inheriting from BaseModel) for the response.
        - Database Initialization: Ensure Base.metadata.create_all(engine) is called to initialize tables.
        - Indentation: Ensure all function bodies have at least one statement (use 'pass' if empty).
        - ANTI-MIMICRY: Do NOT use comments like "# [SYSTEM NOTE: ...]" or "# Rest of file truncated...". These are system markers, not code. You MUST provide the FULL content of the file you are fixing.
        
        Respond ONLY with a JSON object in this exact shape:
        {
          "files": {
            "path/to/file.py": "...full corrected file content..."
          }
        }
        Do not include any explanation outside the JSON.
        """

        user_prompt = f"""
        Original Code has been rejected.
        
        Structured Issues:
        {json.dumps(issues, indent=2)}
        
        Review Feedback:
        {code_review.get("feedback", "")}
        
        Please provide a fix plan as JSON.
        """

        # KG Context Integration
        kg_context = ""
        if self.kg_tools:
            try:
                # Use actual project_id from review (Req 16.5 / HIGH-REFX-3)
                project_id = code_review.get("project_id") or "current"
                context_data = await self.kg_tools.get_component_context(
                    project_id=project_id,
                    component_name="main"
                )
                kg_context = f"\n\nKNOWLEDGE GRAPH ARCHITECTURAL CONTEXT:\n{self.kg_tools.format_for_llm(context_data)}\n"
            except Exception as e:
                logger.error(f"KG Context retrieval failed: {e}")

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"{user_prompt}{kg_context}{kg_similar_fixes}")
        ]

        response = await self.llm.generate(messages, temperature=0.5, agent_name="Reflexion")

        # Parse the LLM response as structured fix_plan JSON
        fix_plan_dict = extract_json_from_text(response.content)
        if not isinstance(fix_plan_dict, dict):
            logger.warning(f"reflect_on_feedback: failed to parse fix_plan JSON from content: {response.content[:100]}")
            fix_plan_dict = {"files": {}}

        updated_repo = self._apply_fix_plan_to_repo(original_code, fix_plan_dict)

        # KG: store the error fix for future retrieval (Req 16.2)
        if self.kg_tools and fix_plan_dict.get("files"):
            try:
                from foundry.services.knowledge_graph import knowledge_graph_service
                error_type = code_review.get("error_type", "review_failure")
                language = code_review.get("language", "python")
                project_id = code_review.get("project_id", "current")
                fixed_snippet = next(iter(fix_plan_dict["files"].values()), "")[:500]
                await knowledge_graph_service.store_error_fix(
                    project_id=project_id,
                    error_type=error_type,
                    error_message=code_review.get("feedback", ""),
                    fix_description=f"Reflexion fix for {error_type}",
                    fixed_code=fixed_snippet,
                    language=language,
                )
            except Exception as e:
                logger.warning(f"store_error_fix failed (non-blocking): {e}")

        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.ENGINEER,
            message_type=MessageType.TASK,
            payload={
                "fix_plan": fix_plan_dict,
                "code_repo": updated_repo,
            }
        )

    def _synthesize_semantic_failure(
        self,
        stub_files: Dict[str, str],
        prior_result: ExecutionResult
    ) -> ExecutionResult:
        """
        PATENT-CRITICAL METHOD: Semantic Completeness Verification via Execution-State Synthesis.

        This method implements the core novelty of the Semantic Completeness Verification
        mechanism. It accepts a runtime-success ExecutionResult (exit_code=0, success=True)
        and converts it into a semantic failure state based solely on static analysis
        of the generated code's function bodies.

        The conversion is necessary because conventional execution pipelines cannot
        distinguish between (a) code that runs to completion correctly and (b) code that
        runs to completion by executing meaningless placeholder bodies. Both produce
        exit_code=0. This method bridges that gap by synthesizing a failure signal that
        the reflexion loop can act on as if a runtime error had occurred.

        Args:
            stub_files: Dict mapping filenames to descriptions of incomplete functions,
                        as returned by _find_stub_files().
            prior_result: The ExecutionResult from the most recent sandbox run,
                          which had success=True but semantic incompleteness.

        Returns:
            A new ExecutionResult with success=False and a synthesized stderr message
            describing the semantic failure, ready for injection into the reflexion loop.
        """
        stub_description = "; ".join([
            f"{fname}: {desc}" for fname, desc in stub_files.items()
        ])
        synthesized_stderr = (
            f"SEMANTIC_COMPLETENESS_FAILURE: Static analysis detected {len(stub_files)} "
            f"file(s) with incomplete function implementations after successful execution. "
            f"Affected files: {stub_description}. "
            f"Each function must contain real implementation logic, not placeholder bodies."
        )
        logger.warning(
            f"[SemanticCompletenessVerification] Synthesizing failure from success state. "
            f"Stub files detected: {list(stub_files.keys())}"
        )
        return ExecutionResult(
            success=False,
            stdout=prior_result.stdout,
            stderr=synthesized_stderr,
            exit_code=1,
            execution_time=prior_result.execution_time,
            resource_usage=prior_result.resource_usage,
            errors=[f"Stub: {fname}" for fname in stub_files]
        )

    def _find_stub_files(self, code_repo: Dict[str, str], language: str) -> Dict[str, str]:
        """
        PATENT-CRITICAL: Converts a syntactic execution-success state into a semantic
        failure state by detecting incomplete function implementations via static analysis.
        
        This is the core of the Semantic Completeness Verification mechanism: even when
        the generated code executes without error (exit_code=0), this method detects
        functions that exist only as declarations with no meaningful implementation.
        The caller synthesizes a failure ExecutionResult from this static finding,
        re-injecting the failure signal into the reflexion loop without any actual
        runtime failure having occurred.
        """
        stub_files = {}

        if language == "python":
            stub_patterns = [
                # Pattern 1: function with only 'pass' or '...' (with optional docstring)
                re.compile(
                    r'def\s+(\w+)\([^)]*\).*:\s*\n'
                    r'(?:\s+(?:"""[^"]*"""|\'\'\'[^\']*\'\'\')\s*\n)?'
                    r'\s+(pass|\.\.\.)\s*$',
                    re.MULTILINE
                ),
                # Pattern 2: function that only raises NotImplementedError
                re.compile(
                    r'def\s+(\w+)\([^)]*\).*:\s*\n'
                    r'(?:\s+(?:"""[^"]*"""|\'\'\'[^\']*\'\'\')\s*\n)?'
                    r'\s+raise\s+NotImplementedError',
                    re.MULTILINE
                ),
                # Pattern 3: empty try-except with pass in handler
                re.compile(
                    r'def\s+(\w+)\([^)]*\).*:\s*\n\s+try:\s*\n\s+pass\s*\n\s+except',
                    re.MULTILINE
                ),
                # Pattern 4: function with only a return None and no logic
                re.compile(
                    r'def\s+(\w+)\([^)]*\).*:\s*\n'
                    r'(?:\s+(?:"""[^"]*"""|\'\'\'[^\']*\'\'\')\s*\n)?'
                    r'\s+return\s+None\s*$',
                    re.MULTILINE
                ),
            ]
            for filename, content in code_repo.items():
                if not filename.endswith('.py') or '__init__' in filename:
                    continue
                stubs_found = []
                for pattern in stub_patterns:
                    for match in pattern.finditer(content):
                        func_name = match.group(1) if match.lastindex >= 1 else "unknown"
                        stubs_found.append(func_name)
                if stubs_found:
                    stub_files[filename] = f"Incomplete functions: {', '.join(set(stubs_found))}"

        elif language in ("javascript", "typescript"):
            js_stub_patterns = [
                # Pattern 1: named function with empty body
                re.compile(r'function\s+(\w+)\s*\([^)]*\)\s*\{\s*\}', re.MULTILINE),
                # Pattern 2: arrow function assigned to const/let with empty body
                re.compile(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{\s*\}', re.MULTILINE),
                # Pattern 3: TODO-only body (common LLM stub pattern)
                re.compile(r'function\s+(\w+)\s*\([^)]*\)\s*\{\s*console\.log\(["\']TODO["\']', re.MULTILINE),
                # Pattern 4: throw new Error("not implemented")
                re.compile(r'function\s+(\w+)\s*\([^)]*\)\s*\{\s*throw\s+new\s+Error\(["\']not\s+implemented', re.MULTILINE | re.IGNORECASE),
            ]
            for filename, content in code_repo.items():
                if not filename.endswith(('.js', '.ts', '.jsx', '.tsx')):
                    continue
                stubs_found = []
                for pattern in js_stub_patterns:
                    for match in pattern.finditer(content):
                        func_name = match.group(1) if match.lastindex >= 1 else "unknown"
                        stubs_found.append(func_name)
                if stubs_found:
                    stub_files[filename] = f"Incomplete functions: {', '.join(set(stubs_found))}"

        elif language == "java":
            java_stub_patterns = [
                # Pattern 1: Empty method body
                re.compile(r'(?:public|private|protected|static|\s)*[\w<>\s]+\s+(\w+)\s*\([^)]*\)\s*\{\s*\}', re.MULTILINE),
                # Pattern 2: UnsupportedOperationException
                re.compile(r'throw\s+new\s+UnsupportedOperationException\(', re.MULTILINE),
                # Pattern 3: return null-only body
                re.compile(r'\{\s*return\s+null;\s*\}', re.MULTILINE),
                # Pattern 4: TODO-only body
                re.compile(r'\{\s*//\s*TODO.*\}', re.MULTILINE),
            ]
            for filename, content in code_repo.items():
                if not filename.endswith('.java'):
                    continue
                stubs_found = []
                for pattern in java_stub_patterns:
                    for match in pattern.finditer(content):
                        func_name = match.group(1) if match.lastindex and match.lastindex >= 1 else "unknown"
                        stubs_found.append(func_name)
                if stubs_found:
                    stub_files[filename] = f"Incomplete functions: {', '.join(set(stubs_found))}"

        elif language == "go":
            go_stub_patterns = [
                # Pattern 1: Empty function body
                re.compile(r'func\s+(\w+)\s*\([^)]*\)\s*(?:[\w\s,*()]+)?\s*\{\s*\}', re.MULTILINE),
                # Pattern 2: panic("not implemented")
                re.compile(r'panic\(["\']not\s+implemented["\']\)', re.MULTILINE | re.IGNORECASE),
                # Pattern 3: return nil-only body
                re.compile(r'\{\s*return\s+nil\s*\}', re.MULTILINE),
            ]
            for filename, content in code_repo.items():
                if not filename.endswith('.go'):
                    continue
                stubs_found = []
                for pattern in go_stub_patterns:
                    for match in pattern.finditer(content):
                        func_name = match.group(1) if match.lastindex and match.lastindex >= 1 else "unknown"
                        stubs_found.append(func_name)
                if stubs_found:
                    stub_files[filename] = f"Incomplete functions: {', '.join(set(stubs_found))}"

        elif language == "rust":
            rust_stub_patterns = [
                # Pattern 1: Empty function body
                re.compile(r'fn\s+(\w+)\s*\([^)]*\)\s*(?:->\s*[\w\s,<>():]+)?\s*\{\s*\}', re.MULTILINE),
                # Pattern 2: todo!() macro
                re.compile(r'todo!\(\)', re.MULTILINE),
                # Pattern 3: unimplemented!() macro
                re.compile(r'unimplemented!\(\)', re.MULTILINE),
                # Pattern 4: panic!("not implemented")
                re.compile(r'panic!\(["\']not\s+implemented["\']\)', re.MULTILINE | re.IGNORECASE),
            ]
            for filename, content in code_repo.items():
                if not filename.endswith('.rs'):
                    continue
                stubs_found = []
                for pattern in rust_stub_patterns:
                    for match in pattern.finditer(content):
                        func_name = match.group(1) if match.lastindex and match.lastindex >= 1 else "unknown"
                        stubs_found.append(func_name)
                if stubs_found:
                    stub_files[filename] = f"Incomplete functions: {', '.join(set(stubs_found))}"

        return stub_files


# Alias for backward compatibility
ReflexionAgent = ReflexionEngine
