"""Configuration loader for agent-inference-stack.

Loads settings from YAML files with environment-specific overrides
and environment variable support.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


CONFIG_DIR = Path(__file__).parent.parent / "config"


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file, returning empty dict if not found."""
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dicts, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> dict[str, Any]:
    """Load configuration with environment-specific overrides.

    Returns:
        Merged configuration dictionary.
    """
    env = os.getenv("APP_ENV", "development")
    base = _load_yaml(CONFIG_DIR / "settings.yaml")
    override = _load_yaml(CONFIG_DIR / f"settings.{env}.yaml")
    return _deep_merge(base, override)


class AgentConfig(BaseModel):
    """Configuration for a single agent."""

    model: str = "claude-sonnet-4-6"
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)
    timeout_seconds: int = Field(default=120, gt=0)


class AgentsConfig(BaseModel):
    """Configuration for all agents."""

    planning: AgentConfig = Field(default_factory=AgentConfig)
    research: AgentConfig = Field(default_factory=AgentConfig)
    execution: AgentConfig = Field(default_factory=AgentConfig)
    validation: AgentConfig = Field(default_factory=AgentConfig)


class RedisConfig(BaseModel):
    """Redis connection configuration."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    max_connections: int = 50
    request_ttl_seconds: int = 86400


class PostgresConfig(BaseModel):
    """PostgreSQL connection configuration."""

    host: str = "localhost"
    port: int = 5432
    database: str = "agent_inference_stack"
    user: str = "agent_user"
    password: str = ""
    pool_size: int = 20
    max_overflow: int = 10

    @property
    def dsn(self) -> str:
        """Build asyncpg DSN."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and YAML.

    Environment variables take precedence over YAML configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False
    log_level: str = "INFO"

    # AI provider API keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    default_model: str = "claude-sonnet-4-6"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "agent_inference_stack"
    postgres_user: str = "agent_user"
    postgres_password: str = ""

    # Orchestrator
    max_concurrent_agents: int = 10
    request_timeout_seconds: int = 300
    max_retries: int = 3

    # Security
    secret_key: str = "change-me-in-production"
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse allowed origins as list."""
        return [o.strip() for o in self.allowed_origins.split(",")]


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get cached application settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
