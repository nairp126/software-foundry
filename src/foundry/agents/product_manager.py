import json
import os
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
        # Fix L: Domain Anchoring
        grounding_anchor = f"\nABSOLUTE DOMAIN: {requirements}\n"
        
        system_prompt = f"""You are an expert Product Manager.{grounding_anchor}
        Analyze the user's requirements and produce a structured Product Requirements Document (PRD) as JSON.
        
        REQUIRED JSON STRUCTURE:
        {{
            "project_name": "...",
            "high_level_description": "...",
            "core_features": ["...", "..."],
            "user_stories": ["...", "..."],
            "technical_constraints": ["..."]
        }}
        
        CRITICAL: 
        1. YOU MUST STAY WITHIN THE USER'S DOMAIN. 
        2. RETURN ONLY THE JSON OBJECT. NO MARKDOWN, NO EXPLANATIONS.
        3. No polite fillers like "Sure, I'd be happy to help".
        """
        
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"PROJECT: {requirements}\n\nTask: Generate PRD JSON.")
        ]
        
        print(f"DEBUG: PM Agent Analyzing: '{requirements[:50]}...'")
        response = await self.llm.generate(messages, temperature=0.1)
        content = response.content.strip()
        print(f"DEBUG: PM Agent Raw Response: '{content[:100]}...'")
        
        # Hard Trace for diagnostics
        try:
            debug_path = os.path.join(os.getcwd(), "pm_debug.json")
            with open(debug_path, "w") as f:
                json.dump({"requirements": requirements, "response": content}, f)
        except:
            pass

        # Fix H: Keyword Validation Gate
        requirements_lower = requirements.lower()
        content_lower = content.lower()
        
        # Heuristic: The model should mention some key nouns from the request
        key_terms = [t for t in requirements_lower.split() if len(t) > 3]
        match_count = sum(1 for term in key_terms if term in content_lower)
        
        if len(key_terms) > 0 and match_count == 0:
            print(f"WARNING: Project Drift detected in PM Agent (Matches: {match_count}/{len(key_terms)}). Retrying with 'Direct Anchor Pass'.")
            focus_messages = [
                LLMMessage(role="system", content=f"STRICT REQUIREMENT: You are a Product Manager for a {requirements} project. You MUST generate a PRD ONLY for a {requirements}. DO NOT hallucinate e-commerce or marketing platforms."),
                LLMMessage(role="user", content=f"Generate the PRD JSON for a {requirements}. Use ONLY this domain.")
            ]
            response = await self.llm.generate(focus_messages, temperature=0.0)
            content = response.content.strip()
            print(f"DEBUG: PM Agent Focus Pass Response: '{content[:100]}...'")
            
            # Fix N: Hard Fallback if second attempt also drifted
            content_lower_v2 = content.lower()
            match_count_v2 = sum(1 for term in key_terms if term in content_lower_v2)
            if match_count_v2 == 0:
                print(f"FATAL: PM Agent persistently drifting on '{requirements}'. Triggering Fix N (Hard Fallback Template).")
                fallback_prd = {
                    "project_name": f"{requirements.title()} App",
                    "high_level_description": f"A specialized application for handling {requirements} logic, designed for reliability and performance.",
                    "core_features": [f"Basic {requirements} functions", "Data persistence", "User interface for interaction"],
                    "user_stories": [f"As a user, I want to use the {requirements} features to achieve my goal."],
                    "technical_constraints": ["Python 3.11+", "Scalable architecture"]
                }
                content = json.dumps(fallback_prd, indent=2)

        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.PRODUCT_MANAGER,
            message_type=MessageType.RESPONSE,
            payload={
                "prd": content,
                "requirements": requirements # Fix L: Persistence
            }
        )
