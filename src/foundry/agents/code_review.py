import json
import re
import logging
from typing import Dict, Any, List, Optional
from foundry.agents.base import Agent, AgentType, AgentMessage, MessageType
from foundry.llm.base import LLMMessage
from foundry.llm.factory import LLMProviderFactory
from foundry.testing.quality_gates import QualityGates

logger = logging.getLogger(__name__)

class CodeReviewAgent(Agent):
    def __init__(self, model_name: Optional[str] = None):
        super().__init__(AgentType.CODE_REVIEW, model_name)
        self.llm = LLMProviderFactory.create_provider(model_name=self.model_name)
        self.quality_gates = QualityGates()

    async def process_message(self, message: AgentMessage) -> AgentMessage:
        if message.message_type == MessageType.TASK:
            code = message.payload.get("code_repo") or message.payload.get("code")
            project_id = message.payload.get("project_id", "current")
            language = message.payload.get("language", "python")
            sandbox_results = message.payload.get("sandbox_results")
            return await self.analyze_code(code, project_id, language, sandbox_results)
        return None

    async def analyze_code(
        self,
        code_files: Dict[str, str],
        project_id: str = "current",
        language: str = "python",
        sandbox_results: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        """
        Analyzes the provided code files for bugs, security issues, and style.
        Merges sandbox execution errors into the issues list (Req 20.1).
        Uses language-aware review prompt (Req 20.2).
        Always returns structured issues list under "issues" key (Req 20.3).
        Human-readable summary stored under "feedback" key (Req 3.2).
        """
        if not code_files:
            return AgentMessage(
                sender=self.agent_type,
                recipient=AgentType.REFLEXION,
                message_type=MessageType.TASK,
                payload={
                    "status": "REJECTED",
                    "feedback": "Code generation failed entirely. No code was provided.",
                    "issues": [],
                }
            )

        # Step 1: Run Dynamic Analysis in Sandbox
        gate_results = None
        try:
            gate_results = await self.quality_gates.run_quality_gates(
                code_files=code_files,
                language=language,
                project_path=project_id
            )
        except Exception as e:
            logger.warning(f"Dynamic analysis failed: {e}")

        # Step 2: Collect sandbox execution errors from caller-provided results (Req 20.1)
        sandbox_issues: List[Dict[str, Any]] = []
        if sandbox_results:
            errors = sandbox_results.get("errors") or []
            stderr = sandbox_results.get("stderr", "")
            if errors:
                for err in errors:
                    sandbox_issues.append({
                        "severity": "HIGH",
                        "file": err.get("file", "unknown"),
                        "description": str(err.get("message", err)),
                    })
            elif stderr:
                sandbox_issues.append({
                    "severity": "HIGH",
                    "file": "runtime",
                    "description": stderr[:500],
                })

        files_content = ""
        for filename, content in code_files.items():
            files_content += f"--- {filename} ---\n{content}\n\n"

        # Step 3: Build Synthesized Prompt (language-aware — Req 20.2)
        dynamic_context = ""
        if gate_results:
            dynamic_context = "\n\nCRITICAL: DYNAMIC ANALYSIS RESULTS (From Docker Sandbox):\n"
            dynamic_context += f"Overall Status: {'PASSED' if gate_results.passed else 'FAILED'}\n"
            dynamic_context += f"Summary:\n{gate_results.summary}\n"

            if gate_results.security_issues:
                dynamic_context += f"\nSecurity Risks detected by automated security scans for {language}:\n"
                for issue in gate_results.security_issues:
                    dynamic_context += f"- [{issue.severity.value.upper()}] {issue.file}:{issue.line}: {issue.description}\n"

        system_prompt = f"""You are an expert Senior Software Engineer and Security Auditor.
        Review the provided {language} code files.

        Analyze the code for:
        1. Correctness: Does it look like it works? Are there logic errors?
        2. Security: Are there hardcoded secrets, injection vulnerabilities, or other risks specific to {language}?
        3. Style: Is the code clean, readable, and follows {language} best practices?

        {dynamic_context}

        Output your review in the following JSON format:
        {{
            "status": "APPROVED" | "REJECTED",
            "feedback": "A human-readable summary of your findings.",
            "issues": [
                {{
                    "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
                    "file": "filename",
                    "line": 123,
                    "description": "description of the issue",
                    "suggestion": "optional fix suggestion"
                }}
            ]
        }}

        If there are CRITICAL or HIGH severity issues, status MUST be REJECTED.
        If there are only MEDIUM or LOW issues, status can be APPROVED with comments.
        """

        user_prompt = f"Please review the following code:\n\n{files_content}"

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]

        response = await self.llm.generate(messages, temperature=0.2, json_mode=True)

        # Parse review response
        review_data = response.content
        logger.debug(f"Code Review Raw Response: {str(review_data)[:200]}...")
        
        if isinstance(review_data, str):
            try:
                # 1. First try: Greedy extract between first { and last }
                start = review_data.find('{')
                end = review_data.rfind('}')
                if start != -1 and end != -1 and end > start:
                    clean_json = review_data[start:end+1]
                else:
                    clean_json = review_data.strip()
                
                # 2. Strip any remaining markdown fences
                if "```" in clean_json:
                    clean_json = re.sub(r'```[a-z]*\n|```', '', clean_json).strip()
                
                review_data = json.loads(clean_json)
            except Exception as e:
                logger.error(f"CRITICAL: Failed to parse review output for project {project_id}. Error: {e}.")
                # Last resort fallback if it's mostly JSON but maybe has a trailing comma or something
                try:
                    import ast
                    review_data = ast.literal_eval(clean_json)
                    if not isinstance(review_data, dict):
                         raise ValueError("Not a dictionary")
                except:
                    review_data = {
                        "status": "REJECTED",
                        "feedback": f"AUTO-REJECT: JSON parsing failed. Error: {str(e)[:100]}",
                        "issues": [],
                    }

        # Ensure review_data is a dict
        if not isinstance(review_data, dict):
            review_data = {"status": "REJECTED", "feedback": str(review_data), "issues": []}

        # Step 4: Merge sandbox issues into the structured issues list (Req 20.1 / HIGH-REV-1)
        existing_issues = review_data.get("issues", [])
        normalised_issues: List[Dict[str, Any]] = []

        # 4a. Add Gate Results (Bandit, Pylint, etc.) directly to structured issues
        if gate_results:
            for sec_issue in gate_results.security_issues:
                normalised_issues.append({
                    "severity": sec_issue.severity.value.upper(),
                    "file": sec_issue.file,
                    "line": sec_issue.line,
                    "description": sec_issue.description,
                    "suggestion": sec_issue.recommendation,
                    "source": "security_gate"
                })
            for lint_issue in gate_results.lint_issues:
                normalised_issues.append({
                    "severity": lint_issue.severity.upper() if isinstance(lint_issue.severity, str) else "MEDIUM",
                    "file": lint_issue.file,
                    "line": lint_issue.line,
                    "description": lint_issue.message,
                    "suggestion": f"Fix {lint_issue.rule}",
                    "source": "lint_gate"
                })
            for type_issue in gate_results.type_issues:
                normalised_issues.append({
                    "severity": "MEDIUM",
                    "file": type_issue.file,
                    "line": type_issue.line,
                    "description": type_issue.message,
                    "suggestion": f"Fix type error {type_issue.error_code or ''}",
                    "source": "type_gate"
                })

        # 4b. Normalise LLM issues
        for item in existing_issues:
            if isinstance(item, dict):
                normalised_issues.append({
                    "severity": item.get("severity", "MEDIUM").upper(),
                    "file": item.get("file", "unknown"),
                    "line": item.get("line"),
                    "description": item.get("description", str(item)),
                    "suggestion": item.get("suggestion", ""),
                    "source": "llm_reviewer"
                })
            else:
                normalised_issues.append({
                    "severity": "MEDIUM",
                    "file": "unknown",
                    "description": str(item),
                    "source": "llm_reviewer"
                })

        # Prepend sandbox issues so they are visible first
        merged_issues = sandbox_issues + normalised_issues

        # Escalate status if sandbox found HIGH issues
        status = review_data.get("status", "REJECTED")
        if sandbox_issues and status == "APPROVED":
            status = "REJECTED"

        payload = {
            "status": status,
            "feedback": review_data.get("feedback", ""),
            "issues": merged_issues,
        }

        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.REFLEXION, # Corrected semantic routing (MED-REV-1)
            message_type=MessageType.TASK,
            payload=payload,
        )
