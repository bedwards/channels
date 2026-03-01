"""
Base Ingester

Abstract base class for all source ingesters.
"""

from abc import ABC, abstractmethod
from typing import Optional

from src.core.models import Source, SourceItem


class BaseIngester(ABC):
    """Abstract base class for source ingestion plugins."""

    @abstractmethod
    def fetch_latest(
        self, source: Source, max_items: int = 5,
        since_hours: Optional[int] = None
    ) -> list[SourceItem]:
        """Fetch latest items from a source.

        Args:
            source: The source to fetch from.
            max_items: Maximum number of items to return.
            since_hours: Only return items newer than this many hours.

        Returns:
            List of SourceItem objects with content populated.
        """
        ...

    @abstractmethod
    def fetch_item(self, url: str, source: Source) -> Optional[SourceItem]:
        """Fetch a single item by URL.

        Args:
            url: Direct URL to the content item.
            source: The parent source.

        Returns:
            SourceItem with content populated, or None on failure.
        """
        ...

    def validate_source(self, source: Source) -> bool:
        """Validate that a source is accessible."""
        try:
            items = self.fetch_latest(source, max_items=1)
            return len(items) > 0
        except Exception:
            return False
