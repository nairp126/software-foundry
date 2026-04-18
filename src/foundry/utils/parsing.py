import json
import re
import logging
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

def extract_json_from_text(text: str) -> Optional[Any]:
    """
    Robustly extracts and parses JSON from a string that may contain 
    markdown code blocks or other conversational text.
    """
    if not text or not isinstance(text, str):
        return None
        
    text = text.strip()
    if not text:
        return None

    # 1. Try to find content between triple backticks
    # Look for ```json ... ``` or just ``` ... ```
    json_match = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL | re.IGNORECASE)
    if json_match:
        content = json_match.group(1).strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # If that fails, fall through to greedy matching on the block content
            text = content

    # 2. Greedy brace matching
    # Find the first '{' and the last '}'
    start = text.find('{')
    end = text.rfind('}')
    
    if start != -1 and end != -1 and end > start:
        json_str = text[start:end+1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # Try to fix common LLM mistakes like trailing commas or single quotes
            try:
                # 1. Replace single quotes with double quotes for keys/strings (risky but sometimes needed)
                # Only do this if it looks like a Python dict string
                if "'" in json_str:
                     import ast
                     res = ast.literal_eval(json_str)
                     if isinstance(res, (dict, list)):
                         return res
                
                # 2. Remove trailing commas before closing braces/brackets
                fixed = re.sub(r',\s*([\]}])', r'\1', json_str)
                return json.loads(fixed)
            except:
                logger.error(f"Failed to parse greedy JSON extract: {e}")
                return None
    
    # 3. Last resort: try parsing the whole thing if it's not empty
    try:
        return json.loads(text)
    except Exception as e:
        logger.error(f"Last resort JSON parsing failed: {e}. Raw content snippet: {text[:500]}...")
        return None

def parse_agent_response(content: Any) -> Dict[str, Any]:
    """
    Ensures an agent response (which might be a string from an LLM 
    or an already parsed dict) is returned as a dictionary.
    """
    if isinstance(content, dict):
        return content
        
    if isinstance(content, str):
        parsed = extract_json_from_text(content)
        if isinstance(parsed, dict):
            return parsed
        return {"raw_response": content, "status": "ERROR", "feedback": "Failed to parse structured response"}
        
    return {"status": "ERROR", "feedback": f"Invalid response type: {type(content)}"}
