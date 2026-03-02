"""
Source Discovery Service

When primary sources haven't posted recently, this finds related
content from backup sources and web searches to ensure daily coverage.
"""

import os
from typing import Optional

from src.core.config import ConfigLoader
from src.core.models import Source, SourceItem, SourceType


class SourceDiscovery:
    """Finds fresh content when primary sources are dry."""

    def __init__(self, config: Optional[ConfigLoader] = None):
        self.config = config or ConfigLoader()

    def find_fresh_sources(
        self, channel_slug: str, needed_count: int = 3
    ) -> list[SourceItem]:
        """Find fresh source material for a channel.

        Strategy:
        1. Check primary sources for new content
        2. If insufficient, check backup sources
        3. If still insufficient, search for related content

        Args:
            channel_slug: The channel needing content.
            needed_count: How many fresh source items we need.

        Returns:
            List of SourceItem objects ready for composition.
        """
        channel_config = self.config.load_channel(channel_slug)
        items: list[SourceItem] = []

        # 1. Check primary sources
        primary_sources = channel_config.get("sources", {}).get("primary", [])
        for src_config in primary_sources:
            from src.core.registry import PluginRegistry
            source = Source(
                id=src_config["id"],
                source_type=SourceType(src_config["type"]),
                url=src_config["url"],
                stance_level=src_config.get("stance", 3),
                tab=src_config.get("tab", "videos"),
            )
            ingester = PluginRegistry.create("ingester", src_config["type"])
            network = self.config.load_network()
            freshness = network.get("freshness", {})
            max_hours = freshness.get("news_max_hours", 72)

            new_items = ingester.fetch_latest(
                source, max_items=needed_count, since_hours=max_hours
            )
            items.extend(new_items)

            if len(items) >= needed_count:
                return items[:needed_count]

        # 2. Check backup sources
        backup_sources = channel_config.get("sources", {}).get("backup", [])
        for src_config in backup_sources:
            if len(items) >= needed_count:
                break

            source = Source(
                id=src_config["id"],
                source_type=SourceType(src_config["type"]),
                url=src_config["url"],
                stance_level=src_config.get("stance", 3),
                tab=src_config.get("tab", "videos"),
            )
            from src.core.registry import PluginRegistry
            ingester = PluginRegistry.create("ingester", src_config["type"])
            new_items = ingester.fetch_latest(source, max_items=2)
            items.extend(new_items)

        return items[:needed_count]

    def suggest_backup_sources(
        self, channel_slug: str, keywords: list[str]
    ) -> list[dict]:
        """Suggest potential backup sources based on channel keywords.

        This uses the Gemini API to suggest YouTube channels and Substack
        publications that cover similar topics.

        Returns list of dicts with 'name', 'url', 'type', 'relevance'.
        """
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return []

        channel_config = self.config.load_channel(channel_slug)
        channel_name = channel_config.get("name", channel_slug)

        # Build prompt for source suggestions
        prompt = f"""Suggest 5 YouTube channels and 5 Substack publications that cover 
similar topics to a channel called "{channel_name}" focused on these keywords: 
{', '.join(keywords)}.

For each suggestion, provide:
- Name
- URL
- Type (youtube or substack)
- Brief description of relevance

Format as JSON array."""

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
            response = model.generate_content(prompt)
            # Parse response — best-effort JSON extraction
            import json
            import re
            json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"Source suggestion failed: {e}")

        return []
