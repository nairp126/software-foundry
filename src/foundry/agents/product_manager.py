import json
import os
import re
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

    def _extract_json(self, content: str) -> dict:
        """Strip markdown fences, parse JSON, return {} on failure."""
        if not content:
            return {}
        # Strip markdown fences (```json ... ``` or ``` ... ```)
        stripped = re.sub(r"^```[a-zA-Z]*\s*", "", content.strip(), flags=re.MULTILINE)
        stripped = re.sub(r"\s*```$", "", stripped.strip(), flags=re.MULTILINE)
        stripped = stripped.strip()
        # Try to find outermost JSON object
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            stripped = stripped[start : end + 1]
        try:
            result = json.loads(stripped)
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.message_type == MessageType.TASK:
            content = message.payload.get("prompt") or message.payload.get("content", "")
            return await self.analyze_requirements(content)
        return None

    async def analyze_requirements(self, requirements: str) -> AgentMessage:
        """
        Analyze natural language requirements and generate a PRD.
        """
        word_count = len(requirements.split())
        short_prompt = word_count < 10

        grounding_anchor = f"\nABSOLUTE DOMAIN: {requirements}\n"

        clarifying_note = (
            '\n        - "clarifying_questions": ["..."]  // include when prompt is ambiguous\n'
            if short_prompt else ""
        )

        system_prompt = f"""You are an expert Product Manager.{grounding_anchor}
        Analyze the user's requirements and produce a structured Product Requirements Document (PRD) as JSON.

        REQUIRED JSON STRUCTURE:
        {{
            "project_name": "...",
            "high_level_description": "...",
            "core_features": ["...", "..."],
            "user_stories": ["...", "..."],
            "non_functional_requirements": ["..."],
            "acceptance_criteria": ["..."],
            "technical_constraints": ["..."]{clarifying_note}
        }}

        CRITICAL:
        1. YOU MUST STAY WITHIN THE USER'S DOMAIN.
        2. RETURN ONLY THE JSON OBJECT. NO MARKDOWN, NO EXPLANATIONS.
        3. No polite fillers like "Sure, I'd be happy to help".
        {"4. The prompt is very short — include a non-empty 'clarifying_questions' list asking about scope, target users, and constraints." if short_prompt else ""}
        """
        
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"PROJECT: {requirements}\n\nTask: Generate PRD JSON.")
        ]
        
        print(f"DEBUG: PM Agent Analyzing: '{requirements[:50]}...'")
        response = await self.llm.generate(messages, temperature=0.1)
        raw_content = response.content.strip()
        print(f"DEBUG: PM Agent Raw Response: '{raw_content[:100]}...'")
        
        # Hard Trace for diagnostics
        try:
            debug_path = os.path.join(os.getcwd(), "pm_debug.json")
            with open(debug_path, "w") as f:
                json.dump({"requirements": requirements, "response": raw_content}, f)
        except Exception:
            pass

        # Use _extract_json instead of direct json.loads (Req 17.4)
        prd_dict = self._extract_json(raw_content)
        content = raw_content  # keep raw for keyword gate below

        # Fix H: Keyword Validation Gate
        requirements_lower = requirements.lower()
        content_lower = raw_content.lower()
        
        key_terms = [t for t in requirements_lower.split() if len(t) > 3]
        match_count = sum(1 for term in key_terms if term in content_lower)
        
        if len(key_terms) > 0 and match_count == 0:
            print(f"WARNING: Project Drift detected in PM Agent (Matches: {match_count}/{len(key_terms)}). Retrying with 'Direct Anchor Pass'.")
            focus_messages = [
                LLMMessage(role="system", content=f"STRICT REQUIREMENT: You are a Product Manager for a {requirements} project. You MUST generate a PRD ONLY for a {requirements}. DO NOT hallucinate e-commerce or marketing platforms."),
                LLMMessage(role="user", content=f"Generate the PRD JSON for a {requirements}. Use ONLY this domain.")
            ]
            response = await self.llm.generate(focus_messages, temperature=0.0)
            raw_content = response.content.strip()
            content = raw_content
            print(f"DEBUG: PM Agent Focus Pass Response: '{raw_content[:100]}...'")
            
            content_lower_v2 = raw_content.lower()
            match_count_v2 = sum(1 for term in key_terms if term in content_lower_v2)
            if match_count_v2 == 0:
                print(f"FATAL: PM Agent persistently drifting on '{requirements}'. Triggering Fix N (Hard Fallback Template).")
                fallback_prd: Dict[str, Any] = {
                    "project_name": f"{requirements.title()} App",
                    "high_level_description": f"A specialized application for handling {requirements} logic, designed for reliability and performance.",
                    "core_features": [f"Basic {requirements} functions", "Data persistence", "User interface for interaction"],
                    "user_stories": [f"As a user, I want to use the {requirements} features to achieve my goal."],
                    "non_functional_requirements": ["Performance", "Reliability"],
                    "acceptance_criteria": [f"The {requirements} feature works end-to-end."],
                    "technical_constraints": ["Scalable architecture"],
                }
                if short_prompt:
                    fallback_prd["clarifying_questions"] = [
                        "What is the target user base?",
                        "What is the expected scale?",
                        "Are there any specific constraints or integrations required?",
                    ]
                content = json.dumps(fallback_prd, indent=2)
                prd_dict = fallback_prd
            else:
                prd_dict = self._extract_json(raw_content)
        
        # Ensure short prompts always have clarifying_questions (Req 17.3)
        if short_prompt and isinstance(prd_dict, dict) and not prd_dict.get("clarifying_questions"):
            prd_dict["clarifying_questions"] = [
                "What is the target user base?",
                "What is the expected scale?",
                "Are there any specific constraints or integrations required?",
            ]
            content = json.dumps(prd_dict, indent=2)

        # KG: store each PRD requirement (Req 16.4)
        try:
            features = prd_dict.get("core_features", [])
            user_stories = prd_dict.get("user_stories", [])
            all_reqs = features + user_stories
            if all_reqs:
                from foundry.services.knowledge_graph import knowledge_graph_service
                project_id = prd_dict.get("project_name", "unknown")[:36]
                for req_text in all_reqs:
                    try:
                        await knowledge_graph_service.store_requirement(
                            project_id=project_id,
                            text=str(req_text),
                            source_agent="ProductManagerAgent",
                        )
                    except Exception:
                        pass
        except Exception:
            pass  # Non-blocking — KG outage must never block the pipeline

        return AgentMessage(
            sender=self.agent_type,
            recipient=AgentType.PRODUCT_MANAGER,
            message_type=MessageType.RESPONSE,
            payload={
                "prd": content,
                "requirements": requirements,
            }
        )