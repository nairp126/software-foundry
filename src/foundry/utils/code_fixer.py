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

    # 0.3 Fix empty classes and functions (IndentationError prevention)
    # If a class or top-level function is defined but immediately followed by another top-level construct
    code = re.sub(
        r'^(class\s+\w+(?:\s*\(.*?\))?):[ \t]*\n(?:[ \t]*\n)*(?=@\w+|class\s+|def\s+|async\s+def\s+|if\s+__name__)', 
        r'\1:\n    pass\n\n', 
        code, 
        flags=re.MULTILINE
    )
    code = re.sub(
        r'^((?:async\s+)?def\s+\w+\s*\(.*?\)):[ \t]*\n(?:[ \t]*\n)*(?=@\w+|class\s+|def\s+|async\s+def\s+|if\s+__name__)', 
        r'\1:\n    pass\n\n', 
        code, 
        flags=re.MULTILINE
    )

    base_name = os.path.basename(filename)
    headers = []
    
    # 0. Future annotations for forward references (MUST BE ABSOLUTELY FIRST)
    if 'from __future__ import annotations' not in code:
        headers.append("from __future__ import annotations")

    # 0.1 Typing imports
    if ('List[' in code or 'Dict[' in code or 'Optional[' in code or 'Any' in code) and 'from typing import' not in code:
        headers.append("from typing import List, Dict, Any, Optional, Union")
        logger.info(f"Deterministic fix: Identified typing imports for {filename}")

    # 1. SQLAlchemy core components
    if 'create_engine' in code and 'from sqlalchemy import' not in code and 'import create_engine' not in code:
        headers.append("from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean, Float, DateTime")
        logger.info(f"Deterministic fix: Identified SQLAlchemy core for {filename}")
    
    # 2. SQLAlchemy ORM components
    if 'sessionmaker' in code and 'from sqlalchemy.orm import' not in code and 'import sessionmaker' not in code:
        headers.append("from sqlalchemy.orm import sessionmaker, relationship, Session")
        logger.info(f"Deterministic fix: Identified SQLAlchemy ORM for {filename}")
    
    # 3. Base definition and declarative_base
    has_base_call = 'declarative_base(' in code
    has_base_usage = 'Base' in code
    has_base_def = 'Base =' in code
    has_base_import = 'import declarative_base' in code
    
    if (has_base_usage or has_base_call) and not has_base_import:
        headers.append("from sqlalchemy.orm import declarative_base")
        if not has_base_def:
            headers.append("Base = declarative_base()")
            logger.info(f"Deterministic fix: Identified Base definition for {filename}")
        
    # 4. FastAPI components & App Injection
    has_fastapi_import = 'from fastapi import' in code or 'import fastapi' in code
    has_app_def = 'app =' in code
    has_app_usage = '@app.' in code or 'uvicorn.run(app' in code or 'uvicorn.run("main:app"' in code
    
    if has_app_usage and not has_app_def:
        headers.append("app = FastAPI()")
        logger.info(f"Deterministic fix: Injected missing app definition for {filename}")
        if not has_fastapi_import:
            headers.append("from fastapi import FastAPI, HTTPException, Depends, status")
    elif 'FastAPI' in code and not has_fastapi_import:
        headers.append("from fastapi import FastAPI, HTTPException, Depends, status")
        logger.info(f"Deterministic fix: Identified FastAPI core for {filename}")
        
    # 5. Pydantic components
    if 'BaseModel' in code and 'from pydantic import' not in code:
        headers.append("from pydantic import BaseModel")
        logger.info(f"Deterministic fix: Identified BaseModel for {filename}")

    # Apply headers if any
    if headers:
        # Prepend headers but avoid double-injecting if they were somehow partially there
        unique_headers = []
        for h in headers:
            if h not in code:
                unique_headers.append(h)
        if unique_headers:
            code = "\n".join(unique_headers) + "\n\n" + code

    # 5.1 GLOBAL IMPORT HARDENING: Fix partial imports in the existing code
    # Self-healing: Fix previous corruption from greedy regex if present
    if 'from sqlalchemy, Float' in code:
        code = code.replace('from sqlalchemy, Float, Boolean, DateTime, Text.ext.declarative', 'from sqlalchemy.ext.declarative')
        code = code.replace('from sqlalchemy, Float, Boolean, DateTime, Text.orm', 'from sqlalchemy.orm')
    
    # NEW Self-healing: Fix corruption where imports were injected into class/function names
    if ', Float, Boolean, DateTime, Text' in code:
        code = re.sub(r'(class\s+\w+),\s*Float,\s*Boolean,\s*DateTime,\s*Text', r'\1', code)
        code = re.sub(r'(def\s+\w+),\s*Float,\s*Boolean,\s*DateTime,\s*Text', r'\1', code)

    # We use [ \t]+ to ensure we don't match across newlines (\s matches \n)
    if 'from sqlalchemy import' in code and 'Float' not in code:
        code = re.sub(r'^from\s+sqlalchemy\s+import\s+([a-zA-Z0-9_, \t]+)', r'from sqlalchemy import \1, Float, Boolean, DateTime, Text', code, flags=re.MULTILINE)
    if 'from fastapi import' in code and 'Depends' not in code:
        code = re.sub(r'^from\s+fastapi\s+import\s+([a-zA-Z0-9_, \t]+)', r'from fastapi import \1, Depends, HTTPException, status', code, flags=re.MULTILINE)

    # 5.2 Dependency Patch: Fix Depends(instance) common error
    if 'Depends(' in code:
        # If 'db = SessionLocal()' exists, and 'Depends(db)' is used
        session_instances = re.findall(r'^(\w+)\s*=\s*SessionLocal\(\)', code, flags=re.MULTILINE)
        for inst in session_instances:
            # Avoid replacing if it's already a correct callable or string
            code = code.replace(f'Depends({inst})', 'Depends(get_db)')
            if 'def get_db()' not in code:
                # Inject a standard get_db generator if we are switching to it
                get_db_snippet = "\ndef get_db():\n    db = SessionLocal()\n    try:\n        yield db\n    finally:\n        db.close()\n"
                code = code.replace('SessionLocal = sessionmaker', 'SessionLocal = sessionmaker' + get_db_snippet)

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
    
    # 11. Reorder Definitions (Models to the top)
    if base_name != '__init__.py':
        code = reorder_definitions(code)
    
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
        # Insert after __future__ if it exists
        if code.startswith('from __future__'):
            parts = code.split('\n', 1)
            return parts[0] + "\n" + "\n".join(to_add) + "\n" + (parts[1] if len(parts) > 1 else "")
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
        logger.warning(f"AST unparse failed for strip_unused_imports: {e}")
        return code

