from typing import Dict, Any, List, Optional
from foundry.agents.base import Agent, AgentType, AgentMessage, MessageType
from foundry.llm.base import LLMMessage
from foundry.llm.factory import LLMProviderFactory

class CodeReviewAgent(Agent):
    def __init__(self, model_name: Optional[str] = None):
        super().__init__(AgentType.CODE_REVIEW, model_name)
        self.llm = LLMProviderFactory.create_provider(model_name=self.model_name)

    async def process_message(self, message: AgentMessage) -> AgentMessage:
        if message.message_type == MessageType.TASK:
            code = message.payload.get("code")
            return await self.analyze_code(code)
        return None

    async def analyze_code(self, code_files: Dict[str, str]) -> AgentMessage:
        """
        Analyzes the provided code files for bugs, security issues, and style.
        """
        files_content = ""
        for filename, content in code_files.items():
            files_content += f"--- {filename} ---\n{content}\n\n"

        system_prompt = """You are an expert Senior Software Engineer and Security Auditor.
        Your goal is to review the provided code files.
        
        Analyze the code for:
        1.  **Correctness**: Does it look like it works? Are there logic errors?
        2.  **Security**: Are there hardcoded secrets, injection vulnerabilities, or other risks?
        3.  **Style**: Is the code clean, readable, and Pythonic?
        
        Output your review in the following JSON format:
        {
            "status": "APPROVED" | "REJECTED",
            "feedback": "A summary of your findings",
            "issues": [
                {
                    "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
                    "file": "filename",
                    "line": line_number,
                    "description": "description of the issue",
                    "suggestion": "how to fix it"
                }
            ]
        }
        
        If there are CRITICAL or HIGH severity issues, status MUST be REJECTED.
        If there are only MEDIUM or LOW issues, status can be APPROVED with comments.
        """

        user_prompt = f"Please review the following code:\n\n{files_content}"

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]

        # Use Qwen to generate the review
        response = await self.llm.generate(messages, temperature=0.2, json_mode=True)
        
        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.DEVOPS,  # Or REFLEXION if rejected, controlled by orchestrator
            message_type=MessageType.TASK,
            payload={"review": response.content}
        )
