# Changelog

All notable changes to the Autonomous Software Foundry project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Foundation & LLM Integration (2024-01-15)

#### Project Foundation
- FastAPI backend with async support
- PostgreSQL database with SQLAlchemy ORM and Alembic migrations
- Redis for caching and session management
- Docker Compose development environment with health checks
- Celery for background task processing
- Git repository with conventional commits
- GitHub Actions CI/CD pipeline
- Pre-commit hooks for code quality
- Comprehensive test suite with pytest
- Project validation script
- Makefile with common development commands

#### LLM Integration (vLLM + Qwen)
- **vLLM Provider Implementation**
  - OpenAI-compatible API integration
  - Streaming support for real-time code generation
  - Automatic reconnection and error handling
  - Token usage tracking and cost monitoring
  
- **Qwen Model Configuration**
  - Qwen2.5-Coder-32B-Instruct as default model (24GB VRAM)
  - Qwen2.5-Coder-14B-Instruct for fast iteration (12GB VRAM)
  - Configurable per-agent model selection
  - Temperature and parameter customization
  
- **Provider Architecture**
  - Abstract base class for LLM providers
  - Factory pattern for easy provider instantiation
  - Fallback chain support (vLLM → OpenAI → Anthropic)
  - Extensible design for future providers
  
- **Configuration System**
  - Environment-based configuration with Pydantic
  - Support for multiple LLM providers
  - Cost tracking and usage analytics
  - Model selection per agent type

#### Documentation
- **Setup Guides**
  - README.md with quick start instructions
  - SETUP.md with detailed setup workflow
  - VLLM_SETUP.md with comprehensive vLLM configuration
  - LLM_CONFIGURATION.md with provider comparison
  - QWEN_INTEGRATION_SUMMARY.md with implementation details
  
- **Specification Documents**
  - Updated requirements.md with vLLM implementation status
  - Updated design.md with technology stack details
  - Updated tasks.md with completed LLM integration tasks
  
- **Cost Analysis**
  - vLLM: ~$110/month (electricity)
  - OpenAI GPT-4: ~$500-2000/month
  - Anthropic Claude: ~$300-1500/month
  - ROI: vLLM pays for itself in 0.5-0.7 months

#### Testing
- Integration test script for vLLM provider
- Configuration validation tests
- Health check endpoints
- Database session fixtures

#### Infrastructure
- Docker Compose with PostgreSQL, Redis, Neo4j
- Service health checks and automatic restarts
- Volume persistence for data
- Network isolation and security

### Changed
- Updated all spec documents to reflect vLLM + Qwen as primary LLM provider
- Modified default LLM provider from commercial APIs to local vLLM
- Updated cost models and hardware requirements in documentation

### Technical Details

**Dependencies Added:**
- vLLM (via external server)
- httpx for async HTTP requests
- asyncpg for PostgreSQL async support
- pydantic-settings for configuration management

**Project Structure:**
```
autonomous-software-foundry/
├── src/foundry/
│   ├── llm/                    # LLM provider implementations
│   │   ├── base.py            # Abstract base class
│   │   ├── vllm_provider.py   # vLLM implementation
│   │   ├── factory.py         # Provider factory
│   │   └── test.py            # Integration tests
│   ├── agents/                # Agent implementations (future)
│   ├── api/                   # API endpoints (future)
│   ├── models/                # Database models
│   ├── config.py              # Configuration management
│   ├── database.py            # Database setup
│   ├── redis_client.py        # Redis client
│   ├── celery_app.py          # Celery configuration
│   └── main.py                # FastAPI application
├── docs/                      # Documentation
│   ├── VLLM_SETUP.md
│   ├── LLM_CONFIGURATION.md
│   └── QWEN_INTEGRATION_SUMMARY.md
├── tests/                     # Test suite
├── alembic/                   # Database migrations
├── scripts/                   # Utility scripts
└── .github/workflows/         # CI/CD pipelines
```

**Git History:**
```
1e2ef6a docs: update spec documents to reflect vLLM + Qwen implementation
defe1e1 docs: add comprehensive Qwen+vLLM integration summary
72ddf9a docs: add comprehensive LLM configuration guide and update README
513239f feat: add vLLM integration with Qwen models for local inference
a52148d docs: add comprehensive setup guide
7ab96f6 feat: add project setup validation script
d484ec5 feat: add API structure, Makefile, tests, and Docker ignore
4673462 feat: initial project foundation setup with FastAPI, PostgreSQL, Redis, and Docker
```

## [0.1.0] - Foundation Release

### Summary
Complete project foundation with FastAPI backend, PostgreSQL database, Redis caching, Docker development environment, and vLLM + Qwen LLM integration. Ready for agent implementation (Task 2).

### Next Steps
1. Implement core agent orchestration system (Task 2)
2. Implement Product Manager Agent (Task 3)
3. Implement Architect Agent (Task 5)
4. Implement Engineering Agent (Task 6)
5. Implement Reflexion Engine (Task 7)

---

## Version History

- **0.1.0** - Foundation + LLM Integration (Current)
- **0.2.0** - Agent Orchestration (Planned)
- **0.3.0** - Core Agents (Planned)
- **0.4.0** - Reflexion Engine (Planned)
- **0.5.0** - MVP Release (Planned)
