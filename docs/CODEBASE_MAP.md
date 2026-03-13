# Codebase Map: Autonomous Software Foundry

## Directory Structure
```text
autonomous-software-foundry/
├── src/foundry/           # Main application code
│   ├── agents/            # LangGraph specialized agents
│   │   ├── base.py        # Base agent class and protocols
│   │   ├── product_manager.py
│   │   ├── architect.py
│   │   ├── engineer.py
│   │   ├── code_review.py
│   │   ├── devops.py
│   │   └── reflexion.py   # Self-healing engine
│   ├── api/               # FastAPI endpoints and schemas
│   ├── llm/               # LLM Provider abstraction (Ollama)
│   ├── models/            # SQLAlchemy database models
│   ├── sandbox/           # Secure code execution environment
│   ├── services/          # Core business logic (projects, git)
│   ├── testing/           # QA and testing utilities
│   ├── orchestrator.py    # LangGraph state machine orchestrator
│   └── main.py            # FastAPI application entrypoint
├── docs/                  # Documentation and guides
├── tests/                 # Pytest test suite examples
├── alembic/               # Database migrations
└── generated_projects/    # Output directory for agent-generated code
```

## Key Components

- **Agents (`src/foundry/agents/`)**: Specialized AI workers that perform distinct software development roles.
- **LLM Engine (`src/foundry/llm/`)**: Provides a unified interface to Ollama and Qwen models for code generation and analysis.
- **Orchestrator (`src/foundry/orchestrator.py`)**: Uses LangGraph to manage the workflow, passing state and messages between the specialized agents.
- **Services (`src/foundry/services/`)**: Abstractions for interacting with the database, Git repositories, and other external systems.
- **Sandbox (`src/foundry/sandbox/`)**: The secure, Dockerized environment used by the Reflexion Engine to execute and test generated code safely.
