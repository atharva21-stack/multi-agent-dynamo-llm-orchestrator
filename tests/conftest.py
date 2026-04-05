"""Shared pytest fixtures for agent-inference-stack tests."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def sample_user_request() -> str:
    return "Research the top 5 CRM software companies and their market share"


@pytest.fixture
def sample_context() -> dict[str, Any]:
    return {"industry": "CRM", "focus": "enterprise", "year": 2024}


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response."""
    mock_content = MagicMock()
    mock_content.text = '{"result": "test output", "confidence": "high"}'

    mock_usage = MagicMock()
    mock_usage.input_tokens = 100
    mock_usage.output_tokens = 50

    mock_response = MagicMock()
    mock_response.content = [mock_content]
    mock_response.usage = mock_usage
    return mock_response


@pytest.fixture
def mock_planning_response():
    """Mock planning agent LLM response."""
    return '''```json
{
  "tasks": [
    {"id": "task_1", "task": "Research CRM market landscape", "agent_type": "research", "dependencies": [], "priority": 1},
    {"id": "task_2", "task": "Identify top 5 competitors", "agent_type": "research", "dependencies": ["task_1"], "priority": 2},
    {"id": "task_3", "task": "Synthesize findings into report", "agent_type": "execution", "dependencies": ["task_2"], "priority": 3}
  ],
  "estimated_tokens": 5000,
  "rationale": "Sequential research then synthesis approach"
}
```'''


@pytest.fixture
def mock_search_results():
    """Mock search results for research agent tests."""
    from src.agents.tools.search import SearchResult
    return [
        SearchResult(title="Salesforce CRM Leader", url="https://example.com/1", snippet="Salesforce holds 20% market share"),
        SearchResult(title="HubSpot Growth", url="https://example.com/2", snippet="HubSpot sees 30% YoY growth"),
        SearchResult(title="Microsoft Dynamics", url="https://example.com/3", snippet="Dynamics leads enterprise segment"),
    ]


@pytest.fixture
def agent_config():
    """Default agent config for tests."""
    from src.agents.base import AgentConfig
    return AgentConfig(
        name="test_agent",
        model="claude-haiku-4-5-20251001",
        temperature=0.1,
        max_tokens=1024,
        max_retries=1,
    )


@pytest.fixture
def planning_agent_config():
    from src.agents.base import AgentConfig
    return AgentConfig(name="planning", model="claude-sonnet-4-6", temperature=0.1, max_tokens=4096)


@pytest.fixture
def mock_settings():
    """Mock application settings."""
    settings = MagicMock()
    settings.app_env = "test"
    settings.log_level = "DEBUG"
    settings.request_timeout_seconds = 30
    settings.max_concurrent_agents = 5
    settings.max_retries = 1
    settings.anthropic_api_key = "test-key"
    settings.redis_host = "localhost"
    settings.redis_port = 6379
    settings.postgres_host = "localhost"
    settings.postgres_port = 5432
    return settings
