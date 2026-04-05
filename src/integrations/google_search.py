"""Google Custom Search integration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import structlog

from src.integrations.base_integration import BaseIntegration

logger = structlog.get_logger(__name__)


@dataclass
class SearchResult:
    """A Google search result."""
    title: str
    url: str
    snippet: str
    domain: str = ""


class GoogleSearch(BaseIntegration):
    """Google Custom Search API integration.

    Example:
        search = GoogleSearch()
        results = await search.search("top SaaS companies 2024", num_results=5)
        for r in results:
            print(r.title, r.url)
    """

    def __init__(self) -> None:
        super().__init__(name="google_search", rate_limit_per_minute=100)
        self.api_key = os.getenv("GOOGLE_SEARCH_API_KEY", "")
        self.engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")
        self._base_url = "https://www.googleapis.com/customsearch/v1"

    async def authenticate(self) -> None:
        """Google Search uses API key auth (no separate auth step needed)."""
        if not self.api_key:
            logger.warning("google_search_api_key_not_set")

    async def is_healthy(self) -> bool:
        """Check if Google Search is configured."""
        return bool(self.api_key and self.engine_id)

    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        """Execute a Google search.

        Args:
            query: Search query string.
            num_results: Number of results (max 10 per API call).

        Returns:
            List of SearchResult objects.
        """
        if not await self.is_healthy():
            logger.warning("google_search_not_configured_returning_empty")
            return []

        self._log.info("searching", query=query[:80], num_results=num_results)

        try:
            data = await self._make_request(
                "GET",
                self._base_url,
                params={
                    "key": self.api_key,
                    "cx": self.engine_id,
                    "q": query,
                    "num": min(num_results, 10),
                },
            )
        except Exception as e:
            self._log.error("search_failed", query=query[:80], error=str(e))
            return []

        results = []
        for item in data.get("items", []):
            url = item.get("link", "")
            domain = ""
            if url:
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                except Exception:
                    pass
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=url,
                    snippet=item.get("snippet", ""),
                    domain=domain,
                )
            )

        self._log.info("search_completed", results_count=len(results))
        return results
