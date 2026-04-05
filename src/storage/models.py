"""SQLAlchemy ORM models for persistent storage."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all ORM models."""


class RequestModel(Base):
    """Persistent storage of execution requests."""

    __tablename__ = "requests"

    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_request = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="pending", index=True)
    result_json = Column(JSONB)
    total_tokens = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime)

    agent_executions = relationship("AgentExecutionModel", back_populates="request")


class AgentExecutionModel(Base):
    """Persistent record of individual agent executions."""

    __tablename__ = "agent_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(UUID(as_uuid=True), ForeignKey("requests.request_id"))
    agent_type = Column(String(50), nullable=False)
    task_id = Column(String(100))
    status = Column(String(50), nullable=False)
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Float, default=0.0)
    error = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    request = relationship("RequestModel", back_populates="agent_executions")


def create_engine(dsn: str):
    """Create async SQLAlchemy engine."""
    return create_async_engine(dsn, echo=False, pool_size=20, max_overflow=10)


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Create async session factory."""
    return async_sessionmaker(engine, expire_on_commit=False)
