"""
Feedback Loop

Extracts actionable feedback from audience comments and incorporates
it into the content generation formula for each channel.

This creates a virtuous cycle:
  Comments → Feedback extraction → Channel-specific adjustments → Better content
"""

import json
import os
from datetime import datetime
from typing import Optional

from src.core.config import ConfigLoader
from src.core.database import Database


class FeedbackLoop:
    """Extracts and incorporates audience feedback into content generation."""

    def __init__(
        self,
        config: Optional[ConfigLoader] = None,
        db: Optional[Database] = None,
    ):
        self.config = config or ConfigLoader()
        self.db = db or Database()

    def extract_feedback(
        self, comments: list[dict], channel_slug: str
    ) -> list[dict]:
        """Analyze comments to extract actionable feedback.

        Categorizes feedback into:
        - topic_requests: Topics viewers want covered
        - corrections: Factual corrections to incorporate
        - style_feedback: Preferences about format, length, tone
        - disagreements: Substantive disagreements to engage with
        - recurring_themes: Patterns across multiple comments

        Returns list of feedback items with type and summary.
        """
        if not comments:
            return []

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return []

        # Batch comments for analysis
        comments_text = "\n\n".join(
            f"[{c.get('author', 'Anon')}]: {c['text']}"
            for c in comments[:50]  # Cap at 50 comments per batch
        )

        prompt = f"""Analyze these audience comments from the channel "{channel_slug}" 
and extract actionable feedback. Group into these categories:

1. TOPIC_REQUESTS — Topics, questions, or subjects viewers want covered
2. CORRECTIONS — Factual corrections or clarifications needed
3. STYLE_FEEDBACK — Preferences about format, length, tone, structure
4. DISAGREEMENTS — Substantive disagreements worth engaging with in future content
5. RECURRING_THEMES — Patterns or sentiments that appear across multiple comments

For each item, provide:
- category (one of the above)
- summary (1-2 sentences)
- strength (how many comments support this, or how strong the signal is: weak/moderate/strong)
- actionable (specific suggestion for how to incorporate this)

Comments:
{comments_text}

Format as a JSON array with keys: category, summary, strength, actionable.
Return only actionable items — skip generic praise and spam.
"""

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
            response = model.generate_content(prompt)

            import re
            json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if json_match:
                feedback_items = json.loads(json_match.group())

                # Save to database
                for item in feedback_items:
                    self._save_feedback(channel_slug, item)

                return feedback_items

        except Exception as e:
            print(f"Feedback extraction failed: {e}")

        return []

    def get_channel_feedback_context(
        self, channel_slug: str, limit: int = 10
    ) -> str:
        """Get accumulated feedback for a channel as a context string
        to inject into the content composition prompt.

        This is the key integration point: feedback from comments
        directly shapes future content generation.

        Returns:
            Markdown-formatted feedback context string.
        """
        try:
            rows = self.db.conn.execute(
                """SELECT feedback_type, summary, created_at
                   FROM comment_feedback
                   WHERE channel_slug = ? AND incorporated = 0
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (channel_slug, limit)
            ).fetchall()
        except Exception:
            return ""

        if not rows:
            return ""

        sections = {
            "topic_requests": [],
            "corrections": [],
            "style_feedback": [],
            "disagreements": [],
            "recurring_themes": [],
        }

        for row in rows:
            ftype = row["feedback_type"]
            if ftype in sections:
                sections[ftype].append(row["summary"])

        context = "\n## Audience Feedback (incorporate into content)\n\n"

        if sections["topic_requests"]:
            context += "### Topics Requested by Audience\n"
            for item in sections["topic_requests"]:
                context += f"- {item}\n"
            context += "\n"

        if sections["corrections"]:
            context += "### Corrections to Address\n"
            for item in sections["corrections"]:
                context += f"- ⚠️ {item}\n"
            context += "\n"

        if sections["style_feedback"]:
            context += "### Style Preferences\n"
            for item in sections["style_feedback"]:
                context += f"- {item}\n"
            context += "\n"

        if sections["disagreements"]:
            context += "### Substantive Disagreements to Engage\n"
            for item in sections["disagreements"]:
                context += f"- {item}\n"
            context += "\n"

        if sections["recurring_themes"]:
            context += "### Recurring Themes\n"
            for item in sections["recurring_themes"]:
                context += f"- {item}\n"
            context += "\n"

        return context

    def mark_feedback_incorporated(
        self, channel_slug: str
    ) -> int:
        """Mark all unincorporated feedback for a channel as incorporated.

        Called after content is composed using the feedback context.
        Returns number of items marked.
        """
        cursor = self.db.conn.execute(
            """UPDATE comment_feedback
               SET incorporated = 1
               WHERE channel_slug = ? AND incorporated = 0""",
            (channel_slug,)
        )
        self.db.conn.commit()
        return cursor.rowcount

    def get_feedback_summary(
        self, channel_slug: Optional[str] = None
    ) -> dict:
        """Get summary of feedback status across channels."""
        if channel_slug:
            where = "WHERE channel_slug = ?"
            params = (channel_slug,)
        else:
            where = ""
            params = ()

        try:
            total = self.db.conn.execute(
                f"SELECT COUNT(*) as cnt FROM comment_feedback {where}",
                params
            ).fetchone()["cnt"]

            pending = self.db.conn.execute(
                f"""SELECT COUNT(*) as cnt FROM comment_feedback
                    {where} {'AND' if where else 'WHERE'} incorporated = 0""",
                params
            ).fetchone()["cnt"]

            return {
                "total_feedback": total,
                "pending": pending,
                "incorporated": total - pending,
            }
        except Exception:
            return {"total_feedback": 0, "pending": 0, "incorporated": 0}

    def _save_feedback(self, channel_slug: str, item: dict) -> None:
        """Save a feedback item to the database."""
        self.db.conn.execute(
            """INSERT INTO comment_feedback
               (channel_slug, comment_id, feedback_type, summary,
                incorporated, created_at)
               VALUES (?, ?, ?, ?, 0, ?)""",
            (
                channel_slug,
                "",  # Aggregated feedback, not tied to single comment
                item.get("category", "unknown"),
                item.get("summary", ""),
                datetime.utcnow().isoformat(),
            ),
        )
        self.db.conn.commit()
