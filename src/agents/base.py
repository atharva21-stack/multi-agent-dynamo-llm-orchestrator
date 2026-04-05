"""Base agent infrastructure for agent-inference-stack.

All agent types inherit from BaseAgent which provides:
- Lifecycle management (state tracking)
- Token counting and cost calculation
- Error handling and retry logic
- Structured logging
- LLM call abstraction
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class AgentState(str, Enum):
    """Lifecycle state of an agent execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentConfig(BaseModel):
    """Configuration for a single agent instance."""

    name: str = Field(description="Human-readable agent name")
    model: str = Field(default="claude-sonnet-4-6", description="LLM model identifier")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)
    timeout_seconds: int = Field(default=120, gt=0)
    max_retries: int = Field(default=3, ge=0)
    cost_per_1k_input_tokens: float = Field(default=0.003)
    cost_per_1k_output_tokens: float = Field(default=0.015)


class AgentException(Exception):
    """Base exception for agent errors."""

    def __init__(self, message: str, agent_name: str = "", details: dict | None = None):
        super().__init__(message)
        self.agent_name = agent_name
        self.details = details or {}


class AgentTimeoutException(AgentException):
    """Raised when an agent exceeds its timeout."""


class AgentFailedException(AgentException):
    """Raised when an agent fails after all retries."""


class BaseAgent(ABC):
    """Abstract base class for all agent types.

    Subclasses must implement the `process` method which contains
    the agent-specific logic. The `execute` method wraps `process`
    with retry logic, timing, and state management.

    Example:
        class MyAgent(BaseAgent):
            async def process(self, input_data: dict) -> dict:
                result = await self._call_llm("Do something with: " + str(input_data))
                return {"output": result}
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.state = AgentState.PENDING
        self.input_data: dict[str, Any] | None = None
        self.output_data: dict[str, Any] | None = None
        self.tokens_used: int = 0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.cost_usd: float = 0.0
        self.error: str | None = None
        self.started_at: float | None = None
        self.completed_at: float | None = None
        self._execution_id = str(uuid.uuid4())[:8]
        self._log = logger.bind(
            agent=config.name,
            model=config.model,
            execution_id=self._execution_id,
        )

    @abstractmethod
    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's core logic.

        Args:
            input_data: Task-specific input data.

        Returns:
            Agent output as a dictionary.
        """

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent with retry logic and state tracking.

        Args:
            input_data: Task-specific input data.

        Returns:
            Agent output with metadata.

        Raises:
            AgentFailedException: After all retries are exhausted.
            AgentTimeoutException: If execution exceeds timeout.
        """
        self.state = AgentState.RUNNING
        self.input_data = input_data
        self.started_at = time.perf_counter()
        self._log.info("agent_started")

        last_error: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                result = await self.process(input_data)
                self.output_data = result
                self.state = AgentState.COMPLETED
                self.completed_at = time.perf_counter()
                latency_ms = (self.completed_at - self.started_at) * 1000
                self._log.info(
                    "agent_completed",
                    latency_ms=round(latency_ms, 2),
                    tokens_used=self.tokens_used,
                    cost_usd=round(self.cost_usd, 6),
                )
                return {
                    **result,
                    "_meta": {
                        "agent": self.config.name,
                        "tokens_used": self.tokens_used,
                        "cost_usd": self.cost_usd,
                        "latency_ms": latency_ms,
                        "attempts": attempt + 1,
                    },
                }

            except AgentTimeoutException:
                raise
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    delay = 2**attempt  # exponential backoff
                    self._log.warning(
                        "agent_retry",
                        attempt=attempt + 1,
                        max_retries=self.config.max_retries,
                        error=str(e),
                        retry_in_seconds=delay,
                    )
                    import asyncio
                    await asyncio.sleep(delay)

        self.state = AgentState.FAILED
        self.error = str(last_error)
        self.completed_at = time.perf_counter()
        self._log.error(
            "agent_failed",
            error=str(last_error),
            attempts=self.config.max_retries + 1,
        )
        raise AgentFailedException(
            f"Agent {self.config.name} failed after {self.config.max_retries + 1} attempts: {last_error}",
            agent_name=self.config.name,
        )

    def _count_tokens_estimate(self, text: str) -> int:
        """Estimate token count from text (approx 4 chars per token)."""
        return len(text) // 4

    def _track_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Track token usage and compute cost."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.tokens_used += input_tokens + output_tokens
        input_cost = (input_tokens / 1000) * self.config.cost_per_1k_input_tokens
        output_cost = (output_tokens / 1000) * self.config.cost_per_1k_output_tokens
        self.cost_usd += input_cost + output_cost

    async def _call_llm(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Call the configured LLM provider.

        Args:
            prompt: User-facing prompt.
            system_prompt: Optional system instruction.
            temperature: Override temperature (uses config default if None).
            max_tokens: Override max tokens (uses config default if None).

        Returns:
            LLM response text.
        """
        import os
        temp = temperature if temperature is not None else self.config.temperature
        max_tok = max_tokens if max_tokens is not None else self.config.max_tokens

        # Estimate input tokens
        input_text = (system_prompt + prompt)
        estimated_input = self._count_tokens_estimate(input_text)

        model = self.config.model

        if model.startswith("claude"):
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
            messages = [{"role": "user", "content": prompt}]
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tok,
                "temperature": temp,
                "messages": messages,
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            response = await client.messages.create(**kwargs)
            output_text = response.content[0].text
            actual_input = response.usage.input_tokens
            actual_output = response.usage.output_tokens
            self._track_tokens(actual_input, actual_output)
            return output_text

        elif model.startswith("gpt"):
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
            msgs = []
            if system_prompt:
                msgs.append({"role": "system", "content": system_prompt})
            msgs.append({"role": "user", "content": prompt})
            response = await client.chat.completions.create(
                model=model,
                messages=msgs,
                temperature=temp,
                max_tokens=max_tok,
            )
            output_text = response.choices[0].message.content or ""
            actual_input = response.usage.prompt_tokens if response.usage else estimated_input
            actual_output = response.usage.completion_tokens if response.usage else len(output_text) // 4
            self._track_tokens(actual_input, actual_output)
            return output_text

        else:
            # Fallback: vLLM or mock
            self._log.warning("unknown_model_using_mock", model=model)
            mock_response = f"[MOCK response for model={model}] Processed: {prompt[:100]}..."
            self._track_tokens(estimated_input, len(mock_response) // 4)
            return mock_response

    @property
    def latency_ms(self) -> float:
        """Return execution latency in milliseconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return 0.0
