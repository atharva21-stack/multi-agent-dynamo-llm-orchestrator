"""Unit tests for the orchestrator system."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.orchestration.orchestrator import Orchestrator
from src.orchestration.scheduler import DependencyResolver


@pytest.mark.unit
class TestDependencyResolver:
    """Tests for DAG topological sort."""

    def test_simple_linear_chain(self):
        resolver = DependencyResolver()
        from src.agents.models import Task, AgentType
        tasks = [
            Task(id="t1", task="task1", agent_type=AgentType.RESEARCH),
            Task(id="t2", task="task2", agent_type=AgentType.EXECUTION, dependencies=["t1"]),
            Task(id="t3", task="task3", agent_type=AgentType.VALIDATION, dependencies=["t2"]),
        ]
        waves = resolver.topological_sort(tasks)
        assert len(waves) == 3
        assert waves[0][0].id == "t1"
        assert waves[1][0].id == "t2"
        assert waves[2][0].id == "t3"

    def test_parallel_tasks(self):
        """Tasks with no dependencies can run in parallel."""
        resolver = DependencyResolver()
        from src.agents.models import Task, AgentType
        tasks = [
            Task(id="t1", task="task1", agent_type=AgentType.RESEARCH),
            Task(id="t2", task="task2", agent_type=AgentType.RESEARCH),
            Task(id="t3", task="task3", agent_type=AgentType.EXECUTION, dependencies=["t1", "t2"]),
        ]
        waves = resolver.topological_sort(tasks)
        assert len(waves) == 2
        assert len(waves[0]) == 2  # t1 and t2 in parallel
        assert waves[1][0].id == "t3"

    def test_single_task(self):
        resolver = DependencyResolver()
        from src.agents.models import Task, AgentType
        tasks = [Task(id="t1", task="task1", agent_type=AgentType.EXECUTION)]
        waves = resolver.topological_sort(tasks)
        assert len(waves) == 1
        assert waves[0][0].id == "t1"


@pytest.mark.unit
class TestOrchestrator:
    """Tests for Orchestrator class."""

    @pytest.mark.asyncio
    async def test_initialize(self, mock_settings):
        orch = Orchestrator(settings=mock_settings)
        await orch.initialize()
        assert orch._initialized is True

    @pytest.mark.asyncio
    async def test_get_request_state_not_found(self, mock_settings):
        orch = Orchestrator(settings=mock_settings)
        await orch.initialize()
        with pytest.raises(KeyError):
            await orch.get_request_state("nonexistent-id")

    @pytest.mark.asyncio
    async def test_submit_request_returns_id(self, mock_settings):
        orch = Orchestrator(settings=mock_settings)
        await orch.initialize()

        # Mock the pipeline so it doesn't actually call LLMs
        with patch.object(orch, "_execute_pipeline", new=AsyncMock()):
            result = await orch.submit_request("Test request")

        assert "request_id" in result
        assert result["request_id"] is not None

    @pytest.mark.asyncio
    async def test_get_metrics_empty(self, mock_settings):
        orch = Orchestrator(settings=mock_settings)
        await orch.initialize()
        metrics = await orch.get_metrics()
        assert metrics["total_requests"] == 0
        assert metrics["successful_requests"] == 0
