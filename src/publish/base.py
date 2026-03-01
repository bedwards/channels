"""
Base Publisher

Abstract base class for publishing plugins.
"""

from abc import ABC, abstractmethod
from typing import Optional

from src.core.models import ContentPiece, PublishRecord


class BasePublisher(ABC):
    """Abstract base class for publishing plugins."""

    @abstractmethod
    def publish(self, piece: ContentPiece) -> Optional[PublishRecord]:
        """Publish a content piece to the target platform.

        Args:
            piece: ContentPiece ready for publishing.

        Returns:
            PublishRecord on success, None on failure.
        """
        ...

    @abstractmethod
    def validate_credentials(self) -> bool:
        """Validate that publishing credentials are configured."""
        ...
