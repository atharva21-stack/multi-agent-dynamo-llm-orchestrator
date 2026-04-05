"""Full system demo showing the complete multi-agent pipeline.

Usage:
    ANTHROPIC_API_KEY=your-key python examples/full_system_demo.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.logging_config import configure_logging
from src.orchestration.orchestrator import Orchestrator


async def main() -> None:
    configure_logging(level="INFO", environment="development")

    print("=" * 60)
    print("agent-inference-stack: Full Pipeline Demo")
    print("=" * 60)

    orchestrator = Orchestrator()
    await orchestrator.initialize()

    user_request = (
        "Research the top 5 enterprise CRM software companies, "
        "including their market share, pricing, and key differentiators"
    )
    print(f"\nUser Request:\n  {user_request}\n")
    print("Processing... (this may take 30-60 seconds)\n")

    result = await orchestrator.process_request(user_request)

    print("=" * 60)
    print(f"Status:       {result['status']}")
    print(f"Total Tokens: {result['total_tokens']:,}")
    print(f"Total Cost:   ${result['total_cost_usd']:.6f}")
    if result.get("duration_ms"):
        print(f"Duration:     {result['duration_ms']/1000:.1f}s")

    if result.get("validation_result"):
        vr = result["validation_result"]
        print(f"\nValidation Score: {vr.get('score', 0):.2f}")
        print(f"Valid: {vr.get('is_valid', False)}")

    print("\nAgent Execution Summary:")
    for record in result.get("agent_results", []):
        print(f"  [{record['agent_type']:12}] {record['status']:10} "
              f"tokens={record['tokens_used']:4} "
              f"cost=${record['cost_usd']:.6f}")

    if result.get("error"):
        print(f"\nError: {result['error']}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
