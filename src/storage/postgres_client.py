"""PostgreSQL async client with connection pooling."""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class PostgreSQLClient:
    """Async PostgreSQL client using asyncpg with connection pooling.

    Example:
        client = PostgreSQLClient(dsn="postgresql://user:pass@host/db")
        await client.connect()
        rows = await client.execute("SELECT * FROM requests WHERE id=$1", (request_id,))
    """

    def __init__(self, dsn: str, pool_size: int = 20) -> None:
        self._dsn = dsn
        self._pool_size = pool_size
        self._pool = None

    async def connect(self) -> None:
        """Initialize connection pool."""
        try:
            import asyncpg
            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=2,
                max_size=self._pool_size,
            )
            logger.info("postgres_connected")
        except Exception as e:
            logger.warning("postgres_connection_failed", error=str(e))

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("postgres_disconnected")

    async def execute(
        self, query: str, params: tuple | None = None
    ) -> list[dict[str, Any]]:
        """Execute a query and return results as list of dicts."""
        if not self._pool:
            logger.warning("postgres_not_connected")
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *(params or ()))
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error("postgres_query_error", query=query[:100], error=str(e))
            raise

    async def execute_one(
        self, query: str, params: tuple | None = None
    ) -> dict[str, Any] | None:
        """Execute a query and return a single row."""
        results = await self.execute(query, params)
        return results[0] if results else None

    async def execute_many(
        self, query: str, params_list: list[tuple]
    ) -> None:
        """Execute a query with multiple parameter sets."""
        if not self._pool:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(query, params_list)

    async def create_tables(self) -> None:
        """Initialize database schema."""
        if not self._pool:
            return
        schema_sql = """
        CREATE TABLE IF NOT EXISTS requests (
            request_id UUID PRIMARY KEY,
            user_request TEXT NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            result_json JSONB,
            total_tokens INTEGER DEFAULT 0,
            total_cost_usd FLOAT DEFAULT 0.0,
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS agent_executions (
            id SERIAL PRIMARY KEY,
            request_id UUID REFERENCES requests(request_id),
            agent_type VARCHAR(50) NOT NULL,
            task_id VARCHAR(100),
            status VARCHAR(50) NOT NULL,
            tokens_used INTEGER DEFAULT 0,
            cost_usd FLOAT DEFAULT 0.0,
            latency_ms FLOAT DEFAULT 0.0,
            error TEXT,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ
        );

        CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
        CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests(created_at);
        CREATE INDEX IF NOT EXISTS idx_agent_executions_request_id ON agent_executions(request_id);
        """
        async with self._pool.acquire() as conn:
            await conn.execute(schema_sql)
        logger.info("database_tables_created")
