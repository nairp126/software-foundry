# Autonomous Software Foundry — Agent & Orchestration Audit Report

> **Date:** March 2026  
> **Scope:** Full source audit of all 6 agents + orchestrator based on live codebase  
> **Model in use:** Qwen2.5-Coder-7B via Ollama  
> **Languages targeted:** Python · JavaScript/Node.js · TypeScript · Java

---

## Executive Summary

| Component | File | Implementation Status | Critical Bugs | High Issues | Medium Issues |
|-----------|------|-----------------------|:---:|:---:|:---:|
| Orchestrator | `orchestrator.py` | Partial — core flow wired, key bugs remain | 4 | 5 | 3 |
| Product Manager | `product_manager.py` | Partial — PRD works but schema is thin | 1 | 3 | 3 |
| Architect | `architect.py` | Partial — multi-pass validation added, still Python-only | 2 | 3 | 2 |
| Engineer | `engineer.py` | Partial — recovery loop added, still Python-only hardcoded | 3 | 4 | 3 |
| Code Review | `code_review.py` | Partial — sandbox integration present, key mismatches | 2 | 3 | 2 |
| Reflexion | `reflexion.py` | Partial — execution loop works, output contract broken | 3 | 3 | 2 |
| DevOps | `devops.py` | Minimal stub — code_repo ignored, no language awareness | 3 | 2 | 1 |

**Overall assessment:** The pipeline can generate code in limited scenarios but will fail E2E tests in all but the simplest cases due to four compounding issues: state context loss between nodes, the reflexion loop returning a text plan instead of fixed code, all agents being hardcoded to Python-only (blocking multi-language support), and the DevOps agent ignoring the actual code it receives.

---

## Table of Contents

