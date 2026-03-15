# Autonomous Software Foundry — Complete Fixes & Changes Master Document
 
> **Scope:** All pipeline bugs, multi-language refactor, Knowledge Graph deep integration  
> **Languages targeted:** Python · JavaScript/Node.js · TypeScript · Java  
> **Model:** Qwen2.5-Coder-7B (Ollama)  
> **Status at time of writing:** E2E tests failing, KG partially wired, sandbox partially connected
 
---
 
## Table of Contents
 
1. [Critical Pipeline Fixes (Do These First)](#1-critical-pipeline-fixes)
2. [Multi-Language Refactor](#2-multi-language-refactor)
3. [Knowledge Graph — Current State Assessment](#3-knowledge-graph-current-state-assessment)
4. [Knowledge Graph — Deep Integration Plan](#4-knowledge-graph-deep-integration-plan)
5. [Agent-by-Agent Fix List](#5-agent-by-agent-fix-list)
6. [Orchestrator Fixes](#6-orchestrator-fixes)
7. [Infrastructure & DevOps Fixes](#7-infrastructure--devops-fixes)
8. [Ollama Stability Fixes](#8-ollama-stability-fixes)
9. [What to Throw Away](#9-what-to-throw-away)
10. [Execution Order](#10-execution-order)
 
---
 
## 1. Critical Pipeline Fixes
 
These 6 fixes are the reason **every E2E test currently fails**. Do these before anything else. Each is a small, isolated change.
 
---
 
### FIX-1 · docker-compose.yml · Add generated_projects volume mount
 
**Problem:** Generated files exist inside the container but are invisible on the host. Every E2E test sees nothing.
 
**File:** `docker-compose.yml`
 
```yaml
# Add to BOTH the api service and celery-worker service:
volumes:
  - ./generated_projects:/app/generated_projects
```
 
---
 
### FIX-2 · orchestrator.py · State merge — all nodes destroy context
 
**Problem:** Every node returns a fresh `project_context` dict. LangGraph's TypedDict uses last-write-wins for non-annotated fields, so every node transition silently wipes whatever the previous node added. This is why `code_repo` disappears before reflexion can see it.
 
**File:** `src/foundry/orchestrator.py`
 
```python
# WRONG — every node currently does this:
return {
    "project_context": {"code_repo": code_repo, "architecture": architecture}
    # ^^^ wipes prd, requirements, language, everything else
}
 
# CORRECT — every node must do this:
return {
    "project_context": {**state["project_context"], "code_repo": code_repo}
    # ^^^ merges into existing context
}
```
 
**Nodes that need this fix:** `_pm_node`, `_architect_node`, `_engineer_node`, `_code_review_node`, `_reflexion_node`, `_devops_node` — all 6.
 
---
 
### FIX-3 · orchestrator.py · review_feedback key mismatch
 
**Problem:** `_reflexion_node` reads `state["review_feedback"].get("comments", "")` but `CodeReviewAgent` returns the key `"feedback"`. Reflexion always gets an empty string as context and cannot generate targeted fixes.
 
**File:** `src/foundry/orchestrator.py`, function `_reflexion_node`
 
```python
# WRONG:
review_comments = state["review_feedback"].get("comments", "")
 
# CORRECT:
review_comments = (
    state["review_feedback"].get("feedback")
    or state["review_feedback"].get("comments", "")
)
```
 
---
 
### FIX-4 · reflexion.py · Missing QualityGates import
 
**Problem:** `__init__` does `self.quality_gates = QualityGates()` but `QualityGates` is not imported. The reflexion agent crashes on instantiation with `NameError`, meaning the entire reflexion/fix pipeline has never run.
 
**File:** `src/foundry/agents/reflexion.py`
 
```python
# Add to imports at top of file:
from foundry.testing.quality_gates import QualityGates
```
 
---
 
### FIX-5 · orchestrator.py · MAX_REFLEXION_RETRIES boundary condition
 
**Problem:** `_should_continue_from_review` checks `reflexion_count < MAX_REFLEXION_RETRIES` (3). But `reflexion_count` is incremented *inside* the reflexion node, not before the routing decision. This allows 4 attempts, not 3. If the state merge bug above causes `reflexion_count` not to persist, this loops forever.
 
**File:** `src/foundry/orchestrator.py`
 
```python
# WRONG:
if state.get("reflexion_count", 0) < MAX_REFLEXION_RETRIES:
    return "fix"
 
# CORRECT:
if state.get("reflexion_count", 0) >= MAX_REFLEXION_RETRIES:
    return "fail"
return "fix"
```
 
---
 
### FIX-6 · reflexion.py · Reflexion returns fix_plan text, not updated code
 
**Problem:** `execute_and_fix()` generates a `fix_plan` string via LLM and returns it in the payload. The orchestrator passes this text back to the engineer as `fix_instructions`. The engineer then *regenerates from scratch* using this text as soft guidance — which a 7B model frequently ignores. The reflexion loop has never actually fixed code.
 
**File:** `src/foundry/agents/reflexion.py`, `src/foundry/orchestrator.py`
 
In `reflexion.py` — after generating the fix plan, apply it to the repo:
 
```python
# After generating fix_plan via LLM, apply it:
updated_repo = await self._apply_fix_plan_to_repo(fix_plan, current_repo)
 
return AgentMessage(
    sender=self.agent_type,
    recipient=AgentType.ENGINEER,
    message_type=MessageType.RESPONSE,
    payload={
        "fix_plan": fix_plan,
        "code_repo": updated_repo,   # <-- orchestrator uses this
        "status": "fixed"
    }
)
```
 
In `orchestrator.py` — `_reflexion_node` must put the fixed code back into project_context:
 
```python
async def _reflexion_node(self, state: GraphState) -> Dict[str, Any]:
    # ... (send message, get response) ...
    
    fixed_code_repo = response.payload.get("code_repo", state["project_context"].get("code_repo", {}))
    fix_plan = response.payload.get("fix_plan", "")
    
    return {
        "messages": [...],
        "project_context": {
            **state["project_context"],
            "code_repo": fixed_code_repo,   # <-- fixed code replaces broken code
            "last_fix_plan": fix_plan
        },
        "review_feedback": {
            **state["review_feedback"],
            "reflexion_fix": fix_plan
        },
        "reflexion_count": state.get("reflexion_count", 0) + 1
    }
```
 
---
 
## 2. Multi-Language Refactor
 
You are adding Python, JavaScript/Node.js, TypeScript, and Java. Every piece of "Python-only" enforcement in the codebase must be replaced with language-aware equivalents.
 
---
 
### 2.1 · Project model — add language field
 
**File:** `src/foundry/models/project.py`
 
```python
class Project(Base):
    # ... existing fields ...
    language: Mapped[str] = mapped_column(String(50), default="python")
    framework: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
```
 
**File:** `src/foundry/main.py` — `ProjectCreateRequest`
 
```python
class ProjectCreateRequest(BaseModel):
    requirements: str
    language: str = "python"   # "python" | "javascript" | "typescript" | "java"
    framework: Optional[str] = None  # "fastapi" | "express" | "spring" | etc.
```
 
---
 
### 2.2 · LangGraph state — add language to GraphState
 
**File:** `src/foundry/orchestrator.py`
 
```python
class GraphState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    current_agent: str
    project_context: Dict[str, Any]
    review_feedback: Dict[str, Any]
    project_id: str
    reflexion_count: int
    success_flag: bool
    language: str        # NEW — propagates through all nodes
    framework: str       # NEW — e.g. "express", "spring-boot", "fastapi"
```
 
Pass it through the `run()` method:
 
```python
async def run(self, project_id: str, initial_prompt: str, language: str = "python", framework: str = ""):
    initial_state = {
        ...
        "language": language,
        "framework": framework,
    }
```
 
---
 
### 2.3 · Language config module (new file)
 
**File:** `src/foundry/utils/language_config.py`  
**Purpose:** Single source of truth for all language-specific settings. Every agent reads from here instead of hardcoding.
 
```python
from dataclasses import dataclass, field
from typing import List, Dict
 
@dataclass
class LanguageConfig:
    name: str
    extensions: List[str]
    test_framework: str
    linter: str
    type_checker: str
    package_file: str
    entry_point: str
    coding_standard: str
    web_frameworks: List[str]
    docker_base_image: str
    sandbox_setup_cmd: str
 
LANGUAGE_CONFIGS: Dict[str, LanguageConfig] = {
    "python": LanguageConfig(
        name="python",
        extensions=[".py"],
        test_framework="pytest",
        linter="pylint",
        type_checker="mypy",
        package_file="requirements.txt",
        entry_point="main.py",
        coding_standard="PEP 8",
        web_frameworks=["fastapi", "flask", "django"],
        docker_base_image="python:3.11-slim",
        sandbox_setup_cmd="pip install -r requirements.txt"
    ),
    "javascript": LanguageConfig(
        name="javascript",
        extensions=[".js", ".mjs", ".cjs"],
        test_framework="jest",
        linter="eslint",
        type_checker="none",
        package_file="package.json",
        entry_point="index.js",
        coding_standard="Airbnb Style Guide",
        web_frameworks=["express", "fastify", "koa", "hapi"],
        docker_base_image="node:20-slim",
        sandbox_setup_cmd="npm install"
    ),
    "typescript": LanguageConfig(
        name="typescript",
        extensions=[".ts", ".tsx"],
        test_framework="jest",
        linter="eslint",
        type_checker="tsc",
        package_file="package.json",
        entry_point="src/index.ts",
        coding_standard="TypeScript strict mode",
        web_frameworks=["express", "nestjs", "fastify"],
        docker_base_image="node:20-slim",
        sandbox_setup_cmd="npm install"
    ),
    "java": LanguageConfig(
        name="java",
        extensions=[".java"],
        test_framework="junit5",
        linter="checkstyle",
        type_checker="javac",
        package_file="pom.xml",
        entry_point="src/main/java/Main.java",
        coding_standard="Google Java Style Guide",
        web_frameworks=["spring-boot", "quarkus", "micronaut"],
        docker_base_image="eclipse-temurin:21-jdk-slim",
        sandbox_setup_cmd="mvn install -q"
    ),
}
 
def get_config(language: str) -> LanguageConfig:
    return LANGUAGE_CONFIGS.get(language.lower(), LANGUAGE_CONFIGS["python"])
```
 
---
 
### 2.4 · Remove all Python-hardcoded enforcement
 
**Files to change:** `architect.py`, `engineer.py`, `code_review.py`, `orchestrator.py`, `product_manager.py`
 
Replace every instance of:
- `"ABSOLUTE PYTHON REQUIREMENT"` → `f"Generate {language} code following {config.coding_standard}"`
- `"PROHIBITED: No JavaScript, No Node.js"` → remove entirely
- `_recover_with_python_force()` → `_recover_with_correct_language(filename, code, language)`
- `forbidden_exts = ['.js', '.ts', '.jsx', ...]` in `_store_artifact` → remove entirely
- `"ABSOLUTE PYTHON REQUIREMENT"` in `_plan_file_structure` → use `config.extensions`
- `CODING_STANDARDS = {"python": "PEP 8"}` → import from `language_config.py`
 
**Specific changes in `engineer.py`:**
 
```python
# OLD:
CODING_STANDARDS = {"python": "PEP 8 (Strict Enforcement)"}
 
# NEW:
from foundry.utils.language_config import get_config
# Use get_config(language).coding_standard in all prompts
```
 
```python
# OLD: _detect_language always returns "python"
def _detect_language(self, architecture_content: str) -> str:
    return "python"
 
# NEW: use language from state/payload
def _detect_language(self, architecture_content: str, requested_language: str = "python") -> str:
    return requested_language  # trust what the user asked for
```
 
---
 
### 2.5 · Wrong-language detection (replaces JS leakage blocking)
 
Instead of blocking JS, validate that generated code matches the *requested* language.
 
**File:** `src/foundry/utils/language_guards.py` (new file)
 
```python
import re
from typing import Dict
 
# Patterns that indicate a SPECIFIC language was generated
LANGUAGE_INDICATORS: Dict[str, re.Pattern] = {
    "python": re.compile(r'\b(def |import |from .+ import|class .+:|print\(|if __name__)', re.M),
    "javascript": re.compile(r'\b(const |let |var |require\(|module\.exports|export default|=>\s*{)', re.M),
    "typescript": re.compile(r'(: string|: number|: boolean|interface |type .+ =|<T>)', re.M),
    "java": re.compile(r'\b(public class|import java\.|System\.out|@Override|void )', re.M),
}
 
def detect_actual_language(code: str) -> str:
    """Detect what language the code actually is."""
    scores = {}
    for lang, pattern in LANGUAGE_INDICATORS.items():
        scores[lang] = len(pattern.findall(code))
    return max(scores, key=scores.get)
 
def is_wrong_language(code: str, expected: str) -> bool:
    """Returns True if the code appears to be in a different language than expected."""
    actual = detect_actual_language(code)
    if actual == expected:
        return False
    # Allow some overlap (e.g. TypeScript has JS patterns)
    if expected == "typescript" and actual == "javascript":
        return False
    return True
```
 
Use this in `engineer.py` instead of `_has_js_leakage()`:
 
```python
from foundry.utils.language_guards import is_wrong_language
 
# In generate_code loop:
if is_wrong_language(code, language):
    code = await self._recover_with_correct_language(filename, code, language)
```
 
---
 
### 2.6 · Multi-language code parser for KG (see Section 4)
 
The current `code_parser.py` only handles Python AST. Section 4.3 covers the full multi-language parser plan.
 
---
 
### 2.7 · ingestion_pipeline — pass language through
 
**File:** `src/foundry/graph/ingestion.py`
 
```python
async def ingest_project(
    self,
    project_id: str,
    project_name: str,
    project_path: str,
    language: str = "python",    # NEW
    metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    # Route to correct parser based on language
    parser = self._get_parser(language)
    ...
 
def _get_parser(self, language: str):
    from foundry.utils.language_config import get_config
    config = get_config(language)
    # Return appropriate parser (see Section 4.3)
```
 
---
 
### 2.8 · test_generator.py — complete the framework map
 
**File:** `src/foundry/testing/test_generator.py`
 
```python
# Current FRAMEWORK_MAP only has pytest. Expand it:
from enum import Enum
 
class TestFramework(Enum):
    PYTEST = "pytest"
    JEST = "jest"
    VITEST = "vitest"
    JUNIT = "junit5"
    MOCHA = "mocha"
 
FRAMEWORK_MAP = {
    "python": TestFramework.PYTEST,
    "javascript": TestFramework.JEST,
    "typescript": TestFramework.JEST,
    "java": TestFramework.JUNIT,
}
```
 
---
 
## 3. Knowledge Graph — Current State Assessment
 
### What currently exists and works
 
| Component | File | Status | Notes |
|-----------|------|--------|-------|
| Neo4j client connection | `graph/neo4j_client.py` | ✅ Working | Connect/disconnect, execute_query/write |
| Project node creation | `services/knowledge_graph.py` | ✅ Working | `create_project()` |
| Function/Class/Module storage | `services/knowledge_graph.py` | ✅ Working | Stores with `content` field for GraphRAG |
| DEPENDS_ON relationships | `services/knowledge_graph.py` | ✅ Working | `store_dependency_relationship()` |
| CALLS relationships | `services/knowledge_graph.py` | ✅ Working | `create_call_relationship()` |
| Python AST parser | `graph/code_parser.py` | ✅ Working | Extracts functions, classes, imports, content snippets |
| Ingestion pipeline | `graph/ingestion.py` | ✅ Working | Full two-pass ingestion (nodes then relationships) |
| `get_surgical_context()` | `tools/knowledge_graph_tools.py` | ✅ Implemented | GraphRAG retrieval — but **not called by any agent** |
| `get_project_file_map()` | `tools/knowledge_graph_tools.py` | ✅ Implemented | **Not called by any agent** |
| Impact analysis | `tools/knowledge_graph_tools.py` | ✅ Implemented | **Not called by any agent** |
| Cross-project patterns | — | ❌ Missing | No `Pattern` node type, no cross-project queries |
| JavaScript parser | — | ❌ Missing | Ingestion only handles `.py` files |
| Java parser | — | ❌ Missing | Same |
| Architecture decisions in KG | — | ❌ Missing | No `ArchitectureDecision` node |
| PRD/requirements in KG | — | ❌ Missing | No `Requirement` node |
| KG used during code gen | `engineer.py` | ⚠️ Partial | `kg_tools` exists but only used during fix mode, not initial generation |
| KG used during reflexion | `reflexion.py` | ❌ Not connected | `kg_tools` attribute exists but never called |
| KG ingestion after generation | `orchestrator.py` | ✅ Called | But uses hardcoded `"Python Project"` name — needs language |
| KG error on Neo4j offline | All agents | ⚠️ Silently swallowed | Try/except logs but continues — acceptable |
 
### Core Problem: The KG is write-only from the agents' perspective
 
Data flows **into** the KG after code generation (ingestion pipeline), but **nothing flows back out** to inform generation. `get_surgical_context()`, impact analysis, and the file map are all implemented but never called. The KG is currently a write-only audit log, not an active context system.
 
---
 
## 4. Knowledge Graph — Deep Integration Plan
 
### 4.1 · New node types needed
 
**File:** `src/foundry/services/knowledge_graph.py` — add these store methods:
 
```python
# Node: Requirement — stores the original PRD
async def store_requirement(self, project_id: str, req_id: str, 
                             text: str, req_type: str) -> None:
    query = """
    MATCH (p:Project {id: $project_id})
    CREATE (r:Requirement {id: $req_id, text: $text, type: $req_type, created_at: datetime()})
    CREATE (p)-[:HAS_REQUIREMENT]->(r)
    """
    await self.client.execute_write(query, {...})
 
# Node: ArchitectureDecision — stores architect's choices
async def store_architecture_decision(self, project_id: str, decision_id: str,
                                       title: str, decision: str, rationale: str,
                                       language: str, framework: str) -> None:
    query = """
    MATCH (p:Project {id: $project_id})
    CREATE (d:ArchitectureDecision {
        id: $decision_id, title: $title, decision: $decision,
        rationale: $rationale, language: $language, framework: $framework,
        created_at: datetime()
    })
    CREATE (p)-[:HAS_DECISION]->(d)
    """
    await self.client.execute_write(query, {...})
 
# Node: Pattern — stores reusable cross-project patterns
async def store_pattern(self, pattern_id: str, name: str, description: str,
                         language: str, pattern_type: str, 
                         code_template: str, success_count: int = 1) -> None:
    query = """
    MERGE (pat:Pattern {name: $name, language: $language, type: $pattern_type})
    ON CREATE SET pat.id = $pattern_id, pat.description = $description,
                  pat.code_template = $code_template, pat.success_count = $success_count,
                  pat.created_at = datetime()
    ON MATCH SET pat.success_count = pat.success_count + 1,
                 pat.updated_at = datetime()
    """
    await self.client.execute_write(query, {...})
 
# Node: ErrorFix — stores successful error→fix pairs for learning
async def store_error_fix(self, project_id: str, fix_id: str, error_type: str,
                           error_message: str, fix_applied: str,
                           language: str, was_successful: bool) -> None:
    query = """
    MATCH (p:Project {id: $project_id})
    CREATE (f:ErrorFix {
        id: $fix_id, error_type: $error_type, error_message: $error_message,
        fix_applied: $fix_applied, language: $language,
        was_successful: $was_successful, created_at: datetime()
    })
    CREATE (p)-[:HAS_FIX]->(f)
    """
    await self.client.execute_write(query, {...})
```
 
---
 
### 4.2 · New query methods needed
 
**File:** `src/foundry/tools/knowledge_graph_tools.py` — add these:
 
```python
async def get_similar_error_fixes(
    self, language: str, error_type: str, limit: int = 3
) -> List[Dict[str, Any]]:
    """Cross-project: find fixes that worked for similar errors in the same language."""
    query = """
    MATCH (f:ErrorFix {language: $language, error_type: $error_type, was_successful: true})
    RETURN f.error_message as error, f.fix_applied as fix, f.created_at as when
    ORDER BY f.created_at DESC
    LIMIT $limit
    """
    results = await self.kg_service.client.execute_query(
        query, {"language": language, "error_type": error_type, "limit": limit}
    )
    return [dict(r) for r in results]
 
async def get_successful_patterns(
    self, language: str, pattern_type: str, limit: int = 5
) -> List[Dict[str, Any]]:
    """Cross-project: return most-used successful patterns for a language."""
    query = """
    MATCH (pat:Pattern {language: $language, type: $pattern_type})
    WHERE pat.success_count > 0
    RETURN pat.name as name, pat.description as description,
           pat.code_template as template, pat.success_count as uses
    ORDER BY pat.success_count DESC
    LIMIT $limit
    """
    results = await self.kg_service.client.execute_query(
        query, {"language": language, "pattern_type": pattern_type, "limit": limit}
    )
    return [dict(r) for r in results]
 
async def get_architecture_context(
    self, project_id: str
) -> str:
    """Get architecture decisions stored for this project, formatted for LLM."""
    query = """
    MATCH (p:Project {id: $project_id})-[:HAS_DECISION]->(d:ArchitectureDecision)
    RETURN d.title as title, d.decision as decision, d.rationale as rationale
    """
    results = await self.kg_service.client.execute_query(
        query, {"project_id": project_id}
    )
    if not results:
        return ""
    parts = [f"- {r['title']}: {r['decision']} (Rationale: {r['rationale']})" 
             for r in results]
    return "ARCHITECTURE DECISIONS IN THIS PROJECT:\n" + "\n".join(parts)
 
async def get_project_summary_for_generation(
    self, project_id: str, filename_being_generated: str
) -> str:
    """
    The main GraphRAG entry point for the engineer agent.
    Returns a compact, LLM-ready summary of what exists in the project
    that is relevant to the file currently being generated.
    """
    # 1. Get file map (what exists)
    file_map = await self.get_project_file_map(project_id)
    
    # 2. Find components this file likely depends on based on naming
    base_name = filename_being_generated.replace("/", "_").replace(".", "_")
    
    # 3. Get surgical context for likely dependencies
    all_exports = []
    for f in file_map:
        exports = f.get("exports", [])
        if isinstance(exports, list):
            all_exports.extend(exports)
    
    surgical = await self.get_surgical_context(
        project_id=project_id,
        dependency_names=all_exports[:10],  # cap to avoid context bloat
        max_snippet_chars=800
    )
    
    # 4. Get architecture decisions
    arch_context = await self.get_architecture_context(project_id)
    
    # Format compact summary
    summary_parts = []
    if file_map:
        files_list = [f["file_path"] for f in file_map]
        summary_parts.append(f"EXISTING FILES IN PROJECT:\n" + "\n".join(f"  - {f}" for f in files_list))
    if surgical:
        summary_parts.append(surgical)
    if arch_context:
        summary_parts.append(arch_context)
    
    return "\n\n".join(summary_parts)
```
 
---
 
### 4.3 · Multi-language code parsers
 
The current `python_parser` only handles `.py` files. Add language-specific parsers.
 
**File:** `src/foundry/graph/js_parser.py` (new)
 
```python
"""
JavaScript/TypeScript code parser using regex-based extraction.
(No AST dependency — keeps it lightweight for local inference.)
"""
import re
from typing import Optional, Dict, List
from foundry.graph.code_parser import ParsedModule, FunctionInfo, ClassInfo, ImportInfo
 
class JSCodeParser:
    """Parser for JavaScript and TypeScript using regex."""
    
    def parse_file(self, file_path: str, language: str = "javascript") -> Optional[ParsedModule]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
        except Exception:
            return None
        
        module = ParsedModule(file_path=file_path)
        
        # Extract imports: import X from 'y' / const X = require('y')
        import_patterns = [
            r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]",
            r"require\(['\"]([^'\"]+)['\"]\)",
        ]
        for pat in import_patterns:
            for match in re.finditer(pat, source, re.MULTILINE):
                module.imports.append(ImportInfo(module=match.group(1), is_from_import=True))
        
        # Extract function declarations and arrow functions assigned to const/let
        func_patterns = [
            r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)",
            r"(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>",
        ]
        for pat in func_patterns:
            for match in re.finditer(pat, source, re.MULTILINE):
                name = match.group(1)
                start = match.start()
                # Estimate line number
                line_num = source[:start].count("\n") + 1
                # Extract a snippet (~20 lines from start)
                snippet_end = source.find("\n", start + 400) if len(source) > start + 400 else len(source)
                module.functions.append(FunctionInfo(
                    name=name, signature=match.group(0),
                    line_number=line_num, end_line=line_num + 10,
                    complexity=1, is_async="async" in match.group(0),
                    content=source[start:snippet_end]
                ))
        
        # Extract classes
        for match in re.finditer(r"class\s+(\w+)(?:\s+extends\s+(\w+))?", source, re.MULTILINE):
            line_num = source[:match.start()].count("\n") + 1
            module.classes.append(ClassInfo(
                name=match.group(1),
                line_number=line_num, end_line=line_num + 20,
                base_classes=[match.group(2)] if match.group(2) else [],
            ))
        
        return module
    
    def parse_directory(self, directory: str, language: str = "javascript") -> Dict[str, ParsedModule]:
        from pathlib import Path
        extensions = [".js", ".mjs"] if language == "javascript" else [".ts", ".tsx"]
        result = {}
        for ext in extensions:
            for f in Path(directory).rglob(f"*{ext}"):
                if any(skip in str(f) for skip in ["node_modules", ".git", "dist", "build"]):
                    continue
                parsed = self.parse_file(str(f), language)
                if parsed:
                    result[str(f)] = parsed
        return result
 
js_parser = JSCodeParser()
```
 
**File:** `src/foundry/graph/java_parser.py` (new)
 
```python
"""
Java code parser using regex-based extraction.
"""
import re
from typing import Optional, Dict
from foundry.graph.code_parser import ParsedModule, FunctionInfo, ClassInfo, ImportInfo
 
class JavaCodeParser:
    
    def parse_file(self, file_path: str) -> Optional[ParsedModule]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
        except Exception:
            return None
        
        module = ParsedModule(file_path=file_path)
        
        # Imports
        for match in re.finditer(r"import\s+([\w.]+);", source):
            module.imports.append(ImportInfo(module=match.group(1), is_from_import=True))
        
        # Classes and interfaces
        for match in re.finditer(
            r"(?:public|private|protected)?\s*(?:abstract\s+)?(?:class|interface|enum)\s+(\w+)"
            r"(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?",
            source, re.MULTILINE
        ):
            line_num = source[:match.start()].count("\n") + 1
            module.classes.append(ClassInfo(
                name=match.group(1), line_number=line_num, end_line=line_num + 50,
                base_classes=[match.group(2)] if match.group(2) else [],
            ))
        
        # Methods
        for match in re.finditer(
            r"(?:public|private|protected)\s+(?:static\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)",
            source, re.MULTILINE
        ):
            line_num = source[:match.start()].count("\n") + 1
            module.functions.append(FunctionInfo(
                name=match.group(1), signature=match.group(0),
                line_number=line_num, end_line=line_num + 15,
                complexity=1, is_async=False,
            ))
        
        return module
    
    def parse_directory(self, directory: str) -> Dict[str, ParsedModule]:
        from pathlib import Path
        result = {}
        for f in Path(directory).rglob("*.java"):
            if any(skip in str(f) for skip in [".git", "target", "build"]):
                continue
            parsed = self.parse_file(str(f))
            if parsed:
                result[str(f)] = parsed
        return result
 
java_parser = JavaCodeParser()
```
 
Update `src/foundry/graph/__init__.py`:
 
```python
from foundry.graph.js_parser import js_parser, JSCodeParser
from foundry.graph.java_parser import java_parser, JavaCodeParser
```
 
Update `src/foundry/graph/ingestion.py` to route by language:
 
```python
def _get_parser(self, language: str):
    if language in ("javascript", "typescript"):
        from foundry.graph.js_parser import js_parser
        return js_parser
    elif language == "java":
        from foundry.graph.java_parser import java_parser
        return java_parser
    else:
        return self.parser  # existing python_parser
```
 
---
 
### 4.4 · Wire KG into Engineer agent — GraphRAG code generation
 
**File:** `src/foundry/agents/engineer.py`
 
This replaces the current "pass all previously generated files as context" approach with surgical KG retrieval.
 
```python
async def _generate_file_content(
    self, filename: str, architecture: str, language: str,
    previously_generated: Dict[str, str] = None,
    prd: str = "", fix_instructions: str = "",
    existing_version: str = None, project_id: str = "current"
) -> str:
    config = get_config(language)
    
    # --- KG CONTEXT RETRIEVAL (replaces "pass all previous files") ---
    kg_context = ""
    if self.kg_tools and project_id != "current":
        try:
            kg_context = await self.kg_tools.get_project_summary_for_generation(
                project_id=project_id,
                filename_being_generated=filename
            )
        except Exception as e:
            logger.warning(f"KG context retrieval failed (non-fatal): {e}")
    
    # Only fall back to raw previous files if KG returned nothing
    context_str = kg_context
    if not context_str and previously_generated:
        # Keep the old approach as fallback, but truncate aggressively
        for prev_file, prev_code in list(previously_generated.items())[:2]:
            truncated = prev_code[-1500:] if len(prev_code) > 1500 else prev_code
            context_str += f"\n--- {prev_file} (existing) ---\n{truncated}\n"
 
    system_prompt = f"""You are an expert Software Engineer specializing in {language}.
Generate the content for: {filename}
Language: {language}
Standard: {config.coding_standard}
 
{context_str}
 
ARCHITECTURE:
{architecture}
 
PRD:
{prd}
 
Requirements:
1. Generate ONLY {language} code.
2. Follow {config.coding_standard}.
3. Use {config.test_framework} patterns where applicable.
4. Include error handling and input validation.
5. No hardcoded secrets — use environment variables.
6. Add type hints/JSDoc/Javadoc as appropriate for {language}.
 
Return ONLY the code. No markdown fences. No explanations.
"""
    ...
```
 
---
 
### 4.5 · Wire KG into Reflexion agent — error fix learning
 
**File:** `src/foundry/agents/reflexion.py`
 
```python
async def execute_and_fix(self, code_repo, language="python", ...):
    for attempt in range(self.MAX_RETRY_ATTEMPTS):
        result = await self.execute_code(code_repo, self.sandbox_env, language, entry_point)
        
        if result.success:
            # STORE SUCCESS PATTERN in KG
            if self.kg_tools:
                try:
                    for filename, code in code_repo.items():
                        # Store file map for future context
                        pass  # Already handled by ingestion pipeline
                except Exception:
                    pass
            # Return success (see FIX-6)
            ...
        
        analysis = await self.analyze_errors(result)
        
        # QUERY KG for similar past fixes before generating a new one
        kg_fix_context = ""
        if self.kg_tools:
            try:
                similar_fixes = await self.kg_tools.get_similar_error_fixes(
                    language=language,
                    error_type=analysis.error_type,
                    limit=2
                )
                if similar_fixes:
                    kg_fix_context = "\nSIMILAR FIXES THAT WORKED IN PAST PROJECTS:\n"
                    for fix in similar_fixes:
                        kg_fix_context += f"- Error: {fix['error'][:100]}\n  Fix: {fix['fix'][:200]}\n"
            except Exception:
                pass
        
        # Include KG context in the fix generation prompt
        fixes = await self._generate_llm_fixes(analysis, code_repo, kg_fix_context)
        
        # After applying fix — STORE this error/fix pair in KG
        if self.kg_tools:
            try:
                await self.kg_tools.kg_service.store_error_fix(
                    project_id=project_id,
                    fix_id=str(uuid4()),
                    error_type=analysis.error_type,
                    error_message=analysis.error_message[:500],
                    fix_applied=str(fixes[0].fixed_code)[:500] if fixes else "",
                    language=language,
                    was_successful=False  # will be updated on next successful run
                )
            except Exception:
                pass
```
 
---
 
### 4.6 · Wire KG into Architect agent — store and retrieve decisions
 
**File:** `src/foundry/agents/architect.py`
 
After `design_architecture()` succeeds, store the key decisions:
 
```python
async def design_architecture(self, prd_content: str, project_id: str = "current", 
                               language: str = "python", framework: str = "") -> AgentMessage:
    # ... existing generation ...
    
    # STORE architecture decision in KG
    if self.kg_tools and project_id != "current":
        try:
            await self.kg_tools.kg_service.store_architecture_decision(
                project_id=project_id,
                decision_id=str(uuid4()),
                title=f"Technology Stack: {language}/{framework}",
                decision=f"Language: {language}, Framework: {framework}",
                rationale=f"Based on PRD requirements: {prd_content[:200]}",
                language=language,
                framework=framework
            )
        except Exception as e:
            logger.warning(f"Failed to store architecture decision: {e}")
    
    # QUERY KG for similar successful architectures from past projects
    pattern_context = ""
    if self.kg_tools:
        try:
            patterns = await self.kg_tools.get_successful_patterns(
                language=language,
                pattern_type="architecture",
                limit=2
            )
            if patterns:
                pattern_context = "\nSUCCESSFUL PATTERNS FROM SIMILAR PROJECTS:\n"
                for p in patterns:
                    pattern_context += f"- {p['name']}: {p['description']}\n"
        except Exception:
            pass
```
 
---
 
### 4.7 · Store PRD requirements in KG
 
**File:** `src/foundry/agents/product_manager.py`
 
After PRD is generated and validated:
 
```python
async def analyze_requirements(self, requirements: str, project_id: str = "current") -> AgentMessage:
    # ... existing generation ...
    
    if self.kg_tools and project_id != "current":
        try:
            prd_dict = json.loads(prd_content)  # if valid JSON
            for i, feature in enumerate(prd_dict.get("core_features", [])):
                await self.kg_tools.kg_service.store_requirement(
                    project_id=project_id,
                    req_id=f"{project_id}_req_{i}",
                    text=feature,
                    req_type="functional"
                )
        except Exception:
            pass
```
 
---
 
### 4.8 · Update orchestrator KG ingestion call
 
**File:** `src/foundry/orchestrator.py`, `_engineer_node`
 
```python
# Current (broken for multi-language):
await ingestion_pipeline.ingest_project(
    project_id=state["project_id"],
    project_name=f"Python Project {state['project_id'][:8]}",  # WRONG
    project_path=project_path
)
 
# Fixed:
language = state.get("language", "python")
await ingestion_pipeline.ingest_project(
    project_id=state["project_id"],
    project_name=f"{language.title()} Project {state['project_id'][:8]}",
    project_path=project_path,
    language=language   # NEW — routes to correct parser
)
```
 
---
 
## 5. Agent-by-Agent Fix List
 
### 5.1 · Product Manager Agent
 
**File:** `src/foundry/agents/product_manager.py`
 
| # | Issue | Fix |
|---|-------|-----|
| PM-1 | JSON parsing fails silently on fenced responses | Add `_extract_json()` that strips ` ```json ` fences and falls back to regex `{.*}` extraction |
| PM-2 | PRD schema too minimal — missing NFRs and acceptance criteria | Expand JSON schema to include `functional_requirements`, `non_functional_requirements`, `acceptance_criteria`, `out_of_scope` |
| PM-3 | No clarifying questions — Req 2.2 unimplemented | Add ambiguity detection: if input < 20 words or < 2 nouns, generate 2-3 questions before PRD |
| PM-4 | `pm_debug.json` written to CWD in production | Gate behind `if settings.debug:` |
| PM-5 | Domain drift retry is too aggressive on short inputs | Replace keyword-count heuristic with domain-noun extraction using NLTK or simple noun list |
| PM-6 | `process_message` ignores `project_id` | Accept and forward `project_id` from payload for KG storage (Section 4.7) |
 
**PM-1 fix — `_extract_json`:**
 
```python
def _extract_json(self, content: str) -> dict:
    # Strip markdown fences
    content = re.sub(r'^```(?:json)?\n?', '', content.strip(), flags=re.MULTILINE)
    content = re.sub(r'\n?```$', '', content.strip(), flags=re.MULTILINE)
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        # Try to find first complete JSON object
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"No valid JSON found in: {content[:200]}")
```
 
**PM-2 fix — expanded schema:**
 
```python
REQUIRED_SCHEMA = """
{
    "project_name": "...",
    "high_level_description": "...",
    "core_features": ["..."],
    "user_stories": ["As a user, I want to... so that..."],
    "functional_requirements": ["The system SHALL..."],
    "non_functional_requirements": ["Performance: ...", "Security: ..."],
    "acceptance_criteria": ["GIVEN... WHEN... THEN..."],
    "technical_constraints": ["..."],
    "out_of_scope": ["..."]
}
"""
```
 
---
 
### 5.2 · Architect Agent
 
**File:** `src/foundry/agents/architect.py`
 
| # | Issue | Fix |
|---|-------|-----|
| ARCH-1 | `_is_non_python_stack()` misses most JS/Node patterns | Expand keyword list — but make it language-aware for multi-language |
| ARCH-2 | `_self_correct_architecture()` output never re-validated | Add second pass through validation after correction |
| ARCH-3 | Architecture returned as raw string, not parsed JSON | Parse and validate JSON before forwarding |
| ARCH-4 | ADR example in prompt has React/TypeScript content | Replace with Python/FastAPI or language-appropriate example |
| ARCH-5 | `organize_file_structure()` has no language constraint | Add `language` parameter, use `get_config(language).extensions` |
| ARCH-6 | `design_architecture()` not language-aware | Accept `language` + `framework` params, inject into prompt |
 
**ARCH-1 + ARCH-6 combined fix:**
 
```python
async def design_architecture(self, prd_content: str, language: str = "python", 
                               framework: str = "", project_id: str = "current") -> AgentMessage:
    config = get_config(language)
    
    system_prompt = f"""You are an expert System Architect specializing in {language}.
Design a system architecture based on the PRD.
 
TARGET LANGUAGE: {language}
TARGET FRAMEWORK: {framework or config.web_frameworks[0]}
CODING STANDARD: {config.coding_standard}
PACKAGE MANAGER FILE: {config.package_file}
ENTRY POINT: {config.entry_point}
 
The Architecture Design MUST use {language} and {framework or config.web_frameworks[0]}.
Return ONLY a valid JSON object. No markdown fences.
"""
```
 
**ARCH-2 fix — double validation:**
 
```python
architecture_content = response.content
if self._is_wrong_stack(architecture_content, language):
    logger.warning("Wrong stack detected. Running self-correction...")
    architecture_content = await self._self_correct_architecture(
        architecture_content, prd_content, language, framework
    )
    # Second pass — if still wrong, use fallback
    if self._is_wrong_stack(architecture_content, language):
        logger.error("Self-correction failed. Using fallback template.")
        architecture_content = self._language_fallback_architecture(language, framework, prd_content)
```
 
**ARCH-3 fix — parse and validate JSON:**
 
```python
try:
    architecture_dict = self._extract_json(architecture_content)
    architecture_content = json.dumps(architecture_dict)  # normalized
except (ValueError, json.JSONDecodeError):
    logger.error("Architecture JSON invalid. Using fallback.")
    architecture_content = self._language_fallback_architecture(language, framework, prd_content)
```
 
---
 
### 5.3 · Engineer Agent
 
**File:** `src/foundry/agents/engineer.py`
 
| # | Issue | Fix |
|---|-------|-----|
| ENG-1 | Raw polluted architecture string in prompt | Sanitize using `language_guards.py` before injection |
| ENG-2 | `_detect_language()` always returns "python" | Use `requested_language` parameter from state |
| ENG-3 | JS detection patterns are incomplete | Replace with `is_wrong_language()` from `language_guards.py` |
| ENG-4 | `_recover_with_python_force()` is Python-specific | Rename to `_recover_with_correct_language(filename, code, language)` |
| ENG-5 | Recovery is one-shot, no retry loop | See FIX note below |
| ENG-6 | `_request_code_improvements()` has no language constraint | Add `language` param to prompt |
| ENG-7 | `_extract_imports()` has JS/TS branches | Remove all non-Python branches (or add language routing) |
| ENG-8 | `_plan_file_structure()` hardcodes `.py` extensions | Use `get_config(language).extensions` |
| ENG-9 | `write_code_to_disk()` uses different cleanup than `_clean_code()` | Use `_clean_code()` in both places |
| ENG-10 | File limit (3) + test gen = 6+ LLM calls → timeout on 7B | Make limit configurable, skip tests on budget exceeded |
| ENG-11 | CODING_STANDARDS dict is Python-only | Replace with `get_config(language).coding_standard` |
| ENG-12 | KG `kg_context` only used in fix mode | Use for initial generation too (Section 4.4) |
 
**ENG-5 fix — recovery loop:**
 
```python
for attempt in range(3):
    if is_wrong_language(code, language):
        logger.warning(f"Wrong language in {filename}, recovery attempt {attempt + 1}/3")
        code = await self._recover_with_correct_language(filename, code, language, architecture_content)
    else:
        break
else:
    # All 3 attempts still wrong language
    config = get_config(language)
    logger.error(f"FATAL: All recovery attempts failed for {filename}. Writing stub.")
    code = (
        f"# AUTO-STUB: Language enforcement failed after 3 attempts.\n"
        f"# This file requires manual implementation in {language}.\n"
        f"# File: {filename}\n"
    )
```
 
**ENG-4 fix — language-aware recovery:**
 
```python
async def _recover_with_correct_language(
    self, filename: str, dirty_code: str, language: str, architecture: str
) -> str:
    config = get_config(language)
    system_prompt = (
        f"CRITICAL: The generated code is in the wrong language. "
        f"You MUST rewrite it in {language} following {config.coding_standard}. "
        f"Use {config.web_frameworks[0]} for web logic if applicable. "
        f"Return ONLY the corrected {language} code."
    )
    user_prompt = f"File: {filename}\nArchitecture: {architecture}\n\nWrong-language code:\n{dirty_code}"
    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=user_prompt)
    ]
    response = await self.llm.generate(messages, temperature=0.1)
    return self._clean_code(response.content)
```
 
---
 
### 5.4 · Code Review Agent
 
**File:** `src/foundry/agents/code_review.py`
 
| # | Issue | Fix |
|---|-------|-----|
| REV-1 | Returns key `"feedback"` but orchestrator reads `"comments"` | Fixed in FIX-3 (orchestrator side) — also document correct key contract here |
| REV-2 | Structured `issues` list never forwarded to reflexion | Orchestrator must pass full issues list in reflexion payload |
| REV-3 | Bare `except` on JSON parse swallows all errors | Change to `except (json.JSONDecodeError, ValueError) as e:` |
| REV-4 | Quality gate sandbox results not added to issues list | Merge `gate_results.security_issues` and `gate_results.lint_issues` into `review_data["issues"]` |
| REV-5 | Review prompt says "Python-only auditor" | Make language-aware — pass language from state |
| REV-6 | `json_mode=True` but model often returns text review | Add text-extraction fallback if JSON parse fails |
 
**REV-2 fix — orchestrator passes full issues to reflexion:**
 
In `orchestrator.py`, `_reflexion_node`:
 
```python
payload = {
    "task_type": "execute_and_fix",
    "code_repo": code_repo,
    "feedback": state["review_feedback"].get("feedback", ""),
    "issues": state["review_feedback"].get("issues", []),   # NEW — full structured list
    "project_id": state["project_id"],
    "language": state.get("language", "python"),
}
```
 
**REV-4 fix — merge sandbox results into issues list:**
 
```python
# After getting gate_results:
if gate_results and not gate_results.passed:
    for sec_issue in gate_results.security_issues:
        review_data["issues"].append({
            "severity": sec_issue.severity.value.upper(),
            "file": sec_issue.file,
            "line": sec_issue.line,
            "description": sec_issue.description,
            "suggestion": sec_issue.recommendation,
            "source": "bandit"
        })
    for lint_issue in gate_results.lint_issues:
        review_data["issues"].append({
            "severity": "MEDIUM",
            "file": lint_issue.file,
            "line": lint_issue.line,
            "description": lint_issue.message,
            "suggestion": f"Fix {lint_issue.rule}",
            "source": "pylint"
        })
```
 
---
 
### 5.5 · Reflexion Engine
 
**File:** `src/foundry/agents/reflexion.py`
 
| # | Issue | Fix |
|---|-------|-----|
| REFX-1 | `QualityGates` not imported | `from foundry.testing.quality_gates import QualityGates` — see FIX-4 |
| REFX-2 | Returns `fix_plan` text, not updated `code_repo` | See FIX-6 |
| REFX-3 | Multi-file fix targets only entry point | Implement `_apply_fix_plan_to_repo()` that iterates all files |
| REFX-4 | Internal retry (5) × orchestrator retry (3) = 15 total LLM calls | Set internal `MAX_RETRY_ATTEMPTS = 2`, let orchestrator do the outer loop |
| REFX-5 | KG fix history not queried | See Section 4.5 |
| REFX-6 | Successful fixes not stored in KG | Store `ErrorFix` node with `was_successful=True` on success |
| REFX-7 | `dependencies` list not passed to sandbox `create_sandbox()` | Pass `dependencies` through from payload to `execute_code()` |
 
**REFX-3 fix — `_apply_fix_plan_to_repo()`:**
 
```python
async def _apply_fix_plan_to_repo(
    self, fix_plan: str, code_repo: Dict[str, str], 
    language: str = "python"
) -> Dict[str, str]:
    """Apply a fix plan to all files in the repo using LLM."""
    updated_repo = dict(code_repo)
    
    for filename, code in code_repo.items():
        system_prompt = f"""You are a code fixer. Apply the fix plan to this {language} file.
Fix Plan:
{fix_plan}
 
Return ONLY the corrected code for this file. If this file does not need changes, return it unchanged.
"""
        user_prompt = f"File: {filename}\n\nCurrent code:\n{code}"
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        response = await self.llm.generate(messages, temperature=0.1)
        updated_code = self._clean_response(response.content)
        if updated_code.strip():
            updated_repo[filename] = updated_code
    
    return updated_repo
```
 
---
 
### 5.6 · DevOps Agent
 
**File:** `src/foundry/agents/devops.py`
 
| # | Issue | Fix |
|---|-------|-----|
| DEV-1 | `code_repo` received but never used | Extract `requirements.txt`/`package.json` and entry point from `code_repo` |
| DEV-2 | Bare `except` returns empty dict silently | Change to specific exception + log |
| DEV-3 | Generates Dockerfile with generic Python image | Use `get_config(language).docker_base_image` |
| DEV-4 | AWS CDK entirely unimplemented | Defer to Phase 2 — but remove from requirements checklist ✓ claim |
| DEV-5 | `recipient=AgentType.ENGINEER` — wrong recipient | Change to `AgentType.ORCHESTRATOR` or remove (orchestrator reads payload directly) |
| DEV-6 | Not language-aware | Accept `language` from payload, use `language_config.py` |
 
**DEV-1 + DEV-3 + DEV-6 combined fix:**
 
```python
async def prepare_deployment(self, architecture: Any, code_repo: Optional[Dict] = None,
                              language: str = "python") -> AgentMessage:
    config = get_config(language)
    
    # Extract useful info from code_repo
    deps_content = ""
    entry_point = config.entry_point
    if code_repo:
        deps_file = code_repo.get(config.package_file, "")
        deps_content = f"\n{config.package_file}:\n{deps_file}" if deps_file else ""
        # Find entry point
        for fname in code_repo.keys():
            if fname.endswith(tuple(config.extensions)) and "main" in fname.lower():
                entry_point = fname
                break
    
    system_prompt = f"""You are an expert DevOps Engineer.
Generate deployment configuration for a {language} project.
 
Base Docker image: {config.docker_base_image}
Entry point: {entry_point}
Setup command: {config.sandbox_setup_cmd}
{deps_content}
 
Return a JSON object with keys as filenames and values as file content.
Include: Dockerfile, docker-compose.yml, and .dockerignore.
"""
```
 
---
 
## 6. Orchestrator Fixes
 
**File:** `src/foundry/orchestrator.py`
 
Summary of all orchestrator-level changes:
 
| # | Change | Details |
|---|--------|---------|
| ORCH-1 | FIX-2: State merge in all nodes | Use `{**state["project_context"], ...}` in all 6 nodes |
| ORCH-2 | FIX-3: Wrong key for review feedback | `"feedback"` not `"comments"` |
| ORCH-3 | FIX-5: Reflexion count boundary | `>=` not `<` |
| ORCH-4 | FIX-6: Reflexion returns updated code_repo | `_reflexion_node` uses `fixed_code_repo` from response |
| ORCH-5 | Add `language` and `framework` to GraphState | Pass from `run()` through all nodes |
| ORCH-6 | `_engineer_node` passes `language` to engineer | Add to payload |
| ORCH-7 | `_architect_node` passes `language` and `framework` | Add to payload |
| ORCH-8 | `_devops_node` passes `language` to DevOps agent | Add to payload |
| ORCH-9 | `_code_review_node` passes `language` to code review | Add to payload |
| ORCH-10 | Pass full `issues` list to reflexion payload | See REV-2 fix |
| ORCH-11 | Fix `_store_artifact` — remove forbidden extension list | Remove `.js`, `.ts`, `.java` from blocked list |
| ORCH-12 | `_store_artifact` — add `language` to dir context check | Only block extensions that don't match target language |
| ORCH-13 | KG ingestion passes `language` | See Section 4.8 |
| ORCH-14 | `success_flag` — `_devops_node` must merge, not overwrite | Use `{**state, "success_flag": True}` |
| ORCH-15 | `_store_artifact` makedirs on empty dirname | Guard with `if dir_part:` |
| ORCH-16 | `AgentOrchestrator` must be instantiated per-project | Already done in `main.py` (Fix K) — verify it's there |
 
**ORCH-11 + ORCH-12 — language-aware artifact gate:**
 
```python
async def _store_artifact(self, project_id: str, name: str, content: str, 
                           artifact_type: ArtifactType, language: str = "python"):
    if artifact_type == ArtifactType.code:
        # Strip markdown
        content = re.sub(r'^```\w*\n?', '', content.strip(), flags=re.MULTILINE)
        content = re.sub(r'\n?```$', '', content.strip(), flags=re.MULTILINE)
        
        # Language-aware validation — only block wrong-language code, not valid target extensions
        from foundry.utils.language_guards import is_wrong_language
        from foundry.utils.language_config import get_config
        config = get_config(language)
        
        # Block files with extensions that don't belong to ANY supported language
        completely_unsupported = ['.php', '.rb', '.swift', '.kt']
        if any(name.lower().endswith(ext) for ext in completely_unsupported):
            logger.critical(f"Unsupported file type blocked: {name}")
            return
        
        # Check language of content in expected-language files
        if name.endswith(tuple(config.extensions)):
            if is_wrong_language(content, language):
                logger.critical(f"Wrong language content in {name}. Writing stub.")
                content = f"# STUB: Wrong language detected. Manual implementation needed.\n"
    
    # Ensure directory exists
    project_dir = os.path.join(settings.generated_projects_path, project_id)
    file_path = os.path.join(project_dir, name)
    dir_part = os.path.dirname(file_path)
    if dir_part:
        os.makedirs(dir_part, exist_ok=True)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    ...
```
 
---
 
## 7. Infrastructure & DevOps Fixes
 
### 7.1 · docker-compose.yml
 
```yaml
services:
  api:
    volumes:
      - ./generated_projects:/app/generated_projects   # FIX-1
      - ./logs:/app/logs                               # also add this
 
  celery-worker:
    volumes:
      - ./generated_projects:/app/generated_projects   # FIX-1
      - ./logs:/app/logs
    environment:
      - OLLAMA_SEMAPHORE=1                              # Ollama concurrency limit signal
```
 
### 7.2 · Alembic migration — add language to projects table
 
```python
# new migration file
def upgrade() -> None:
    op.add_column('projects', sa.Column('language', sa.String(50), 
                                         nullable=False, server_default='python'))
    op.add_column('projects', sa.Column('framework', sa.String(100), nullable=True))
```
 
### 7.3 · Neo4j constraints — add for new node types
 
**File:** `src/foundry/graph/neo4j_client.py`, `create_constraints()`
 
```python
constraints = [
    # existing...
    "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Requirement) REQUIRE r.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (d:ArchitectureDecision) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (f:ErrorFix) REQUIRE f.id IS UNIQUE",
    "CREATE INDEX IF NOT EXISTS FOR (p:Pattern) ON (p.language, p.type)",
    "CREATE INDEX IF NOT EXISTS FOR (f:ErrorFix) ON (f.language, f.error_type)",
]
```
 
---
 
## 8. Ollama Stability Fixes
 
**File:** `src/foundry/llm/ollama_provider.py`
 
```python
import asyncio
 
class OllamaProvider(BaseLLMProvider):
    # Class-level semaphore — limits to 1 concurrent Ollama request
    _semaphore = asyncio.Semaphore(1)
    
    DEFAULT_OPTIONS = {
        "num_ctx": 4096,       # Reduce from default 8192 — faster, fits 7B
        "num_thread": 4,       # Stable CPU usage
        "num_predict": 2048,   # Hard cap on output length — prevents runaway generation
        "temperature": 0.2,    # Default low temp for code
    }
    
    async def generate(self, messages, temperature=0.2, **kwargs):
        async with self._semaphore:   # Serialize all requests
            try:
                return await asyncio.wait_for(
                    self._do_generate(messages, temperature, **kwargs),
                    timeout=120.0   # 2 minute hard timeout per request
                )
            except asyncio.TimeoutError:
                logger.error("Ollama request timed out after 120s")
                raise
```
 
Also ensure `httpx.Timeout` is set explicitly:
 
```python
self.client = httpx.AsyncClient(
    base_url=self.base_url,
    timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0)
)
```
 
---
 
## 9. What to Throw Away
 
These items from the fix plan document are either already done, obsolete due to multi-language support, or counterproductive. **Do not implement them.**
 
| Item | Reason to Skip |
|------|---------------|
| `_sanitize_architecture_for_engineer()` replacing JS terms | Breaks JS/TS projects. Use `language_guards.is_wrong_language()` instead |
| Expanded `_is_non_python_stack()` with 20+ JS keywords | Replaced by language-aware stack validation |
| `_python_fallback_architecture()` | Replaced by `_language_fallback_architecture(language, framework, prd)` |
| `JS_PATTERNS` as a blocking gate in engineer | Replace with `is_wrong_language()` check |
| Fix O — hard-coded PRD templates | Crutch for 1.5B model. At 7B, good anchoring in prompts is sufficient. Skip. |
| The `final_repo` extension renaming loop in engineer.py | Replace with correct-language validation, not forced `.py` renaming |
| `forbidden_exts` list in `_store_artifact` | Remove — breaks JS/TS/Java projects |
| `"ABSOLUTE PYTHON REQUIREMENT"` in all prompts | Replace with `f"Generate {language} code"` |
| `"PROHIBITED: No JavaScript, No Node.js"` in all prompts | Remove entirely |
| React-removal from ADR example | Fix the prompt example to use language-appropriate stack |
 
---
 
## 10. Execution Order
 
Work through these in order. Each stage is a functioning checkpoint.
 
### Stage 1 — Unblock E2E tests (1–2 hours)
 
1. `docker-compose.yml` — add volume mounts (FIX-1)
2. `reflexion.py` — add `QualityGates` import (FIX-4)
3. `orchestrator.py` — fix `"comments"` → `"feedback"` key (FIX-3)
4. `orchestrator.py` — fix state merge in all 6 nodes (FIX-2)
5. `orchestrator.py` — fix `reflexion_count >= MAX_REFLEXION_RETRIES` (FIX-5)
6. Run E2E test — files should now appear on host, reflexion should run
 
### Stage 2 — Fix the reflexion loop (2–4 hours)
 
7. `reflexion.py` — implement `_apply_fix_plan_to_repo()` and return `code_repo` (FIX-6)
8. `orchestrator.py` — use `fixed_code_repo` from reflexion in `_reflexion_node` (FIX-6)
9. `orchestrator.py` — pass full `issues` list from review to reflexion (REV-2)
10. Run E2E test — reflexion loop should now actually fix code
 
### Stage 3 — Multi-language foundation (half day)
 
11. Create `src/foundry/utils/language_config.py`
12. Create `src/foundry/utils/language_guards.py`
13. Add `language` + `framework` to `GraphState`, `ProjectCreateRequest`, `Project` model
14. Run Alembic migration
15. Update all agents to use `get_config(language)` — remove all Python-only enforcement
16. Test Python project still works, then test a JS project
 
### Stage 4 — Knowledge Graph deep integration (1–2 days)
 
17. Add new Neo4j node types and constraints (Section 4.1, 7.3)
18. Add new query methods to `knowledge_graph_tools.py` (Section 4.2)
19. Add `js_parser.py` and `java_parser.py` (Section 4.3)
20. Wire `get_project_summary_for_generation()` into engineer agent (Section 4.4)
21. Wire error fix storage + retrieval into reflexion agent (Section 4.5)
22. Wire architecture decision storage into architect agent (Section 4.6)
23. Wire requirement storage into PM agent (Section 4.7)
24. Update ingestion pipeline to route by language (Section 4.8)
 
### Stage 5 — Agent quality improvements (ongoing)
 
25. PM agent: `_extract_json()`, expanded schema, clarifying questions (Section 5.1)
26. Architect agent: double validation, JSON normalization, language-aware ADRs (Section 5.2)
27. Engineer agent: recovery loop, KG context in initial generation (Section 5.3)
28. Code review: merge sandbox results into issues list (Section 5.4)
29. DevOps: use `code_repo` for context-aware Dockerfile (Section 5.6)
 
### Stage 6 — Stability (ongoing)
 
30. Ollama semaphore + timeout (Section 8)
31. Property-based and E2E tests for each language
 
---
 
*Document generated from codebase audit — March 2026*  
*Files audited: orchestrator.py, engineer.py, architect.py, product_manager.py, code_review.py, reflexion.py, devops.py, knowledge_graph.py, knowledge_graph_tools.py, ingestion.py, code_parser.py, neo4j_client.py, quality_gates.py, test_generator.py, ollama_provider.py*