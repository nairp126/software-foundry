# Autonomous Software Foundry — Complete Project Audit Report

> **Date:** March 2026  
> **Scope:** Full project-wide audit covering all subsystems, services, models, infrastructure, and tooling  
> **Model:** Qwen2.5-Coder-7B via Ollama (local inference)  
> **Target languages:** Python · JavaScript/Node.js · TypeScript · Java

---

## Table of Contents

1. [Executive Summary & Health Matrix](#1-executive-summary--health-matrix)
2. [Project Structure Overview](#2-project-structure-overview)
3. [Core Infrastructure](#3-core-infrastructure)
4. [API Layer (FastAPI)](#4-api-layer-fastapi)
5. [Database & Data Models](#5-database--data-models)
6. [LLM Provider Layer](#6-llm-provider-layer)
7. [Agent Orchestration](#7-agent-orchestration)
8. [Agent Implementations](#8-agent-implementations)
9. [Knowledge Graph Subsystem](#9-knowledge-graph-subsystem)
10. [Sandbox & Code Execution](#10-sandbox--code-execution)
11. [Testing & Quality Gates](#11-testing--quality-gates)
12. [Version Control Integration](#12-version-control-integration)
13. [Middleware & Security](#13-middleware--security)
14. [Services Layer](#14-services-layer)
15. [Utilities & Language Support](#15-utilities--language-support)
16. [Infrastructure & DevOps Configuration](#16-infrastructure--devops-configuration)
17. [What Is Missing (Not Yet Built)](#17-what-is-missing-not-yet-built)
18. [Cross-Cutting Issues](#18-cross-cutting-issues)
19. [Prioritised Improvements & Fix Checklist](#19-prioritised-improvements--fix-checklist)

---

## 1. Executive Summary & Health Matrix

| Subsystem | Files | Status | Completeness | Critical Issues |
|-----------|-------|--------|:---:|:---:|
| Core Infrastructure | `database.py`, `config.py`, `redis_client.py` | ✅ Solid | 85% | 0 |
| API Layer | `main.py`, `api/schemas.py` | ✅ Working | 70% | 2 |
| Database Models | `models/` | ✅ Working | 75% | 1 |
| LLM Providers | `llm/` | ✅ Working | 80% | 1 |
| Orchestrator | `orchestrator.py` | ⚠️ Partial | 55% | 4 |
| Agent — PM | `agents/product_manager.py` | ⚠️ Partial | 60% | 1 |
| Agent — Architect | `agents/architect.py` | ⚠️ Partial | 65% | 2 |
| Agent — Engineer | `agents/engineer.py` | ⚠️ Partial | 60% | 3 |
| Agent — Code Review | `agents/code_review.py` | ⚠️ Partial | 65% | 2 |
| Agent — Reflexion | `agents/reflexion.py` | ⚠️ Partial | 55% | 3 |
| Agent — DevOps | `agents/devops.py` | ❌ Stub | 20% | 3 |
| Knowledge Graph | `graph/`, `services/knowledge_graph.py`, `tools/` | ✅ Good | 70% | 1 |
| Sandbox Execution | `sandbox/`, `services/sandbox_service.py` | ⚠️ Partial | 50% | 2 |
| Testing & QA | `testing/` | ✅ Good | 70% | 0 |
| Version Control | `vcs/git_manager.py`, `services/git_service.py` | ✅ Good | 75% | 1 |
| Middleware & Security | `middleware/` | ✅ Good | 75% | 1 |
| Services Layer | `services/` | ✅ Mostly good | 70% | 1 |
| Utilities | `utils/` | ✅ Good | 80% | 0 |
| Test Coverage | `tests/` | ❌ Missing | 5% | — |
| VS Code Extension | — | ❌ Not started | 0% | — |
| AWS CDK / Cloud | — | ❌ Not started | 0% | — |

**Overall project completeness: ~58% of MVP scope implemented**

**Summary of the most impactful gaps:**

- Four critical orchestrator bugs mean E2E pipeline never completes successfully
- Zero automated test coverage of the codebase itself
- VS Code extension (core client) does not exist
- Resume-from-pause restores project to `created` status instead of the correct running state
- WebSocket broadcast not connected to actual agent status changes
- `language` and `framework` not threaded through the full pipeline state

---

## 2. Project Structure Overview

### Confirmed existing files and modules

```
src/foundry/
├── agents/
│   ├── base.py                    ✅ Agent base class, AgentMessage, AgentType
│   ├── product_manager.py         ✅ Implemented
│   ├── architect.py               ✅ Implemented
│   ├── engineer.py                ✅ Implemented
│   ├── code_review.py             ✅ Implemented
│   ├── reflexion.py               ✅ Implemented
│   ├── devops.py                  ⚠️ Minimal stub
│   └── __init__.py
├── api/
│   ├── schemas.py                 ✅ All Pydantic schemas
│   └── __init__.py
├── graph/
│   ├── neo4j_client.py            ✅ Full async Neo4j client
│   ├── code_parser.py             ✅ Python AST parser + content extraction
│   ├── ingestion.py               ✅ Multi-language ingestion pipeline
│   └── __init__.py
├── llm/
│   ├── base.py                    ✅ BaseLLMProvider, LLMMessage, LLMResponse
│   ├── ollama_provider.py         ✅ Full implementation with semaphore + timeout
│   ├── vllm_provider.py           ✅ Stub with basic structure
│   ├── factory.py                 ✅ Provider factory
│   ├── test.py                    ✅ Integration test script
│   └── __init__.py
├── middleware/
│   ├── auth.py                    ✅ API key auth with master key support
│   ├── rate_limit.py              ✅ Redis sliding window rate limiter
│   ├── security.py                ✅ Security headers middleware
│   └── __init__.py
├── models/
│   ├── base.py                    ✅ UUID PK, timestamps
│   ├── project.py                 ✅ Project with language/framework fields
│   ├── artifact.py                ✅ Artifact storage
│   ├── approval.py                ✅ Approval workflow models
│   ├── api_key.py                 ✅ API key with hashing
│   └── __init__.py
├── sandbox/
│   ├── environment.py             ✅ SandboxEnvironment with Docker
│   ├── error_analysis.py          ✅ ErrorAnalyzer, FixGenerator
│   └── __init__.py
├── services/
│   ├── knowledge_graph.py         ✅ Full KG service
│   ├── git_service.py             ✅ Basic git init/commit
│   ├── sandbox_service.py         ✅ Docker-based execution
│   ├── agent_control.py           ✅ Pause/resume/cancel/checkpoint
│   └── project_service.py         ✅ Project CRUD with lifecycle
├── testing/
│   ├── test_generator.py          ✅ Multi-language test generation
│   ├── quality_gates.py           ✅ Linting/type/security gates
│   └── __init__.py
├── tools/
│   └── knowledge_graph_tools.py   ✅ Agent-facing KG query tools
├── utils/
│   ├── language_config.py         ✅ 4-language config dataclass
│   ├── language_guards.py         ✅ Language mismatch detection
│   └── __init__.py
├── vcs/
│   └── git_manager.py             ✅ Full GitManager with branching
├── config.py                      ✅ Pydantic settings
├── database.py                    ✅ Async SQLAlchemy
├── main.py                        ✅ Full FastAPI app
├── orchestrator.py                ✅ LangGraph orchestrator
└── redis_client.py                ✅ Redis client wrapper
```

### Confirmed missing

```
tests/                             ❌ No test files exist
vscode-extension/                  ❌ Not started
cdk/                               ❌ Not started (AWS CDK)
alembic/versions/                  ❌ No migration files (only alembic.ini exists)
docs/                              ✅ OLLAMA_SETUP.md, VLLM_SETUP.md, etc.
```

---

## 3. Core Infrastructure

### 3.1 Database (`database.py`)

**Status: ✅ Solid**

- Async SQLAlchemy with `asyncpg` driver
- `get_db()` async generator for FastAPI dependency injection
- Connection pooling: configurable `pool_size` and `max_overflow`
- Proper rollback on error, close in finally

**Issues:**

- `echo=settings.debug` logs all SQL in debug mode, including any potentially sensitive query values — acceptable for dev but should be reviewed before production

**Missing:**

- No Alembic migration files exist. The schema is created via `Base.metadata.create_all()` on startup rather than managed migrations. This means schema changes require manual intervention and there is no upgrade path.

**Recommended fix:** Add `alembic init alembic` and generate the initial migration. Add migration check to lifespan startup.

---

### 3.2 Configuration (`config.py`)

**Status: ✅ Good**

- Pydantic `BaseSettings` with environment variable support
- Covers: database, Redis, Neo4j, Ollama, LLM settings, paths, API keys

**Issues:**

- `CORS allow_origins=["*"]` in `main.py` — wildcard CORS is insecure for production. Should be configurable from settings.
- No validation that `generated_projects_path` exists at startup

---

### 3.3 Redis (`redis_client.py`)

**Status: ✅ Working**

- Async Redis client with connect/disconnect lifecycle
- Used by rate limiter, agent control, and checkpointing

**Issues:**

- If Redis is unavailable at startup, the rate limiter silently allows all requests. This is the correct degraded behavior but is not logged as a warning.

---

## 4. API Layer (FastAPI)

### 4.1 Endpoints implemented in `main.py`

| Method | Path | Status | Notes |
|--------|------|--------|-------|
| POST | `/projects` | ✅ Working | Creates project, fires background task |
| GET | `/projects` | ✅ Working | Lists projects with status filter |
| GET | `/projects/{id}` | ✅ Working | Fetches single project |
| DELETE | `/projects/{id}` | ✅ Working | Deletes project + artifacts |
| GET | `/projects/{id}/artifacts` | ✅ Working | Returns all artifacts |
| GET | `/projects/{id}/approval` | ✅ Working | Get latest approval |
| POST | `/projects/{id}/approve` | ✅ Working | Approves pending gate |
| POST | `/projects/{id}/reject` | ✅ Working | Rejects + marks project failed |
| GET | `/projects/{id}/agent/status` | ✅ Working | Agent status + pause check |
| POST | `/projects/{id}/agent/pause` | ✅ Working | Sets pause flag in Redis |
| POST | `/projects/{id}/agent/resume` | ⚠️ Bug | Restores to `created`, not correct state |
| POST | `/projects/{id}/agent/cancel` | ✅ Working | Cancel + optional rollback |
| GET | `/ws/projects/{id}` | ⚠️ Partial | WebSocket connected but no broadcast |
| POST | `/api-keys` | ✅ Working | Creates key, returns plaintext once |
| GET | `/api-keys` | ✅ Working | Lists keys (no secret) |
| DELETE | `/api-keys/{id}` | ✅ Working | Deletes key |
| PATCH | `/api-keys/{id}/deactivate` | ✅ Working | Soft deactivation |
| GET | `/health` | ✅ Working | Returns healthy |

### 4.2 Critical Issues

#### API-BUG-1 · Resume endpoint restores project to `created` status

```python
# Current:
project.status = ProjectStatus.created   # WRONG

# Should be:
checkpoint = await agent_control_service.get_checkpoint(project_id)
if checkpoint and checkpoint.get("agent_state", {}).get("current_status"):
    project.status = ProjectStatus(checkpoint["agent_state"]["current_status"])
else:
    project.status = ProjectStatus.created  # fallback only
```

There is no mechanism to actually resume the LangGraph graph execution from where it paused. Setting status to `created` will cause the project to appear as new. A real resume requires LangGraph checkpointing with `MemorySaver` or a custom checkpoint serializer.

---

#### API-BUG-2 · WebSocket endpoint does not broadcast real-time updates

```python
@app.websocket("/ws/projects/{project_id}")
async def project_websocket(websocket: WebSocket, project_id: UUID):
    # Accepts connection, polls DB every 2 seconds, sends status
    # But: agent nodes never push events to this channel
```

The WebSocket polls the database for status — it does not receive events when agents change state. Clients see status changes with up to a 2-second delay and never see intermediate agent events (e.g., "generating file X", "running sandbox", "review passed"). To fix, agents must push events via Redis pub/sub and the WebSocket handler must subscribe.

---

#### API-BUG-3 · `ProjectCreateRequest` does not accept `language` or `framework`

```python
class ProjectCreateRequest(BaseModel):
    requirements: str
    name: Optional[str] = None
    description: Optional[str] = None
    approval_policy: Optional[str] = "standard"
    # language and framework not here
```

Even though `Project` model has `language` and `framework` columns, the creation endpoint cannot receive them. Every project defaults to Python.

---

#### API-BUG-4 · `_run_project_background` does not pass `language` to orchestrator

```python
async def _run_project_background(project_id: str, requirements: str) -> None:
    orchestrator = AgentOrchestrator()
    await orchestrator.run(project_id=str(project_id), initial_prompt=requirements)
    # language never passed
```

---

### 4.3 Medium Issues

- No pagination on `GET /projects` — will be slow with many projects
- No search/filter by name on project list
- `approval_policy` stored as string in request but as `ApprovalPolicy` enum in model — no validation bridge
- Error response for WebSocket disconnect is swallowed silently
- `deactivate_api_key` endpoint does not require `require_api_key` — any unauthenticated request can deactivate a key by guessing its ID

---

## 5. Database & Data Models

### 5.1 Models

**`Project`** — `models/project.py`

- ✅ UUID primary key via `BaseModel`
- ✅ `language` and `framework` columns added
- ✅ `approval_policy` enum
- ✅ `prd`, `architecture`, `code_review` as JSONB
- ⚠️ `prd` and `architecture` are stored as JSONB in the model but the orchestrator writes them as string artifacts to the filesystem — the model fields are never populated by the pipeline

**`Artifact`** — `models/artifact.py`

- ✅ Linked to `Project` via FK
- ✅ `ArtifactType` enum: `code`, `documentation`, `review`, `devops`, `test`
- ✅ `content` stored as Text
- ⚠️ No `language` field on artifact — cannot query "all Python files for project X"

**`ApprovalRequest`** — `models/approval.py`

- ✅ `stage`, `status`, `content` (JSONB), `reviewer_comment`
- ⚠️ Approval content is stored but never actually blocks the pipeline — the orchestrator does not check for pending approvals before proceeding to the next node

**`APIKey`** — `models/api_key.py`

- ✅ SHA-256 hashing, prefix storage
- ✅ Expiry, is_active, last_used tracking
- ✅ `rate_limit_per_minute` column — but the rate limiter uses the same 60/min for all keys regardless of this value

**Missing models:**

- No `AgentExecution` record — cannot track per-agent timing, token counts, or error history
- No `ProjectEvent` log table — no audit trail of state transitions
- No migration files — all schema changes require manual intervention

---

### 5.2 Critical Issues

#### DB-BUG-1 · `approval_policy` value in `ProjectCreateRequest` is not validated

The request accepts `approval_policy: Optional[str] = "standard"` but the model expects an `ApprovalPolicy` enum. An invalid string like `"aggressive"` will raise a cryptic DB error at commit time rather than a clean 422 response.

---

## 6. LLM Provider Layer

### 6.1 `ollama_provider.py`

**Status: ✅ Solid**

- Class-level `asyncio.Semaphore(1)` for request serialization ✅
- `num_ctx=4096`, `num_predict=2048` limits ✅
- `asyncio.wait_for(timeout=120.0)` hard timeout ✅
- Proactive connection check before generation ✅
- `stream_generate()` async generator for streaming ✅
- `json_mode=True` format parameter supported ✅
- Token usage metadata returned ✅

**Issues:**

#### LLM-BUG-1 · `vllm_provider.py` raises `NotImplementedError` — listed as implemented in task plan

```python
async def generate(self, messages, ...):
    raise NotImplementedError("vLLM provider generate not implemented")
```

Tasks.md marks this as ✅ but the actual implementation is a stub. Any configuration using `provider_name="vllm"` will crash at the first agent call.

---

#### LLM-ISSUE-1 · OpenAI and Anthropic providers raise `NotImplementedError` in factory

Both are listed in the factory with `raise NotImplementedError(...)`. Any production fallback configuration relying on these will crash.

#### LLM-ISSUE-2 · No LLM call logging to structured logger

All token usage is returned in `LLMResponse.metadata` but nothing logs it persistently. There is no way to audit which model was used, how many tokens, or cost per project without adding instrumentation.

#### LLM-ISSUE-3 · `json_mode=True` not universally available in Ollama

Ollama's `format: "json"` instruction only works with models that support it. Qwen2.5-Coder-7B does support it, but there is no fallback if the model returns non-JSON despite the flag.

---

## 7. Agent Orchestration

*(Covered in depth in the separate Agent Audit Report — summary here)*

### 7.1 Status

**Status: ⚠️ Partial — 4 critical bugs prevent E2E completion**

| Bug | Description | Impact |
|-----|-------------|--------|
| State merge | All nodes except `_devops_node` return fresh `project_context` dicts, destroying prior context | CRITICAL — pipeline loses PRD before engineer runs |
| Key mismatch | Reflexion reads `"comments"` but review returns `"feedback"` | CRITICAL — reflexion gets empty context always |
| QualityGates import | Missing import in `reflexion.py` — `NameError` on instantiation | CRITICAL — reflexion agent never runs |
| Reflexion output | Returns `fix_plan` text on fix path, not updated `code_repo` | CRITICAL — broken code never actually fixed |

### 7.2 Improvements needed

- `language` and `framework` must be added to `GraphState` and threaded through all 6 nodes
- KG ingestion call hardcodes `"Python Project"` as name — must use actual PRD project name and pass language
- `success_flag` can be lost due to state merge issue — needs explicit propagation
- `_store_artifact` `makedirs` crashes on empty dirname for root-level files on Windows
- `MAX_REFLEXION_RETRIES` boundary check off-by-one (`<` vs `>=`)
- No approval gate between architect and engineer nodes (design spec requires user approval after architecture)
- `_code_review_node` does not pass `language` to code review agent

---

## 8. Agent Implementations

*(Covered in depth in the separate Agent Audit Report — summary of current status here)*

### 8.1 Quick status summary

| Agent | Key strength | Key weakness |
|-------|-------------|--------------|
| Product Manager | Domain anchoring, fallback templates | No JSON extraction, thin PRD schema, no clarifying questions |
| Architect | Multi-pass validation, sanitization, fallback arch | Sanitizer breaks multi-language; arch not parsed to JSON before forwarding |
| Engineer | 3-attempt recovery, GraphRAG, language coding standards map | Language hardcoded to python in `generate_code()`; last-mile rename loop breaks multi-language |
| Code Review | Sandbox + LLM synthesis, robust JSON parse, structured issues | Review prompt hardcoded Python-only; sandbox findings not merged into issues list |
| Reflexion | Full sandbox execution loop, KG impact analysis, dependency extraction | Missing QualityGates import; returns text on fix path not updated code |
| DevOps | `code_repo` received | `code_repo` never used; bare except swallows all failures; Python-only hardcoded |

---

## 9. Knowledge Graph Subsystem

### 9.1 What is fully implemented

| Component | File | Status |
|-----------|------|--------|
| Neo4j async client | `graph/neo4j_client.py` | ✅ Full — connect, query, write, constraints, health check |
| Python AST parser | `graph/code_parser.py` | ✅ Full — functions, classes, imports, content snippets, call graph |
| Multi-language ingestion | `graph/ingestion.py` | ✅ Good — routes by language, two-pass (nodes then relationships) |
| KG service — write methods | `services/knowledge_graph.py` | ✅ Full — store_function, store_class, store_module, store_component, store_pattern, store_error_fix, relationships |
| KG service — query methods | `services/knowledge_graph.py` | ✅ Good — find_dependencies, analyze_impact, search_patterns, get_project_context |
| Agent tools | `tools/knowledge_graph_tools.py` | ✅ Full — surgical context, file map, impact analysis, find callers, pattern search |
| Neo4j constraints | `graph/neo4j_client.py` | ✅ Updated — includes Requirement, ArchitectureDecision, Pattern, ErrorFix node types |
| Store pattern/error_fix | `services/knowledge_graph.py` | ✅ Implemented with non-blocking try/except |

### 9.2 What is partially wired to agents

| Integration Point | Status | Notes |
|-------------------|--------|-------|
| KG ingestion after code gen | ✅ Called in `_engineer_node` | But uses hardcoded `"Python Project"` name; language not passed |
| Engineer surgical context | ✅ Used in `_generate_file_content` | Only on fix pass, not initial generation |
| Reflexion impact analysis | ⚠️ Called | Uses `project_id="current"` — never returns real data |
| Architect KG query | ❌ Not called | `kg_tools` instantiated but `design_architecture()` never uses it |
| PM requirement storage | ❌ Not called | `kg_tools` not even instantiated in PM |
| Cross-project pattern query | ❌ Not called | Methods exist but no agent calls them |

### 9.3 Issues

#### KG-BUG-1 · `get_surgical_context()` uses `project_id` parameter but Neo4j query uses `project_id` as a keyword arg

```python
# In knowledge_graph_tools.py:
results = await self.kg_service.client.execute_query(
    query,
    project_id=project_id,   # keyword arg
    names=dependency_names
)
```

But `execute_query` signature is `execute_query(self, query, parameters=None)`. The keyword arguments are not being passed as the `parameters` dict — they are being ignored. The query runs without parameters and returns empty results every time.

**Fix:**

```python
results = await self.kg_service.client.execute_query(
    query,
    {"project_id": project_id, "names": dependency_names}
)
```

---

#### KG-ISSUE-1 · JS and Java parsers are not yet implemented

`ingestion.py` has the routing logic to call `_get_parser(language)` for JS/Java, but the actual parser classes (`JSCodeParser`, `JavaCodeParser`) are not created. JS and Java projects will either silently skip ingestion or fall back to the Python parser which will parse nothing useful.

#### KG-ISSUE-2 · No `Requirement` node is ever stored

`knowledge_graph.py` has the constraint for `Requirement` nodes but no `store_requirement()` method and no agent calls it. Requirements from the PM agent are never persisted to the KG.

#### KG-ISSUE-3 · `store_error_fix()` and `store_pattern()` exist but are never called

These are implemented with non-blocking try/except, but no agent calls them. Cross-project learning from successful fixes is planned but not connected.

#### KG-ISSUE-4 · `get_project_file_map()` query uses wrong property name

```cypher
MATCH (project:Project {project_id: $project_id})
```

But project nodes are created with `id`, not `project_id`:

```cypher
CREATE (p:Project {id: $project_id, ...})
```

The file map query returns empty every time.

---

## 10. Sandbox & Code Execution

### 10.1 Dual sandbox implementations

There are two separate sandbox implementations:

| File | Purpose | Status |
|------|---------|--------|
| `sandbox/environment.py` | `SandboxEnvironment` — used by `ReflexionEngine` and `QualityGates` | ✅ More complete |
| `services/sandbox_service.py` | `SandboxService` — standalone Docker executor | ✅ Separate, simpler |

These are not integrated — `sandbox_service.py` is never called by agents or the orchestrator. Only `sandbox/environment.py` is used.

### 10.2 `sandbox/environment.py`

**Status: ✅ Good foundation**

- Creates Docker container per execution
- Network isolation (`--network none`)
- Memory and CPU limits
- Timeout enforcement
- Multi-file execution via temp directory
- Cleanup in `finally` block

### 10.3 Issues

#### SANDBOX-BUG-1 · `sandbox/environment.py` is synchronous subprocess in an async context

```python
process = subprocess.run(docker_args, ...)   # BLOCKING
```

`subprocess.run` is a blocking call. When called from an `async` function, it blocks the entire event loop for the duration of container execution (up to 30s). Other requests/tasks cannot run during this time.

**Fix:** Use `asyncio.create_subprocess_exec` instead:

```python
process = await asyncio.create_subprocess_exec(
    *docker_args,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
)
stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
```

---

#### SANDBOX-BUG-2 · Java sandbox not configured

`sandbox_service.py` image map only has `python` and `javascript`/`typescript`. `sandbox/environment.py` also lacks Java container configuration. Java projects will use the Python image and fail.

---

#### SANDBOX-ISSUE-1 · Docker socket mount security risk

Both sandbox implementations assume `/var/run/docker.sock` is mounted into the API container. This gives the API container full Docker host access, which is a container escape vector. For production, this should be replaced with a dedicated sidecar container or socket proxy (e.g., `docker-socket-proxy`).

#### SANDBOX-ISSUE-2 · `services/sandbox_service.py` never called — dead code

The `SandboxService` in `services/sandbox_service.py` is imported in `__init__.py` as `sandbox_service` but is never referenced by any agent, orchestrator node, or API endpoint. Only `sandbox/environment.py` (`SandboxEnvironment`) is used by the reflexion engine and quality gates.

---

## 11. Testing & Quality Gates

### 11.1 `testing/test_generator.py`

**Status: ✅ Good**

- Multi-language framework selection: pytest, jest, vitest, junit
- `get_test_filename()` follows framework conventions (PascalCase for JUnit, `.test.js` for Jest)
- Framework-specific prompt instructions per language
- Code extraction from markdown-fenced LLM responses
- Coverage analysis estimation via LLM

**Issues:**

- Coverage analysis is estimated by LLM, not actually measured by running tests. Coverage numbers are fabricated.
- `generate_unit_tests()` passes the entire source code into one LLM call — for files >1000 lines this will exceed the 4096 token context window.

---

### 11.2 `testing/quality_gates.py`

**Status: ✅ Solid foundation**

- Pylint, ESLint, mypy, tsc stubs, Bandit, npm audit stubs
- Runs tools via Docker sandbox
- JSON output parsing for all tool types
- `QualityGateResult` dataclass with pass/fail and issue lists
- `run_quality_gates()` calls linting + type checking + security in sequence

**Issues:**

- ESLint and npm audit are implemented but only produce empty lists — the actual tool invocations are present but the output parsing may not match the tool's actual JSON format
- `_run_tsc()` returns `[]` — TypeScript type checking is a stub
- `_run_rubocop()` returns `[]` — Ruby is a stub (expected)
- Quality gate execution itself uses the same blocking subprocess issue as the sandbox

---

### 11.3 Project test coverage

**Status: ❌ No tests exist**

There are zero `tests/` directory files. The entire system has no automated tests — no unit tests, no integration tests, no property-based tests, no E2E tests. The only test file is `src/foundry/llm/test.py` which is a manual integration smoke test script, not a pytest suite.

This is the single largest quality risk in the project.

---

## 12. Version Control Integration

### 12.1 Dual Git implementations

| File | Class | Status | Used by |
|------|-------|--------|---------|
| `services/git_service.py` | `GitService` | ✅ Basic | Imported in `orchestrator.py` but never called |
| `vcs/git_manager.py` | `GitManager` | ✅ Comprehensive | Not called by any orchestrator node |

**Neither Git implementation is called by the orchestrator pipeline.** Projects are generated and persisted to disk but no Git repository is initialized and no commit is made.

### 12.2 `vcs/git_manager.py`

**Status: ✅ Well implemented**

- `initialize_repository()` — init, gitignore, gitattributes, initial commit
- `create_commit()` — conventional commit format with scope and breaking change support
- `create_feature_branch()` — `foundry/<agent>/<feature>` naming convention
- `get_current_branch()`, `list_branches()`, `merge_branch()`
- `create_tag()` — semantic versioning
- `detect_conflicts()`, `resolve_conflicts()` — 3-way merge detection

**Issues:**

#### VCS-BUG-1 · `git_service.py` imported in orchestrator but `git_manager.py` is the complete implementation

The orchestrator imports `git_service` but only uses it in a commented-out or non-functional path. `GitManager` (the complete implementation) is never imported by the orchestrator. The better implementation is completely disconnected.

---

#### VCS-ISSUE-1 · Git operations not integrated into the code generation flow

The orchestrator's `_engineer_node` should call `git_manager.initialize_repository()` on first generation and `git_manager.create_commit()` after each successful code generation. This is currently never done.

---

## 13. Middleware & Security

### 13.1 Authentication (`middleware/auth.py`)

**Status: ✅ Good**

- `APIKeyHeader` for `X-API-Key` header
- SHA-256 key hashing — plaintext never stored
- Master key support via `settings.foundry_api_key`
- Expiry check, `is_active` flag, last-used timestamp update
- `get_api_key` (optional) and `require_api_key` (enforced) dependencies

**Issues:**

- Master key returns a mock `APIKey` object with `id=None` — endpoints that call `api_key.id` will crash with `AttributeError`
- `deactivate_api_key` endpoint has no `require_api_key` dependency — anyone can deactivate a key
- No IP whitelisting (column exists in model but never checked)

---

### 13.2 Rate Limiting (`middleware/rate_limit.py`)

**Status: ✅ Good**

- Redis sliding window using sorted sets
- Per-API-key and per-IP tracking
- Rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- Health and docs paths bypassed
- Graceful Redis failure (allows all requests)

**Issues:**

- Rate limit is 60/min globally, but `APIKey` model has `rate_limit_per_minute` per key — the middleware never reads the per-key value

---

### 13.3 Security Headers (`middleware/security.py`)

**Status: ✅ Good**

- HSTS, CSP, X-Frame-Options, X-Content-Type-Options, XSS-Protection, Referrer-Policy, Permissions-Policy

**Issues:**

- CSP includes `'unsafe-inline'` and `'unsafe-eval'` for scripts — these reduce CSP effectiveness. Acceptable for development but should be tightened before production.
- CORS allows `*` in `main.py` — wildcard CORS overrides the CSP intent for cross-origin requests

---

## 14. Services Layer

### 14.1 `services/agent_control.py`

**Status: ✅ Good**

- Pause, resume, cancel with Redis flags
- Checkpoint save/get/delete with 7-day TTL
- Control status check

**Issues:**

- `pause_execution()` sets a Redis flag, but the orchestrator never checks this flag during execution. Pausing only works at the API boundary — an in-progress agent node will not stop.
- Checkpoints store `agent_state: Dict` but there is no mechanism to restore LangGraph execution from a checkpoint (LangGraph requires `MemorySaver` or custom checkpointing configured at graph compile time).
- `resume_execution()` only deletes the Redis key. The API endpoint then sets `project.status = ProjectStatus.created`, which loses all progress.

---

### 14.2 `services/project_service.py`

**Status: ✅ Good**

- Full CRUD with lifecycle management
- `delete_project()` — multi-step: CDK destroy stub, KG cleanup stub, filesystem delete, DB record delete
- `list_projects()` with status filter and metadata
- Resource usage and cost estimation stubs

**Issues:**

- `_destroy_cloud_resources()` is a stub — CDK integration is not implemented
- `_delete_knowledge_graph_nodes()` is a stub — KG cleanup does not happen on project deletion
- `_get_resource_usage()` and `_estimate_monthly_cost()` return hardcoded `0` and `0.0`

---

### 14.3 `services/knowledge_graph.py`

**Status: ✅ Well implemented** — covered in detail in Section 9.

---

## 15. Utilities & Language Support

### 15.1 `utils/language_config.py`

**Status: ✅ Complete**

- `LanguageConfig` dataclass with all language metadata
- 4 languages: Python, JavaScript, TypeScript, Java
- Fields: extensions, entry_point, package_file, test_pattern, linters, test_framework, base_image, coding_standard, web_frameworks, forbidden_patterns
- `get_language_config(language)` with Python fallback

**Issues:**

- `forbidden_patterns` field exists but is never read by any agent or guard — it was intended to be used for wrong-language detection but `language_guards.py` uses its own separate signature list

---

### 15.2 `utils/language_guards.py`

**Status: ✅ Good**

- Language signature patterns for Python, JavaScript, TypeScript, Java
- `detect_language_mismatch(code, expected_language)` — returns True if code appears to be in a different language
- `recover_prompt(filename, dirty_code, target_language, architecture)` — builds corrective LLM prompt
- Scoring mechanism: counts signature hits per language, mismatch when a different language scores higher

**Issues:**

- `recover_prompt()` calls `get_language_config(language)` and then accesses `config["name"]` and `config["extension"]` as dict keys, but `get_language_config()` returns a `LanguageConfig` dataclass, not a dict. This will raise `TypeError` when the recovery prompt is built.

**Fix:**

```python
# Wrong:
config = get_language_config(target_language)
lang_name = config["name"]

# Correct:
config = get_language_config(target_language)
lang_name = config.name
```

---

### 15.3 `utils/__init__.py`

**Status: ✅ Clean** — exports `get_language_config`, `detect_language_mismatch`, `recover_prompt`.

---

## 16. Infrastructure & DevOps Configuration

### 16.1 `docker-compose.yml`

**Status: ✅ Core services present**

Services confirmed: `api`, `celery-worker`, `postgres`, `redis`, `neo4j`, `ollama`

**Issues:**

#### INFRA-BUG-1 · `generated_projects` volume not mounted to host

The generated project files are written to `/app/generated_projects` inside the container, but this directory is not mounted to the host filesystem. When the E2E test looks for generated files, they are invisible.

**Fix (already documented in fixes document):**

```yaml
volumes:
  - ./generated_projects:/app/generated_projects
```

Must be added to both `api` and `celery-worker` services.

---

#### INFRA-ISSUE-1 · Ollama model not pulled in docker-compose startup

The `ollama` service starts but does not pull `qwen2.5-coder:7b` automatically. The API will fail on first LLM call with a 404 "model not found" error until the model is manually pulled.

Add to docker-compose:

```yaml
ollama:
  entrypoint: ["/bin/sh", "-c", "ollama serve & sleep 5 && ollama pull qwen2.5-coder:7b && wait"]
```

#### INFRA-ISSUE-2 · No Alembic migration configuration

`alembic.ini` exists but no `alembic/versions/` migration files. The database schema is created via `Base.metadata.create_all()` which is not suitable for production schema management.

#### INFRA-ISSUE-3 · No health check for dependent services

`api` service starts without waiting for postgres, redis, and neo4j to be ready. Race conditions on first startup can cause connection errors.

Add `depends_on` with health checks:

```yaml
api:
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
```

---

## 17. What Is Missing (Not Yet Built)

### 17.1 VS Code Extension — 0% complete

The primary user-facing client is not started. No TypeScript extension code exists. Per requirements:

- WebSocket connection to backend
- Phantom File Tree rendering
- Real-time token streaming into editor
- Approve/reject UI
- Agent dashboard panel

### 17.2 AWS CDK Integration — 0% complete

Requirements 7.1-7.6 mandate:

- CDK infrastructure generation (TypeScript/Python)
- `cdk synth` validation before deployment
- `cdk bootstrap` detection
- `cdk deploy --require-approval never`
- CfnOutput capture (Load Balancer URLs, S3 buckets)
- `cdk destroy --force` on deletion

None of this exists. DevOps agent generates only a Dockerfile and docker-compose.yml.

### 17.3 Alembic migrations — 0% complete

Schema changes are applied via `Base.metadata.create_all()`. Production deployments require proper Alembic migration history.

### 17.4 OpenAI and Anthropic providers — stubs only

Both raise `NotImplementedError`. Production fallback chains are not functional.

### 17.5 LangGraph human-in-the-loop approval gate

The design requires a pause between architect and engineer for user approval of the architecture. The LangGraph graph goes directly from `architect → engineer` with no approval checkpoint. `ApprovalRequest` model exists but is never created by the orchestrator.

### 17.6 Real pause/resume for LangGraph graph

Current pause sets a Redis flag but the graph never checks it. True pause/resume requires LangGraph `MemorySaver` checkpointing configured at compile time, and the `run()` method must support resuming from a thread ID.

### 17.7 Automated test suite for the project itself

Zero pytest tests for any component. The entire codebase is tested manually only.

### 17.8 JS/Java parsers for Knowledge Graph

`js_parser.py` and `java_parser.py` are referenced in ingestion routing but do not exist as files.

### 17.9 Cost estimation

`project_service.py` has `_estimate_monthly_cost()` that returns `0.0`. No integration with AWS pricing API or local estimation.

### 17.10 Monitoring dashboard

No Prometheus metrics, no Grafana dashboard, no structured log shipping.

### 17.11 `store_requirement()` method in KG service

The `Requirement` node type has a constraint in Neo4j but there is no service method to create them. PM agent cannot store requirements in KG.

---

## 18. Cross-Cutting Issues

### 18.1 `print()` statements throughout agents

All agents use `print(f"DEBUG: ...")` and `print(f"CRITICAL: ...")` instead of `logger.info/warning/error`. This pollutes stdout, cannot be filtered by log level, and writes sensitive data to container logs.

**Fix:** Replace all `print()` calls in `agents/` with `logger.info()`, `logger.warning()`, `logger.critical()`.

### 18.2 Language threading gap

`language` and `framework` exist in the `Project` model and `ProjectCreateRequest` could accept them, but they are never:

1. Passed to the orchestrator `run()` method
2. Added to `GraphState`
3. Forwarded in any agent message payload

Every project, regardless of what was requested, executes as a Python project.

### 18.3 No structured event logging

The system has no `ProjectEvent` table or event bus. When debugging a failed project, there is no way to see the sequence: "PM generated PRD at 10:01, Architect started at 10:02, Engineer failed at 10:05 with error X". Only the final `project.status` is persisted.

### 18.4 `approve/reject` endpoints don't actually gate the pipeline

The approval endpoints exist and work correctly, but the pipeline never checks for pending approvals. The graph flows continuously from node to node. The approval model is orphaned infrastructure with no consumer.

### 18.5 Redis connection failure handling

If Redis goes down during a project run, the rate limiter silently allows all requests (correct), but `agent_control_service` operations will throw unhandled exceptions because there is no try/except around Redis operations in `AgentControlService`.

---

## 19. Prioritised Improvements & Fix Checklist

### P0 — Must fix before any E2E test passes

- [ ] **INFRA-BUG-1** — Add `generated_projects` volume mount to docker-compose for `api` and `celery-worker`
- [ ] **ORCH-BUG-1** — Fix state merge in `_pm_node`, `_architect_node`, `_engineer_node`, `_code_review_node`, `_reflexion_node` (use `{**state["project_context"], ...}`)
- [ ] **ORCH-BUG-2** — Fix `"comments"` → `"feedback"` key in `_reflexion_node`
- [ ] **REFX-BUG-1** — Add `from foundry.testing.quality_gates import QualityGates` to `reflexion.py`
- [ ] **ORCH-BUG-3** — Fix reflexion node to propagate `code_repo` from response back into `project_context`
- [ ] **ORCH-BUG-4** — Fix `reflexion_count >= MAX_REFLEXION_RETRIES` boundary (`<` vs `>=`)
- [ ] **KG-BUG-1** — Fix `execute_query()` parameter passing in `get_surgical_context()` (use positional dict, not keyword args)
- [ ] **KG-ISSUE-4** — Fix `get_project_file_map()` Cypher to use `{id: $project_id}` not `{project_id: $project_id}`

### P1 — Required for multi-language support and reliable operation

- [ ] **API-BUG-3** — Add `language` and `framework` to `ProjectCreateRequest`
- [ ] **API-BUG-4** — Pass `language` and `framework` from request → project model → `_run_project_background()` → `orchestrator.run()`
- [ ] **ORCH** — Add `language: str` and `framework: str` to `GraphState`; thread through all node payloads
- [ ] **ENG-BUG-1** — Replace `language = "python"` hardcode with `message.payload.get("language", "python")`
- [ ] **UTILS-BUG-1** — Fix `recover_prompt()` to use `config.name` and `config.extensions[0]` not dict key access
- [ ] **ARCH-BUG-1** — Make `_sanitize_architecture_for_engineer()` conditional on Python-only projects; skip for JS/Java
- [ ] **REV-BUG-2** — Replace `"Python-only auditor"` system prompt with language-parameterized version
- [ ] **DEV-BUG-1** — Use `code_repo` in `devops.py` to extract deps and entry point; use `get_language_config(language).base_image`
- [ ] **SANDBOX-BUG-1** — Replace blocking `subprocess.run` with `asyncio.create_subprocess_exec` in sandbox
- [ ] **INFRA-ISSUE-3** — Add `depends_on` with health checks to docker-compose

### P2 — Quality, reliability, and completeness

- [ ] **KG-ISSUE-1** — Create `graph/js_parser.py` and `graph/java_parser.py`
- [ ] **KG-ISSUE-2** — Add `store_requirement()` to `knowledge_graph.py`; call from PM agent after PRD generation
- [ ] **KG-ISSUE-3** — Call `store_error_fix()` from reflexion agent on successful fix; call `store_pattern()` from architect
- [ ] **VCS-BUG-1** — Integrate `GitManager` into `_engineer_node`: init repo on first generation, commit on each completion
- [ ] **API-BUG-1** — Fix resume endpoint to restore correct project status from checkpoint
- [ ] **API-BUG-2** — Connect WebSocket broadcasts to agent execution events via Redis pub/sub
- [ ] **AUTH-BUG-1** — Fix master key mock object to return a real `APIKey` with valid `id`
- [ ] **AUTH-BUG-2** — Add `require_api_key` to `deactivate_api_key` endpoint
- [ ] **RATE** — Read `api_key.rate_limit_per_minute` in rate limiter instead of hardcoded 60
- [ ] **INFRA-ISSUE-1** — Auto-pull Ollama model in docker-compose startup
- [ ] **INFRA-ISSUE-2** — Add Alembic migration files
- [ ] **DB-BUG-1** — Add `ApprovalPolicy` validation to `ProjectCreateRequest`
- [ ] **CROSS-1** — Replace all `print()` in agents with structured `logger` calls
- [ ] **LLM-BUG-1** — Implement vLLM provider (or mark clearly as not available)
- [ ] **LLM-ISSUE-1** — Implement OpenAI provider (or provide clear error messages)
- [ ] Add `language` field to `Artifact` model — enables per-language artifact queries
- [ ] Add `AgentExecution` model — track per-agent timing, token usage, success/fail
- [ ] Add approval gate in LangGraph graph between `architect` and `engineer` nodes

### P3 — Complete the system

- [ ] **TESTS** — Write pytest suite: unit tests for all agents, services, utils; integration tests for API; E2E tests for full pipeline
- [ ] **VS Code Extension** — Build TypeScript extension (WebSocket, phantom tree, streaming, dashboard)
- [ ] **AWS CDK** — Implement DevOps agent CDK generation, `cdk synth`, `cdk deploy`, health checks
- [ ] **Pause/Resume** — Implement LangGraph `MemorySaver` checkpointing for true graph pause/resume
- [ ] **Monitoring** — Add Prometheus metrics, structured JSON logging with correlation IDs
- [ ] **Approval gate** — Wire `ApprovalRequest` creation and checking into orchestrator flow
- [ ] **Cost estimation** — Implement `_estimate_monthly_cost()` with actual logic
- [ ] **OpenAI/Anthropic providers** — Full implementation for production fallback

---

*Audit based on direct source review of all files in `src/foundry/` including:*  
*`main.py`, `orchestrator.py`, `config.py`, `database.py`, `redis_client.py`*  
*`agents/` (all 6 agents + base)*  
*`api/schemas.py`*  
*`graph/` (neo4j_client, code_parser, ingestion)*  
*`llm/` (base, ollama_provider, vllm_provider, factory)*  
*`middleware/` (auth, rate_limit, security)*  
*`models/` (project, artifact, approval, api_key, base)*  
*`sandbox/` (environment, error_analysis)*  
*`services/` (knowledge_graph, git_service, sandbox_service, agent_control, project_service)*  
*`testing/` (test_generator, quality_gates)*  
*`tools/knowledge_graph_tools.py`*  
*`utils/` (language_config, language_guards)*  
*`vcs/git_manager.py`*  
*`tasks.md`, `design.md`, `requirements.md`, `COMPLETE_REQUIREMENTS.md`*
