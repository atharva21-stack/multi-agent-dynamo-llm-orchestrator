"""Unit tests for inference engine components."""
from __future__ import annotations

import pytest

from src.inference.dynamo_optimizer import DynamoOptimizer
from src.inference.cache import InferenceCache


@pytest.mark.unit
class TestDynamoOptimizer:
    """Tests for Dynamo batch optimizer."""

    def test_empty_input(self):
        optimizer = DynamoOptimizer()
        schedule = optimizer.optimize_batch_schedule([])
        assert schedule.total_requests == 0
        assert schedule.total_batches == 0

    def test_single_request(self):
        optimizer = DynamoOptimizer()
        schedule = optimizer.optimize_batch_schedule([512])
        assert schedule.total_requests == 1
        assert schedule.total_batches == 1

    def test_batching_respects_max_batch_size(self):
        optimizer = DynamoOptimizer()
        token_counts = [100] * 20
        schedule = optimizer.optimize_batch_schedule(token_counts, max_batch_size=5)
        for batch in schedule.batches:
            assert len(batch) <= 5

    def test_all_requests_scheduled(self):
        optimizer = DynamoOptimizer()
        token_counts = [256, 512, 1024, 768, 128, 2048]
        schedule = optimizer.optimize_batch_schedule(token_counts, max_batch_size=4)
        scheduled_indices = [idx for batch in schedule.batches for idx in batch]
        assert sorted(scheduled_indices) == list(range(len(token_counts)))

    def test_cost_reduction_estimation(self):
        optimizer = DynamoOptimizer()
        token_counts = [512] * 8
        reduction = optimizer.estimate_cost_reduction(token_counts, max_batch_size=4)
        assert isinstance(reduction, float)
        assert reduction >= 0.0


@pytest.mark.unit
class TestInferenceCache:
    """Tests for inference caching."""

    @pytest.mark.asyncio
    async def test_miss_when_no_redis(self):
        cache = InferenceCache(redis_client=None)
        result = await cache.get("test prompt", model="claude-haiku-4-5-20251001")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_when_no_redis(self):
        cache = InferenceCache(redis_client=None)
        # Should not raise
        await cache.set("test prompt", "test response", model="test")

    def test_hit_rate_empty(self):
        cache = InferenceCache(redis_client=None)
        assert cache.hit_rate == 0.0

    def test_cache_key_consistent(self):
        cache = InferenceCache(redis_client=None)
        key1 = cache._make_key("hello", "model-a")
        key2 = cache._make_key("hello", "model-a")
        assert key1 == key2

    def test_cache_key_different_prompts(self):
        cache = InferenceCache(redis_client=None)
        key1 = cache._make_key("prompt one", "model-a")
        key2 = cache._make_key("prompt two", "model-a")
        assert key1 != key2
