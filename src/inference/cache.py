"""Inference result caching with Redis backend."""
from __future__ import annotations

import hashlib
import json
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class InferenceCache:
    """Redis-backed cache for inference results.

    Caches prompt-response pairs to avoid redundant LLM calls.
    Cache keys are SHA-256 hashes of (model, prompt, params).

    Example:
        cache = InferenceCache(redis_client=redis)
        result = await cache.get("my-prompt", model="claude-haiku-4-5-20251001")
        if result is None:
            result = await llm.generate("my-prompt")
            await cache.set("my-prompt", result, model="claude-haiku-4-5-20251001", ttl=3600)
    """

    def __init__(self, redis_client=None, default_ttl: int = 3600) -> None:
        self._redis = redis_client
        self.default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def _make_key(self, prompt: str, model: str = "", **kwargs: Any) -> str:
        """Create a cache key from prompt and parameters."""
        key_data = json.dumps(
            {"prompt": prompt, "model": model, **kwargs},
            sort_keys=True,
        )
        return "inference:" + hashlib.sha256(key_data.encode()).hexdigest()[:32]

    async def get(self, prompt: str, model: str = "", **kwargs: Any) -> str | None:
        """Retrieve a cached inference result.

        Returns:
            Cached response string, or None if not cached.
        """
        if not self._redis:
            return None

        key = self._make_key(prompt, model, **kwargs)
        try:
            value = await self._redis.get(key)
            if value is not None:
                self._hits += 1
                logger.debug("inference_cache_hit", key=key[:16])
                return value if isinstance(value, str) else value.get("text")
            self._misses += 1
            return None
        except Exception as e:
            logger.warning("inference_cache_get_error", error=str(e))
            return None

    async def set(
        self,
        prompt: str,
        response: str,
        model: str = "",
        ttl: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Cache an inference result."""
        if not self._redis:
            return

        key = self._make_key(prompt, model, **kwargs)
        try:
            await self._redis.set(key, {"text": response}, ttl=ttl or self.default_ttl)
            logger.debug("inference_cache_set", key=key[:16], ttl=ttl or self.default_ttl)
        except Exception as e:
            logger.warning("inference_cache_set_error", error=str(e))

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as a fraction 0.0-1.0."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def get_metrics(self) -> dict[str, Any]:
        """Return cache performance metrics."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 4),
            "total_requests": self._hits + self._misses,
        }
