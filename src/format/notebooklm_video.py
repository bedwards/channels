"""
NotebookLM Video Overview Format Plugin

Prepares source documents for NotebookLM Video Overview.
Adds visual style preferences and video-specific instructions.
"""

from pathlib import Path

from src.core.models import ContentPiece, ContentStatus
from src.core.registry import PluginRegistry
from .base import BaseFormatter


@PluginRegistry.register("formatter", "notebooklm_video")
class NotebookLMVideoFormatter(BaseFormatter):
    """Formats content for NotebookLM Video Overview."""

    def format(self, piece: ContentPiece, output_dir: Path) -> ContentPiece:
        """Prepare source document for NotebookLM Video Overview."""
        output_dir.mkdir(parents=True, exist_ok=True)

        source_doc = self._create_source_document(piece)
        source_doc_path = output_dir / "notebooklm_source.md"
        source_doc_path.write_text(source_doc)

        instructions = self.get_human_instructions(piece)
        instructions_path = output_dir / "instructions.md"
        instructions_path.write_text(instructions)

        piece.formatted_content = source_doc
        piece.notebooklm_source_doc_path = str(source_doc_path)
        piece.human_instructions = instructions
        piece.status = ContentStatus.AWAITING_HUMAN

        return piece

    def _create_source_document(self, piece: ContentPiece) -> str:
        """Create source document optimized for video overview."""
        doc = f"""# {piece.title}

{piece.subtitle}

---

## Visual Narrative Structure

### Opening Hook
What is the single most striking thing about this story?
Why should the viewer care in the first 10 seconds?

### The Setup
{self._extract_first_section(piece.draft_content)}

### The Complication
What makes this more complex than it first appears?

### The Resolution
What should the viewer be thinking about after watching?

---

## Full Analysis

{piece.draft_content}

---

## Key Visual Moments

These sections contain strong visual potential:

{self._identify_visual_moments(piece.draft_content)}

---

## Discussion Guide

1. Open with the most striking fact or claim
2. Walk through the evidence
3. Present the counterargument fairly
4. Deliver the "wait one second" insight
5. Close with what this means going forward
"""
        return doc

    def get_human_instructions(self, piece: ContentPiece) -> str:
        """Generate instructions for NotebookLM Video Overview."""
        visual_style = piece.metadata.get("visual_style", "Deep Dive")

        return f"""# NotebookLM Video Overview — Instructions

## Channel: {piece.channel_slug}
## Title: {piece.title}

### Steps (estimated: 5-8 minutes)

1. **Open NotebookLM**: Go to [notebooklm.google.com](https://notebooklm.google.com)

2. **Create New Notebook**: Click "New Notebook"

3. **Upload Source Document**: 
   - Click "Add Source" → "Text" or "Upload"
   - Upload: `{piece.notebooklm_source_doc_path}`

4. **Generate Video Overview**:
   - Click "Video Overview" in the Studio panel
   - Select format: **{visual_style}**
   - Click "Generate"
   - Wait for generation (usually 5-10 minutes)

5. **Review & Download**:
   - Preview the generated video
   - If satisfactory, click download
   - Save to: `data/content/{piece.channel_slug}/video/`

6. **Publish**: Run:
   ```
   python -m src.cli publish {piece.channel_slug} --video <path_to_downloaded_video>
   ```
"""

    def _extract_first_section(self, content: str) -> str:
        """Extract the first major section of content."""
        lines = content.split("\n")
        section_lines = []
        in_section = False

        for line in lines:
            if line.strip().startswith("# ") and not in_section:
                in_section = True
                continue
            if line.strip().startswith("## ") and in_section:
                if section_lines:
                    break
                continue
            if in_section:
                section_lines.append(line)

        text = "\n".join(section_lines).strip()
        return text[:1000] if text else "See full analysis below."

    def _identify_visual_moments(self, content: str) -> str:
        """Identify sections with strong visual storytelling potential."""
        moments = []
        import re

        # Look for specific data points, comparisons, timelines
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Lines with numbers/statistics
            if re.search(r'\d+%|\$\d+|billion|million|\d{4}', line):
                moments.append(f"- 📊 {line[:150]}")
            # Blockquotes
            elif line.startswith(">"):
                moments.append(f"- 💬 {line[:150]}")
            # Historical references
            elif re.search(r'(in \d{4}|century|decade|era|period)', line, re.I):
                moments.append(f"- 📜 {line[:150]}")

            if len(moments) >= 8:
                break

        return "\n".join(moments) if moments else "See full analysis for visual content opportunities."
