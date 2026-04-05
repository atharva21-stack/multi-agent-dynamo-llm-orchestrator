"""End-to-end tests for the full multi-agent pipeline.

These tests exercise the complete pipeline from request submission
to validated output, using mocked LLM calls.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.orchestration.orchestrator import Orchestrator
from src.agents.base import AgentConfig


@pytest.mark.e2e
class TestFullPipeline:
    """End-to-end pipeline tests with mocked LLMs."""

    PLANNING_RESPONSE = '''
    {
      "tasks": [
        {"id": "t1", "task": "Research the topic", "agent_type": "research", "dependencies": [], "priority": 1},
        {"id": "t2", "task": "Analyze and synthesize findings", "agent_type": "execution", "dependencies": ["t1"], "priority": 2}
      ],
      "estimated_tokens": 3000,
      "rationale": "Research then synthesize approach"
    }
    '''

    RESEARCH_QUERY_RESPONSE = '{"queries": ["test query 1", "test query 2"]}'
    RESEARCH_SYNTHESIS_RESPONSE = '{"summary": "Key findings summary", "key_findings": ["Finding 1", "Finding 2"], "sources": [{"title": "Source 1", "url": "https://example.com"}], "confidence": "high", "gaps": []}'
    EXECUTION_RESPONSE = '{"result": "Analysis complete: Found 5 key trends", "steps_taken": ["Analyzed data", "Wrote report"], "tools_used": [], "confidence": "high", "notes": ""}'
    VALIDATION_RESPONSE = '{"is_valid": true, "score": 0.88, "issues": [], "recommendations": [], "summary": "Output is comprehensive and addresses the request"}'

    @pytest.mark.asyncio
    async def test_complete_pipeline_success(self):
        """Test that the full pipeline completes with mocked LLMs."""
        orch = Orchestrator()
        await orch.initialize()

        all_responses = [
            self.PLANNING_RESPONSE,
            self.RESEARCH_QUERY_RESPONSE,
            self.RESEARCH_SYNTHESIS_RESPONSE,
            self.EXECUTION_RESPONSE,
            self.VALIDATION_RESPONSE,
        ]
        call_idx = 0

        async def mock_llm_call(self_agent, prompt, system_prompt="", **kwargs):
            nonlocal call_idx
            resp = all_responses[min(call_idx, len(all_responses) - 1)]
            call_idx += 1
            return resp

        from src.agents.base import BaseAgent
        from src.agents.tools.search import MockSearchTool

        with patch.object(BaseAgent, "_call_llm", mock_llm_call):
            result = await orch.process_request(
                "Research the top 5 trends in enterprise software for 2024"
            )

        assert result["status"] == "completed"
        assert result["total_tokens"] > 0
        assert result["result"] is not None

    @pytest.mark.asyncio
    async def test_pipeline_tracks_costs(self):
        """Verify cost tracking works across the pipeline."""
        orch = Orchestrator()
        await orch.initialize()

        all_responses = [
            self.PLANNING_RESPONSE,
            self.RESEARCH_QUERY_RESPONSE,
            self.RESEARCH_SYNTHESIS_RESPONSE,
            self.EXECUTION_RESPONSE,
            self.VALIDATION_RESPONSE,
        ]
        call_idx = 0

        async def mock_llm(self_agent, prompt, system_prompt="", **kwargs):
            nonlocal call_idx
            # Track tokens
            self_agent._track_tokens(100, 50)
            resp = all_responses[min(call_idx, len(all_responses) - 1)]
            call_idx += 1
            return resp

        from src.agents.base import BaseAgent
        with patch.object(BaseAgent, "_call_llm", mock_llm):
            result = await orch.process_request("Analyze software trends")

        assert result["total_cost_usd"] > 0
