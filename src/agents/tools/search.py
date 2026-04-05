"""Search tools for the Research Agent."""
from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SearchResult:
    """A single search result."""

    title: str
    url: str
    snippet: str
    domain: str = ""
    relevance_score: float = 0.0

    def __post_init__(self) -> None:
        if not self.domain and self.url:
            try:
                from urllib.parse import urlparse
                self.domain = urlparse(self.url).netloc
            except Exception:
                self.domain = ""


class SearchTool(ABC):
    """Abstract base class for search providers."""

    @abstractmethod
    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        """Execute a search query.

        Args:
            query: Search query string.
            num_results: Maximum number of results to return.

        Returns:
            List of SearchResult objects.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for logging."""


class MockSearchTool(SearchTool):
    """Mock search tool for development/testing (no API key required)."""

    @property
    def name(self) -> str:
        return "mock_search"

    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        """Return mock search results for development."""
        await asyncio.sleep(0.1)  # Simulate network latency
        return [
            SearchResult(
                title=f"Result {i+1} for: {query[:50]}",
                url=f"https://example.com/result-{i+1}",
                snippet=f"This is a mock search result snippet for '{query}'. "
                        f"It contains relevant information about the topic. Result number {i+1}.",
                relevance_score=1.0 - (i * 0.1),
            )
            for i in range(min(num_results, 5))
        ]


class GoogleSearchTool(SearchTool):
    """Google Custom Search API integration."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_SEARCH_API_KEY", "")
        self.engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")

    @property
    def name(self) -> str:
        return "google_search"

    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        """Search using Google Custom Search API."""
        if not self.api_key or not self.engine_id:
            logger.warning("google_search_not_configured_falling_back_to_mock")
            return await MockSearchTool().search(query, num_results)

        import httpx
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.engine_id,
            "q": query,
            "num": min(num_results, 10),
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("items", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                )
            )
        return results


def get_search_tool() -> SearchTool:
    """Get the configured search tool, falling back to mock if not configured."""
    api_key = os.getenv("GOOGLE_SEARCH_API_KEY", "")
    if api_key:
        return GoogleSearchTool()
    return MockSearchTool()
