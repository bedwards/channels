"""
Source Preparation

Prepares source material for agent-driven composition.
The agent (Claude Opus 4.6 in Antigravity) reads the prepared brief
and writes the content directly — no API calls needed.

Output: A markdown brief in data/sources/<channel>/<date>/brief.md
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.config import ConfigLoader
from src.core.database import Database
from src.core.models import Source, SourceType
from src.core.registry import PluginRegistry
from src.ingest.discovery import SourceDiscovery


class SourcePreparer:
    """Prepares source material for agent composition."""

    def __init__(
        self,
        config: Optional[ConfigLoader] = None,
        db: Optional[Database] = None,
    ):
        self.config = config or ConfigLoader()
        self.db = db or Database()
        self.data_dir = Path("data")

    def prepare(
        self, channel_slug: str, max_sources: int = 3
    ) -> Path:
        """Prepare source material for a channel and save as a brief.

        Returns the path to the prepared brief markdown file.
        """
        channel_config = self.config.load_channel(channel_slug)
        voice_config = self.config.load_voice()
        today = datetime.now().strftime("%Y-%m-%d")

        # Create output directory
        brief_dir = self.data_dir / "sources" / channel_slug / today
        brief_dir.mkdir(parents=True, exist_ok=True)

        # Discover fresh sources
        print(f"  🔍 Finding fresh sources for {channel_config['name']}...")
        discovery = SourceDiscovery(self.config)
        source_items = discovery.find_fresh_sources(
            channel_slug, needed_count=max_sources
        )

        if not source_items:
            print(f"  ❌ No fresh sources found")
            return brief_dir / "brief.md"

        print(f"  ✅ Found {len(source_items)} source(s)")
        for item in source_items:
            print(f"     → {item.title}")

        # Build the brief
        brief = self._build_brief(
            channel_slug, channel_config, voice_config, source_items
        )

        # Save brief
        brief_path = brief_dir / "brief.md"
        brief_path.write_text(brief)

        # Save individual source transcripts
        for i, item in enumerate(source_items, 1):
            source_path = brief_dir / f"source_{i}.md"
            source_path.write_text(
                f"# {item.title}\n\n"
                f"**Source:** {item.source_id}\n"
                f"**URL:** {item.url}\n"
                f"**Published:** {item.published_at or 'Unknown'}\n\n"
                f"---\n\n{item.content}\n"
            )

        print(f"\n  📁 Brief saved to: {brief_path}")
        print(f"  📁 {len(source_items)} source file(s) saved")

        return brief_path

    def _build_brief(
        self, channel_slug, channel_config, voice_config, source_items
    ) -> str:
        """Build a comprehensive brief for agent composition."""
        voice = voice_config.get("voice", {})
        formula = voice.get("formula", {})

        # Stance information
        stance_info = []
        for item in source_items:
            stance = self.config.get_stance_for_source(item.source_id)
            stance_info.append(
                f"- **{item.source_id}**: stance {stance['level']}/5 "
                f"({stance['level_name']})\n"
                f"  Notes: {stance['composition_notes']}\n"
                f"  Source-specific: {stance['source_notes']}"
            )

        # Source summaries
        sources_text = ""
        for i, item in enumerate(source_items, 1):
            sources_text += f"\n### Source {i}: {item.title}\n\n"
            sources_text += f"- **From:** {item.source_id} ({item.url})\n"
            if item.published_at:
                sources_text += f"- **Published:** {item.published_at.strftime('%Y-%m-%d')}\n"
            sources_text += f"- **Length:** {len(item.content)} characters\n\n"
            # Include full content (up to 8K chars per source)
            sources_text += f"#### Transcript/Content\n\n"
            sources_text += f"{item.content[:8000]}\n"
            if len(item.content) > 8000:
                sources_text += f"\n*[Truncated — full text in source_{i}.md]*\n"

        # Format-specific guidelines
        format_plugin = channel_config.get("format", {}).get("plugin", "")
        format_guide = self._get_format_guide(format_plugin)

        # Build the brief
        brief = f"""# Composition Brief — {channel_config['name']}

**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Channel:** {channel_config['name']} ({channel_slug})
**Platform:** {channel_config.get('platform', 'unknown')}
**Format:** {format_plugin}

---

## Voice & Style

{voice.get('system_prompt', '')}

## Composition Formula

### 1. Report as Our Own ({int(formula.get('report_as_own', {}).get('weight', 0.25) * 100)}%)
{formula.get('report_as_own', {}).get('description', '')}

### 2. Reference the Source ({int(formula.get('reference_source', {}).get('weight', 0.10) * 100)}%)
{formula.get('reference_source', {}).get('description', '')}

### 3. Frame in Context ({int(formula.get('frame_in_context', {}).get('weight', 0.35) * 100)}%)
{formula.get('frame_in_context', {}).get('description', '')}

### 4. Research and Quote ({int(formula.get('research_and_quote', {}).get('weight', 0.30) * 100)}%)
{formula.get('research_and_quote', {}).get('description', '')}

## Source Stances

{chr(10).join(stance_info)}

{format_guide}

## Source Material

{sources_text}

---

## Output Requirements

1. Start with a compelling title (# Title) and subtitle
2. Write 1,500–3,000 words
3. Include specific names, dates, statistics
4. Quote or paraphrase at least 3 external sources beyond the provided material
5. End with a thought that lingers — the "wait one second" insight
6. Do NOT summarize the source — use it as a springboard
7. Follow the composition formula weights above
8. Match the voice precisely — no generic AI prose

## Output Location

Save the composed piece to: `data/output/{channel_slug}/{datetime.now().strftime('%Y-%m-%d')}/draft.md`
"""
        return brief

    def _get_format_guide(self, format_plugin: str) -> str:
        """Get format-specific writing guidelines."""
        guides = {
            "substack_essay": """## Format: Substack Essay
- Use markdown formatting with headers, emphasis, blockquotes
- Include a strong opening that hooks within 2 sentences
- Break into clear sections with subheadings
- Use blockquotes for key quotes
- End with sources/further reading section""",

            "notebooklm_audio": """## Format: NotebookLM Audio Overview Source Document
- Write as a comprehensive briefing document
- Include clear thesis statements that hosts can discuss
- Embed provocative questions and counterarguments
- Include enough detail and quotes for a 10-15 minute conversation
- Structure with clear sections and key takeaways""",

            "notebooklm_video": """## Format: NotebookLM Video Overview Source Document
- Write as a visual-friendly briefing document
- Include clear thesis with supporting evidence
- Structure for visual storytelling with distinct segments
- Embed specific examples and data points
- Include both analysis and narrative elements""",
        }
        return guides.get(format_plugin, "")
