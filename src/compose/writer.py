"""
AI Content Composer

Implements the 4-part composition formula:
1. Report as our own — rephrase, expand, claim what we agree with
2. Reference the source — lightly, not a book report
3. Frame in context — history, disagreements, what's NOT being said
4. Research and quote — supporting/contrasting sources for our contribution

Uses the Gemini API with voice configuration from voice.yml.
"""

import os
import uuid
from datetime import datetime
from typing import Optional

from src.core.config import ConfigLoader
from src.core.models import (
    Channel, ContentPiece, ContentStatus, FormatType, SourceItem,
)


class ContentComposer:
    """Composes original analytical content from source material."""

    def __init__(self, config: Optional[ConfigLoader] = None):
        self.config = config or ConfigLoader()
        self._voice = None
        self._api_key = None

    @property
    def voice(self) -> dict:
        if self._voice is None:
            self._voice = self.config.load_voice()
        return self._voice

    @property
    def api_key(self) -> str:
        if self._api_key is None:
            self._api_key = self.config.require_env("GOOGLE_API_KEY")
        return self._api_key

    def compose(
        self,
        channel: Channel,
        source_items: list[SourceItem],
        format_type: Optional[FormatType] = None,
    ) -> ContentPiece:
        """Compose a content piece from source material.

        Args:
            channel: The output channel this is for.
            source_items: Source material to work from.
            format_type: Override format type (defaults to channel config).

        Returns:
            ContentPiece with draft_content populated.
        """
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)

        network_config = self.config.load_network()
        gemini_config = network_config.get("gemini", {})

        model = genai.GenerativeModel(
            gemini_config.get("model", "gemini-2.5-pro-preview-05-06"),
            system_instruction=self._build_system_prompt(channel, source_items),
        )

        # Build the composition prompt with audience feedback
        prompt = self._build_composition_prompt(channel, source_items)

        # Inject audience feedback from comments into the prompt
        feedback_context = self._get_feedback_context(channel.slug)
        if feedback_context:
            prompt += feedback_context

        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": gemini_config.get("temperature", 0.7),
                "max_output_tokens": gemini_config.get("max_output_tokens", 8192),
            },
        )

        draft = response.text

        # Mark feedback as incorporated now that content used it
        if feedback_context:
            self._mark_feedback_incorporated(channel.slug)

        # Extract title from draft (first line if it starts with #)
        title, subtitle = self._extract_title(draft)

        piece = ContentPiece(
            id=str(uuid.uuid4()),
            channel_slug=channel.slug,
            title=title,
            subtitle=subtitle,
            draft_content=draft,
            source_items=source_items,
            status=ContentStatus.DRAFTED,
            format_type=format_type or channel.format_type,
            created_at=datetime.utcnow(),
        )

        return piece

    def _build_system_prompt(
        self, channel: Channel, source_items: list[SourceItem]
    ) -> str:
        """Build the system prompt with voice config and stance info."""
        voice_config = self.voice
        system_prompt = voice_config.get("voice", {}).get("system_prompt", "")

        # Add stance-specific instructions
        stance_instructions = []
        for item in source_items:
            stance = self.config.get_stance_for_source(item.source_id)
            stance_instructions.append(
                f"\nSource: {item.source_id} (stance: {stance['level_name']}, "
                f"level {stance['level']}/5)\n"
                f"Notes: {stance['composition_notes']}\n"
                f"Source-specific: {stance['source_notes']}"
            )

        if stance_instructions:
            system_prompt += "\n\n## Source Stance Instructions\n"
            system_prompt += "\n".join(stance_instructions)

        return system_prompt

    def _build_composition_prompt(
        self, channel: Channel, source_items: list[SourceItem]
    ) -> str:
        """Build the user prompt for content composition."""
        formula = self.voice.get("voice", {}).get("formula", {})

        # Source material
        sources_text = ""
        for i, item in enumerate(source_items, 1):
            sources_text += f"\n\n--- SOURCE {i}: {item.title} ---\n"
            sources_text += f"From: {item.source_id} ({item.url})\n"
            if item.published_at:
                sources_text += f"Published: {item.published_at.strftime('%Y-%m-%d')}\n"
            sources_text += f"\n{item.content[:6000]}\n"  # Cap at 6K chars per source

        # Format-specific guidelines
        format_guide = self._get_format_guide(channel.format_type)

        prompt = f"""## Composition Task

Write an original analytical piece for the channel "{channel.name}" based on the 
source material below. Follow the composition formula precisely:

### 1. Report as Our Own ({int(formula.get('report_as_own', {}).get('weight', 0.25) * 100)}%)
{formula.get('report_as_own', {}).get('description', '')}

### 2. Reference the Source ({int(formula.get('reference_source', {}).get('weight', 0.10) * 100)}%)
{formula.get('reference_source', {}).get('description', '')}

### 3. Frame in Context ({int(formula.get('frame_in_context', {}).get('weight', 0.35) * 100)}%)
{formula.get('frame_in_context', {}).get('description', '')}

### 4. Research and Quote ({int(formula.get('research_and_quote', {}).get('weight', 0.30) * 100)}%)
{formula.get('research_and_quote', {}).get('description', '')}

{format_guide}

## Source Material
{sources_text}

## Output Requirements
- Start with a compelling title (# Title) and subtitle
- Write 1,500-3,000 words
- Include specific names, dates, statistics
- Quote or paraphrase at least 3 external sources beyond the provided material
- End with a thought that lingers — the "wait one second" insight
- Do NOT summarize the source — use it as a springboard
"""

        return prompt

    def _get_format_guide(self, format_type: FormatType) -> str:
        """Get format-specific writing guidelines."""
        guides = {
            FormatType.SUBSTACK_ESSAY: """
### Format: Substack Essay
- Use markdown formatting with headers, emphasis, blockquotes
- Include a strong opening that hooks within 2 sentences
- Break into clear sections with subheadings
- Use blockquotes for key quotes
- End with sources/further reading section
""",
            FormatType.NOTEBOOKLM_AUDIO: """
### Format: NotebookLM Audio Overview Source Document
- Write as a comprehensive briefing document
- Include clear thesis statements that hosts can discuss
- Embed provocative questions and counterarguments
- Include enough detail and quotes for a 10-15 minute conversation
- Structure with clear sections and key takeaways
""",
            FormatType.NOTEBOOKLM_VIDEO: """
### Format: NotebookLM Video Overview Source Document
- Write as a visual-friendly briefing document
- Include clear thesis with supporting evidence
- Structure for visual storytelling with distinct segments
- Embed specific examples and data points
- Include both analysis and narrative elements
""",
        }
        return guides.get(format_type, "")

    def _extract_title(self, draft: str) -> tuple[str, str]:
        """Extract title and subtitle from drafted content."""
        lines = draft.strip().split("\n")
        title = "Untitled"
        subtitle = ""

        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith("# ") and not line.startswith("## "):
                title = line[2:].strip()
                # Check next non-empty line for subtitle
                for j in range(i + 1, min(i + 4, len(lines))):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith("#"):
                        if next_line.startswith("*") and next_line.endswith("*"):
                            subtitle = next_line.strip("*").strip()
                        elif len(next_line) < 200:
                            subtitle = next_line
                        break
                break

        return title, subtitle

    def _get_feedback_context(self, channel_slug: str) -> str:
        """Get audience feedback context to inject into composition prompt."""
        try:
            from src.engage.feedback import FeedbackLoop
            feedback = FeedbackLoop(self.config)
            return feedback.get_channel_feedback_context(channel_slug)
        except Exception:
            return ""

    def _mark_feedback_incorporated(self, channel_slug: str) -> None:
        """Mark feedback as incorporated after content is composed."""
        try:
            from src.engage.feedback import FeedbackLoop
            feedback = FeedbackLoop(self.config)
            count = feedback.mark_feedback_incorporated(channel_slug)
            if count > 0:
                print(f"  📊 Incorporated {count} audience feedback item(s)")
        except Exception:
            pass
