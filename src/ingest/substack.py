"""
Substack Feed Ingester

Parses Substack RSS/Atom feeds to extract articles.
"""

import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional
from html import unescape

import feedparser

from src.core.models import Source, SourceItem, SourceType
from src.core.registry import PluginRegistry
from .base import BaseIngester


@PluginRegistry.register("ingester", "substack")
class SubstackIngester(BaseIngester):
    """Ingests articles from Substack RSS/Atom feeds."""

    def fetch_latest(
        self, source: Source, max_items: int = 5,
        since_hours: Optional[int] = None
    ) -> list[SourceItem]:
        """Fetch latest articles from a Substack feed."""
        feed_url = self._get_feed_url(source.url)
        feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            print(f"Feed parse error for {feed_url}: {feed.bozo_exception}")
            return []

        items = []
        for entry in feed.entries[:max_items * 2]:  # Fetch extra to filter
            item = self._parse_entry(entry, source)
            if not item:
                continue

            # Filter by freshness
            if since_hours and item.published_at:
                cutoff = datetime.utcnow() - timedelta(hours=since_hours)
                if item.published_at < cutoff:
                    continue

            items.append(item)
            if len(items) >= max_items:
                break

        return items

    def fetch_item(self, url: str, source: Source) -> Optional[SourceItem]:
        """Fetch a single Substack article by URL."""
        # Try to find it in the feed first
        feed_url = self._get_feed_url(source.url)
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            if entry.get("link") == url or entry.get("id") == url:
                return self._parse_entry(entry, source)

        return None

    def _get_feed_url(self, url: str) -> str:
        """Ensure URL points to RSS feed."""
        url = url.rstrip("/")
        if url.endswith("/feed"):
            return url
        if "substack.com" in url:
            # Handle various Substack URL formats
            if "/p/" in url or "/inbox/" in url:
                # Single post URL — extract subdomain for feed
                parts = url.split("/")
                base = "/".join(parts[:3])
                return f"{base}/feed"
            return f"{url}/feed"
        # For custom domains, try /feed
        return f"{url}/feed"

    def _parse_entry(
        self, entry: dict, source: Source
    ) -> Optional[SourceItem]:
        """Parse a feed entry into a SourceItem."""
        title = entry.get("title", "Untitled")

        # Extract content — try multiple fields
        content = ""
        if "content" in entry and entry["content"]:
            content = entry["content"][0].get("value", "")
        elif "summary" in entry:
            content = entry.get("summary", "")
        elif "description" in entry:
            content = entry.get("description", "")

        if not content:
            return None

        # Clean HTML to plain text
        content = self._html_to_text(content)

        # Parse published date
        published_at = None
        if "published_parsed" in entry and entry["published_parsed"]:
            try:
                published_at = datetime(*entry["published_parsed"][:6])
            except (TypeError, ValueError):
                pass
        elif "updated_parsed" in entry and entry["updated_parsed"]:
            try:
                published_at = datetime(*entry["updated_parsed"][:6])
            except (TypeError, ValueError):
                pass

        url = entry.get("link", entry.get("id", ""))

        return SourceItem(
            source_id=source.id,
            source_type=SourceType.SUBSTACK,
            url=url,
            title=title,
            content=content,
            published_at=published_at,
            metadata={
                "author": entry.get("author", ""),
                "tags": [t.get("term", "") for t in entry.get("tags", [])],
                "feed_url": self._get_feed_url(source.url),
            },
        )

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to clean plain text."""
        # Remove scripts and styles
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)

        # Convert block elements to newlines
        text = re.sub(r"<(br|p|div|h[1-6]|li|blockquote)[^>]*>", "\n", text)
        text = re.sub(r"</(p|div|h[1-6]|li|blockquote)>", "\n", text)

        # Remove remaining HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Decode HTML entities
        text = unescape(text)

        # Clean up whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip()
