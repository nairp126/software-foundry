# Autonomous Software Foundry

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)
![LangGraph](https://img.shields.io/badge/LangGraph-Agentic-orange)
![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-black)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Multi-agent ecosystem that automates the complete software development lifecycle from natural language requirements to deployed production applications.

## ✨ Features

- **Multi-Agent Orchestration**: LangGraph-based coordination of specialized agents
- **Persistent Project Memory**: Neo4j knowledge graph for semantic code understanding
- **Execution Feedback Loops**: Reflexion engine for automatic error detection and correction
- **Autonomous Cloud Deployment**: AWS CDK-based infrastructure provisioning
- **Human-in-the-Loop Controls**: Granular approval workflows at critical decision points

## 🏗️ Architecture

The system uses a hierarchical multi-agent architecture orchestrated by LangGraph. For a deep dive into the state machine and system design, please see the [**Architecture Documentation**](docs/ARCHITECTURE.md).

### Specialized Agents:

- **Product Manager Agent**: Requirements analysis and PRD generation
- **Architect Agent**: System design and technology stack selection
- **Engineering Agent**: Code generation and implementation
- **Code Review Agent**: Quality analysis and security scanning
- **DevOps Agent**: Cloud infrastructure and deployment automation
- **Reflexion Engine**: Self-healing error correction system

## 📋 Prerequisites

- Python 3.11+
- Docker and Docker Compose
- PostgreSQL 16+
- Redis 7+
- Neo4j 5.16+
- **LLM Inference**:
  - **Ollama** (recommended): 8GB+ VRAM or CPU

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone <repository-url>
cd autonomous-software-foundry
```

### 2. Set up Ollama with Qwen models

This project uses **Qwen2.5-Coder models** served via **Ollama** for local, Windows-compatible inference.

**Install Ollama:**
- Windows: Download from https://ollama.com/download/windows
- macOS: `brew install ollama`
- Linux: `curl -fsSL https://ollama.com/install.sh | sh`

**Pull Qwen model:**
```bash
# Qwen2.5-Coder 7B (recommended for development)
ollama pull qwen2.5-coder:7b

# Verify installation
ollama list
```

Ollama runs automatically on `http://localhost:11434`

See [docs/OLLAMA_SETUP.md](docs/OLLAMA_SETUP.md) for detailed setup instructions and model options.

### 3. Set up environment variables

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Start services with Docker Compose

```bash
docker-compose up -d
```

This will start:
- PostgreSQL database (port 5432)
- Redis cache (port 6379)
- Neo4j graph database (ports 7474, 7687)
- FastAPI application (port 8000)
- Celery worker

### 5. Run database migrations

```bash
docker-compose exec api alembic upgrade head
```

### 6. Access the application

- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474
- Ollama API: http://localhost:11434

## 🛠️ Development Setup

### Install dependencies

```bash
pip install -r requirements-dev.txt
```

### Run tests

```bash
pytest tests/ -v --cov=src/foundry
```

### Run linting

```bash
ruff check src tests
black src tests
```

### Run type checking

```bash
mypy src
```

## 📚 Documentation Index

We maintain comprehensive documentation for all system components in the `docs/` directory:

| Component | Description |
| :--- | :--- |
| [**Architecture & Design**](docs/ARCHITECTURE.md) | LangGraph state machine flow, agent interactions, and DB design |
| [**Codebase Map**](docs/CODEBASE_MAP.md) | Structured walkthrough of the project repository |
| [**Local Setup (Ollama)**](docs/OLLAMA_SETUP.md) | Guide to running Qwen models locally |
| [**Reflexion Engine**](docs/REFLEXION_ENGINE.md) | Details on the execute-analyze-fix self-healing loop |
| [**Project Lifecycle**](docs/PROJECT_LIFECYCLE.md) | How projects are created, managed, and archived |
| [**Testing & QA**](docs/TESTING_QA.md) | Automated testing guidelines and quality gates |
| [**Agent Orchestration**](docs/AGENT_ORCHESTRATION_API.md) | API reference for the LangGraph orchestrator |
| [**Approval Workflow**](docs/APPROVAL_WORKFLOW.md) | Human-in-the-loop review processes |
| [**Authentication**](docs/API_AUTHENTICATION_GUIDE.md) | Securing FastAPI endpoints |
| [**Git Integration**](docs/GIT_INTEGRATION.md) | Automated version control workflows |

## ⚙️ Configuration

Key environment variables to run the Foundry locally:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `NEO4J_URI`: Neo4j connection URI
- `DEFAULT_LLM_PROVIDER`: Set to `ollama`
- `OLLAMA_BASE_URL`: Full URL to your local Ollama instance (default: `http://localhost:11434`)
- `OLLAMA_MODEL_NAME`: e.g., `qwen2.5-coder:7b`

*(Optional Commercial Providers)*
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key

See `.env.example` and [**SETUP.md**](SETUP.md) for complete configuration options.

## 🤝 Contributing

We welcome contributions! Please review our [**Contributing Guide**](CONTRIBUTING.md) before submitting pull requests.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run formatting and tests (`make format`, `make lint`, `make typecheck`)
5. Submit a pull request

## 📄 License

[License information to be added]

## 💬 Support

For issues and questions, please open an issue on GitHub.
