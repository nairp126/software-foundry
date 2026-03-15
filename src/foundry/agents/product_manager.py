import json
from typing import Dict, Any, Optional
from foundry.agents.base import Agent, AgentType, AgentMessage, MessageType
from foundry.llm.factory import LLMProviderFactory
from foundry.llm.base import LLMMessage

class ProductManagerAgent(Agent):
    """
    Product Manager Agent responsible for requirements analysis and PRD generation.
    """
    
    def __init__(self, model_name: Optional[str] = None):
        super().__init__(AgentType.PRODUCT_MANAGER, model_name)
        self.llm = LLMProviderFactory.create_provider(model_name=self.model_name)
        
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.message_type == MessageType.TASK:
            content = message.payload.get("prompt") or message.payload.get("content", "")
            return await self.analyze_requirements(content)
        return None

    async def analyze_requirements(self, requirements: str) -> AgentMessage:
        """
        Analyze natural language requirements and generate a PRD.
        """
        system_prompt = """You are an expert Product Manager. 
        Your goal is to analyze the user's natural language requirements and produce a structured Product Requirements Document (PRD).
        
        The PRD should include:
        1. Project Name
        2. High-Level Description
        3. Core Features (Functional Requirements)
        4. Technical Constraints (Non-Functional Requirements)
        5. User Stories
        
        Return the result as a JSON object.
        """
        
        user_prompt = f"Analyze the following requirements:\n\n{requirements}"
        
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        response = await self.llm.generate(messages, temperature=0.7)
        
        # In a real implementation, we would parse JSON and handle errors.
        # For now, we return the content directly.
        
        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.ARCHITECT,
            message_type=MessageType.TASK,
            payload={"prd": response.content, "original_requirements": requirements}
        )
