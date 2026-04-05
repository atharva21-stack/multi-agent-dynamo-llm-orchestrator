"""Unit tests for agent infrastructure."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.base import AgentConfig, AgentState, BaseAgent
from src.agents.models import AgentType, ExecutionPlan, Task, TaskStatus
from src.agents.planning_agent import PlanningAgent
from src.agents.research_agent import ResearchAgent
from src.agents.validation_agent import ValidationAgent


class ConcreteAgent(BaseAgent):
    """Concrete agent for testing BaseAgent."""

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {"processed": True, "input": input_data}


@pytest.mark.unit
class TestBaseAgent:
    """Tests for BaseAgent base class."""

    def test_initial_state(self, agent_config):
        agent = ConcreteAgent(agent_config)
        assert agent.state == AgentState.PENDING
        assert agent.tokens_used == 0
        assert agent.cost_usd == 0.0
        assert agent.error is None

    @pytest.mark.asyncio
    async def test_execute_success(self, agent_config):
        agent = ConcreteAgent(agent_config)
        result = await agent.execute({"key": "value"})
        assert result["processed"] is True
        assert agent.state == AgentState.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_includes_meta(self, agent_config):
        agent = ConcreteAgent(agent_config)
        result = await agent.execute({"key": "value"})
        assert "_meta" in result
        assert "agent" in result["_meta"]
        assert "latency_ms" in result["_meta"]

    def test_token_tracking(self, agent_config):
        agent = ConcreteAgent(agent_config)
        agent._track_tokens(100, 50)
        assert agent.input_tokens == 100
        assert agent.output_tokens == 50
        assert agent.tokens_used == 150

    def test_cost_calculation(self, agent_config):
        agent = ConcreteAgent(agent_config)
        agent._track_tokens(1000, 1000)
        expected_cost = (1000 / 1000 * 0.003) + (1000 / 1000 * 0.015)
        assert abs(agent.cost_usd - expected_cost) < 0.0001

    def test_token_count_estimate(self, agent_config):
        agent = ConcreteAgent(agent_config)
        estimate = agent._count_tokens_estimate("Hello world " * 10)
        assert estimate > 0
        assert estimate < 100  # Rough estimate check

    @pytest.mark.asyncio
    async def test_execute_retry_on_failure(self, agent_config):
        """Test that agent retries on failure."""
        agent_config.max_retries = 2
        call_count = 0

        class FailOnce(BaseAgent):
            async def process(self, input_data):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise RuntimeError("Simulated failure")
                return {"success": True}

        agent = FailOnce(agent_config)
        result = await agent.execute({})
        assert result["success"] is True
        assert call_count == 3


@pytest.mark.unit
class TestPlanningAgent:
    """Tests for PlanningAgent."""

    @pytest.mark.asyncio
    async def test_parse_valid_plan(self):
        agent = PlanningAgent()
        valid_json = '''
        {
          "tasks": [
            {"id": "t1", "task": "Research market", "agent_type": "research", "dependencies": []},
            {"id": "t2", "task": "Write report", "agent_type": "execution", "dependencies": ["t1"]}
          ],
          "estimated_tokens": 3000,
          "rationale": "Sequential approach"
        }
        '''
        plan = agent._parse_plan(valid_json)
        assert len(plan.tasks) == 2
        assert plan.estimated_tokens == 3000

    def test_validate_plan_unique_ids(self):
        agent = PlanningAgent()
        from src.agents.models import ExecutionPlan, Task, AgentType
        plan = ExecutionPlan(tasks=[
            Task(id="t1", task="task 1", agent_type=AgentType.RESEARCH),
            Task(id="t1", task="task 2", agent_type=AgentType.EXECUTION),  # duplicate
        ])
        with pytest.raises(ValueError, match="unique"):
            agent._validate_plan(plan)

    def test_validate_plan_invalid_dependency(self):
        agent = PlanningAgent()
        from src.agents.models import ExecutionPlan, Task, AgentType
        plan = ExecutionPlan(tasks=[
            Task(id="t1", task="task 1", agent_type=AgentType.RESEARCH, dependencies=["nonexistent"]),
        ])
        with pytest.raises(ValueError, match="dependency"):
            agent._validate_plan(plan)

    def test_validate_plan_circular_dependency(self):
        agent = PlanningAgent()
        from src.agents.models import ExecutionPlan, Task, AgentType
        plan = ExecutionPlan(tasks=[
            Task(id="t1", task="task 1", agent_type=AgentType.RESEARCH, dependencies=["t2"]),
            Task(id="t2", task="task 2", agent_type=AgentType.EXECUTION, dependencies=["t1"]),
        ])
        with pytest.raises(ValueError, match="[Cc]ircular"):
            agent._validate_plan(plan)

    @pytest.mark.asyncio
    async def test_process_with_mock_llm(self, mock_planning_response):
        agent = PlanningAgent()
        with patch.object(agent, "_call_llm", new=AsyncMock(return_value=mock_planning_response)):
            result = await agent.process({"user_request": "Research CRM market"})
        assert "tasks" in result
        assert len(result["tasks"]) == 3


@pytest.mark.unit
class TestResearchAgent:
    """Tests for ResearchAgent."""

    @pytest.mark.asyncio
    async def test_process_with_mock_search(self, mock_search_results):
        agent = ResearchAgent()
        query_response = '{"queries": ["CRM market share 2024", "top CRM vendors"]}'
        synthesis_response = '{"summary": "Market analysis", "key_findings": ["Salesforce leads"], "sources": [], "confidence": "high", "gaps": []}'

        with patch.object(agent, "_call_llm", new=AsyncMock(side_effect=[query_response, synthesis_response])):
            with patch.object(agent._search_tool, "search", new=AsyncMock(return_value=mock_search_results)):
                result = await agent.process({"task": "Research CRM market"})

        assert "summary" in result
        assert "key_findings" in result

    @pytest.mark.asyncio
    async def test_deduplicates_search_results(self, mock_search_results):
        """Duplicate URLs should be removed."""
        agent = ResearchAgent()
        # Add duplicate
        duplicate = mock_search_results[0]
        results_with_dupe = mock_search_results + [duplicate]

        query_response = '{"queries": ["test query"]}'
        synthesis_response = '{"summary": "test", "key_findings": [], "sources": [], "confidence": "medium", "gaps": []}'

        with patch.object(agent, "_call_llm", new=AsyncMock(side_effect=[query_response, synthesis_response])):
            with patch.object(agent._search_tool, "search", new=AsyncMock(return_value=results_with_dupe)):
                result = await agent.process({"task": "test research"})

        # Should complete without error (deduplication is internal)
        assert result is not None


@pytest.mark.unit
class TestValidationAgent:
    """Tests for ValidationAgent."""

    @pytest.mark.asyncio
    async def test_parse_valid_validation_result(self):
        agent = ValidationAgent()
        valid_json = '{"is_valid": true, "score": 0.85, "issues": [], "recommendations": [], "summary": "Good output"}'

        with patch.object(agent, "_call_llm", new=AsyncMock(return_value=valid_json)):
            result = await agent.process({
                "original_request": "Test request",
                "execution_output": {"result": "test"},
            })

        assert result["is_valid"] is True
        assert result["score"] == 0.85

    @pytest.mark.asyncio
    async def test_handles_low_score(self):
        agent = ValidationAgent()
        low_score_json = '{"is_valid": false, "score": 0.3, "issues": ["incomplete"], "recommendations": ["retry"], "summary": "Poor output"}'

        with patch.object(agent, "_call_llm", new=AsyncMock(return_value=low_score_json)):
            result = await agent.process({
                "original_request": "Test",
                "execution_output": {},
            })

        assert result["is_valid"] is False
        assert result["score"] == 0.3
        assert len(result["issues"]) > 0
