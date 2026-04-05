"""Research Agent for agent-inference-stack.

Gathers and synthesizes information by:
1. Generating targeted search queries
2. Executing parallel searches
3. Synthesizing findings using LLM
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import structlog

from src.agents.base import AgentConfig, BaseAgent
from src.agents.prompts.research import (
    QUERY_GENERATION_TEMPLATE,
    RESEARCH_SYSTEM_PROMPT,
    SYNTHESIS_TEMPLATE,
)
from src.agents.tools.search import SearchResult, get_search_tool

logger = structlog.get_logger(__name__)


class ResearchAgent(BaseAgent):
    """Agent that researches topics using search and LLM synthesis.

    Example:
        agent = ResearchAgent()
        result = await agent.execute({
            "task": "Find top 5 competitors of Salesforce",
            "context": {}
        })
        # Returns: {"summary": "...", "key_findings": [...], "sources": [...]}
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="research",
                model="claude-haiku-4-5-20251001",
                temperature=0.3,
                max_tokens=2048,
            )
        super().__init__(config)
        self._search_tool = get_search_tool()

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Research a topic and return synthesized findings.

        Args:
            input_data: Dict with keys:
                - task (str): Research task description
                - context (dict): Optional additional context
                - max_results (int): Max results per query (default 5)

        Returns:
            Dict with summary, key_findings, sources, confidence, gaps.
        """
        task = input_data.get("task", "")
        context = input_data.get("context", {})
        max_results = input_data.get("max_results", 5)

        if not task:
            raise ValueError("task is required for ResearchAgent")

        self._log.info("research_started", task_preview=task[:100])

        # Step 1: Generate search queries
        queries = await self._generate_queries(task, context)
        self._log.info("queries_generated", count=len(queries))

        # Step 2: Execute searches in parallel
        all_results: list[SearchResult] = []
        search_tasks = [
            self._search_tool.search(query, max_results)
            for query in queries
        ]
        results_lists = await asyncio.gather(*search_tasks, return_exceptions=True)

        for result_list in results_lists:
            if isinstance(result_list, list):
                all_results.extend(result_list)
            else:
                self._log.warning("search_failed", error=str(result_list))

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique_results: list[SearchResult] = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_results.append(r)

        self._log.info(
            "searches_completed",
            total_results=len(all_results),
            unique_results=len(unique_results),
        )

        # Step 3: Synthesize findings
        findings = await self._synthesize_findings(task, unique_results)
        self._log.info("research_completed", confidence=findings.get("confidence"))

        return findings

    async def _generate_queries(self, task: str, context: dict[str, Any]) -> list[str]:
        """Generate targeted search queries for the research task."""
        prompt = QUERY_GENERATION_TEMPLATE.format(
            task=task,
            context=json.dumps(context) if context else "None",
        )
        response = await self._call_llm(prompt=prompt, system_prompt=RESEARCH_SYSTEM_PROMPT)

        # Parse JSON response
        cleaned = re.sub(r"```(?:json)?\n?", "", response).strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                queries = data.get("queries", [task])
                return [str(q) for q in queries[:4]]  # Max 4 queries
            except json.JSONDecodeError:
                pass
        # Fallback: use task as single query
        return [task]

    async def _synthesize_findings(
        self,
        task: str,
        results: list[SearchResult],
    ) -> dict[str, Any]:
        """Synthesize search results into structured findings."""
        if not results:
            return {
                "summary": f"No search results found for: {task}",
                "key_findings": [],
                "sources": [],
                "confidence": "low",
                "gaps": ["No search results available"],
            }

        # Format results for the prompt
        results_text = "\n\n".join(
            f"[{i+1}] {r.title}\nURL: {r.url}\n{r.snippet}"
            for i, r in enumerate(results[:15])  # Limit to 15 results
        )

        prompt = SYNTHESIS_TEMPLATE.format(task=task, search_results=results_text)
        response = await self._call_llm(
            prompt=prompt,
            system_prompt=RESEARCH_SYSTEM_PROMPT,
            max_tokens=2048,
        )

        cleaned = re.sub(r"```(?:json)?\n?", "", response).strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # Fallback: return raw text as summary
        return {
            "summary": response[:1000],
            "key_findings": [],
            "sources": [{"title": r.title, "url": r.url} for r in results[:5]],
            "confidence": "medium",
            "gaps": [],
        }
