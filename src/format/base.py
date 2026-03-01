"""
Base Format Plugin

Abstract base class for content format plugins.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from src.core.models import ContentPiece


class BaseFormatter(ABC):
    """Abstract base class for format plugins."""

    @abstractmethod
    def format(self, piece: ContentPiece, output_dir: Path) -> ContentPiece:
        """Format a content piece for its target platform.

        Args:
            piece: ContentPiece with draft_content populated.
            output_dir: Directory to write formatted output files.

        Returns:
            Updated ContentPiece with formatted_content and file paths set.
        """
        ...

    @abstractmethod
    def get_human_instructions(self, piece: ContentPiece) -> str:
        """Generate human-readable instructions for manual steps.

        Returns:
            Markdown-formatted instructions for the human operator.
        """
        ...
