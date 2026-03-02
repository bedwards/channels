"""
YouTube Publisher

Uploads videos to YouTube via the Data API v3 with OAuth 2.0.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.models import ContentPiece, Platform, PublishRecord
from src.core.registry import PluginRegistry
from .base import BasePublisher


@PluginRegistry.register("publisher", "youtube")
class YouTubePublisher(BasePublisher):
    """Publishes videos to YouTube via Data API v3."""

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
    ]
    TOKEN_PATH = Path(__file__).parent.parent.parent / "tokens" / "youtube.json"

    def publish(self, piece: ContentPiece) -> Optional[PublishRecord]:
        """Upload a video to YouTube."""
        if not piece.video_path and not piece.audio_path:
            print(f"No video or audio file for piece {piece.id}")
            return None

        media_path = piece.video_path or piece.audio_path
        if not Path(media_path).exists():
            print(f"Media file not found: {media_path}")
            return None

        try:
            service = self._get_youtube_service()
            if not service:
                return None

            # Prepare video metadata
            body = {
                "snippet": {
                    "title": piece.title[:100],
                    "description": self._build_description(piece),
                    "categoryId": "25",  # News & Politics
                    "tags": self._extract_tags(piece),
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                },
            }

            # Upload
            from googleapiclient.http import MediaFileUpload
            media = MediaFileUpload(
                media_path,
                mimetype="video/*",
                resumable=True,
                chunksize=1024 * 1024,
            )

            request = service.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"Upload progress: {int(status.progress() * 100)}%")

            video_id = response.get("id")
            publish_url = f"https://www.youtube.com/watch?v={video_id}"

            print(f"✅ Published to YouTube: {publish_url}")

            # Upload thumbnail if available
            if piece.image_path and Path(piece.image_path).exists():
                try:
                    service.thumbnails().set(
                        videoId=video_id,
                        media_body=MediaFileUpload(piece.image_path),
                    ).execute()
                    print("✅ Thumbnail set")
                except Exception as e:
                    print(f"⚠️ Thumbnail upload failed: {e}")

            return PublishRecord(
                piece_id=piece.id,
                channel_slug=piece.channel_slug,
                platform=Platform.YOUTUBE,
                publish_url=publish_url,
                published_at=datetime.utcnow(),
                title=piece.title,
                metadata={"video_id": video_id},
            )

        except Exception as e:
            print(f"YouTube upload failed: {e}")
            return None

    def validate_credentials(self) -> bool:
        """Check if YouTube OAuth credentials are configured."""
        client_id = os.environ.get("YOUTUBE_CLIENT_ID")
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
        return bool(client_id and client_secret)

    def _get_youtube_service(self):
        """Get authenticated YouTube API service."""
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build

            creds = None

            # Load saved token
            if self.TOKEN_PATH.exists():
                creds = Credentials.from_authorized_user_file(
                    str(self.TOKEN_PATH), self.SCOPES
                )

            # If no valid creds, run OAuth flow
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    from google.auth.transport.requests import Request
                    creds.refresh(Request())
                else:
                    client_config = {
                        "installed": {
                            "client_id": os.environ.get("YOUTUBE_CLIENT_ID"),
                            "client_secret": os.environ.get("YOUTUBE_CLIENT_SECRET"),
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
                        }
                    }
                    flow = InstalledAppFlow.from_client_config(
                        client_config, self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                # Save token
                self.TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
                self.TOKEN_PATH.write_text(creds.to_json())

            return build("youtube", "v3", credentials=creds)

        except Exception as e:
            print(f"Failed to authenticate with YouTube: {e}")
            return None

    def _build_description(self, piece: ContentPiece) -> str:
        """Build a rich YouTube video description.

        Structure:
        1. Above-the-fold hook (first 2-3 lines — visible before "Show more")
        2. Key topics / section breakdown
        3. Source credits with links
        4. Channel info + subscribe CTA
        5. SEO hashtags
        """
        import re
        lines = []

        # 1. Above-the-fold hook — subtitle + opening punch
        if piece.subtitle:
            lines.append(piece.subtitle)
            lines.append("")

        # Extract opening insight from draft (first non-header paragraph)
        if piece.draft_content:
            for para in piece.draft_content.split("\n\n"):
                para = para.strip()
                if para and not para.startswith("#") and not para.startswith("**") and not para.startswith("---"):
                    # Clean markdown
                    clean = re.sub(r'[*_]', '', para)
                    if len(clean) > 50:
                        lines.append(clean[:300])
                        lines.append("")
                        break

        # 2. Key topics from section headers
        if piece.draft_content:
            headers = re.findall(r'^###?\s+(.+)', piece.draft_content, re.MULTILINE)
            if headers:
                lines.append("📋 IN THIS VIDEO:")
                for h in headers[:8]:
                    h = h.strip().strip('#').strip()
                    if h and len(h) > 3:
                        lines.append(f"• {h}")
                lines.append("")

        # 3. Source credits
        if piece.source_items:
            lines.append("📌 SOURCES:")
            for item in piece.source_items:
                if item.url:
                    lines.append(f"• {item.title}: {item.url}")
                else:
                    lines.append(f"• {item.title} ({item.source_id})")
            lines.append("")

        # 4. Channel branding
        lines.append("─" * 40)
        lines.append("")
        lines.append("Part of the Lluminate Network")
        lines.append("Independent analysis. No sponsors. No algorithm bait.")
        lines.append("")
        lines.append("🔔 Subscribe and turn on notifications")
        lines.append("💬 Join the conversation in the comments")
        lines.append("")

        # 5. SEO hashtags
        tags = self._extract_tags(piece)
        if tags:
            hashtags = " ".join(f"#{t.replace(' ', '')}" for t in tags[:15])
            lines.append(hashtags)

        return "\n".join(lines)[:5000]

    def _extract_tags(self, piece: ContentPiece) -> list[str]:
        """Extract relevant tags from content and metadata."""
        import re
        tags = ["analysis", "commentary", "politics"]

        # Tags from source IDs
        for item in piece.source_items:
            if item.source_id:
                tags.append(item.source_id.replace("-", " "))

        # Tags from section headers in draft
        if piece.draft_content:
            headers = re.findall(r'^###?\s+(.+)', piece.draft_content, re.MULTILINE)
            for h in headers:
                # Extract key nouns/phrases from headers
                words = h.strip().strip('#').strip().split()
                for w in words:
                    w = re.sub(r'[^a-zA-Z]', '', w)
                    if len(w) > 4 and w.lower() not in ('about', 'their', 'these', 'those', 'which', 'where', 'never', 'actually', 'means'):
                        tags.append(w.lower())

        # Deduplicate preserving order
        seen = set()
        unique = []
        for t in tags:
            if t.lower() not in seen:
                seen.add(t.lower())
                unique.append(t)

        return unique[:30]
