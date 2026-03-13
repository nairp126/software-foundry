# Autonomous Software Foundry - Complete Setup Guide

This comprehensive guide will walk you through setting up, running, and testing the Autonomous Software Foundry project from scratch. Whether you're a new user, evaluating the project for a demo, or contributing to development, this guide has you covered.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (5 Minutes)](#quick-start-5-minutes)
3. [Detailed Setup](#detailed-setup)
4. [Running the Application](#running-the-application)
5. [Testing the Project](#testing-the-project)
6. [Demo Walkthrough](#demo-walkthrough)
7. [Development Workflow](#development-workflow)
8. [Troubleshooting](#troubleshooting)
9. [Advanced Configuration](#advanced-configuration)

---

## Prerequisites

### Required Software

- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **Docker Desktop** - [Download](https://www.docker.com/products/docker-desktop/)
- **Git** - [Download](https://git-scm.com/downloads/)

### Hardware Requirements

**Minimum (for testing/demo):**
- 8GB RAM
- 20GB free disk space
- 4 CPU cores

**Recommended (for development):**
- 16GB+ RAM
- 50GB+ free disk space
- 8+ CPU cores
- GPU with 8GB+ VRAM (for Ollama with Qwen models)

### Operating System Support

- ✅ Linux (Ubuntu 20.04+, Debian 11+)
- ✅ macOS (12.0+)
- ✅ Windows 10/11 (with WSL2 for best experience)

---

## Quick Start (5 Minutes)

Get the project running quickly for a demo or evaluation:

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/autonomous-software-foundry.git
cd autonomous-software-foundry
```

### Step 2: Start Infrastructure with Docker

```bash
# Start PostgreSQL, Redis, and Neo4j
docker-compose up -d postgres redis neo4j

# Wait for services to be healthy (30-60 seconds)
docker-compose ps
```

### Step 3: Create Environment File

```bash
cp .env.example .env
```

### Step 4: Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt
```

### Step 5: Run Database Migrations

```bash
alembic upgrade head
```

### Step 6: Start the Application

```bash
uvicorn src.foundry.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 7: Verify Installation

Open your browser and visit:
- **API Root**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

You should see:
```json
{
  "name": "autonomous-software-foundry",
  "version": "0.3.0",
  "status": "running"
}
```

🎉 **Success!** The application is now running. Skip to [Demo Walkthrough](#demo-walkthrough) to try it out.

---

## Detailed Setup

For a complete understanding of each component and configuration option:

### 1. System Preparation

#### Linux (Ubuntu/Debian)

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Log out and back in for group changes to take effect
```

#### macOS

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.11
brew install python@3.11

# Install Docker Desktop from https://www.docker.com/products/docker-desktop/
```

#### Windows (with WSL2)

```powershell
# Install WSL2
wsl --install

# Install Ubuntu from Microsoft Store
# Then follow Linux instructions inside WSL2
```

### 2. Clone and Navigate to Project

```bash
git clone https://github.com/your-org/autonomous-software-foundry.git
cd autonomous-software-foundry

# Verify project structure
ls -la
```

### 3. Python Environment Setup

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate     # Windows

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install all dependencies
pip install -r requirements-dev.txt

# Verify installation
pip list | grep fastapi
```

### 4. Docker Infrastructure Setup

#### Start All Services

```bash
# Start all infrastructure services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f
```

#### Service Details

| Service | Port | Purpose | Health Check |
|---------|------|---------|--------------|
| PostgreSQL | 5432 | Main database | `docker-compose exec postgres pg_isready` |
| Redis | 6379 | Cache & message broker | `docker-compose exec redis redis-cli ping` |
| Neo4j | 7474, 7687 | Knowledge graph | http://localhost:7474 |

#### Verify Services

```bash
# PostgreSQL
docker-compose exec postgres psql -U foundry_user -d foundry_db -c "SELECT version();"

# Redis
docker-compose exec redis redis-cli ping
# Expected output: PONG

# Neo4j (visit in browser)
# http://localhost:7474
# Username: neo4j
# Password: neo4j_password
```

### 5. Environment Configuration

Create and configure your `.env` file:

```bash
cp .env.example .env
```

Edit `.env` with your preferred text editor:

```bash
# Application Settings
APP_NAME=autonomous-software-foundry
APP_VERSION=0.3.0
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Database Configuration
DATABASE_URL=postgresql://foundry_user:foundry_password@localhost:5432/foundry_db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j_password

# LLM Provider Configuration (Ollama - Primary)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_NAME=qwen2.5-coder:7b
DEFAULT_LLM_PROVIDER=ollama

# Alternative: vLLM (requires Linux/WSL2)
# VLLM_BASE_URL=http://localhost:8001/v1
# VLLM_API_KEY=EMPTY
# VLLM_MODEL_NAME=Qwen/Qwen2.5-Coder-32B-Instruct
# DEFAULT_LLM_PROVIDER=vllm

# Optional: Commercial LLM Providers
# OPENAI_API_KEY=your_openai_key_here
# ANTHROPIC_API_KEY=your_anthropic_key_here

# AWS Configuration (optional, for deployment)
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=your_account_id_here

# Security
SECRET_KEY=change_this_to_a_random_secret_key_in_production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# Monitoring
ENABLE_METRICS=true
ENABLE_TRACING=false
```

**Generate a secure SECRET_KEY:**

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 6. LLM Provider Setup (Choose One)

#### Option A: Ollama (Recommended for Development)

**Advantages:** Easy setup, Windows/macOS/Linux compatible, lower resource requirements

```bash
# Install Ollama
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# macOS
brew install ollama

# Windows - Download from https://ollama.com/download

# Start Ollama service
ollama serve

# Pull Qwen model (in a new terminal)
ollama pull qwen2.5-coder:7b

# Test the model
ollama run qwen2.5-coder:7b "Write a hello world in Python"
```

See [docs/OLLAMA_SETUP.md](docs/OLLAMA_SETUP.md) for detailed instructions.

#### Option B: vLLM (For Production/Linux)

**Advantages:** Better performance, larger models, production-ready

```bash
# Install vLLM (Linux only, or WSL2 on Windows)
pip install vllm

# Start vLLM server
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-Coder-32B-Instruct \
  --host 0.0.0.0 \
  --port 8001 \
  --dtype auto \
  --max-model-len 8192

# Update .env
# DEFAULT_LLM_PROVIDER=vllm
```

See [docs/VLLM_SETUP.md](docs/VLLM_SETUP.md) for detailed instructions.

#### Option C: Commercial APIs (OpenAI/Anthropic)

```bash
# Add to .env
OPENAI_API_KEY=sk-your-key-here
DEFAULT_LLM_PROVIDER=openai

# OR
ANTHROPIC_API_KEY=sk-ant-your-key-here
DEFAULT_LLM_PROVIDER=anthropic
```

### 7. Database Initialization

```bash
# Run migrations to create all tables
alembic upgrade head

# Verify tables were created
docker-compose exec postgres psql -U foundry_user -d foundry_db -c "\dt"

# Expected tables:
# - projects
# - artifacts
# - approval_requests
# - api_keys
# - alembic_version
```

### 8. Validate Setup

Run the validation script to ensure everything is configured correctly:

```bash
python scripts/validate_setup.py
```

Expected output:
```
✓ Python version: 3.11.x
✓ Docker is running
✓ PostgreSQL is accessible
✓ Redis is accessible
✓ Neo4j is accessible
✓ All required files present
✓ Environment variables configured
✓ Database migrations up to date
✓ All checks passed! Project setup is complete.
```

---

## Running the Application

### Development Mode (with auto-reload)

```bash
# Activate virtual environment
source venv/bin/activate

# Start the application
uvicorn src.foundry.main:app --reload --host 0.0.0.0 --port 8000

# Application will be available at:
# - API: http://localhost:8000
# - Docs: http://localhost:8000/docs
# - ReDoc: http://localhost:8000/redoc
```

### Production Mode (with Gunicorn)

```bash
gunicorn src.foundry.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### Docker Mode (complete stack)

```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f api

# Stop all services
docker-compose down
```

### Background Workers (Celery)

In a separate terminal:

```bash
# Activate virtual environment
source venv/bin/activate

# Start Celery worker
celery -A src.foundry.celery_app worker --loglevel=info

# Start Celery beat (for scheduled tasks)
celery -A src.foundry.celery_app beat --loglevel=info
```

---

## Testing the Project

### Run All Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests with coverage
pytest tests/ -v --cov=src/foundry --cov-report=html --cov-report=term

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Run Specific Test Suites

```bash
# API Authentication tests
pytest tests/test_api_authentication.py -v

# Agent Orchestration tests
pytest tests/test_agent_orchestration_api.py -v

# Approval Workflow tests
pytest tests/test_approval_service.py -v
pytest tests/test_approval_workflow_integration.py -v

# Reflexion Engine tests
pytest tests/test_reflexion.py -v
pytest tests/test_sandbox.py -v
pytest tests/test_error_analysis.py -v

# Security tests
pytest tests/test_rate_limiting.py -v
pytest tests/test_security_headers.py -v

# Property-based tests
pytest tests/test_testing_properties.py -v
pytest tests/test_engineer_properties.py -v
```

### Run Tests by Category

```bash
# Unit tests only
pytest tests/ -v -m "not integration"

# Integration tests only
pytest tests/ -v -m integration

# Fast tests only (skip slow tests)
pytest tests/ -v -m "not slow"
```

### Test with Different Python Versions

```bash
# Using tox (if configured)
tox

# Or manually with different Python versions
python3.11 -m pytest tests/
python3.12 -m pytest tests/
```

### Performance Testing

```bash
# Run with profiling
pytest tests/ --profile

# Run with benchmarks
pytest tests/ --benchmark-only
```

### Generate Test Reports

```bash
# JUnit XML report (for CI/CD)
pytest tests/ --junitxml=test-results.xml

# HTML report
pytest tests/ --html=test-report.html --self-contained-html
```

---

## Demo Walkthrough

### Demo 1: Create an API Key

```bash
# Create an API key
curl -X POST http://localhost:8000/api-keys \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Demo API Key",
    "expires_in_days": 30,
    "rate_limit_per_minute": 100
  }'

# Save the returned key (it will only be shown once!)
# Example response:
# {
#   "id": "123e4567-e89b-12d3-a456-426614174000",
#   "name": "Demo API Key",
#   "key": "asf_AbCdEfGhIjKlMnOpQrStUvWxYz123456",
#   "key_prefix": "asf_AbCd",
#   "expires_at": "2024-02-17T10:00:00Z",
#   "rate_limit_per_minute": 100,
#   "created_at": "2024-01-17T10:00:00Z"
# }

# Set your API key as an environment variable
export API_KEY="asf_AbCdEfGhIjKlMnOpQrStUvWxYz123456"
```

### Demo 2: Create a Project

```bash
# Create a new project
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "name": "Todo App",
    "description": "A simple todo application",
    "requirements": "Build a REST API for managing todo items with CRUD operations"
  }'

# Save the project ID from the response
export PROJECT_ID="<project-id-from-response>"
```

### Demo 3: Monitor Project Status

```bash
# Get project details
curl -X GET http://localhost:8000/projects/$PROJECT_ID \
  -H "X-API-Key: $API_KEY"

# Get agent execution status
curl -X GET http://localhost:8000/projects/$PROJECT_ID/agent/status \
  -H "X-API-Key: $API_KEY"

# List all projects
curl -X GET http://localhost:8000/projects \
  -H "X-API-Key: $API_KEY"
```

### Demo 4: Agent Control

```bash
# Pause agent execution
curl -X POST http://localhost:8000/projects/$PROJECT_ID/agent/pause \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "reason": "Need to review architecture"
  }'

# Resume agent execution
curl -X POST http://localhost:8000/projects/$PROJECT_ID/agent/resume \
  -H "X-API-Key: $API_KEY"

# Cancel agent execution
curl -X POST http://localhost:8000/projects/$PROJECT_ID/agent/cancel \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "rollback": true
  }'
```

### Demo 5: Approval Workflow

```bash
# Get approval status
curl -X GET http://localhost:8000/projects/$PROJECT_ID/approval \
  -H "X-API-Key: $API_KEY"

# Approve a pending request
curl -X POST http://localhost:8000/projects/$PROJECT_ID/approve \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "comment": "Architecture looks good, proceed with implementation"
  }'

# Reject a pending request
curl -X POST http://localhost:8000/projects/$PROJECT_ID/reject \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "comment": "Please revise the database schema"
  }'
```

### Demo 6: WebSocket Real-time Updates

Create a simple HTML file to test WebSocket:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Project Status Monitor</title>
</head>
<body>
    <h1>Project Status Monitor</h1>
    <div id="status"></div>
    <script>
        const projectId = 'YOUR_PROJECT_ID_HERE';
        const ws = new WebSocket(`ws://localhost:8000/ws/projects/${projectId}`);
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            document.getElementById('status').innerHTML = `
                <p>Status: ${data.status}</p>
                <p>Updated: ${data.updated_at}</p>
            `;
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    </script>
</body>
</html>
```

### Demo 7: Run Example Scripts

```bash
# Approval workflow demo
python examples/approval_workflow_demo.py

# Project lifecycle demo
python examples/project_lifecycle_demo.py

# Reflexion engine demo
python examples/reflexion_demo.py

# Architect organization demo
python examples/architect_organization_demo.py

# Git integration demo
python examples/git_integration_demo.py

# Testing demo
python examples/testing_demo.py
```

---

## Development Workflow

### Code Quality Tools

#### Formatting with Black

```bash
# Format all Python files
black src tests

# Check formatting without making changes
black --check src tests

# Format specific file
black src/foundry/main.py
```

#### Linting with Ruff

```bash
# Lint all files
ruff check src tests

# Auto-fix issues
ruff check --fix src tests

# Check specific file
ruff check src/foundry/main.py
```

#### Type Checking with mypy

```bash
# Type check all files
mypy src

# Type check with strict mode
mypy --strict src

# Type check specific file
mypy src/foundry/main.py
```

#### Import Sorting with isort

```bash
# Sort imports
isort src tests

# Check import sorting
isort --check-only src tests
```

### Pre-commit Hooks

Install pre-commit hooks to automatically check code before commits:

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Update hooks to latest versions
pre-commit autoupdate
```

### Database Management

#### Create a New Migration

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add new table"

# Create empty migration
alembic revision -m "Custom migration"

# Edit the generated migration file in alembic/versions/
```

#### Apply Migrations

```bash
# Upgrade to latest
alembic upgrade head

# Upgrade to specific revision
alembic upgrade <revision_id>

# Downgrade one revision
alembic downgrade -1

# Show current revision
alembic current

# Show migration history
alembic history
```

#### Database Utilities

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U foundry_user -d foundry_db

# Backup database
docker-compose exec postgres pg_dump -U foundry_user foundry_db > backup.sql

# Restore database
docker-compose exec -T postgres psql -U foundry_user -d foundry_db < backup.sql

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d postgres
alembic upgrade head
```

### Redis Management

```bash
# Connect to Redis CLI
docker-compose exec redis redis-cli

# Common Redis commands:
# PING - Test connection
# KEYS * - List all keys
# GET key - Get value
# DEL key - Delete key
# FLUSHALL - Clear all data (WARNING: deletes everything)

# Monitor Redis commands in real-time
docker-compose exec redis redis-cli MONITOR
```

### Neo4j Management

```bash
# Access Neo4j browser
# Open http://localhost:7474 in your browser
# Username: neo4j
# Password: neo4j_password

# Run Cypher queries
# MATCH (n) RETURN n LIMIT 25
# MATCH (n) DETACH DELETE n  (WARNING: deletes all nodes)
```

### Docker Management

```bash
# View running containers
docker-compose ps

# View logs for all services
docker-compose logs -f

# View logs for specific service
docker-compose logs -f api

# Restart a service
docker-compose restart api

# Rebuild a service
docker-compose up -d --build api

# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v

# Remove unused Docker resources
docker system prune -a
```

### Makefile Commands

The project includes a Makefile with common commands:

```bash
# Install dependencies
make install

# Run tests
make test

# Run tests with coverage
make test-cov

# Format code
make format

# Lint code
make lint

# Type check
make typecheck

# Run all quality checks
make check

# Start services
make up

# Stop services
make down

# View logs
make logs

# Database migrations
make migrate

# Create new migration
make migration MSG="Add new table"

# Clean up
make clean
```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: Port Already in Use

**Error:** `Address already in use` or `Port 8000 is already allocated`

**Solution:**
```bash
# Find process using the port
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows

# Or change the port in .env or command
uvicorn src.foundry.main:app --port 8001
```

#### Issue: Database Connection Failed

**Error:** `could not connect to server: Connection refused`

**Solution:**
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Restart PostgreSQL
docker-compose restart postgres

# Check logs
docker-compose logs postgres

# Verify connection string in .env
# DATABASE_URL=postgresql://foundry_user:foundry_password@localhost:5432/foundry_db
```

#### Issue: Redis Connection Failed

**Error:** `Error connecting to Redis`

**Solution:**
```bash
# Check if Redis is running
docker-compose ps redis

# Restart Redis
docker-compose restart redis

# Test connection
docker-compose exec redis redis-cli ping

# Verify REDIS_URL in .env
```

#### Issue: Docker Daemon Not Running

**Error:** `Cannot connect to the Docker daemon`

**Solution:**
```bash
# Start Docker Desktop (GUI application)
# Or start Docker service
sudo systemctl start docker  # Linux
```

#### Issue: Permission Denied (Docker)

**Error:** `permission denied while trying to connect to the Docker daemon socket`

**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker

# Verify
docker ps
```

#### Issue: Module Not Found

**Error:** `ModuleNotFoundError: No module named 'foundry'`

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements-dev.txt

# Install package in editable mode
pip install -e .

# Verify Python path
python -c "import sys; print(sys.path)"
```

#### Issue: Alembic Migration Failed

**Error:** `Target database is not up to date`

**Solution:**
```bash
# Check current revision
alembic current

# Show migration history
alembic history

# Downgrade to previous revision
alembic downgrade -1

# Upgrade to head
alembic upgrade head

# If stuck, stamp the database
alembic stamp head
```

#### Issue: Ollama Model Not Found

**Error:** `model 'qwen2.5-coder:7b' not found`

**Solution:**
```bash
# Pull the model
ollama pull qwen2.5-coder:7b

# List available models
ollama list

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

#### Issue: Tests Failing

**Error:** Various test failures

**Solution:**
```bash
# Ensure test database is clean
docker-compose down -v
docker-compose up -d postgres redis
alembic upgrade head

# Clear pytest cache
rm -rf .pytest_cache
rm -rf __pycache__

# Run tests with verbose output
pytest tests/ -v -s

# Run specific failing test
pytest tests/test_specific.py::test_function -v -s
```

#### Issue: High Memory Usage

**Solution:**
```bash
# Check Docker resource usage
docker stats

# Limit Docker resources in Docker Desktop settings
# Or in docker-compose.yml:
# services:
#   api:
#     mem_limit: 2g
#     cpus: 2

# Restart services
docker-compose restart
```

#### Issue: Slow Performance

**Solution:**
```bash
# Check system resources
htop  # Linux/macOS
# Task Manager on Windows

# Optimize Docker
docker system prune -a

# Use smaller LLM model
# In .env: OLLAMA_MODEL_NAME=qwen2.5-coder:1.5b

# Reduce worker count
# In .env: API_WORKERS=2
```

---

## Advanced Configuration

### Environment-Specific Configuration

#### Development Environment

```bash
# .env.development
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
API_WORKERS=1
ENABLE_METRICS=true
ENABLE_TRACING=true
```

#### Staging Environment

```bash
# .env.staging
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO
API_WORKERS=4
ENABLE_METRICS=true
ENABLE_TRACING=true
```

#### Production Environment

```bash
# .env.production
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
API_WORKERS=8
ENABLE_METRICS=true
ENABLE_TRACING=true

# Use production-grade secrets
SECRET_KEY=<generate-secure-key>
DATABASE_URL=postgresql://user:pass@prod-db:5432/foundry_db
REDIS_URL=redis://prod-redis:6379/0

# Use production LLM provider
DEFAULT_LLM_PROVIDER=vllm
VLLM_BASE_URL=http://llm-server:8001/v1
```

### Load Environment Files

```bash
# Load specific environment
export ENV=development
uvicorn src.foundry.main:app --env-file .env.$ENV

# Or use direnv (auto-load on directory change)
echo "dotenv .env.development" > .envrc
direnv allow
```

### Custom Configuration

Create a custom configuration file:

```python
# config/custom.py
from foundry.config import Settings

class CustomSettings(Settings):
    # Add custom settings
    custom_feature_enabled: bool = True
    custom_api_endpoint: str = "https://api.example.com"
    
    class Config:
        env_prefix = "CUSTOM_"
```

### Database Connection Pooling

Optimize database connections for production:

```python
# In .env
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600
```

### Redis Configuration

Advanced Redis settings:

```bash
# In .env
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5
REDIS_RETRY_ON_TIMEOUT=true
REDIS_HEALTH_CHECK_INTERVAL=30
```

### Celery Configuration

Configure background task processing:

```bash
# In .env
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_ACCEPT_CONTENT=["json"]
CELERY_TIMEZONE=UTC
CELERY_ENABLE_UTC=true
CELERY_TASK_TRACK_STARTED=true
CELERY_TASK_TIME_LIMIT=3600
CELERY_WORKER_PREFETCH_MULTIPLIER=4
```

### Logging Configuration

Configure structured logging:

```python
# config/logging.py
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "logs/foundry.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"],
    },
}
```

### Security Hardening

#### Enable HTTPS

```bash
# Generate self-signed certificate for development
openssl req -x509 -newkey rsa:4096 -nodes \
  -out cert.pem -keyout key.pem -days 365

# Run with HTTPS
uvicorn src.foundry.main:app \
  --ssl-keyfile=key.pem \
  --ssl-certfile=cert.pem
```

#### Configure CORS

```python
# In src/foundry/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific domains
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=3600,
)
```

#### Rate Limiting Configuration

```bash
# In .env
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_ENABLED=true
```

### Monitoring and Observability

#### Prometheus Metrics

```bash
# Install prometheus client
pip install prometheus-client

# Metrics endpoint will be available at /metrics
curl http://localhost:8000/metrics
```

#### Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed health check (includes dependencies)
curl http://localhost:8000/health/detailed
```

#### Application Logs

```bash
# View application logs
tail -f logs/foundry.log

# View with jq for JSON logs
tail -f logs/foundry.log | jq .

# Filter by log level
tail -f logs/foundry.log | jq 'select(.levelname=="ERROR")'
```

### Performance Optimization

#### Enable Caching

```python
# In .env
ENABLE_CACHING=true
CACHE_TTL=3600
CACHE_MAX_SIZE=1000
```

#### Database Query Optimization

```python
# Use connection pooling
# Enable query logging in development
DATABASE_ECHO=true  # Development only

# Use read replicas for read-heavy workloads
DATABASE_READ_URL=postgresql://user:pass@read-replica:5432/foundry_db
```

#### Async Workers

```bash
# Use more workers for production
gunicorn src.foundry.main:app \
  --workers 8 \
  --worker-class uvicorn.workers.UvicornWorker \
  --worker-connections 1000 \
  --max-requests 10000 \
  --max-requests-jitter 1000 \
  --timeout 120
```

---

## Project Structure

```
autonomous-software-foundry/
├── .github/
│   └── workflows/           # CI/CD pipelines
│       ├── ci.yml          # Continuous integration
│       └── deploy.yml      # Deployment workflow
├── .kiro/
│   └── specs/              # Project specifications
│       └── autonomous-software-foundry/
│           ├── requirements.md
│           ├── design.md
│           └── tasks.md
├── alembic/                # Database migrations
│   ├── versions/           # Migration files
│   ├── env.py             # Migration environment
│   └── script.py.mako     # Migration template
├── docs/                   # Documentation
│   ├── OLLAMA_SETUP.md
│   ├── VLLM_SETUP.md
│   ├── WINDOWS_SETUP.md
│   ├── LLM_CONFIGURATION.md
│   ├── API_AUTHENTICATION_GUIDE.md
│   ├── AGENT_ORCHESTRATION_API.md
│   ├── APPROVAL_WORKFLOW.md
│   ├── PROJECT_LIFECYCLE.md
│   ├── GIT_INTEGRATION.md
│   ├── TESTING_QA.md
│   └── REFLEXION_ENGINE.md
├── examples/               # Example scripts
│   ├── approval_workflow_demo.py
│   ├── project_lifecycle_demo.py
│   ├── reflexion_demo.py
│   └── ...
├── scripts/                # Utility scripts
│   └── validate_setup.py
├── src/foundry/           # Application source code
│   ├── agents/            # Agent implementations
│   │   ├── architect.py
│   │   └── reflexion.py
│   ├── api/               # API schemas
│   │   └── schemas.py
│   ├── llm/               # LLM providers
│   │   ├── base.py
│   │   ├── ollama_provider.py
│   │   ├── vllm_provider.py
│   │   └── factory.py
│   ├── middleware/        # Middleware components
│   │   ├── auth.py
│   │   ├── rate_limit.py
│   │   └── security.py
│   ├── models/            # Database models
│   │   ├── project.py
│   │   ├── artifact.py
│   │   ├── approval.py
│   │   └── api_key.py
│   ├── sandbox/           # Code execution sandbox
│   │   ├── environment.py
│   │   └── error_analysis.py
│   ├── services/          # Business logic services
│   │   ├── project_service.py
│   │   ├── approval_service.py
│   │   └── agent_control.py
│   ├── tasks/             # Background tasks
│   │   └── approval_tasks.py
│   ├── testing/           # Testing utilities
│   │   ├── test_generator.py
│   │   └── quality_gates.py
│   ├── config.py          # Configuration management
│   ├── database.py        # Database setup
│   ├── redis_client.py    # Redis client
│   ├── celery_app.py      # Celery configuration
│   ├── orchestrator.py    # Agent orchestrator
│   └── main.py            # FastAPI application
├── tests/                 # Test suite
│   ├── conftest.py        # Pytest configuration
│   ├── test_api_authentication.py
│   ├── test_agent_orchestration_api.py
│   ├── test_approval_service.py
│   ├── test_reflexion.py
│   └── ...
├── .dockerignore          # Docker ignore file
├── .env.example           # Example environment file
├── .gitignore             # Git ignore file
├── .pre-commit-config.yaml # Pre-commit hooks
├── alembic.ini            # Alembic configuration
├── CHANGELOG.md           # Project changelog
├── docker-compose.yml     # Docker services
├── Dockerfile             # Docker image
├── Makefile               # Common commands
├── pyproject.toml         # Project metadata
├── README.md              # Project overview
├── requirements-dev.txt   # Development dependencies
├── requirements.txt       # Production dependencies
└── SETUP.md               # This file
```

---

## Additional Resources

### Documentation

- **API Documentation**: http://localhost:8000/docs (when running)
- **ReDoc**: http://localhost:8000/redoc (when running)
- **Project Specs**: `.kiro/specs/autonomous-software-foundry/`
- **Feature Docs**: `docs/` directory

### External Resources

- **FastAPI**: https://fastapi.tiangolo.com/
- **SQLAlchemy**: https://docs.sqlalchemy.org/
- **Alembic**: https://alembic.sqlalchemy.org/
- **Redis**: https://redis.io/documentation
- **Neo4j**: https://neo4j.com/docs/
- **Docker**: https://docs.docker.com/
- **Ollama**: https://ollama.com/
- **vLLM**: https://docs.vllm.ai/
- **Qwen Models**: https://huggingface.co/Qwen

### Community and Support

- **GitHub Issues**: Report bugs and request features
- **Discussions**: Ask questions and share ideas
- **Contributing**: See CONTRIBUTING.md (if available)
- **Code of Conduct**: See CODE_OF_CONDUCT.md (if available)

---

## Next Steps

Now that you have the project set up, here are some suggested next steps:

### For Evaluation/Demo Users

1. ✅ Complete the [Quick Start](#quick-start-5-minutes)
2. ✅ Run through the [Demo Walkthrough](#demo-walkthrough)
3. ✅ Explore the API documentation at http://localhost:8000/docs
4. ✅ Try the example scripts in `examples/`
5. ✅ Review the feature documentation in `docs/`

### For Developers

1. ✅ Complete the [Detailed Setup](#detailed-setup)
2. ✅ Set up your [Development Workflow](#development-workflow)
3. ✅ Run the [Test Suite](#testing-the-project)
4. ✅ Review the project specifications in `.kiro/specs/`
5. ✅ Check the [CHANGELOG.md](CHANGELOG.md) for recent updates
6. ✅ Read the implementation task list in `.kiro/specs/autonomous-software-foundry/tasks.md`

### For Contributors

1. ✅ Fork the repository
2. ✅ Set up pre-commit hooks
3. ✅ Create a feature branch
4. ✅ Write tests for your changes
5. ✅ Submit a pull request

---

## Frequently Asked Questions

### Q: Do I need a GPU to run this project?

**A:** No, but it's recommended for better performance with local LLM models. You can:
- Use CPU-only mode (slower but works)
- Use smaller models (qwen2.5-coder:1.5b)
- Use commercial APIs (OpenAI, Anthropic)

### Q: How much does it cost to run?

**A:** 
- **Local (Ollama/vLLM)**: ~$35-110/month in electricity
- **OpenAI GPT-4**: ~$500-2000/month
- **Anthropic Claude**: ~$300-1500/month
- **Infrastructure (Docker)**: Free for development

### Q: Can I use this in production?

**A:** The current version (0.3.0) includes production-ready components:
- ✅ API authentication and security
- ✅ Rate limiting
- ✅ Database migrations
- ✅ Error handling
- ⚠️ Agent orchestration is still in development
- ⚠️ Full end-to-end workflows not yet complete

### Q: What's the difference between Ollama and vLLM?

**A:**
- **Ollama**: Easier setup, cross-platform, good for development
- **vLLM**: Better performance, Linux-only, better for production

See [docs/LLM_CONFIGURATION.md](docs/LLM_CONFIGURATION.md) for detailed comparison.

### Q: How do I contribute?

**A:** 
1. Check open issues on GitHub
2. Review the task list in `.kiro/specs/autonomous-software-foundry/tasks.md`
3. Fork the repository and create a feature branch
4. Write tests for your changes
5. Submit a pull request

### Q: Where can I get help?

**A:**
- Check this SETUP.md file
- Review documentation in `docs/`
- Check [Troubleshooting](#troubleshooting) section
- Open an issue on GitHub
- Join community discussions

---

## Summary

You now have a complete guide to setting up, running, and testing the Autonomous Software Foundry project. Whether you're evaluating the project, running a demo, or contributing to development, this guide should help you get started quickly.

**Quick Reference:**

```bash
# Start infrastructure
docker-compose up -d postgres redis neo4j

# Activate virtual environment
source venv/bin/activate

# Run migrations
alembic upgrade head

# Start application
uvicorn src.foundry.main:app --reload

# Run tests
pytest tests/ -v --cov=src/foundry

# Access API
open http://localhost:8000/docs
```

**Happy coding! 🚀**

---

*Last updated: 2024-01-17*
*Version: 0.3.0*
