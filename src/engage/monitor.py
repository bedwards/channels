"""
Comment Monitor

Monitors comments on published posts across YouTube and Substack.
Fetches new comments since last check for auto-reply and feedback.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from src.core.config import ConfigLoader
from src.core.database import Database


class CommentMonitor:
    """Monitors comments across all channels and platforms."""

    def __init__(
        self,
        config: Optional[ConfigLoader] = None,
        db: Optional[Database] = None,
    ):
        self.config = config or ConfigLoader()
        self.db = db or Database()

    def fetch_new_comments(
        self, channel_slug: Optional[str] = None
    ) -> list[dict]:
        """Fetch all new comments since last check.

        Returns list of comment dicts with:
            - platform, channel_slug, post_id, post_title
            - comment_id, author, text, timestamp
            - parent_id (if reply), sentiment
        """
        channels = self.config.load_all_channels()
        all_comments = []

        for slug, ch_config in channels.items():
            if channel_slug and slug != channel_slug:
                continue

            platform = ch_config.get("platform", "")
            if platform == "youtube":
                comments = self._fetch_youtube_comments(slug, ch_config)
            elif platform == "substack":
                comments = self._fetch_substack_comments(slug, ch_config)
            else:
                continue

            all_comments.extend(comments)

        return all_comments

    def _fetch_youtube_comments(
        self, slug: str, config: dict
    ) -> list[dict]:
        """Fetch new YouTube comments via Data API v3."""
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return []

        try:
            from googleapiclient.discovery import build
            service = build("youtube", "v3", developerKey=api_key)

            # Get our recent videos
            channel_id = config.get("publish", {}).get("channel_id", "")
            if not channel_id:
                return []

            # List recent videos
            videos_response = service.search().list(
                part="id,snippet",
                channelId=channel_id,
                order="date",
                maxResults=10,
                type="video",
            ).execute()

            comments = []
            for video in videos_response.get("items", []):
                video_id = video["id"]["videoId"]
                video_title = video["snippet"]["title"]

                try:
                    comments_response = service.commentThreads().list(
                        part="snippet",
                        videoId=video_id,
                        maxResults=100,
                        order="time",
                    ).execute()

                    for thread in comments_response.get("items", []):
                        snippet = thread["snippet"]["topLevelComment"]["snippet"]
                        comment = {
                            "platform": "youtube",
                            "channel_slug": slug,
                            "post_id": video_id,
                            "post_title": video_title,
                            "comment_id": thread["id"],
                            "author": snippet.get("authorDisplayName", ""),
                            "text": snippet.get("textDisplay", ""),
                            "timestamp": snippet.get("publishedAt", ""),
                            "parent_id": None,
                            "like_count": snippet.get("likeCount", 0),
                        }
                        comments.append(comment)

                        # Get replies
                        if thread["snippet"].get("totalReplyCount", 0) > 0:
                            replies_response = service.comments().list(
                                part="snippet",
                                parentId=thread["id"],
                                maxResults=50,
                            ).execute()

                            for reply in replies_response.get("items", []):
                                r_snippet = reply["snippet"]
                                comments.append({
                                    "platform": "youtube",
                                    "channel_slug": slug,
                                    "post_id": video_id,
                                    "post_title": video_title,
                                    "comment_id": reply["id"],
                                    "author": r_snippet.get("authorDisplayName", ""),
                                    "text": r_snippet.get("textDisplay", ""),
                                    "timestamp": r_snippet.get("publishedAt", ""),
                                    "parent_id": r_snippet.get("parentId"),
                                    "like_count": r_snippet.get("likeCount", 0),
                                })

                except Exception as e:
                    print(f"  ⚠️ Comments disabled or error for {video_id}: {e}")

            return comments

        except Exception as e:
            print(f"YouTube comment fetch failed for {slug}: {e}")
            return []

    def _fetch_substack_comments(
        self, slug: str, config: dict
    ) -> list[dict]:
        """Fetch Substack comments.

        Note: Substack doesn't expose comments in RSS. This uses the
        unofficial API or web scraping as a best-effort approach.
        """
        # Substack comments require authenticated API access
        # For now, log that manual check is needed
        return []

    def get_unanswered_comments(
        self, channel_slug: Optional[str] = None
    ) -> list[dict]:
        """Get comments that haven't been replied to yet."""
        all_comments = self.fetch_new_comments(channel_slug)

        # Filter to comments that aren't from us and aren't replies
        # (we track our replies in the DB)
        replied_ids = self._get_replied_comment_ids()

        unanswered = [
            c for c in all_comments
            if c["comment_id"] not in replied_ids
            and c["parent_id"] is None  # Top-level comments only
        ]

        return unanswered

    def _get_replied_comment_ids(self) -> set[str]:
        """Get set of comment IDs we've already replied to."""
        try:
            rows = self.db.conn.execute(
                "SELECT comment_id FROM comment_replies"
            ).fetchall()
            return {row["comment_id"] for row in rows}
        except Exception:
            # Table may not exist yet
            return set()
