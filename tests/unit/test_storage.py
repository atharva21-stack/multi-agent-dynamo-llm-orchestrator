"""Unit tests for storage layer."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.storage.redis_client import RedisClient


@pytest.mark.unit
class TestRedisClient:
    """Tests for Redis client."""

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_connected(self):
        client = RedisClient()
        result = await client.get("some-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_returns_false_when_not_connected(self):
        client = RedisClient()
        result = await client.set("key", {"data": "value"})
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_connected(self):
        client = RedisClient()
        result = await client.delete("key")
        assert result is False

    @pytest.mark.asyncio
    async def test_ping_returns_false_when_not_connected(self):
        client = RedisClient()
        result = await client.ping()
        assert result is False

    @pytest.mark.asyncio
    async def test_get_deserializes_json(self):
        client = RedisClient()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value='{"key": "value", "count": 42}')
        client._client = mock_redis

        result = await client.get("test-key")
        assert result == {"key": "value", "count": 42}

    @pytest.mark.asyncio
    async def test_set_serializes_to_json(self):
        client = RedisClient()
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        client._client = mock_redis

        result = await client.set("test-key", {"data": 123})
        assert result is True
        mock_redis.set.assert_called_once()