1. [Orchestrator](#1-orchestrator)
2. [Product Manager Agent](#2-product-manager-agent)
3. [Architect Agent](#3-architect-agent)
4. [Engineer Agent](#4-engineer-agent)
5. [Code Review Agent](#5-code-review-agent)
6. [Reflexion Engine](#6-reflexion-engine)
7. [DevOps Agent](#7-devops-agent)
8. [Cross-Cutting Issues](#8-cross-cutting-issues)
9. [What Has Been Fixed (Since Last Audit)](#9-what-has-been-fixed-since-last-audit)
10. [Prioritised Fix Checklist](#10-prioritised-fix-checklist)

---

## 1. Orchestrator

**File:** `src/foundry/orchestrator.py`  
**Class:** `AgentOrchestrator`  
**Framework:** LangGraph `StateGraph`

### 1.1 What Is Implemented

- `GraphState` TypedDict with `messages`, `project_context`, `review_feedback`, `project_id`, `reflexion_count`, `success_flag`
- Full 6-node LangGraph graph: `product_manager → architect → engineer → code_review → (reflexion | devops | END)`
- Conditional routing from `code_review` via `_should_continue_from_review`
- Status updates to PostgreSQL at each node via `_update_project_status`
- Artifact persistence to filesystem + DB via `_store_artifact`
- KG ingestion after code generation
- Write-time gate in `_store_artifact` blocks forbidden extensions and JS content in `.py` files
- Per-request orchestrator instantiation (avoids cross-project memory pollution)

### 1.2 Critical Bugs

#### BUG-ORCH-1 · State merge destroys context at every node transition

**Severity:** CRITICAL — causes all downstream failures

`_pm_node`, `_architect_node`, and `_engineer_node` each return a **fresh** `project_context` dict instead of merging into the existing one. LangGraph uses last-write-wins for all TypedDict keys not annotated with a reducer. The result is that every node transition silently deletes everything added by the previous node.

```python
# CURRENT — _pm_node wipes everything with a fresh dict:
return {
    "project_context": {
        "prd": prd,
        "requirements": state.get("requirements", "")
    }
}

# CURRENT — _architect_node re-adds prd but drops requirements:
return {
    "project_context": {
        "architecture": architecture,
        "prd": prd,
        "requirements": state.get("requirements", "")
    }
}

# CURRENT — _engineer_node drops requirements again:
return {
    "project_context": {"code_repo": code_repo, "architecture": architecture, "prd": prd}
}
```

**Fix:** Every node must use the spread operator:

```python
return {
    "project_context": {**state["project_context"], "prd": prd}
}
```

**Nodes requiring this fix:** `_pm_node`, `_architect_node`, `_engineer_node`, `_code_review_node`, `_reflexion_node`

Note: `_devops_node` already uses `{**state["project_context"], "deployment": deployment_results}` — this is correct.

---

#### BUG-ORCH-2 · `review_feedback` key mismatch — reflexion gets empty context

**Severity:** CRITICAL

`_reflexion_node` reads:

```python
review_comments = state["review_feedback"].get("comments", "")
```

But `CodeReviewAgent.analyze_code()` returns a payload with key `"feedback"`, not `"comments"`. The reflexion agent always receives an empty string as context and cannot generate targeted fixes.

**Fix:**

```python
review_comments = (
    state["review_feedback"].get("feedback")
    or state["review_feedback"].get("comments", "")
)
```

---

#### BUG-ORCH-3 · Reflexion loop returns fix_plan text, never updated code_repo

**Severity:** CRITICAL

`_reflexion_node` extracts `fix_plan` (a text string) from the reflexion response and stores it in `review_feedback`. When the graph loops back to `_engineer_node`, the engineer receives this as `fix_instructions` — soft guidance text that a 7B model frequently ignores. The engineer then regenerates from scratch, discarding all previous fixes.

The reflexion agent's `execute_and_fix()` does return `"code_repo": current_repo` on success, but on the fix-plan path it returns only `"fix_plan"`. The orchestrator must retrieve and propagate the updated `code_repo`:

```python
# In _reflexion_node:
response = await self.reflexion_agent.process_message(message)
fixed_code_repo = response.payload.get("code_repo", state["project_context"].get("code_repo", {}))
fix_plan = response.payload.get("fix_plan", "")

return {
    "messages": [...],
    "project_context": {
        **state["project_context"],
        "code_repo": fixed_code_repo,   # propagate fixed code
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

#### BUG-ORCH-4 · `MAX_REFLEXION_RETRIES` boundary check is off-by-one

**Severity:** CRITICAL

```python
# CURRENT — allows 4 cycles, not 3:
if state.get("reflexion_count", 0) < MAX_REFLEXION_RETRIES:
    return "fix"
```

`reflexion_count` is incremented inside `_reflexion_node`, so on the 3rd rejection the count is 2, and `2 < 3` routes to "fix" again (4th attempt). If the state merge bug causes count not to persist, this loops forever.

**Fix:**

```python
if state.get("reflexion_count", 0) >= MAX_REFLEXION_RETRIES:
    return "fail"
return "fix"
```

---

### 1.3 High Issues

#### HIGH-ORCH-1 · `_store_artifact` — `makedirs` on empty dirname crashes on some OS

When `name = "main.py"` (no subdirectory), `os.path.dirname(file_path)` returns an empty string. `os.makedirs("")` raises `FileNotFoundError` on Windows.

```python
# Fix:
dir_part = os.path.dirname(file_path)
if dir_part:
    os.makedirs(dir_part, exist_ok=True)
```

---

#### HIGH-ORCH-2 · `_store_artifact` blocks `.js`, `.ts`, `.java` extensions — breaks multi-language support

```python
forbidden_exts = ['.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.php', '.html', '.css']
```

This hard blocks every JavaScript, TypeScript, and Java project. Since multi-language support is now a requirement, this gate must be replaced with a language-aware check that only blocks wrong-language extensions for the current project's target language.

---

#### HIGH-ORCH-3 · `JS_PATTERNS` regex still present as class attribute — blocks JS projects

The regex at the top of `AgentOrchestrator` is used in `_store_artifact` to block JS content in `.py` files. This is correct for Python-only projects but will incorrectly block valid JS/TS code. Must be language-parameterized.

---

#### HIGH-ORCH-4 · `_code_review_node` does not pass `language` to review agent

```python
payload = {
    "code_repo": code_repo,
    "project_id": state["project_id"]
    # language missing
}
```

The code review agent defaults to `"python"` and its system prompt explicitly says "Python-only auditor." JS and Java projects will always be rejected.

---

#### HIGH-ORCH-5 · `success_flag` can be lost due to state merge issue

`_devops_node` returns `"success_flag": True`, but if final state accumulation via `{**final_state, **value}` in the `run()` loop drops it due to ordering, the project is permanently marked `failed` even on successful generation. The `run()` loop should explicitly track `success_flag` separately.

---

### 1.4 Medium Issues

#### MED-ORCH-1 · KG ingestion hardcodes `"Python Project"` as project name

```python
await ingestion_pipeline.ingest_project(
    project_id=state["project_id"],
    project_name=f"Python Project {state['project_id'][:8]}",  # hardcoded
    project_path=project_path
)
```

Must use the actual project name from PRD and pass `language` to route to the correct parser.

---

#### MED-ORCH-2 · `_reflexion_node` does not pass `language` or structured `issues` list to reflexion agent

The reflexion payload only sends `feedback` (a string). The structured `issues` list from code review (with file, line, severity, description per issue) is never forwarded. Reflexion cannot make targeted per-file fixes without it.

---

#### MED-ORCH-3 · `GraphState` has no `language` or `framework` field

All language-specific routing must be done after reading it from `project_context` (unreliable) rather than from a dedicated state field. Adding `language: str` and `framework: str` to `GraphState` and threading them from `run()` through all nodes is required for multi-language support.

---

## 2. Product Manager Agent

**File:** `src/foundry/agents/product_manager.py`  
**Class:** `ProductManagerAgent`

### 2.1 What Is Implemented

- Natural language requirements → PRD JSON via LLM
- Domain grounding anchor injected into system prompt (Fix L)
- Keyword validation heuristic with retry on domain drift
- Hard fallback template if both attempts drift
- `pm_debug.json` written for diagnostics
- `requirements` key persisted in response payload (Fix L)

### 2.2 Critical Bugs

#### BUG-PM-1 · No robust JSON extraction — silently passes raw strings downstream

The agent calls `json.dumps` / `json.loads` on `content` but has no extraction step for fenced responses. When the LLM outputs:

```
Here is your PRD:
```json
{"project_name": "..."}
```

```

The content variable is the full string including the sentence and fences. `json.loads` fails, the bare `except: pass` swallows the error, and `content` (the raw malformed string) is returned as `prd` to the orchestrator. The architect then receives this as its input PRD.

**Fix — add `_extract_json()` before any downstream use:**

```python
def _extract_json(self, content: str) -> dict:
    # Strip fences
    content = re.sub(r'^```(?:json)?\n?', '', content.strip(), flags=re.MULTILINE)
    content = re.sub(r'\n?```$', '', content.strip(), flags=re.MULTILINE)
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"No valid JSON in response: {content[:200]}")
```

---

### 2.3 High Issues

#### HIGH-PM-1 · PRD schema is critically thin — missing NFRs and acceptance criteria

Required by Req 2.3/2.4 but absent. Current schema:

```json
{"project_name", "high_level_description", "core_features", "user_stories", "technical_constraints"}
```

Missing: `functional_requirements`, `non_functional_requirements`, `acceptance_criteria`, `out_of_scope`. The architect uses only what's in the PRD — a thin PRD produces a thin, inconsistent architecture.

---

#### HIGH-PM-2 · Keyword heuristic logic is inverted for common words

`key_terms` extracts all words > 3 chars from the requirements. For a prompt like `"build a todo list app"`, the terms include `["build", "list"]` — generic words that appear in almost any PRD. `match_count` will always be > 0, so the validation never triggers even when the PRD is completely wrong. Conversely, for `"fft"` (3 chars), `key_terms` is empty and the check is bypassed entirely.

---

#### HIGH-PM-3 · Clarifying questions (Req 2.2) entirely unimplemented

The design spec requires generating clarifying questions for ambiguous inputs. The method doesn't exist. For very short prompts (< 15 words, < 3 distinct nouns), the agent should ask 2-3 targeted questions before generating the PRD. Without this, vague inputs produce garbage PRDs that cascade into garbage architecture.

---

### 2.4 Medium Issues

#### MED-PM-1 · `pm_debug.json` written to `os.getcwd()` unconditionally in production

Writes sensitive user requirements to the filesystem on every single call. Must be gated:

```python
if settings.debug:
    # write debug file
```

#### MED-PM-2 · `process_message` ignores `project_id` — cannot store requirements in KG

`process_message` accepts only the `prompt` payload key. `project_id` is available in the message payload but not extracted or forwarded to `analyze_requirements`. KG storage of requirements (for cross-project learning) requires this.

#### MED-PM-3 · Fallback PRD template `technical_constraints` hardcodes Python

```python
"technical_constraints": ["Python 3.11+", "Scalable architecture"]
```

This will inject Python into a Java or JS project's requirements.

---

## 3. Architect Agent

**File:** `src/foundry/agents/architect.py`  
**Class:** `ArchitectAgent`

### 3.1 What Is Implemented

- Multi-pass validation loop (up to 2 LLM attempts) with `_is_non_python_stack()` check
- `_self_correct_architecture()` via in-conversation correction message
- `_sanitize_architecture_for_engineer()` — replaces JS/Node terms with Python equivalents and renames `.js`/`.ts` extensions to `.py`
- `_python_fallback_architecture()` — hard-coded Python fallback template if both passes fail
- Expanded forbidden keyword list in `_is_non_python_stack()` covering Vue, Angular, webpack, etc.
- KG tools instantiated (but not called during architecture design)

### 3.2 Critical Bugs

#### BUG-ARCH-1 · `_sanitize_architecture_for_engineer()` is destructive for multi-language projects

This method forcibly replaces `"React"` → `"Python/Jinja2"`, `"TypeScript"` → `"Python"`, renames all `.js`/`.ts` extensions to `.py`, and replaces `"MongoDB"` → `"PostgreSQL"`. For a JavaScript or Java project, this will corrupt the entire architecture before the engineer sees it. This sanitizer must be removed or made conditional on the target language.

---

#### BUG-ARCH-2 · Architecture validated twice but never parsed/normalized as JSON

The system prompt says "Return the result as a JSON object" but `architecture_content = response.content` stores the raw string, which may be:

- Valid JSON `{"projectName": ...}`  
- Markdown-fenced JSON (` ```json\n{...}\n``` `)  
- Plain prose description

This raw string is passed directly to the engineer. If it contains prose or fences, the engineer's LLM receives confusing mixed input. The architect must parse, validate, and re-serialize the JSON before forwarding.

---

### 3.3 High Issues

#### HIGH-ARCH-1 · `_is_non_python_stack()` must become `_is_wrong_stack(content, language)`

Currently hardcoded to check for Python violations. For JS projects it will always trigger and force Python. Needs a `language` parameter to check for the appropriate forbidden patterns.

#### HIGH-ARCH-2 · ADR prompt example in `document_architectural_decisions()` uses React/TypeScript

```python
"title": "Selection of React for Frontend"
"decision": "Use React with TypeScript for frontend development"
```

This few-shot example teaches the LLM to recommend React/TypeScript in any ADR regardless of the actual stack. Replace with a language-neutral or Python/FastAPI example.

#### HIGH-ARCH-3 · `organize_file_structure()` has no language constraint

Method prompt says "Generate a comprehensive file structure" with no language restriction. For a Python project with a frontend-flavored PRD, it may output `src/components/App.tsx`, `package.json`, etc.

---

### 3.4 Medium Issues

#### MED-ARCH-1 · `design_architecture()` does not accept or use `project_id`

Cannot store architecture decisions in KG. `kg_tools` is instantiated but `design_architecture` never calls it.

#### MED-ARCH-2 · `_python_fallback_architecture()` hardcodes `"SQLite"` and `"Python 3.11"`

For a Java or JS project this fallback will produce an entirely wrong architecture. Must be parameterized by language.

---

## 4. Engineer Agent

**File:** `src/foundry/agents/engineer.py`  
**Class:** `EngineerAgent`

### 4.1 What Is Implemented

- `JS_PATTERNS` compiled regex for leakage detection
- 3-attempt recovery loop with auto-stub fallback on persistent failure
- GraphRAG via `get_surgical_context()` — used when KG has data; falls back to raw previous-file context
- Incremental repair mode — uses `existing_version` as baseline when `fix_instructions` present
- Last-mile filename extension normalization (forces `.py` on non-Python extensions)
- Quality gates run after generation
- Test generation run after quality gates
- KG context retrieval during fix mode via `get_component_context()`

### 4.2 Critical Bugs

#### BUG-ENG-1 · `_detect_language()` always returns `"python"` — blocks all multi-language projects

```python
def _detect_language(self, architecture_content: str) -> str:
    """Hardened language detection: Always returns 'python'."""
    return "python"
```

And in `generate_code()`:

```python
language = "python"  # Force Python as per system constraints
```

This is the root cause of all JavaScript, TypeScript, and Java projects failing to generate correct code. The language must come from the LangGraph state (via message payload from orchestrator).

---

#### BUG-ENG-2 · `_request_code_improvements()` has no language constraint

```python
system_prompt = """You are a Python Quality Expert. 
...
ABSOLUTE REQUIREMENT: You MUST implement improvements using ONLY Python 3.11+.
PROHIBITED: Do NOT use any JavaScript, Node, or web-framework syntax."""
```

Quality improvements for JS/TS/Java files will produce Python-contaminated code.

---

#### BUG-ENG-3 · Last-mile filename renaming loop corrupts multi-language projects

```python
if any(f_clean.lower().endswith(ext) for ext in ['.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs']):
    new_name = os.path.splitext(f_clean)[0] + ".py"
    final_repo[new_name] = content
```

Renames `index.js` → `index.py`, `Main.java` → `Main.py` etc. for every project regardless of target language.

---

### 4.3 High Issues

#### HIGH-ENG-1 · KG context only retrieved during fix mode, not initial generation

`kg_context` from `get_component_context()` is only populated when `fix_instructions` is present. On the first pass (initial generation), the KG is empty anyway — but on repeat generations or second projects, existing KG data is ignored.

The `get_project_summary_for_generation()` method should be called on every generation pass, not just during repair.

#### HIGH-ENG-2 · `_plan_file_structure()` hardcodes `.py` extensions and `"FastAPI"` override

```python
system_prompt = f"""...
ABSOLUTE REQUIREMENT: You MUST use ONLY .py extensions for code files.
PROHIBITED: No .js, .ts, .jsx, .html, .css, .java, .go, .rs.
If the architecture suggests a 'Frontend' with 'React', use 'FastAPI' with 'Jinja2' patterns.
"""
```

Must use `get_config(language).extensions` and `get_config(language).web_frameworks`.

#### HIGH-ENG-3 · File generation capped at 3 files then immediately generates tests — LLM call explosion

`files_to_generate = files_to_generate[:3]` limits code files. Then `generate_tests()` adds test files for each. Each file requires 2-4 LLM calls (generation + optional quality check + possible recovery). On a 7B model over Ollama with no semaphore, this is 8-24 sequential LLM calls per engineer invocation, reliably causing timeouts.

#### HIGH-ENG-4 · `CODING_STANDARDS` dict only has `"python"` key

```python
CODING_STANDARDS = {"python": "PEP 8 (Strict Enforcement)"}
```

For any other language, `coding_standard` falls back to `"industry best practices"` — a useless prompt directive. Must be populated for all target languages.

---

### 4.4 Medium Issues

#### MED-ENG-1 · `_extract_imports()` has JS/TS branches despite Python-only system

The function has a full `elif filename.endswith(('.js', '.ts', '.jsx', '.tsx')):` branch. This dead code will silently process JS files if they slip past the naming guard and is actively misleading given the Python-only constraint that was previously applied.

#### MED-ENG-2 · `write_code_to_disk()` cleanup is weaker than `_clean_code()`

`write_code_to_disk` only strips the first and last line if the content starts with a backtick. `_clean_code()` uses regex and is much more robust. These two should be unified.

#### MED-ENG-3 · `_request_code_generation()` is defined but never called

This internal method exists and takes `filename`, `architecture`, `language`, `coding_standard` etc. as separate parameters. `_generate_file_content()` constructs its own prompt inline instead of calling this method. The abstraction is never used.

---

## 5. Code Review Agent

**File:** `src/foundry/agents/code_review.py`  
**Class:** `CodeReviewAgent`

### 5.1 What Is Implemented

- QualityGates integration: runs Bandit, Pylint, mypy in Docker sandbox before LLM review
- Sandbox results injected into LLM prompt as `dynamic_context`
- Robust JSON extraction: finds outermost `{}` and strips markdown before parsing
- `"approved"` bridge field added to payload for LangGraph routing
- Stores `code_review.json` artifact
- Returns structured `issues` list with severity, file, line, description, suggestion

### 5.2 Critical Bugs

#### BUG-REV-1 · `analyze_code()` returns review payload with key `"feedback"` but orchestrator reads `"comments"`

```python
# Code review agent returns:
payload = {"status": "APPROVED", "feedback": "...", "issues": [...]}

# Orchestrator _reflexion_node reads:
review_comments = state["review_feedback"].get("comments", "")  # always empty string
```

This is the key mismatch that prevents reflexion from ever receiving useful context. (Fix is in orchestrator `_reflexion_node`, documented in BUG-ORCH-2.)

---

#### BUG-REV-2 · System prompt hardcodes `"Python-only auditor"` — rejects all JS/Java projects

```python
system_prompt = """...
ABSOLUTE PYTHON REQUIREMENT: You are a Python-only auditor.
1. If the code contains ANY JavaScript, React, Node.js, or non-Python tech, you MUST REJECT it immediately.
"""
```

Every JavaScript and Java project will be auto-rejected with `status: "REJECTED"` regardless of code quality. Must be language-parameterized.

---

### 5.3 High Issues

#### HIGH-REV-1 · `gate_results` security and lint issues are not added to the structured `issues` list

Sandbox results are injected as text into the LLM prompt (`dynamic_context`), but the structured `gate_results.security_issues` and `gate_results.lint_issues` objects are never merged into `review_data["issues"]`. Downstream consumers (reflexion agent, VS Code annotations) can only see sandbox findings if they re-parse free text — they cannot act on them programmatically.

```python
# Add after gate_results block:
if gate_results:
    for sec_issue in gate_results.security_issues:
        review_data.setdefault("issues", []).append({
            "severity": sec_issue.severity.value.upper(),
            "file": sec_issue.file,
            "line": sec_issue.line,
            "description": sec_issue.description,
            "suggestion": sec_issue.recommendation,
            "source": "bandit"
        })
```

#### HIGH-REV-2 · Fallback on JSON parse failure creates misleading error message

```python
review_data = {
    "status": "REJECTED",
    "feedback": "AUTO-REJECT: JSON parsing failed. Please return valid JSON.",
    "issues": ["JSON syntax error"]
}
```

`"issues"` is a list of strings, not dicts. Downstream code expecting `issue["severity"]`, `issue["file"]` etc. will crash with `TypeError`. Use consistent structure.

#### HIGH-REV-3 · `issues` list from review not passed to reflexion by orchestrator

Even when review produces a valid structured issues list, the orchestrator's `_reflexion_node` only passes a `"feedback"` string to reflexion. The per-file, per-line issue details are discarded. Reflexion cannot make surgical fixes without knowing which file has which problem on which line.

---

### 5.4 Medium Issues

#### MED-REV-1 · `recipient` in returned `AgentMessage` is `AgentType.DEVOPS`

```python
return AgentMessage(
    sender=self.agent_type,
    recipient=AgentType.DEVOPS,  # wrong — review goes to orchestrator
    message_type=MessageType.TASK,
    payload=review_data
)
```

The orchestrator ignores this field, but it's semantically wrong and will cause bugs in any future message-routing system.

#### MED-REV-2 · QualityGates only runs Python tools (Bandit, Pylint, mypy)

For JS projects, `_run_eslint()` and `_run_npm_audit()` are stubs returning `[]`. JS projects get no sandbox validation.

---

## 6. Reflexion Engine

**File:** `src/foundry/agents/reflexion.py`  
**Class:** `ReflexionEngine` (aliased as `ReflexionAgent`)

### 6.1 What Is Implemented

- Full `execute_and_fix()` loop: execute in sandbox → analyze errors → generate fix plan → retry up to `MAX_RETRY_ATTEMPTS = 5`
- Dependency extraction from `requirements.txt` in the repo
- KG impact analysis queried during fix generation (`analyze_change_impact()`)
- Legacy `reflect_on_feedback()` kept for backward compatibility
- `should_escalate()` with memory error detection
- Rule-based `FixGenerator` tried first before falling back to LLM
- On success: returns `"code_repo": current_repo` in payload

### 6.2 Critical Bugs

#### BUG-REFX-1 · `QualityGates` used in `__init__` but not imported at top of file

```python
class ReflexionEngine(Agent):
    def __init__(self, model_name: Optional[str] = None):
        ...
        self.quality_gates = QualityGates()  # NameError — not imported
```

`QualityGates` is not in the imports section. The reflexion agent crashes on instantiation with `NameError: name 'QualityGates' is not defined`. This means the entire reflexion/fix pipeline has never run successfully.

**Fix:** Add to imports:

```python
from foundry.testing.quality_gates import QualityGates
```

---

#### BUG-REFX-2 · Fix path returns `"fix_plan"` string only — orchestrator cannot propagate updated code

On the fix path (when execution fails but retries remain), `execute_and_fix()` returns:

```python
payload={
    "status": "needs_fixes",
    "fix_plan": fix_plan,         # text only
    "error": error_context,
    "execution_history": execution_history
}
```

There is no `"code_repo"` key on the fix path. The orchestrator's `_reflexion_node` extracts `fix_plan` and puts it in `review_feedback`, but never updates `project_context["code_repo"]`. The engineer on the next loop receives the same broken code.

**Fix:** Return the current (partially fixed) repo even when fixes still need application:

```python
return AgentMessage(
    payload={
        "status": "needs_fixes",
        "fix_plan": fix_plan,
        "code_repo": current_repo,   # add this
        "error": error_context,
    }
)
```

---

#### BUG-REFX-3 · `MAX_RETRY_ATTEMPTS = 5` × orchestrator `MAX_REFLEXION_RETRIES = 3` = 15 total attempts

Each orchestrator reflexion cycle calls `execute_and_fix()` which internally loops up to 5 times. The outer orchestrator loop allows up to 3 reflexion cycles. This is 5 × 3 = 15 sandbox executions and 15+ LLM calls before final failure. On a 7B model with no concurrency limit, this takes 45-90 minutes and reliably OOMs or times out.

**Fix:** Reduce internal `MAX_RETRY_ATTEMPTS` to 2. Let the orchestrator's outer loop handle escalation:

```python
MAX_RETRY_ATTEMPTS = 2  # inner loop; orchestrator provides outer retry
```

---

### 6.3 High Issues

#### HIGH-REFX-1 · Fix generation always targets only the entry point file

```python
# Comment in code:
# For multi-file, we currently focus on the entry point or use LLM to decide
```

The LLM fix plan is generated for the entire repo but applied via `apply_fixes()` which targets a single `Code` object. Integration errors (wrong imports, mismatched function signatures across files) in multi-file projects are never addressed.

#### HIGH-REFX-2 · `_generate_llm_fixes()` hardcodes Python in fix prompt

```python
system_prompt = """You are an expert code debugger and fixer.
ABSOLUTE REQUIREMENT: You MUST fix the code using ONLY Python 3.11+.
PROHIBITED: Do NOT suggest Node.js, React, npm, or JavaScript solutions.
"""
```

Fixes for JS or Java errors will be Python code.

#### HIGH-REFX-3 · KG impact analysis uses `project_id="current"` fallback in `reflect_on_feedback()`

```python
context_data = await self.kg_tools.get_component_context(
    project_id="current",  # hardcoded fallback
    component_name="main"
)
```

`"current"` is not a real project ID. The query returns nothing. This KG integration always silently fails.

---

### 6.4 Medium Issues

#### MED-REFX-1 · `dependencies` list not threaded through to `create_sandbox()`

`execute_and_fix()` extracts dependencies from `requirements.txt` but the `execute_code()` call signature passes `dependencies` to `environment.execute_code()`. The sandbox `create_sandbox()` receives dependencies only if they were in the original payload — the extracted list from `requirements.txt` parsing is not forwarded.

#### MED-REFX-2 · Successful fixes not stored in KG for cross-project learning

When `result.success` is True, there is no call to store the successful fix pattern. The KG remains empty of error-fix pairs, making cross-project learning impossible.

---

## 7. DevOps Agent

**File:** `src/foundry/agents/devops.py`  
**Class:** `DevOpsAgent`

### 7.1 What Is Implemented

- Single method `prepare_deployment()` that generates Dockerfile and docker-compose.yml
- JSON parsing with markdown fence stripping
- `json_mode=True` on LLM call

### 7.2 Critical Bugs

#### BUG-DEV-1 · `code_repo` is received but never used

```python
async def process_message(self, message: AgentMessage) -> AgentMessage:
    architecture = message.payload.get("architecture")
    code_repo = message.payload.get("code_repo")  # received
    return await self.prepare_deployment(architecture, code_repo)

async def prepare_deployment(self, architecture: ..., code_repo: Optional[str] = None) -> AgentMessage:
    user_prompt = f"Here is the system architecture:\n\n{architecture}"  # code_repo ignored
```

The Dockerfile is generated without knowing: what Python dependencies exist, what the actual entry point is, what ports the app uses, or what environment variables are needed. Generated Dockerfiles will not work for any specific project.

---

#### BUG-DEV-2 · Bare `except` swallows all JSON parse failures silently

```python
try:
    deployment_data = json.loads(deployment_data)
except:
    deployment_data = {}
```

When JSON parsing fails (common with 7B models), `deployment_data` silently becomes `{}`. The orchestrator iterates over an empty dict, stores no artifacts, and reports success. The DevOps stage is a silent no-op on failure. Use specific exception handling and log failures.

---

#### BUG-DEV-3 · Entire AWS CDK requirement (Req 7) unimplemented

Requirements 7.1-7.6 mandate AWS CDK generation, `cdk synth` validation, `cdk bootstrap` detection, and `cdk deploy` execution. The current implementation generates only a Dockerfile and docker-compose.yml. This is a Phase 2 item — but the requirements doc marks it as `✓` implemented, which is incorrect.

---

### 7.3 High Issues

#### HIGH-DEV-1 · Agent is entirely Python-only — no language awareness

The system prompt says "RESTRICTION: Project is ALWAYS Python-based" and hardcodes `python:3.11-slim` as the base image. JS projects need `node:20-slim`, Java projects need `eclipse-temurin:21-jdk-slim`.

#### HIGH-DEV-2 · `recipient` in returned `AgentMessage` is `AgentType.ENGINEER`

```python
return AgentMessage(
    sender=self.agent_type,
    recipient=AgentType.ENGINEER,  # wrong
    ...
)
```

DevOps is the last stage — recipient should be `AgentType.ORCHESTRATOR` or the field should be irrelevant. Copy-pasted from engineer agent template.

---

### 7.4 Medium Issues

#### MED-DEV-1 · No `.dockerignore`, `.env.example`, or `GitHub Actions` workflow generated

A minimal viable deployment package requires at minimum a `.dockerignore` to avoid copying `__pycache__`, `.git`, `venv` into the image, and a `.env.example` as required by Req 15.3.

---

## 8. Cross-Cutting Issues

These issues affect multiple agents and must be solved systemically rather than in each agent individually.

### 8.1 No `language` field in LangGraph state or project model

Every single agent currently determines language through local heuristics or hardcoded values. The fundamental fix is:

1. Add `language: str` and `framework: str` to `GraphState`
2. Accept `language` in `ProjectCreateRequest`
3. Pass from `run()` through every node into every agent message payload
4. Each agent reads `language` from its message payload, not from its own detection logic

Until this is done, multi-language support requires patching every individual agent.

### 8.2 No shared `language_config.py` module

Every language-specific constant (extensions, linters, test frameworks, Docker images, coding standards, entry points, package files) is hardcoded in each agent independently. A central `language_config.py` with a `LanguageConfig` dataclass per language eliminates all the individual Python-only hardcoding in a single change.

### 8.3 KG integration is write-only from agents' perspective

The KG is populated via `ingestion_pipeline` after code generation. But the query tools (`get_surgical_context`, `get_project_file_map`, `get_component_context`, `analyze_change_impact`) are either:

- Not called at all (initial generation pass in engineer)
- Called with hardcoded `project_id="current"` that returns nothing (reflexion legacy path)
- Called only during fix mode (engineer `_generate_file_content`)

None of the agents store requirements, architecture decisions, or successful fix patterns back into the KG for cross-project learning.

### 8.4 No Ollama concurrency control — timeouts on 7B model

All agents make LLM calls concurrently with no serialization. With Qwen-7B on 8GB VRAM, concurrent requests cause memory spikes and `httpx.ReadTimeout`. There is no class-level `asyncio.Semaphore` and no `num_predict` limit to cap output length.

### 8.5 `print()` statements used for all agent-level logging

Every agent uses bare `print(f"DEBUG: ...")` instead of `logger.info(...)`. Debug output goes to stdout mixed with application logs, cannot be filtered by log level, and writes sensitive data (generated code, error messages) to container stdout.

---

## 9. What Has Been Fixed (Since Last Audit)

The following issues identified in prior audits have been resolved in the current codebase:

| Fix ID | Description | Status |
|--------|-------------|--------|
| Fix-K | Fresh orchestrator instantiated per project (no cross-project state leakage) | ✅ Done — `main.py` creates fresh `AgentOrchestrator()` per request |
| Fix-L | Requirements injected as domain anchor into PM, Architect, Engineer prompts | ✅ Done — `grounding_anchor` in all three agents |
| Fix-1 | `_sanitize_architecture_for_engineer()` added to architect | ✅ Done — but now harmful for multi-language |
| Fix-2 | Comprehensive `JS_PATTERNS` regex in engineer | ✅ Done — but needs to become language-aware |
| Fix-3 | 3-attempt recovery loop with auto-stub in engineer | ✅ Done |
| Fix-4 | Python constraint added to `_request_code_improvements()` | ✅ Done — but now Python-only |
| Fix-5 | Write-time JS gate in `_store_artifact()` | ✅ Done — but blocks JS/TS/Java projects |
| Fix-N | Hard fallback PRD template added to PM agent | ✅ Done — but hardcodes Python constraints |
| Fix-H | Keyword validation gate added to PM agent | ✅ Done — but heuristic logic is inverted |
| Multi-pass arch | Architect now loops up to 2 times before using fallback | ✅ Done |
| Incremental repair | Engineer passes `existing_code` as baseline for fix passes | ✅ Done |
| GraphRAG engineer | `get_surgical_context()` used in engineer during fix mode | ✅ Done |
| Code review sandbox | QualityGates integration in code review | ✅ Done |
| Code review JSON | Robust JSON extraction in code review | ✅ Done |
| Reflexion KG | `analyze_change_impact()` called in execute_and_fix | ✅ Done — but uses wrong project_id |
| `json` import devops | `json` was missing from devops imports | ✅ Done |

---

## 10. Prioritised Fix Checklist

### P0 — Pipeline correctness (must fix before any E2E test can pass)

- [ ] **ORCH-1** — Fix state merge in all 6 orchestrator nodes (use `{**state["project_context"], ...}`)
- [ ] **ORCH-2** — Fix `"comments"` → `"feedback"` key in `_reflexion_node`
- [ ] **ORCH-3** — Fix reflexion node to put `code_repo` from response back into `project_context`
- [ ] **ORCH-4** — Fix `reflexion_count >= MAX_REFLEXION_RETRIES` boundary
- [ ] **REFX-1** — Add `from foundry.testing.quality_gates import QualityGates` to reflexion.py
- [ ] **ORCH-1a** — Fix `makedirs` on empty dirname in `_store_artifact`

### P1 — Multi-language foundation (required before JS/Java/TS projects can work)

- [ ] Create `src/foundry/utils/language_config.py` with `LanguageConfig` dataclass for Python, JS, TS, Java
- [ ] Create `src/foundry/utils/language_guards.py` with `detect_actual_language()` and `is_wrong_language()`
- [ ] Add `language: str` and `framework: str` to `GraphState`
- [ ] Accept `language` in `ProjectCreateRequest` and thread through `run()` → all node payloads
- [ ] **ENG-1** — Replace `language = "python"` hardcode with language from message payload
- [ ] **ENG-2** — Make `_request_code_improvements()` language-parameterized
- [ ] **ENG-3** — Remove last-mile filename renaming loop (replace with language-aware validation)
- [ ] **ARCH-1** — Replace `_sanitize_architecture_for_engineer()` with language-aware sanitization
- [ ] **ARCH-2** — Parse and normalize architecture JSON before forwarding to engineer
- [ ] **REV-2** — Make code review system prompt language-parameterized
- [ ] **DEV-1** — Use `code_repo` in devops to extract deps, entry point, and port information
- [ ] **DEV-1a** — Use `get_config(language).docker_base_image` instead of hardcoded Python image
- [ ] **ORCH-2a** — Remove `.js`, `.ts`, `.java` from `forbidden_exts` in `_store_artifact`
- [ ] **PM-3** fallback — Remove `"Python 3.11+"` from PM fallback template constraints

### P2 — Quality and reliability improvements

- [ ] **PM-1** — Add `_extract_json()` with fence stripping and regex fallback to PM agent
- [ ] **PM-2** — Expand PRD schema to include `functional_requirements`, `non_functional_requirements`, `acceptance_criteria`, `out_of_scope`
- [ ] **PM-3** — Implement clarifying question generation for ambiguous inputs (< 15 words)
- [ ] **PM-1a** — Gate `pm_debug.json` write behind `settings.debug`
- [ ] **REV-1** — Merge `gate_results.security_issues` and `gate_results.lint_issues` into structured `issues` list
- [ ] **ORCH-3a** — Pass full `issues` list from review to reflexion payload
- [ ] **REFX-2** — Return `code_repo` on the fix path (not just on success path)
- [ ] **REFX-3** — Reduce `MAX_RETRY_ATTEMPTS` to 2 in reflexion
- [ ] **HIGH-REFX-1** — Implement multi-file fix application in reflexion
- [ ] **DEV-2** — Replace bare `except` in devops JSON parsing with specific exception + logging
- [ ] **ORCH-3b** — Add Ollama `asyncio.Semaphore(1)` and `num_predict=2048` limit
- [ ] **CROSS-5** — Replace all `print()` statements in agents with `logger.info/warning/error()`

### P3 — KG deep integration (requires P0+P1 stable)

- [ ] Add `store_requirement()` to KG service; call from PM agent after PRD generation
- [ ] Add `store_architecture_decision()` to KG service; call from architect after design
- [ ] Add `store_error_fix()` to KG service; call from reflexion on success
- [ ] Add `get_similar_error_fixes()` to KG tools; inject into reflexion fix prompt
- [ ] Add `get_successful_patterns()` to KG tools; inject into architect design prompt
- [ ] Add `get_project_summary_for_generation()` call to engineer initial generation (not just fix mode)
- [ ] Fix reflexion KG call to use real `project_id` instead of `"current"`
- [ ] Add JS parser (`js_parser.py`) and Java parser (`java_parser.py`) for KG ingestion
- [ ] Thread `language` into `ingestion_pipeline.ingest_project()` to route to correct parser
- [ ] Add `Requirement`, `ArchitectureDecision`, `ErrorFix`, `Pattern` node types and Neo4j constraints

---

*Audit based on direct source review of:*  
`orchestrator.py` · `product_manager.py` · `architect.py` · `engineer.py` · `code_review.py` · `reflexion.py` · `devops.py` · `quality_gates.py` · `knowledge_graph_tools.py` · `knowledge_graph.py` · `ingestion.py` · `code_parser.py`
