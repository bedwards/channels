"""
Auto-Responder

Generates and posts AI-powered replies to comments on our published content.
Maintains the channel voice while engaging genuinely with commenters.
"""

import os
from datetime import datetime
from typing import Optional

from src.core.config import ConfigLoader
from src.core.database import Database


class AutoResponder:
    """Generates contextual, voice-consistent replies to comments."""

    def __init__(
        self,
        config: Optional[ConfigLoader] = None,
        db: Optional[Database] = None,
    ):
        self.config = config or ConfigLoader()
        self.db = db or Database()
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create comment tracking tables if they don't exist."""
        self.db.conn.executescript("""
            CREATE TABLE IF NOT EXISTS comment_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id TEXT NOT NULL UNIQUE,
                channel_slug TEXT NOT NULL,
                platform TEXT NOT NULL,
                original_text TEXT NOT NULL,
                reply_text TEXT NOT NULL,
                replied_at TEXT NOT NULL,
                post_id TEXT DEFAULT '',
                author TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS comment_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_slug TEXT NOT NULL,
                comment_id TEXT NOT NULL,
                feedback_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                incorporated BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (comment_id) REFERENCES comment_replies(comment_id)
            );

            CREATE INDEX IF NOT EXISTS idx_feedback_channel
                ON comment_feedback(channel_slug);
            CREATE INDEX IF NOT EXISTS idx_feedback_incorporated
                ON comment_feedback(incorporated);
        """)
        self.db.conn.commit()

    def generate_reply(
        self, comment: dict, post_content: str = ""
    ) -> Optional[str]:
        """Generate a reply to a comment using the channel voice.

        Args:
            comment: Dict with platform, channel_slug, text, author, post_title.
            post_content: The original post content for context.

        Returns:
            Generated reply text, or None if comment doesn't warrant a reply.
        """
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return None

        voice_config = self.config.load_voice()
        channel_config = self.config.load_channel(comment["channel_slug"])

        # Classify the comment first
        comment_type = self._classify_comment(comment["text"])

        # Skip spam, trolling, or comments that don't warrant engagement
        if comment_type in ("spam", "troll", "irrelevant"):
            return None

        system_prompt = f"""You are responding to a comment on the {channel_config['name']} channel.

VOICE: {voice_config.get('voice', {}).get('system_prompt', '')[:500]}

RULES FOR REPLIES:
1. Be genuine and substantive — never generic "thanks for watching!" responses
2. If they make a good point, acknowledge it specifically and build on it
3. If they disagree, engage with the strongest version of their argument
4. If they correct a factual error, thank them and commit to accuracy
5. Keep replies concise (2-4 sentences) unless the comment warrants depth
6. Never be defensive, never be sycophantic
7. If they raise a topic for future content, note it naturally
8. Match the commenter's tone — if they're thoughtful, be thoughtful
9. Never use exclamation marks more than once
10. Sign off naturally, no forced calls to action

COMMENT TYPE: {comment_type}
"""

        prompt = f"""Comment on "{comment.get('post_title', 'our post')}":
Author: {comment.get('author', 'Anonymous')}
Comment: {comment['text']}

{f'Post excerpt for context: {post_content[:1000]}' if post_content else ''}

Generate a genuine, voice-consistent reply:"""

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                "gemini-2.5-flash-preview-04-17",
                system_instruction=system_prompt,
            )
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Reply generation failed: {e}")
            return None

    def post_reply(self, comment: dict, reply_text: str) -> bool:
        """Post a reply to a comment on the original platform.

        Args:
            comment: The original comment dict.
            reply_text: Generated reply text.

        Returns:
            True if reply was posted successfully.
        """
        success = False

        if comment["platform"] == "youtube":
            success = self._post_youtube_reply(comment, reply_text)
        elif comment["platform"] == "substack":
            # Substack reply posting would go here
            print(f"  📋 Substack reply (manual): {reply_text[:100]}...")

        # Record the reply regardless of posting success
        self._record_reply(comment, reply_text)

        return success

    def _post_youtube_reply(
        self, comment: dict, reply_text: str
    ) -> bool:
        """Post a reply to a YouTube comment."""
        try:
            # Need OAuth credentials for posting replies
            from src.publish.youtube import YouTubePublisher
            publisher = YouTubePublisher()
            service = publisher._get_youtube_service()

            if not service:
                return False

            service.comments().insert(
                part="snippet",
                body={
                    "snippet": {
                        "parentId": comment["comment_id"],
                        "textOriginal": reply_text,
                    }
                },
            ).execute()

            print(f"  ✅ Replied to {comment['author']} on YouTube")
            return True

        except Exception as e:
            print(f"  ❌ YouTube reply failed: {e}")
            return False

    def _record_reply(self, comment: dict, reply_text: str) -> None:
        """Record a reply in the database."""
        self.db.conn.execute(
            """INSERT OR IGNORE INTO comment_replies
               (comment_id, channel_slug, platform, original_text, 
                reply_text, replied_at, post_id, author)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                comment["comment_id"],
                comment["channel_slug"],
                comment["platform"],
                comment["text"],
                reply_text,
                datetime.utcnow().isoformat(),
                comment.get("post_id", ""),
                comment.get("author", ""),
            ),
        )
        self.db.conn.commit()

    def _classify_comment(self, text: str) -> str:
        """Classify a comment type for appropriate response strategy.

        Returns: 'substantive', 'question', 'correction', 'praise',
                 'disagreement', 'spam', 'troll', 'irrelevant'
        """
        text_lower = text.lower().strip()

        # Quick heuristic classification (Gemini used for ambiguous cases)
        if len(text_lower) < 10:
            if any(w in text_lower for w in ["spam", "sub4sub", "check my"]):
                return "spam"
            return "praise"  # Short positive comments

        if "?" in text:
            return "question"

        if any(w in text_lower for w in [
            "actually", "correction", "wrong", "incorrect", "mistake"
        ]):
            return "correction"

        if any(w in text_lower for w in [
            "disagree", "but", "however", "that said", "counter",
            "what about", "on the other hand"
        ]):
            return "disagreement"

        if any(w in text_lower for w in [
            "great", "love", "amazing", "excellent", "thank",
            "helpful", "best", "fantastic"
        ]):
            return "praise"

        return "substantive"

    def process_all_comments(
        self, channel_slug: Optional[str] = None,
        dry_run: bool = False,
    ) -> list[dict]:
        """Process all unanswered comments across channels.

        Returns list of {comment, reply, posted} dicts.
        """
        from src.engage.monitor import CommentMonitor
        monitor = CommentMonitor(self.config, self.db)

        unanswered = monitor.get_unanswered_comments(channel_slug)
        results = []

        for comment in unanswered:
            reply = self.generate_reply(comment)
            if not reply:
                continue

            result = {
                "comment": comment,
                "reply": reply,
                "posted": False,
            }

            if not dry_run:
                result["posted"] = self.post_reply(comment, reply)
            else:
                print(f"\n  💬 {comment['author']}: {comment['text'][:80]}...")
                print(f"  ↪️  Reply: {reply[:100]}...")

            results.append(result)

        return results
