"""
Web Scraper Ingester

Scrapes news sites (RSS feeds, article pages) for content.
Used for sources like Texas Tribune that aren't YouTube or Substack.
"""

import re
from datetime import datetime, timedelta
from html import unescape
from typing import Optional

import feedparser
import requests

from src.core.models import Source, SourceItem, SourceType
from src.core.registry import PluginRegistry
from .base import BaseIngester


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


@PluginRegistry.register("ingester", "web")
class WebIngester(BaseIngester):
    """Ingests articles from news websites via RSS or scraping."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch_latest(
        self, source: Source, max_items: int = 5,
        since_hours: Optional[int] = None
    ) -> list[SourceItem]:
        """Fetch latest articles from a web source."""
        feed_url = self._find_feed_url(source.url)
        if feed_url:
            return self._fetch_from_feed(
                feed_url, source, max_items, since_hours
            )
        return []

    def fetch_item(self, url: str, source: Source) -> Optional[SourceItem]:
        """Fetch a single article by URL."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            content = self._extract_article_text(response.text)
            title = self._extract_title(response.text)

            if not content:
                return None

            return SourceItem(
                source_id=source.id,
                source_type=SourceType.WEB,
                url=url,
                title=title,
                content=content,
            )
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            return None

    def _find_feed_url(self, url: str) -> Optional[str]:
        """Try to find an RSS/Atom feed for a website."""
        # Common feed paths
        candidates = [
            f"{url.rstrip('/')}/feed",
            f"{url.rstrip('/')}/rss",
            f"{url.rstrip('/')}/feed.xml",
            f"{url.rstrip('/')}/rss.xml",
            f"{url.rstrip('/')}/atom.xml",
            f"{url.rstrip('/')}/feeds/all.atom.xml",  # Texas Tribune
        ]

        for candidate in candidates:
            try:
                resp = self.session.head(candidate, timeout=10, allow_redirects=True)
                if resp.status_code == 200:
                    return candidate
            except Exception:
                continue

        return None

    def _fetch_from_feed(
        self, feed_url: str, source: Source,
        max_items: int, since_hours: Optional[int]
    ) -> list[SourceItem]:
        """Fetch articles from an RSS/Atom feed."""
        feed = feedparser.parse(feed_url)
        items = []

        for entry in feed.entries[:max_items * 2]:
            title = entry.get("title", "Untitled")

            # Extract content
            content = ""
            if "content" in entry and entry["content"]:
                content = entry["content"][0].get("value", "")
            elif "summary" in entry:
                content = entry.get("summary", "")

            if not content:
                continue

            content = self._html_to_text(content)

            # Parse date
            published_at = None
            if "published_parsed" in entry and entry["published_parsed"]:
                try:
                    published_at = datetime(*entry["published_parsed"][:6])
                except (TypeError, ValueError):
                    pass

            # Filter by freshness
            if since_hours and published_at:
                cutoff = datetime.utcnow() - timedelta(hours=since_hours)
                if published_at < cutoff:
                    continue

            items.append(SourceItem(
                source_id=source.id,
                source_type=SourceType.WEB,
                url=entry.get("link", ""),
                title=title,
                content=content,
                published_at=published_at,
                metadata={
                    "author": entry.get("author", ""),
                    "feed_url": feed_url,
                },
            ))

            if len(items) >= max_items:
                break

        return items

    def _extract_article_text(self, html: str) -> str:
        """Extract main article text from HTML page."""
        # Try to find article/main content
        article_match = re.search(
            r"<article[^>]*>(.*?)</article>",
            html, re.DOTALL
        )
        if article_match:
            html = article_match.group(1)
        else:
            main_match = re.search(
                r'<main[^>]*>(.*?)</main>',
                html, re.DOTALL
            )
            if main_match:
                html = main_match.group(1)

        return self._html_to_text(html)

    def _extract_title(self, html: str) -> str:
        """Extract page title from HTML."""
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL)
        if match:
            return unescape(match.group(1).strip())
        match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
        if match:
            return unescape(re.sub(r"<[^>]+>", "", match.group(1)).strip())
        return "Untitled"

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to clean plain text."""
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<(br|p|div|h[1-6]|li|blockquote)[^>]*>", "\n", text)
        text = re.sub(r"</(p|div|h[1-6]|li|blockquote)>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = unescape(text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()