def reorder_definitions(code: str) -> str:
    """Moves class definitions and imports to the top, and functions/logic to the bottom."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
        
    imports = []
    classes = []
    functions = []
    others = []
    
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
        elif isinstance(node, ast.ClassDef):
            classes.append(node)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node)
        elif isinstance(node, ast.Assign):
            # Move ALL top-level assignments to the top section (imports)
            # This ensures constants, apps, and engines are available to decorators and functions
            imports.append(node)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            # Docstrings
            imports.insert(0, node)
        else:
            others.append(node)
            
    # New order: Docstrings -> Imports -> Assignments -> Classes -> Functions -> Main Logic
    # NOTE: Classes MUST be before Functions so that decorators can resolve response_models
    tree.body = imports + classes + functions + others
    
    try:
        return ast.unparse(tree)
    except:
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
        
    # 4. SYSTEM MARKER STRIPPING
    system_markers = [
        r'# \[SYSTEM NOTE:.*\]',
        r'# \[TRUNCATED.*\]',
        r'# \.\.\. \[truncated\]',
        r'# Rest of file truncated.*',
        r'# \[TRUNCATED DUE TO REPETITION LOOP\]'
    ]
    for marker in system_markers:
        clean_content = re.sub(marker, '', clean_content, flags=re.IGNORECASE | re.MULTILINE)

    # 4.1 DIVERSITY WATCHDOG (Consecutive Repetition Loop Breaker)
    lines = clean_content.split('\n')
    if len(lines) > 50:
        for i in range(len(lines) - 10):
            # Check if current line + next 4 lines repeat consecutively
            block_lines = lines[i:i+5]
            block = "\n".join(block_lines)
            if not block.strip(): continue
            
            # Look for immediate consecutive repetition
            next_block_lines = lines[i+5:i+10]
            next_block = "\n".join(next_block_lines)
            
            if block == next_block:
                # We have a consecutive loop!
                logger.warning(f"Diversity Watchdog: Consecutive repetition detected at line {i}. Truncating.")
                clean_content = "\n".join(lines[:i+5]).rstrip() + f"\n    pass # [TRUNCATED DUE TO REPETITION LOOP]\n"
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
