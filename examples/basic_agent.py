"""Basic agent usage example.

Shows how to use individual agents directly.

Usage:
    ANTHROPIC_API_KEY=your-key python examples/basic_agent.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.base import AgentConfig
from src.agents.planning_agent import PlanningAgent
from src.logging_config import configure_logging


async def main() -> None:
    configure_logging(level="INFO", environment="development")

    print("=== Planning Agent Example ===\n")

    agent = PlanningAgent(
        AgentConfig(
            name="planning",
            model="claude-haiku-4-5-20251001",
            temperature=0.1,
            max_tokens=2048,
        )
    )

    result = await agent.execute({
        "user_request": "Research the top 5 CRM software companies and write a comparison report",
        "context": {"industry": "CRM", "audience": "B2B decision makers"},
    })

    print("Execution Plan:")
    for task in result.get("tasks", []):
        print(f"  [{task['id']}] {task['task']} → {task['agent_type']}")
        if task.get("dependencies"):
            print(f"         depends on: {task['dependencies']}")

    meta = result.get("_meta", {})
    print(f"\nTokens used: {meta.get('tokens_used', 0)}")
    print(f"Cost USD:    ${meta.get('cost_usd', 0):.6f}")
    print(f"Latency:     {meta.get('latency_ms', 0):.1f}ms")


if __name__ == "__main__":
    asyncio.run(main())
