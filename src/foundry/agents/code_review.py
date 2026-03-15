import json
from typing import Dict, Any, List, Optional
from foundry.agents.base import Agent, AgentType, AgentMessage, MessageType
from foundry.llm.base import LLMMessage
from foundry.llm.factory import LLMProviderFactory
from foundry.testing.quality_gates import QualityGates

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
            return await self.analyze_code(code, project_id, language)
        return None

    async def analyze_code(self, code_files: Dict[str, str], project_id: str = "current", language: str = "python") -> AgentMessage:
        """
        Analyzes the provided code files for bugs, security issues, and style.
        Inherits results from dynamic analysis (QualityGates) in sandbox.
        """
        if not code_files:
            return AgentMessage(
                sender=self.agent_type,
                recipient=AgentType.REFLEXION,
                message_type=MessageType.TASK,
                payload={
                    "review": json.dumps({
                        "status": "REJECTED",
                        "feedback": "Code generation failed entirely. No code was provided.",
                        "issues": []
                    })
                }
            )

        # Step 1: Run Dynamic Analysis in Sandbox
        gate_results = None
        try:
            # We assume project_path is derived by orchestrator, but for sandbox we need a unique id
            # QualityGates creates its own temporary environment if path is not absolute
            gate_results = await self.quality_gates.run_quality_gates(
                code_files=code_files,
                language=language,
                project_path=project_id
            )
        except Exception as e:
            print(f"Dynamic analysis failed: {e}")

        files_content = ""
        for filename, content in code_files.items():
            files_content += f"--- {filename} ---\n{content}\n\n"

        # Step 2: Build Synthesized Prompt
        dynamic_context = ""
        if gate_results:
            dynamic_context = "\n\nCRITICAL: DYNAMIC ANALYSIS RESULTS (From Docker Sandbox):\n"
            dynamic_context += f"Overall Status: {'PASSED' if gate_results.passed else 'FAILED'}\n"
            dynamic_context += f"Summary:\n{gate_results.summary}\n"
            
            if gate_results.security_issues:
                dynamic_context += "\nSecurity Risks detected by Bandit:\n"
                for issue in gate_results.security_issues:
                    dynamic_context += f"- [{issue.severity.value.upper()}] {issue.file}:{issue.line}: {issue.description}\n"

        system_prompt = f"""You are an expert Senior Software Engineer and Security Auditor.
        Your goal is to review the provided code files.
        
        ABSOLUTE PYTHON REQUIREMENT: You are a Python-only auditor.
        1. If the code contains ANY JavaScript, React, Node.js, or non-Python tech, you MUST REJECT it immediately with status "REJECTED".
        2. Ensure strictly .py extensions are used.
        
        Analyze the code for:
        1.  **Correctness**: Does it look like it works? Are there logic errors?
        2.  **Security**: Are there hardcoded secrets, injection vulnerabilities, or other Python-specific risks?
        3.  **Style**: Is the code clean, readable, and strictly follows PEP 8 standards?
        
        {dynamic_context}
        
        Output your review in the following JSON format:
        {{
            "status": "APPROVED" | "REJECTED",
            "feedback": "A summary of your findings, INTEGRATING the sandbox results above.",
            "issues": [
                {{
                    "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
                    "file": "filename",
                    "line": line_number,
                    "description": "description of the issue",
                    "suggestion": "how to fix it"
                }}
            ]
        }}
        
        If there are CRITICAL or HIGH severity issues (including those from dynamic analysis), status MUST be REJECTED.
        If there are only MEDIUM or LOW issues, status can be APPROVED with comments.
        """

        user_prompt = f"Please review the following code:\n\n{files_content}"

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]

        # Use Qwen to generate the review
        response = await self.llm.generate(messages, temperature=0.2, json_mode=True)
        
        # Ensure it's a dict
        review_data = response.content
        if isinstance(review_data, str):
            try:
                review_data = json.loads(review_data)
            except:
                review_data = {"status": "REJECTED", "feedback": "Failed to parse review output", "issues": []}

        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.DEVOPS,
            message_type=MessageType.TASK,
            payload=review_data
        )
