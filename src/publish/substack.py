"""
Substack Publisher

Publishes essays to Substack using the unofficial python-substack library.
Falls back to preparing drafts for manual publish if automation fails.
"""

import os
from datetime import datetime
from typing import Optional

from src.core.models import ContentPiece, Platform, PublishRecord
from src.core.registry import PluginRegistry
from .base import BasePublisher


@PluginRegistry.register("publisher", "substack")
class SubstackPublisher(BasePublisher):
    """Publishes essays to Substack."""

    def publish(self, piece: ContentPiece) -> Optional[PublishRecord]:
        """Publish an essay to Substack.

        Attempts automated publishing via python-substack library.
        Falls back to preparing for manual publish.
        """
        # Try automated publish first
        result = self._publish_automated(piece)
        if result:
            return result

        # Fall back to manual instructions
        print(f"⚠️ Automated Substack publish unavailable.")
        print(f"📋 Please publish manually using the instructions file.")
        return None

    def _publish_automated(self, piece: ContentPiece) -> Optional[PublishRecord]:
        """Attempt automated publishing via python-substack."""
        try:
            from substack import Api as SubstackApi

            email = os.environ.get("SUBSTACK_EMAIL")
            password = os.environ.get("SUBSTACK_PASSWORD")

            if not email or not password:
                return None

            api = SubstackApi(email=email, password=password)

            # Create draft
            draft = api.create_draft(
                title=piece.title,
                subtitle=piece.subtitle,
                content=piece.formatted_content or piece.draft_content,
            )

            if not draft:
                return None

            # Upload cover image if available
            if piece.image_path and os.path.exists(piece.image_path):
                try:
                    api.set_cover_image(draft.id, piece.image_path)
                except Exception as e:
                    print(f"⚠️ Cover image upload failed: {e}")

            # Publish the draft
            published = api.publish_draft(draft.id)

            if published:
                publish_url = published.get("url", "")
                print(f"✅ Published to Substack: {publish_url}")

                return PublishRecord(
                    piece_id=piece.id,
                    channel_slug=piece.channel_slug,
                    platform=Platform.SUBSTACK,
                    publish_url=publish_url,
                    published_at=datetime.utcnow(),
                    title=piece.title,
                )

        except ImportError:
            print("python-substack not installed. Run: pip install python-substack")
        except Exception as e:
            print(f"Substack automated publish failed: {e}")

        return None

    def validate_credentials(self) -> bool:
        """Check if Substack credentials are configured."""
        email = os.environ.get("SUBSTACK_EMAIL")
        password = os.environ.get("SUBSTACK_PASSWORD")
        return bool(email and password)
