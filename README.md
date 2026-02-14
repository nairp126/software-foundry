# Autonomous Software Foundry

Multi-agent ecosystem that automates the complete software development lifecycle from natural language requirements to deployed production applications.

## Features

- **Multi-Agent Orchestration**: LangGraph-based coordination of specialized agents
- **Persistent Project Memory**: Neo4j knowledge graph for semantic code understanding
- **Execution Feedback Loops**: Reflexion engine for automatic error detection and correction
- **Autonomous Cloud Deployment**: AWS CDK-based infrastructure provisioning
- **Human-in-the-Loop Controls**: Granular approval workflows at critical decision points

## Architecture

The system uses a hierarchical multi-agent architecture with specialized agents:

- **Product Manager Agent**: Requirements analysis and PRD generation
- **Architect Agent**: System design and technology stack selection
- **Engineering Agent**: Code generation and implementation
- **DevOps Agent**: Cloud infrastructure and deployment automation
- **Code Review Agent**: Quality analysis and security scanning
- **Reflexion Engine**: Self-healing error correction system

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- PostgreSQL 16+
- Redis 7+
- Neo4j 5.16+
- **LLM Inference** (choose one):
  - **Ollama** (recommended for Windows/development): 8GB+ VRAM or CPU
  - **vLLM** (Linux/production): NVIDIA GPU with 12-24GB VRAM, CUDA 11.8+

## Quick Start

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

**Alternative (Linux/WSL2):** For production or larger models, see [docs/VLLM_SETUP.md](docs/VLLM_SETUP.md) for vLLM setup.

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

## Development Setup

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

## Project Structure

```
autonomous-software-foundry/
├── src/foundry/           # Application source code
│   ├── agents/            # Specialized agent implementations
│   ├── models/            # Database models
│   ├── api/               # API endpoints
│   ├── config.py          # Configuration management
│   ├── database.py        # Database setup
│   ├── redis_client.py    # Redis client
│   └── main.py            # FastAPI application
├── tests/                 # Test suite
├── alembic/               # Database migrations
├── docker-compose.yml     # Docker services configuration
├── Dockerfile             # Application container
├── pyproject.toml         # Python project configuration
└── README.md              # This file
```

## Configuration

Key environment variables:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `NEO4J_URI`: Neo4j connection URI
- `OPENAI_API_KEY`: OpenAI API key for LLM access
- `ANTHROPIC_API_KEY`: Anthropic API key for Claude models

See `.env.example` for complete configuration options.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

[License information to be added]

## Support

For issues and questions, please open an issue on GitHub.
