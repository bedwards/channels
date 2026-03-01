"""
SQLite Database Manager

Tracks source usage, content pieces, and publishing records.
Prevents reusing the same source material on the same channel.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    ContentPiece, ContentStatus, FormatType, Platform,
    PublishRecord, SourceUsage,
)


DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "channels.db"


class Database:
    """SQLite database for source tracking and content management."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                url TEXT NOT NULL,
                name TEXT DEFAULT '',
                last_checked TEXT,
                check_interval_hours INTEGER DEFAULT 6
            );

            CREATE TABLE IF NOT EXISTS source_items (
                content_hash TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                published_at TEXT,
                metadata TEXT DEFAULT '{}',
                ingested_at TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES sources(id)
            );

            CREATE TABLE IF NOT EXISTS content_pieces (
                id TEXT PRIMARY KEY,
                channel_slug TEXT NOT NULL,
                title TEXT DEFAULT '',
                subtitle TEXT DEFAULT '',
                draft_content TEXT DEFAULT '',
                formatted_content TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'ingested',
                format_type TEXT NOT NULL,
                image_path TEXT,
                video_path TEXT,
                audio_path TEXT,
                notebooklm_source_doc_path TEXT,
                human_instructions TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                published_at TEXT,
                publish_url TEXT DEFAULT '',
                error TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS source_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                piece_id TEXT NOT NULL,
                source_item_hash TEXT NOT NULL,
                source_id TEXT NOT NULL,
                channel_slug TEXT NOT NULL,
                used_at TEXT NOT NULL,
                FOREIGN KEY (piece_id) REFERENCES content_pieces(id),
                FOREIGN KEY (source_item_hash) REFERENCES source_items(content_hash),
                UNIQUE(source_item_hash, channel_slug)
            );

            CREATE TABLE IF NOT EXISTS publish_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                piece_id TEXT NOT NULL,
                channel_slug TEXT NOT NULL,
                platform TEXT NOT NULL,
                publish_url TEXT NOT NULL,
                published_at TEXT NOT NULL,
                title TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (piece_id) REFERENCES content_pieces(id)
            );

            CREATE INDEX IF NOT EXISTS idx_source_items_source
                ON source_items(source_id);
            CREATE INDEX IF NOT EXISTS idx_source_items_published
                ON source_items(published_at);
            CREATE INDEX IF NOT EXISTS idx_content_pieces_channel
                ON content_pieces(channel_slug);
            CREATE INDEX IF NOT EXISTS idx_content_pieces_status
                ON content_pieces(status);
            CREATE INDEX IF NOT EXISTS idx_source_usage_channel
                ON source_usage(channel_slug);
            CREATE INDEX IF NOT EXISTS idx_source_usage_source
                ON source_usage(source_id);
        """)
        self.conn.commit()

    # --- Source Items ---

    def has_source_item(self, content_hash: str) -> bool:
        """Check if a source item has already been ingested."""
        row = self.conn.execute(
            "SELECT 1 FROM source_items WHERE content_hash = ?",
            (content_hash,)
        ).fetchone()
        return row is not None

    def save_source_item(
        self, content_hash: str, source_id: str, source_type: str,
        url: str, title: str, content: str,
        published_at: Optional[str] = None, metadata: Optional[dict] = None
    ) -> None:
        """Save a new source item."""
        self.conn.execute(
            """INSERT OR IGNORE INTO source_items
               (content_hash, source_id, source_type, url, title, content,
                published_at, metadata, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                content_hash, source_id, source_type, url, title, content,
                published_at, json.dumps(metadata or {}),
                datetime.utcnow().isoformat()
            )
        )
        self.conn.commit()

    # --- Source Usage (dedup) ---

    def is_source_used_on_channel(
        self, source_item_hash: str, channel_slug: str
    ) -> bool:
        """Check if a source item has already been used on a channel."""
        row = self.conn.execute(
            """SELECT 1 FROM source_usage
               WHERE source_item_hash = ? AND channel_slug = ?""",
            (source_item_hash, channel_slug)
        ).fetchone()
        return row is not None

    def record_source_usage(self, usage: SourceUsage) -> None:
        """Record that a source item was used in a content piece."""
        self.conn.execute(
            """INSERT OR IGNORE INTO source_usage
               (piece_id, source_item_hash, source_id, channel_slug, used_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                usage.piece_id, usage.source_item_hash, usage.source_id,
                usage.channel_slug, usage.used_at.isoformat()
            )
        )
        self.conn.commit()

    def get_used_source_hashes_for_channel(
        self, channel_slug: str
    ) -> set[str]:
        """Get all source item hashes already used on a channel."""
        rows = self.conn.execute(
            "SELECT source_item_hash FROM source_usage WHERE channel_slug = ?",
            (channel_slug,)
        ).fetchall()
        return {row["source_item_hash"] for row in rows}

    # --- Content Pieces ---

    def save_content_piece(self, piece: ContentPiece) -> None:
        """Save or update a content piece."""
        self.conn.execute(
            """INSERT OR REPLACE INTO content_pieces
               (id, channel_slug, title, subtitle, draft_content,
                formatted_content, status, format_type, image_path,
                video_path, audio_path, notebooklm_source_doc_path,
                human_instructions, created_at, published_at, publish_url,
                error, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                piece.id, piece.channel_slug, piece.title, piece.subtitle,
                piece.draft_content, piece.formatted_content, piece.status.value,
                piece.format_type.value, piece.image_path, piece.video_path,
                piece.audio_path, piece.notebooklm_source_doc_path,
                piece.human_instructions, piece.created_at.isoformat(),
                piece.published_at.isoformat() if piece.published_at else None,
                piece.publish_url, piece.error, json.dumps(piece.metadata)
            )
        )
        self.conn.commit()

    def get_pending_pieces(
        self, channel_slug: Optional[str] = None
    ) -> list[dict]:
        """Get content pieces that aren't published yet."""
        if channel_slug:
            rows = self.conn.execute(
                """SELECT * FROM content_pieces
                   WHERE channel_slug = ? AND status != 'published'
                   ORDER BY created_at DESC""",
                (channel_slug,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT * FROM content_pieces
                   WHERE status != 'published'
                   ORDER BY created_at DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def get_today_pieces(self, channel_slug: str) -> list[dict]:
        """Get pieces created today for a channel."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        rows = self.conn.execute(
            """SELECT * FROM content_pieces
               WHERE channel_slug = ? AND created_at LIKE ?
               ORDER BY created_at DESC""",
            (channel_slug, f"{today}%")
        ).fetchall()
        return [dict(row) for row in rows]

    def update_piece_status(
        self, piece_id: str, status: ContentStatus, error: str = ""
    ) -> None:
        """Update a content piece's status."""
        self.conn.execute(
            "UPDATE content_pieces SET status = ?, error = ? WHERE id = ?",
            (status.value, error, piece_id)
        )
        self.conn.commit()

    # --- Publish Records ---

    def save_publish_record(self, record: PublishRecord) -> None:
        """Save a publishing record."""
        self.conn.execute(
            """INSERT INTO publish_records
               (piece_id, channel_slug, platform, publish_url, published_at,
                title, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                record.piece_id, record.channel_slug, record.platform.value,
                record.publish_url, record.published_at.isoformat(),
                record.title, json.dumps(record.metadata)
            )
        )
        self.conn.commit()

    def get_channel_publish_count(
        self, channel_slug: str, date: Optional[str] = None
    ) -> int:
        """Get number of published pieces for a channel on a date."""
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        row = self.conn.execute(
            """SELECT COUNT(*) as cnt FROM publish_records
               WHERE channel_slug = ? AND published_at LIKE ?""",
            (channel_slug, f"{date}%")
        ).fetchone()
        return row["cnt"] if row else 0

    # --- Sources ---

    def update_source_last_checked(self, source_id: str) -> None:
        """Update the last_checked timestamp for a source."""
        self.conn.execute(
            """INSERT OR REPLACE INTO sources (id, source_type, url, last_checked)
               VALUES (
                 COALESCE((SELECT id FROM sources WHERE id = ?), ?),
                 COALESCE((SELECT source_type FROM sources WHERE id = ?), 'unknown'),
                 COALESCE((SELECT url FROM sources WHERE id = ?), ''),
                 ?
               )""",
            (source_id, source_id, source_id, source_id,
             datetime.utcnow().isoformat())
        )
        self.conn.commit()

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()
