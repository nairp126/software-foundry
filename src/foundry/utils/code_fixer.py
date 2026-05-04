import re
import os
import ast
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def apply_deterministic_fixes(code: str, filename: str) -> str:
    """
    Applies global deterministic fixes to the code, regardless of which agent generated it.
    Includes import injection, whitespace cleanup, and syntax patching.
    """
    if not code or not filename.endswith('.py'):
        return code

    # 0. Hallucination Sanitizer: Split common comma-joined assignment hallucinations
    # e.g., from sqlalchemy.orm import sessionmaker, Base = declarative_base()
    code = re.sub(r'(from\s+[\w.]+\s+import\s+[\w,\s]+),\s*(Base\s*=)', r'\1\n\2', code)
    code = re.sub(r'(import\s+[\w,\s]+),\s*(Base\s*=)', r'\1\n\2', code)
    
    # 0.1 Split hybrid class/function/decorator lines
    # e.g., class Connection(Base):response_model=Project)
    code = re.sub(r'^(class\s+\w+\s*\(.*?\)):\s*(\w+\s*=)', r'\1:\n    \2', code, flags=re.MULTILINE)
    # e.g., def send_message(message: Message):response_model=Message
    code = re.sub(r'^(\s*(?:async\s+)?def\s+\w+\s*\(.*?\)):\s*(\w+\s*=)', r'\1:\n    \2', code, flags=re.MULTILINE)
    # e.g., @app.post("/messages"):response_model=Message
    code = re.sub(r'^(@\w+\.[\w.]+\s*\(.*?\)):\s*(\w+\s*=)', r'\1\n\2', code, flags=re.MULTILINE)
    
    # 0.2 Fix dangling colons followed by keyword arguments (common in FastAPI hallucinations)
    code = re.sub(r':\s*(response_model|status_code|tags|summary|description)\s*=', r',\n    \1=', code)

    base_name = os.path.basename(filename)
    
    # 0. Typing imports
    if ('List[' in code or 'Dict[' in code or 'Optional[' in code or 'Any' in code) and 'from typing import' not in code:
        code = "from typing import List, Dict, Any, Optional, Union\n" + code
        logger.info(f"Deterministic fix: Prepended typing imports to {filename}")

    # 1. SQLAlchemy core components
    if 'create_engine' in code and 'from sqlalchemy import' not in code and 'import create_engine' not in code:
        code = "from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean, Float, DateTime\n" + code
        logger.info(f"Deterministic fix: Prepended SQLAlchemy core to {filename}")
    
    # 2. SQLAlchemy ORM components
    if 'sessionmaker' in code and 'from sqlalchemy.orm import' not in code and 'import sessionmaker' not in code:
        code = "from sqlalchemy.orm import sessionmaker, relationship, Session\n" + code
        logger.info(f"Deterministic fix: Prepended SQLAlchemy ORM to {filename}")
    
    # 3. Base definition and declarative_base
    has_base_call = 'declarative_base(' in code
    has_base_usage = 'Base' in code
    has_base_def = 'Base =' in code
    has_base_import = 'import declarative_base' in code
    
    if (has_base_usage or has_base_call) and not has_base_def and not has_base_import:
        code = "from sqlalchemy.ext.declarative import declarative_base\nBase = declarative_base()\n\n" + code
        logger.info(f"Deterministic fix: Prepended Base definition to {filename}")
    elif (has_base_usage or has_base_call) and not has_base_import:
        code = "from sqlalchemy.ext.declarative import declarative_base\n\n" + code
        logger.info(f"Deterministic fix: Prepended declarative_base import to {filename}")
        
    # 4. FastAPI components
    if 'FastAPI' in code and 'from fastapi import' not in code:
        code = "from fastapi import FastAPI, HTTPException, Depends, status\n" + code
        logger.info(f"Deterministic fix: Prepended FastAPI core to {filename}")
        
    # 5. Pydantic components
    if 'BaseModel' in code and 'from pydantic import' not in code:
        code = "from pydantic import BaseModel\n" + code
        logger.info(f"Deterministic fix: Prepended BaseModel to {filename}")

    # 6. Relative Import Fix for __init__.py files
    if base_name == '__init__.py':
        # Convert 'from filename import' to 'from .filename import'
        code = re.sub(r'^from ([^.]\S+) import', r'from .\1 import', code, flags=re.MULTILINE)
        logger.info(f"Deterministic fix: Applied relative import patch to {filename}")
    
    # 7. Uvicorn Runner Guard
    if base_name in ('app.py', 'main.py') and 'FastAPI' in code:
        if '__name__' not in code:
            code = code.rstrip() + '\n\nif __name__ == "__main__":\n    import uvicorn\n    uvicorn.run(app, host="0.0.0.0", port=8000)\n'
            logger.info(f"Deterministic fix: Appended uvicorn runner to {filename}")

    # 8. Syntax Error Fix: Parameter ordering (default before non-default)
    code = re.sub(
        r'^(\s*(?:async\s+)?def\s+\w+\s*\([^)]*?)(\w+\s*:\s*[^,=]+=[^,)]+)\s*,\s*(\w+\s*:\s*[^,=]+)(?=\))',
        r'\1\3, \2',
        code,
        flags=re.MULTILINE
    )

    # 9. Dynamic Import Injection (Standard Libs)
    code = inject_missing_standard_libs(code)

    # 10. Vulture Sanitizer (Unused Import Stripper)
    if base_name != '__init__.py':
        code = strip_unused_imports(code)

    return code

