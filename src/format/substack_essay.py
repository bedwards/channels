"""
Substack Essay Format Plugin

Formats content as a complete Substack post with title, subtitle,
sections, source citations, and generated charcoal illustration.
"""

from pathlib import Path
from typing import Optional

from src.core.models import ContentPiece, ContentStatus
from src.core.registry import PluginRegistry
from .base import BaseFormatter
from .image_gen import ImageGenerator


@PluginRegistry.register("formatter", "substack_essay")
class SubstackEssayFormatter(BaseFormatter):
    """Formats content as a Substack essay with charcoal illustration."""

    def __init__(self):
        self.image_gen = ImageGenerator()

    def format(self, piece: ContentPiece, output_dir: Path) -> ContentPiece:
        """Format content as a Substack essay."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Format the essay
        essay = self._format_essay(piece)
        essay_path = output_dir / "essay.md"
        essay_path.write_text(essay)

        # Generate charcoal illustration
        try:
            image_prompt = self._generate_image_prompt(piece)
            image_path = self.image_gen.generate_charcoal_image(
                prompt=image_prompt,
                output_path=output_dir / "cover.png",
            )
            piece.image_path = str(image_path) if image_path else None
        except Exception as e:
            print(f"Image generation failed: {e}")
            piece.image_path = None

        # Generate instructions
        instructions = self.get_human_instructions(piece)
        instructions_path = output_dir / "instructions.md"
        instructions_path.write_text(instructions)

        piece.formatted_content = essay
        piece.human_instructions = instructions
        piece.status = ContentStatus.READY_TO_PUBLISH

        return piece

    def _format_essay(self, piece: ContentPiece) -> str:
        """Format the draft as a publication-ready Substack essay."""
        content = piece.draft_content

        # Ensure proper title formatting
        lines = content.split("\n")
        formatted_lines = []
        title_found = False

        for line in lines:
            if not title_found and line.strip().startswith("# "):
                title_found = True
                formatted_lines.append(line)
                # Add subtitle if we have one and it's not already there
                if piece.subtitle:
                    formatted_lines.append("")
                    formatted_lines.append(f"*{piece.subtitle}*")
            else:
                formatted_lines.append(line)

        essay = "\n".join(formatted_lines)

        # Ensure sources section exists
        if "## Sources" not in essay and "## Further Reading" not in essay:
            sources = self._build_sources_section(piece)
            essay += f"\n\n---\n\n{sources}"

        return essay

    def _build_sources_section(self, piece: ContentPiece) -> str:
        """Build a sources/further reading section."""
        sources = ["## Sources and Further Reading\n"]

        for item in piece.source_items:
            sources.append(f"- [{item.title}]({item.url})")

        return "\n".join(sources)

    def _generate_image_prompt(self, piece: ContentPiece) -> str:
        """Generate a prompt for the charcoal illustration."""
        # Extract key visual concept from the title/content
        concept = piece.title.lower()

        # Remove common non-visual words
        for word in ["the", "a", "an", "of", "in", "on", "and", "or", "but",
                      "is", "are", "was", "were", "it", "this", "that"]:
            concept = concept.replace(f" {word} ", " ")

        return (
            f"A dramatic charcoal drawing inspired by the concept: {concept}. "
            f"Evocative, expressive, hand-drawn on textured paper. "
            f"Black and white with rich tonal range. "
            f"No text, no words, no letters, no numbers in the image."
        )

    def get_human_instructions(self, piece: ContentPiece) -> str:
        """Generate instructions for Substack publishing."""
        image_note = ""
        if piece.image_path:
            image_note = f"\n3. **Set Cover Image**: Upload `{piece.image_path}` as cover image\n"
        else:
            image_note = "\n3. **Cover Image**: Image generation failed — upload manually or skip\n"

        return f"""# Substack Essay — Instructions

## Channel: {piece.channel_slug}
## Title: {piece.title}

### Steps (estimated: 2-3 minutes)

1. **Review Draft**: Open and review the essay at the output path

2. **Publish via CLI** (if automated publishing is set up):
   ```
   python -m src.cli publish {piece.channel_slug}
   ```

   **OR Publish manually**:
   - Open your Substack dashboard
   - Click "New Post"
   - Copy the essay content from the formatted file
   - Set title: **{piece.title}**
   - Set subtitle: **{piece.subtitle}**
{image_note}
4. **Click Publish** (or schedule for optimal time)
"""
