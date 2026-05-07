"""Application configuration management."""

from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="autonomous-software-foundry")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    generated_projects_path: str = Field(default="generated_projects")
    host_generated_projects_path: Optional[str] = Field(default=None) # Path on the actual host (for Docker-in-Docker)
    cors_origins: List[str] = Field(
        default=[
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]
    )

    @field_validator("generated_projects_path")
    @classmethod
    def validate_projects_path(cls, v: str) -> str:
        """Ensure generated_projects_path exists."""
        if not os.path.exists(v):
            os.makedirs(v, exist_ok=True)
        return v

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_workers: int = Field(default=4)

    # Database
    database_url: str = Field(
        default="postgresql://foundry_user:foundry_password@localhost:5432/foundry_db"
    )
    database_pool_size: int = Field(default=20)
    database_max_overflow: int = Field(default=10)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_max_connections: int = Field(default=50)

    # Celery
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="neo4j_password")

    # LLM Providers
    openai_api_key: Optional[str] = Field(default=None)
    anthropic_api_key: Optional[str] = Field(default=None)
    
    # Ollama Configuration (for local Qwen models - PRIMARY)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model_name: str = Field(default="qwen2.5-coder:1.5b")
    
    # vLLM Configuration (for local Qwen models - ALTERNATIVE)
    vllm_base_url: str = Field(default="http://localhost:8001/v1")
    vllm_api_key: str = Field(default="EMPTY")
    vllm_model_name: str = Field(default="Qwen/Qwen2.5-Coder-32B-Instruct")
    
    # Default LLM Provider
    default_llm_provider: str = Field(default="ollama")  # ollama, vllm, openai, anthropic

    # AWS
    aws_region: str = Field(default="us-east-1")
    aws_account_id: Optional[str] = Field(default=None)

    # Security
    secret_key: str = Field(default="change_this_secret_key_in_production")
    foundry_api_key: Optional[str] = Field(default="foundry_master_key_2024") # Static master key
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_minutes: int = Field(default=60)

    # Monitoring
    enable_metrics: bool = Field(default=True)
    enable_tracing: bool = Field(default=False)

    # Patent Readiness / A/B Testing
    enable_kg: bool = Field(default=True)

    # VRAM Budget Manager
    vram_context_overhead_factor: float = Field(default=1.25)
    max_concurrent_agents: int = Field(default=4)
    vram_acquire_timeout_seconds: float = Field(default=120.0)
    enable_kv_calibration: bool = Field(default=True)
    vram_recovery_patience: int = Field(default=5)

    # Sandbox Limits
    sandbox_memory_limit: str = Field(default="512m")
    sandbox_cpu_limit: float = Field(default=1.0)

    # Provider Failover
    enable_provider_failover: bool = Field(default=False)
    fallback_llm_provider: str = Field(default="vllm")
    provider_failover_retry_delay: float = Field(default=2.0)


settings = Settings()