def inject_missing_standard_libs(code: str) -> str:
    """Detects usage of standard libraries and injects missing imports."""
    lib_map = {
        'datetime.': 'import datetime',
        'json.': 'import json',
        'time.': 'import time',
        'math.': 'import math',
        'os.path': 'import os',
        'random.': 'import random',
        'sys.': 'import sys',
        're.': 'import re'
    }
    
    # Track which ones we need to add
    to_add = []
    for key, imp in lib_map.items():
        # Check if keyword is used but import is missing
        if key in code and imp not in code and f"from {imp.split()[-1]}" not in code:
            to_add.append(imp)
    
    if to_add:
        logger.info(f"Dynamic Import Fix: Injecting {to_add}")
        return "\n".join(to_add) + "\n" + code
    return code

def strip_unused_imports(code: str) -> str:
    """Removes imports that are not used in the code body (Vulture Sanitizer)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Fallback: If syntax is broken, don't risk stripping valid imports
        return code

    # Collect all names used in the code
    used_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            # Also catch things like 'datetime' in 'datetime.now()'
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)

    class ImportStripper(ast.NodeTransformer):
        def visit_Import(self, node):
            node.names = [n for n in node.names if n.name.split('.')[0] in used_names or n.asname in used_names]
            return node if node.names else None

        def visit_ImportFrom(self, node):
            if node.module == '__future__':
                return node
            # For 'from x import y', check if 'y' or 'asname' is used
            node.names = [n for n in node.names if n.name in used_names or n.asname in used_names]
            return node if node.names else None

    try:
        new_tree = ImportStripper().visit(tree)
        # ast.unparse is available in Python 3.9+
        return ast.unparse(new_tree)
    except Exception as e:
        logger.warning(f"AST unparse failed for {base_name}: {e}")
        return code

def clean_llm_markdown(content: str) -> str:
    """Strips Markdown code blocks and other non-code text from LLM response."""
    if not content:
        return ""
        
    # 1. Try to extract content between the first and last backticks
    match = re.search(r'```(?:[a-zA-Z]*)\n?(.*?)\n?```', content, re.DOTALL)
    if match:
        clean_content = match.group(1).strip()
    else:
        # 2. Fallback: just strip any leading/trailing backticks and spaces
        clean_content = content.replace('```', '').strip()
        # Explicitly strip stray markdown language identifiers at the very beginning
        clean_content = re.sub(r'^(?:python|js|typescript|java|go|rust)\s*\n', '', clean_content, flags=re.IGNORECASE).strip()
    
    # 3. Aggressive chatter stripping
    chatter_patterns = [
        r'\n\nThis solution follows the specified architecture.*$',
        r'\n\nI hope this helps.*$',
        r'\n\nLet me know if you need anything else.*$',
        r'\n\nRequirements met:.*$',
    ]
    for pattern in chatter_patterns:
        clean_content = re.sub(pattern, '', clean_content, flags=re.DOTALL | re.IGNORECASE).strip()
        
    # 4. DIVERSITY WATCHDOG & SYSTEM MARKER STRIPPING
    # Strip any markers the LLM might have mimicked from the system prompts
    system_markers = [
        r'# \[SYSTEM NOTE:.*\]',
        r'# \[TRUNCATED.*\]',
        r'# \.\.\. \[truncated\]',
        r'# Rest of file truncated.*',
        r'# \[TRUNCATED DUE TO REPETITION LOOP\]'
    ]
    for marker in system_markers:
        clean_content = re.sub(marker, '', clean_content, flags=re.IGNORECASE | re.MULTILINE)

    lines = clean_content.split('\n')
    if len(lines) > 20:
        for i in range(len(lines) - 10):
            block_lines = lines[i:i+3]
            block = "\n".join(block_lines)
            if block.strip() and clean_content.count(block) > 5:
                logger.warning(f"Diversity Watchdog triggered in code_fixer. Truncating.")
                
                # Detect indentation of the first line of the block to match it
                indent_match = re.match(r'^(\s*)', block_lines[0])
                indent = indent_match.group(1) if indent_match else "    "
                
                first_idx = clean_content.find(block) + len(block)
                clean_content = clean_content[:first_idx].rstrip() + f"\n{indent}pass # [TRUNCATED DUE TO REPETITION LOOP]\n"
                break
    
    # 5. SYNTAX SAFETY: If the file ends with a colon (unfinished block), add a pass
    clean_content = clean_content.strip()
    if clean_content.endswith(':'):
        # Infer indentation of last non-empty line
        last_lines = [l for l in clean_content.split('\n') if l.strip()]
        last_indent = ""
        if last_lines:
            last_indent_match = re.match(r'^(\s*)', last_lines[-1])
            last_indent = (last_indent_match.group(1) if last_indent_match else "") + "    "
        clean_content += f"\n{last_indent}pass"
    
    return clean_content
