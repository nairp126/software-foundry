"""
Reflexion Engine: Self-healing system for automatic error detection and correction.

Implements the Execute → Analyze → Fix → Retry → Escalate workflow for code validation.
"""

from typing import Dict, Any, List, Optional
import logging

from foundry.agents.base import Agent, AgentType, AgentMessage, MessageType
from foundry.llm.base import LLMMessage
from foundry.llm.factory import LLMProviderFactory
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
    
    def __init__(self, model_name: str = "qwen2.5-coder:7b"):
        super().__init__(AgentType.REFLEXION, model_name=model_name)
        self.llm = LLMProviderFactory.create_provider(model_name=self.model_name)
        self.sandbox_env = SandboxEnvironment()
        self.error_analyzer = ErrorAnalyzer()
        self.fix_generator = FixGenerator()
        
    async def process_message(self, message: AgentMessage) -> AgentMessage:
        """Process incoming messages."""
        if message.message_type == MessageType.TASK:
            task_type = message.payload.get("task_type")
            
            if task_type == "execute_and_fix":
                # Execute code and automatically fix errors
                return await self.execute_and_fix(
                    code_content=message.payload.get("code"),
                    language=message.payload.get("language", "python"),
                    filename=message.payload.get("filename", "main.py"),
                    dependencies=message.payload.get("dependencies", [])
                )
            elif task_type == "reflect_on_feedback":
                # Legacy: Handle code review feedback
                feedback = message.payload.get("feedback")
                code = message.payload.get("code")
                return await self.reflect_on_feedback(feedback, code)
        
        return None
    
    async def execute_code(
        self,
        code: Code,
        environment: SandboxEnvironment
    ) -> ExecutionResult:
        """
        Execute code in a sandboxed environment.
        
        Args:
            code: Code to execute
            environment: Sandbox environment
            
        Returns:
            ExecutionResult with execution details
        """
        logger.info(f"Executing code in sandbox: {code.filename}")
        
        # Create sandbox
        sandbox = await environment.create_sandbox(
            language=code.language,
            dependencies=[]
        )
        
        try:
            # Execute code
            result = await environment.execute_code(sandbox, code)
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
        
        Your task is to analyze the error and generate a corrected version of the code.
        
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
    
    async def execute_and_fix(
        self,
        code_content: str,
        language: str = "python",
        filename: str = "main.py",
        dependencies: Optional[List[str]] = None
    ) -> AgentMessage:
        """
        Execute code and automatically fix errors with retry logic.
        
        This is the main entry point for the Reflexion Engine workflow.
        
        Args:
            code_content: Code to execute
            language: Programming language
            filename: Filename for the code
            dependencies: List of dependencies to install
            
        Returns:
            AgentMessage with execution results or escalation request
        """
        code = Code(
            content=code_content,
            language=language,
            filename=filename
        )
        
        attempt = 0
        execution_history = []
        
        while attempt < self.MAX_RETRY_ATTEMPTS:
            attempt += 1
            logger.info(f"Execution attempt {attempt}/{self.MAX_RETRY_ATTEMPTS}")
            
            # Execute code
            result = await self.execute_code(code, self.sandbox_env)
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
            
            # Generate fixes
            fixes = await self.generate_fixes(analysis, code.content)
            
            if not fixes:
                logger.warning("No fixes generated, escalating")
                return AgentMessage(
                    sender=self.agent_type,
                    recipient=AgentType.ENGINEER,
                    message_type=MessageType.ERROR,
                    payload={
                        "status": "escalated",
                        "reason": "Unable to generate fixes",
                        "error_analysis": {
                            "error_type": analysis.error_type,
                            "root_cause": analysis.root_cause,
                            "suggestions": analysis.suggested_fixes,
                        },
                        "execution_history": execution_history,
                    }
                )
            
            # Apply fixes
            code = await self.apply_fixes(code, fixes)
            logger.info(f"Applied fixes, retrying execution (attempt {attempt + 1})")
        
        # Max retries exceeded
        logger.error("Max retries exceeded without success")
        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.ENGINEER,
            message_type=MessageType.ERROR,
            payload={
                "status": "failed",
                "reason": f"Max retries ({self.MAX_RETRY_ATTEMPTS}) exceeded",
                "execution_history": execution_history,
            }
        )
    
    async def reflect_on_feedback(
        self, code_review: Dict[str, Any], original_code: Dict[str, str]
    ) -> AgentMessage:
        """
        Legacy method: Analyzes code review feedback and generates fix plan.
        
        This is kept for backward compatibility with the existing workflow.
        """
        system_prompt = """You are a Senior Lead Developer acting as a 'Reflexion' engine.
        The Code Reviewer has REJECTED the current implementation.
        
        Your job is to:
        1. Analyze the feedback and issues reported.
        2. Formulate a clear, step-by-step plan for the Engineer to fix the code.
        
        Output your plan as a string.
        """

        user_prompt = f"""
        Original Code has been rejected.
        
        Review Feedback:
        {code_review}
        
        Please provide a fix plan.
        """

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]

        response = await self.llm.generate(messages, temperature=0.5)
        
        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.ENGINEER,
            message_type=MessageType.TASK,
            payload={"fix_plan": response.content}
        )


# Alias for backward compatibility
ReflexionAgent = ReflexionEngine
