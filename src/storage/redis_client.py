"""Redis client with async connection pooling."""
from __future__ import annotations

import json
import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class RedisClient:
    """Async Redis client with connection pooling and error handling.

    Example:
        client = RedisClient(host="localhost", port=6379)
        await client.set("key", {"data": "value"}, ttl=3600)
        value = await client.get("key")
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: str | None = None,
        db: int = 0,
        max_connections: int = 50,
    ) -> None:
        self._host = host
        self._port = port
        self._password = password
        self._db = db
        self._max_connections = max_connections
        self._client = None

    async def connect(self) -> None:
        """Initialize Redis connection pool."""
        import redis.asyncio as aioredis
        self._client = aioredis.Redis(
            host=self._host,
            port=self._port,
            password=self._password,
            db=self._db,
            max_connections=self._max_connections,
            decode_responses=True,
        )
        await self._client.ping()
        logger.info("redis_connected", host=self._host, port=self._port)

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.aclose()
            logger.info("redis_disconnected")

    async def get(self, key: str) -> Any | None:
        """Get a value by key, deserializing JSON automatically."""
        if not self._client:
            return None
        try:
            value = await self._client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.warning("redis_get_error", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set a key-value pair, serializing to JSON."""
        if not self._client:
            return False
        try:
            serialized = json.dumps(value, default=str)
            if ttl:
                await self._client.setex(key, ttl, serialized)
            else:
                await self._client.set(key, serialized)
            return True
        except Exception as e:
            logger.warning("redis_set_error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key."""
        if not self._client:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.warning("redis_delete_error", key=key, error=str(e))
            return False

    async def hset(self, name: str, key: str, value: Any) -> bool:
        """Set a hash field."""
        if not self._client:
            return False
        try:
            await self._client.hset(name, key, json.dumps(value, default=str))
            return True
        except Exception as e:
            logger.warning("redis_hset_error", name=name, key=key, error=str(e))
            return False

    async def hget(self, name: str, key: str) -> Any | None:
        """Get a hash field."""
        if not self._client:
            return None
        try:
            value = await self._client.hget(name, key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.warning("redis_hget_error", name=name, key=key, error=str(e))
            return None

    async def ping(self) -> bool:
        """Ping Redis to check connectivity."""
        if not self._client:
            return False
        try:
            return await self._client.ping()
        except Exception:
            return False
