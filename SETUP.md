# Setup Guide

This guide will help you get the Autonomous Software Foundry up and running.

## Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose
- Git

## Quick Start

### 1. Verify Project Structure

Run the validation script to ensure all files are in place:

```bash
python scripts/validate_setup.py
```

You should see: `✓ All checks passed! Project setup is complete.`

### 2. Create Environment File

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` and update the following values:
- `OPENAI_API_KEY` - Your OpenAI API key
- `ANTHROPIC_API_KEY` - Your Anthropic API key
- `AWS_ACCOUNT_ID` - Your AWS account ID (for CDK deployment)
- `SECRET_KEY` - Generate a secure random key

### 3. Start Infrastructure Services

Start PostgreSQL, Redis, and Neo4j using Docker Compose:

```bash
docker-compose up -d postgres redis neo4j
```

Wait for services to be healthy (check with `docker-compose ps`).

### 4. Install Python Dependencies

```bash
pip install -r requirements-dev.txt
```

### 5. Run Database Migrations

```bash
alembic upgrade head
```

### 6. Start the Application

#### Option A: Run locally
```bash
uvicorn foundry.main:app --reload
```

#### Option B: Run with Docker
```bash
docker-compose up -d
```

### 7. Verify Installation

Visit http://localhost:8000 - you should see:
```json
{
  "name": "autonomous-software-foundry",
  "version": "0.1.0",
  "status": "running"
}
```

API documentation is available at http://localhost:8000/docs

## Development Workflow

### Running Tests

```bash
pytest tests/ -v --cov=src/foundry
```

### Code Formatting

```bash
black src tests
ruff check --fix src tests
```

### Type Checking

```bash
mypy src
```

### Pre-commit Hooks

Install pre-commit hooks to automatically check code before commits:

```bash
pre-commit install
```

## Docker Services

The `docker-compose.yml` file defines the following services:

- **postgres** (port 5432) - PostgreSQL database
- **redis** (port 6379) - Redis cache and message broker
- **neo4j** (ports 7474, 7687) - Neo4j graph database
- **api** (port 8000) - FastAPI application
- **celery-worker** - Background task worker

### Managing Services

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

## Project Structure

```
autonomous-software-foundry/
├── src/foundry/           # Application source code
│   ├── agents/            # Agent implementations (to be added)
│   ├── api/               # API endpoints (to be added)
│   ├── models/            # Database models
│   ├── config.py          # Configuration management
│   ├── database.py        # Database setup
│   ├── redis_client.py    # Redis client
│   ├── celery_app.py      # Celery configuration
│   └── main.py            # FastAPI application
├── tests/                 # Test suite
├── alembic/               # Database migrations
├── scripts/               # Utility scripts
├── .github/workflows/     # CI/CD pipelines
└── docker-compose.yml     # Docker services
```

## Next Steps

Now that the foundation is set up, you can proceed with implementing the core agents:

1. **Task 2**: Implement core agent orchestration system
2. **Task 3**: Implement Product Manager Agent
3. **Task 5**: Implement Architect Agent
4. **Task 6**: Implement Engineering Agent

Refer to `.kiro/specs/autonomous-software-foundry/tasks.md` for the complete implementation plan.

## Troubleshooting

### Database Connection Issues

If you see database connection errors:
1. Ensure PostgreSQL is running: `docker-compose ps postgres`
2. Check the DATABASE_URL in your `.env` file
3. Verify the database exists: `docker-compose exec postgres psql -U foundry_user -d foundry_db`

### Redis Connection Issues

If Redis connection fails:
1. Ensure Redis is running: `docker-compose ps redis`
2. Test connection: `docker-compose exec redis redis-cli ping`

### Port Conflicts

If ports are already in use, you can modify the port mappings in `docker-compose.yml`.

## Support

For issues and questions, refer to the main README.md or open an issue on GitHub.
