"""
Reflexion Engine: Self-healing system for automatic error detection and correction.

Implements the Execute → Analyze → Fix → Retry → Escalate workflow for code validation.
"""

from typing import Dict, Any, List, Optional
import json
import logging

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
    
    MAX_RETRY_ATTEMPTS = 5  # As per Requirement 5.5
    
    def __init__(self, model_name: Optional[str] = None):
        super().__init__(AgentType.REFLEXION, model_name=model_name)
        self.llm = LLMProviderFactory.create_provider(model_name=self.model_name)
        self.sandbox_env = SandboxEnvironment()
        self.error_analyzer = ErrorAnalyzer()
        self.fix_generator = FixGenerator()
        self.quality_gates = QualityGates() # Added QualityGates initialization
        
        # Knowledge Graph integration
        try:
            from foundry.tools.knowledge_graph_tools import KnowledgeGraphTools
            self.kg_tools = KnowledgeGraphTools()
        except ImportError:
            self.kg_tools = None
        
    async def process_message(self, message: AgentMessage) -> AgentMessage:
        """Process incoming messages."""
        if message.message_type == MessageType.TASK:
            task_type = message.payload.get("task_type")
            
            if task_type == "execute_and_fix":
                # Execute code and automatically fix errors
                return await self.execute_and_fix(
                    code_repo=message.payload.get("code_repo") or message.payload.get("code"),
                    language=message.payload.get("language", "python"),
                    entry_point=message.payload.get("entry_point", "main.py"),
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
        self, analysis: ErrorAnalysis, code_content: str
    ) -> List[CodeFix]:
        """Generate fixes using LLM."""
        system_prompt = """You are an expert code debugger and fixer.

        Analyze the error and provide corrected code.
        Use the same language and framework as the original code.

        Provide ONLY the corrected code without any explanations or markdown formatting.
        """
        
        user_prompt = f"""
        Error Type: {analysis.error_type}
        Error Message: {analysis.error_message}
        Root Cause: {analysis.root_cause}
        
        Suggested Fixes:
        {chr(10).join(f"- {fix}" for fix in analysis.suggested_fixes)}
        
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
        
        response = await self.llm.generate(messages, temperature=0.3)
        
        # Extract code from response
        fixed_code = response.content.strip()
        
        # Remove markdown code blocks if present
        if fixed_code.startswith("```"):
            lines = fixed_code.split("\n")
            fixed_code = "\n".join(lines[1:-1]) if len(lines) > 2 else fixed_code
        
        return [
            CodeFix(
                fix_type="replace",
                target_file="main.py",
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
        
        for file_path, new_content in files_to_patch.items():
            if not isinstance(file_path, str) or not isinstance(new_content, str):
                logger.warning(f"_apply_fix_plan_to_repo: skipping unparseable entry for {file_path!r}")
                continue
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
        if isinstance(code_repo, str):
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

        while attempt < self.MAX_RETRY_ATTEMPTS:
            attempt += 1
            logger.info(f"Execution attempt {attempt}/{self.MAX_RETRY_ATTEMPTS}")
            
            # Execute code
            result = await self.execute_code(current_repo, self.sandbox_env, language, entry_point, dependencies)
            execution_history.append({
                "attempt": attempt,
                "success": result.success,
                "exit_code": result.exit_code,
                "execution_time": result.execution_time,
            })
            
            # Check if execution succeeded
            if result.success:
                logger.info("Code executed successfully!")
                return AgentMessage(
                    sender=self.agent_type,
                    recipient=AgentType.ENGINEER,
                    message_type=MessageType.RESPONSE,
                    payload={
                        "status": "success",
                        "code_repo": current_repo,
                        "result": {
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "execution_time": result.execution_time,
                            "attempts": attempt,
                        },
                        "execution_history": execution_history,
                    }
                )
            
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
            
            # Include feedback if available
            error_context = f"Error: {analysis.error_message}\nRoot Cause: {analysis.root_cause}"
            if feedback:
                error_context += f"\nAdditional Feedback: {feedback}"

            # Generate fixes
            # For multi-file, we currently focus on the entry point or use LLM to decide
            # Simplified for now: use LLM to generate a fix plan for the repo
            system_prompt = """You are an expert code debugger.
            Analyze the error and the project files.
            Provide a fix plan to resolve the issue.
            Use the same language and framework as the original code.

            Since you are in a self-healing loop, respond with the 'fix_plan' string only.
            """
            
            user_prompt = f"""
            Project Files:
            {json.dumps(current_repo, indent=2)}
            
            Execution Error:
            {error_context}
            
            Please provide a fix plan to resolve this.
            """
            
            # KG Context Integration
            kg_context = ""
            if self.kg_tools:
                try:
                    # Try to get impact analysis for the entry point or failing file
                    focus_file = entry_point
                    component_name = os.path.basename(focus_file).split('.')[0]
                    impact_data = await self.kg_tools.analyze_change_impact(
                        project_id=project_id,
                        component_name=component_name
                    )
                    kg_context = f"\n\nKNOWLEDGE GRAPH IMPACT ANALYSIS:\n{self.kg_tools.format_for_llm(impact_data)}\n"
                except Exception as e:
                    print(f"KG Impact analysis failed: {e}")

            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=f"{user_prompt}{kg_context}")
            ]
            
            response = await self.llm.generate(messages, temperature=0.3)

            fix_plan = response.content
            
            # Return to engineer with fix plan
            return AgentMessage(
                sender=self.agent_type,
                recipient=AgentType.ENGINEER,
                message_type=MessageType.TASK,
                payload={
                    "status": "needs_fixes",
                    "fix_plan": fix_plan,
                    "error": error_context,
                    "execution_history": execution_history
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
                # Use a general project-level context for review reflection
                context_data = await self.kg_tools.get_component_context(
                    project_id="current",
                    component_name="main" # Default focus for legacy mode
                )
                kg_context = f"\n\nKNOWLEDGE GRAPH ARCHITECTURAL CONTEXT:\n{self.kg_tools.format_for_llm(context_data)}\n"
            except Exception as e:
                print(f"KG Context retrieval failed: {e}")

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"{user_prompt}{kg_context}{kg_similar_fixes}")
        ]

        response = await self.llm.generate(messages, temperature=0.5)

        # Parse the LLM response as structured fix_plan JSON
        try:
            fix_plan_dict = json.loads(response.content)
            if not isinstance(fix_plan_dict, dict):
                raise ValueError("fix_plan is not a dict")
        except Exception as e:
            logger.warning(f"reflect_on_feedback: failed to parse fix_plan JSON: {e}")
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


# Alias for backward compatibility
ReflexionAgent = ReflexionEngine
