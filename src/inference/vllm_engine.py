"""vLLM inference engine integration.

Provides a unified interface for running local LLM inference via vLLM.
Falls back to Anthropic/OpenAI when vLLM is not available.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class vLLMEngine:
    """vLLM-based inference engine with paged attention and prefix caching.

    When vLLM is not installed (e.g., CPU development), this falls back
    to the Anthropic or OpenAI API for seamless local development.

    Example:
        engine = vLLMEngine(
            model_name="meta-llama/Llama-2-70b-chat-hf",
            tensor_parallel_size=4,
            gpu_memory_utilization=0.90
        )
        await engine.initialize()
        result = await engine.generate("What is the capital of France?")
        # "Paris is the capital of France."
    """

    def __init__(
        self,
        model_name: str = "meta-llama/Llama-2-70b-chat-hf",
        tensor_parallel_size: int = 1,
        gpu_memory_utilization: float = 0.90,
        max_batch_size: int = 32,
        max_sequence_length: int = 4096,
        host: str = "localhost",
        port: int = 8080,
    ) -> None:
        self.model_name = model_name
        self.tensor_parallel_size = tensor_parallel_size
        self.gpu_memory_utilization = gpu_memory_utilization
        self.max_batch_size = max_batch_size
        self.max_sequence_length = max_sequence_length
        self.host = host
        self.port = port
        self._llm = None  # vLLM LLM instance
        self._use_api_fallback = False
        self._initialized = False
        self._total_tokens = 0
        self._total_requests = 0
        self._total_latency_ms = 0.0

    async def initialize(self) -> None:
        """Initialize the vLLM engine or fall back to API.

        Attempts to import vLLM. If unavailable, configures API fallback.
        """
        try:
            # Check if vLLM server is running (HTTP mode)
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"http://{self.host}:{self.port}/health")
                if resp.status_code == 200:
                    self._use_api_fallback = False
                    self._initialized = True
                    logger.info(
                        "vllm_server_connected",
                        host=self.host,
                        port=self.port,
                        model=self.model_name,
                    )
                    return
        except Exception:
            pass

        # Fall back to Anthropic/OpenAI
        self._use_api_fallback = True
        self._initialized = True
        logger.info(
            "vllm_using_api_fallback",
            reason="vLLM server not available",
            anthropic_key_set=bool(os.getenv("ANTHROPIC_API_KEY")),
        )

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        stop: list[str] | None = None,
    ) -> str:
        """Generate a completion for a single prompt.

        Args:
            prompt: Input prompt text.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            stop: Optional stop sequences.

        Returns:
            Generated text string.
        """
        if not self._initialized:
            await self.initialize()

        start = time.perf_counter()
        self._total_requests += 1

        if self._use_api_fallback:
            result = await self._generate_via_api(prompt, max_tokens, temperature, stop)
        else:
            result = await self._generate_via_vllm_server(prompt, max_tokens, temperature, stop)

        latency_ms = (time.perf_counter() - start) * 1000
        self._total_latency_ms += latency_ms

        logger.debug(
            "inference_complete",
            latency_ms=round(latency_ms, 2),
            output_chars=len(result),
        )
        return result

    async def generate_batch(
        self,
        prompts: list[str],
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> list[str]:
        """Generate completions for multiple prompts in parallel.

        Args:
            prompts: List of input prompts.
            max_tokens: Maximum tokens per generation.
            temperature: Sampling temperature.

        Returns:
            List of generated text strings (same order as input).
        """
        if not prompts:
            return []

        logger.info("batch_inference_start", batch_size=len(prompts))

        # Batch against max_batch_size
        results: list[str] = []
        for i in range(0, len(prompts), self.max_batch_size):
            batch = prompts[i:i + self.max_batch_size]
            batch_results = await asyncio.gather(
                *[self.generate(p, max_tokens, temperature) for p in batch]
            )
            results.extend(batch_results)

        return results

    async def _generate_via_api(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        stop: list[str] | None,
    ) -> str:
        """Generate using Anthropic/OpenAI API as fallback."""
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if api_key:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=api_key)
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            self._total_tokens += response.usage.input_tokens + response.usage.output_tokens
            return text

        # Mock response for development
        return f"[vLLM Mock] Response for: {prompt[:100]}..."

    async def _generate_via_vllm_server(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        stop: list[str] | None,
    ) -> str:
        """Generate via vLLM OpenAI-compatible server."""
        import httpx
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stop": stop,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"http://{self.host}:{self.port}/v1/completions",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["text"]
            if "usage" in data:
                self._total_tokens += data["usage"]["total_tokens"]
            return text

    @property
    def avg_latency_ms(self) -> float:
        """Average inference latency in milliseconds."""
        if self._total_requests == 0:
            return 0.0
        return self._total_latency_ms / self._total_requests

    def get_metrics(self) -> dict[str, Any]:
        """Return engine performance metrics."""
        return {
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "total_latency_ms": round(self._total_latency_ms, 2),
            "model": self.model_name,
            "mode": "api_fallback" if self._use_api_fallback else "vllm",
        }
