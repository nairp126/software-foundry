import json
import os
import re
import logging
from typing import Dict, Any, Optional
from foundry.agents.base import Agent, AgentType, AgentMessage, MessageType
from foundry.llm.factory import LLMProviderFactory
from foundry.llm.base import LLMMessage

logger = logging.getLogger(__name__)

class ProductManagerAgent(Agent):
    """
    Product Manager Agent responsible for requirements analysis and PRD generation.
    """
    
    def __init__(self, model_name: Optional[str] = None):
        super().__init__(AgentType.PRODUCT_MANAGER, model_name)
        self.llm = LLMProviderFactory.create_provider(model_name=self.model_name)

    def _extract_json(self, content: str) -> dict:
        """Strip markdown fences, parse JSON, handle multiple blocks, return {} on failure.
        
        Uses a more robust approach with regex-based code block extraction and recursive 
        brace matching fallback (Req 17.4).
        """
        if not content:
            return {}
        
        # 1. Try to find JSON block in markdown fences
        json_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_block_match:
            try:
                data = json.loads(json_block_match.group(1).strip())
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        # 2. Try to find the outermost { ... } (Greedy match)
        start = content.find("{")
        end = content.rfind("}")
        
        if start != -1 and end != -1 and end > start:
            json_candidate = content[start : end + 1]
            try:
                data = json.loads(json_candidate)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                # 3. Last resort: Clean trailing commas and try again
                try:
                    cleaned = re.sub(r",\s*([}\]])", r"\1", json_candidate)
                    data = json.loads(cleaned)
                    if isinstance(data, dict):
                        return data
                except Exception:
                    pass
                
        return {}

    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.message_type == MessageType.TASK:
            content = message.payload.get("prompt") or message.payload.get("content", "")
            project_id = message.payload.get("project_id", "unknown")
            return await self.analyze_requirements(content, project_id=project_id)
        return None

    async def analyze_requirements(self, requirements: str, project_id: str = "unknown") -> AgentMessage:
        """
        Analyze natural language requirements and generate a PRD.
        """
        word_count = len(requirements.split())
        short_prompt = word_count < 10

        grounding_anchor = f"\nABSOLUTE DOMAIN: {requirements}\n"

        system_prompt = f"""You are an expert Product Manager.{grounding_anchor}
        Analyze the user's requirements and produce a structured Product Requirements Document (PRD) as JSON.

        REQUIRED JSON SCHEMA (STRICT):
        {{
            "project_name": "string",
            "high_level_description": "string",
            "core_features": ["list of strings"],
            "functional_requirements": ["list of strings"],
            "user_stories": ["list of strings"],
            "api_specification": {{
                "patterns": "string (e.g. REST, GraphQL)",
                "critical_endpoints": ["list of strings with method and purpose"]
            }},
            "ui_ux_recommendations": ["list of usability and design pointers"],
            "non_functional_requirements": {{
                "security": ["list of strings"],
                "scalability": ["list of strings"],
                "performance": ["list of strings"]
            }},
            "out_of_scope": ["list of strings"],
            "data_model_overview": ["list of strings describing entities and relationships"],
            "acceptance_criteria": ["list of strings"],
            "technical_constraints": ["list of strings"],
            "clarifying_questions": ["list of required strings to finalize project details"]
        }}

        CRITICAL CONSTRAINTS:
        1. YOU MUST STAY WITHIN THE USER'S DOMAIN.
        2. RETURN ONLY THE JSON OBJECT. NO MARKDOWN, NO EXPLANATIONS.
        3. DO NOT use a list for 'non_functional_requirements'. It MUST be a dictionary with keys: 'security', 'scalability', 'performance'.
        4. Include a detailed 'data_model_overview' of at least 3 entities.
        5. 'clarifying_questions' MUST be non-empty. Ask at least 3 deep architectural or business logic questions.
        """
        
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"PROJECT: {requirements}\n\nTask: Generate PRD JSON.")
        ]
        
        logger.info(f"PM Agent Analyzing requirements (Length: {len(requirements)} chars)")
        response = await self.llm.generate(messages, temperature=0.1)
        raw_content = response.content.strip()
        logger.debug(f"PM Agent Raw Response: '{raw_content[:200]}...'")
        
        # Use _extract_json instead of direct json.loads (Req 17.4)
        prd_dict = self._extract_json(raw_content)
        
        # SCHEMA VALIDATION & AUTO-FIX (BUG-PM-1 enhancement)
        def validate_and_fix_schema(data: dict) -> dict:
            defaults = {
                "project_name": "Untitled Project",
                "high_level_description": "No description provided.",
                "core_features": [],
                "functional_requirements": [],
                "user_stories": [],
                "api_specification": {"patterns": "REST", "critical_endpoints": []},
                "ui_ux_recommendations": [],
                "non_functional_requirements": {"security": [], "scalability": [], "performance": []},
                "out_of_scope": [],
                "data_model_overview": [],
                "acceptance_criteria": [],
                "technical_constraints": [],
                "clarifying_questions": ["What is the primary user role?", "Are there specific external integrations?", "What is the expected initial traffic volume?"]
            }
            if not isinstance(data, dict): return defaults
            
            # Ensure NFR is a dict
            if not isinstance(data.get("non_functional_requirements"), dict):
                old_nfr = data.get("non_functional_requirements", [])
                if isinstance(old_nfr, list):
                    data["non_functional_requirements"] = {
                        "security": [s for s in old_nfr if "security" in s.lower() or "auth" in s.lower()],
                        "scalability": [s for s in old_nfr if "scale" in s.lower() or "load" in s.lower()],
                        "performance": [s for s in old_nfr if s not in (data["non_functional_requirements"].get("security", []) + data["non_functional_requirements"].get("scalability", []))]
                    }
                else:
                    data["non_functional_requirements"] = defaults["non_functional_requirements"]
            
            for key, val in defaults.items():
                if key not in data:
                    data[key] = val
            return data

        prd_dict = validate_and_fix_schema(prd_dict)
        content = json.dumps(prd_dict, indent=2)

        # Fix H: Keyword Validation Gate with Stopword filtering
        requirements_lower = requirements.lower()
        content_lower = raw_content.lower()
        
        # Simple stopword list
        STOP_WORDS = {"a", "an", "the", "and", "or", "but", "is", "if", "then", "else", "with", "for", "in", "on", "at", "to", "from", "create", "make", "build", "generate"}
        key_terms = [t for t in re.findall(r'\w+', requirements_lower) if len(t) > 2 and t not in STOP_WORDS]
        
        match_count = sum(1 for term in key_terms if term in content_lower)
        
        if len(key_terms) > 0 and match_count == 0:
            logger.warning(f"Project Drift detected in PM Agent (Matches: {match_count}/{len(key_terms)}). Retrying with 'Direct Anchor Pass'.")
            focus_messages = [
                LLMMessage(role="system", content=f"STRICT REQUIREMENT: You are a Product Manager for a {requirements} project. You MUST generate a PRD ONLY for a {requirements}. DO NOT hallucinate e-commerce or marketing platforms."),
                LLMMessage(role="user", content=f"Generate the PRD JSON for a {requirements}. Use ONLY this domain.")
            ]
            response = await self.llm.generate(focus_messages, temperature=0.0)
            raw_content = response.content.strip()
            content = raw_content
            logger.info("PM Agent Focus Pass completed.")
            
            content_lower_v2 = raw_content.lower()
            match_count_v2 = sum(1 for term in key_terms if term in content_lower_v2)
            if match_count_v2 == 0:
                logger.critical(f"PM Agent persistently drifting on '{requirements[:50]}'. Triggering Fix N (Hard Fallback Template).")
                fallback_prd: Dict[str, Any] = {
                    "project_name": f"{requirements.title()} App",
                    "high_level_description": f"A specialized application for handling {requirements} logic, designed for reliability and performance.",
                    "core_features": [f"Basic {requirements} functions", "Data persistence", "User interface for interaction"],
                    "user_stories": [f"As a user, I want to use the {requirements} features to achieve my goal."],
                    "non_functional_requirements": {
                        "security": ["Standard authentication"],
                        "scalability": ["Horizontal scaling support"],
                        "performance": ["Low latency responses"]
                    },
                    "data_model_overview": [f"Core {requirements} entity"],
                    "acceptance_criteria": [f"The {requirements} feature works end-to-end."],
                    "technical_constraints": ["Scalable architecture"],
                    "clarifying_questions": []
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
        
        # Ensure clarifying_questions are always populated (Req 17.3 + HIGH-PM-1)
        if isinstance(prd_dict, dict) and not prd_dict.get("clarifying_questions"):
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
            func_reqs = prd_dict.get("functional_requirements", [])
            nfrs = []
            if isinstance(prd_dict.get("non_functional_requirements"), dict):
                for category in prd_dict["non_functional_requirements"].values():
                    if isinstance(category, list):
                        nfrs.extend(category)
            
            all_reqs = features + user_stories + func_reqs + nfrs
            if all_reqs:
                from foundry.services.knowledge_graph import knowledge_graph_service
                # Fix MED-PM-2: Use real project_id instead of slicing project_name
                await knowledge_graph_service.connect()
                for req_text in all_reqs:
                    try:
                        await knowledge_graph_service.store_requirement(
                            project_id=project_id,
                            text=str(req_text),
                            source_agent="ProductManagerAgent",
                        )
                    except Exception as e:
                        logger.warning(f"PM Agent KG store failed for requirement: {e}")
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