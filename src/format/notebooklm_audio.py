"""
NotebookLM Audio Overview Format Plugin

Prepares optimized source documents for NotebookLM Audio Overview.
Generates step-by-step instructions for the human NotebookLM step.
"""

from pathlib import Path

from src.core.models import ContentPiece, ContentStatus
from src.core.registry import PluginRegistry
from .base import BaseFormatter


@PluginRegistry.register("formatter", "notebooklm_audio")
class NotebookLMAudioFormatter(BaseFormatter):
    """Formats content for NotebookLM Audio Overview (Deep Dive)."""

    def format(self, piece: ContentPiece, output_dir: Path) -> ContentPiece:
        """Prepare source document optimized for NotebookLM audio generation."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create the source document for NotebookLM
        source_doc = self._create_source_document(piece)
        source_doc_path = output_dir / "notebooklm_source.md"
        source_doc_path.write_text(source_doc)

        # Generate human instructions
        instructions = self.get_human_instructions(piece)
        instructions_path = output_dir / "instructions.md"
        instructions_path.write_text(instructions)

        # Update piece
        piece.formatted_content = source_doc
        piece.notebooklm_source_doc_path = str(source_doc_path)
        piece.human_instructions = instructions
        piece.status = ContentStatus.AWAITING_HUMAN

        return piece

    def _create_source_document(self, piece: ContentPiece) -> str:
        """Create an optimized source document for NotebookLM.

        NotebookLM works best with:
        - Clear thesis statements
        - Well-structured sections
        - Embedded questions and counterarguments
        - Specific quotes and data points
        - Enough substance for a 10-15 minute conversation
        """
        doc = f"""# {piece.title}

{piece.subtitle}

---

## Key Thesis

{self._extract_thesis(piece.draft_content)}

---

## Full Analysis

{piece.draft_content}

---

## Discussion Points for Audio Overview

The following points should be explored in the audio discussion:

1. What is the central claim and why does it matter right now?
2. What historical precedent exists for this situation?
3. What is the strongest counterargument?
4. What is NOT being said in the original source material?
5. What should the listener still be thinking about an hour later?

---

## Key Quotes and Data

{self._extract_quotes(piece.draft_content)}

---

## Sources Referenced

{self._extract_sources(piece.draft_content)}
"""
        return doc

    def get_human_instructions(self, piece: ContentPiece) -> str:
        """Generate step-by-step instructions for the NotebookLM step."""
        return f"""# NotebookLM Audio Overview — Instructions

## Channel: {piece.channel_slug}
## Title: {piece.title}

### Steps (estimated: 3-5 minutes)

1. **Open NotebookLM**: Go to [notebooklm.google.com](https://notebooklm.google.com)

2. **Create New Notebook**: Click "New Notebook"

3. **Upload Source Document**: 
   - Click "Add Source" → "Text" or "Upload"
   - Upload the file: `{piece.notebooklm_source_doc_path}`

4. **Generate Audio Overview**:
   - Click "Audio Overview" in the Studio panel
   - Select format: **Deep Dive**
   - Click "Generate"
   - Wait for generation (usually 2-5 minutes)

5. **Download Audio**:
   - Click the download button on the generated audio
   - Save to: `data/content/{piece.channel_slug}/audio/`

6. **Publish**: Run:
   ```
   python -m src.cli publish {piece.channel_slug} --audio <path_to_downloaded_audio>
   ```
"""

    def _extract_thesis(self, content: str) -> str:
        """Extract the main thesis from the draft content."""
        lines = content.split("\n")
        # Look for the first substantial paragraph after the title
        for i, line in enumerate(lines):
            line = line.strip()
            if (len(line) > 100 and 
                not line.startswith("#") and 
                not line.startswith("*") and
                not line.startswith(">")):
                # Found a substantial paragraph
                return line
        return "See full analysis below."

    def _extract_quotes(self, content: str) -> str:
        """Extract blockquotes from the draft content."""
        quotes = []
        for line in content.split("\n"):
            if line.strip().startswith(">"):
                quotes.append(line.strip())
        return "\n\n".join(quotes) if quotes else "See full analysis for embedded quotes."

    def _extract_sources(self, content: str) -> str:
        """Extract source references from the draft content."""
        import re
        sources = []
        # Find markdown links
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
        for text, url in links:
            sources.append(f"- [{text}]({url})")
        return "\n".join(sources) if sources else "See full analysis for source references."
