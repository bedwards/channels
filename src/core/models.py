"""
Data Models

Core dataclasses representing the domain: sources, channels, content pieces,
publishing records, and source usage tracking.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SourceType(str, Enum):
    YOUTUBE = "youtube"
    SUBSTACK = "substack"
    WEB = "web"


class Platform(str, Enum):
    YOUTUBE = "youtube"
    SUBSTACK = "substack"


class ContentStatus(str, Enum):
    INGESTED = "ingested"           # Source downloaded
    COMPOSING = "composing"         # Draft in progress
    DRAFTED = "drafted"             # Draft ready for review
    FORMATTING = "formatting"       # Being formatted for output
    FORMATTED = "formatted"         # Ready for human steps
    AWAITING_HUMAN = "awaiting_human"  # Needs NotebookLM or review
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHED = "published"
    FAILED = "failed"


class FormatType(str, Enum):
    NOTEBOOKLM_AUDIO = "notebooklm_audio"
    NOTEBOOKLM_VIDEO = "notebooklm_video"
    SUBSTACK_ESSAY = "substack_essay"
    # Future formats
    ELEVENLABS_AUDIO = "elevenlabs_audio"
    VEO_VIDEO = "veo_video"


@dataclass
class Source:
    """A content source — a YouTube channel, Substack publication, or website."""
    id: str                        # Unique slug, e.g. "nate-b-jones"
    source_type: SourceType
    url: str
    name: str = ""
    stance_level: float = 3.0      # 1-5 agreement scale
    last_checked: Optional[datetime] = None
    check_interval_hours: int = 6

    def needs_check(self) -> bool:
        if self.last_checked is None:
            return True
        elapsed = (datetime.utcnow() - self.last_checked).total_seconds() / 3600
        return elapsed >= self.check_interval_hours


@dataclass
class SourceItem:
    """A single item from a source — one video transcript, one article, etc."""
    source_id: str
    source_type: SourceType
    url: str
    title: str
    content: str                   # Full text content
    published_at: Optional[datetime] = None
    content_hash: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.content_hash and self.content:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()[:16]


@dataclass
class Channel:
    """An output channel — one YouTube channel or Substack publication we publish to."""
    slug: str                      # e.g. "the-second-look"
    name: str                      # e.g. "The Second Look"
    platform: Platform
    format_type: FormatType
    source_ids: list[str] = field(default_factory=list)
    backup_source_ids: list[str] = field(default_factory=list)
    discovery_keywords: list[str] = field(default_factory=list)
    schedule: str = "daily"
    platform_channel_id: str = ""  # YouTube channel ID or Substack subdomain
    config: dict = field(default_factory=dict)


@dataclass
class ContentPiece:
    """A piece of content moving through the pipeline."""
    id: str                        # UUID
    channel_slug: str
    title: str = ""
    subtitle: str = ""
    draft_content: str = ""
    formatted_content: str = ""
    source_items: list[SourceItem] = field(default_factory=list)
    status: ContentStatus = ContentStatus.INGESTED
    format_type: FormatType = FormatType.SUBSTACK_ESSAY
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    notebooklm_source_doc_path: Optional[str] = None
    human_instructions: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None
    publish_url: str = ""
    error: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class PublishRecord:
    """Record of a published piece."""
    piece_id: str
    channel_slug: str
    platform: Platform
    publish_url: str
    published_at: datetime
    title: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class SourceUsage:
    """Tracks which source items were used in which content pieces.
    Prevents reusing the same source material on the same channel."""
    piece_id: str
    source_item_hash: str
    source_id: str
    channel_slug: str
    used_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DailyTask:
    """A single task in the daily human task list."""
    channel_slug: str
    channel_name: str
    task_type: str                 # "review_draft", "notebooklm", "publish", etc.
    description: str
    file_path: str = ""
    command: str = ""
    estimated_minutes: float = 2.0
    completed: bool = False
