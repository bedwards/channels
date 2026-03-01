"""
Daily Operations System

Generates the daily task list, coordinates the pipeline for all channels,
and produces clear human instructions for the 30-60 minute daily workflow.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.config import ConfigLoader
from src.core.database import Database
from src.core.models import (
    Channel, ContentPiece, ContentStatus, DailyTask,
    FormatType, Platform, Source, SourceType, SourceUsage,
)
from src.core.registry import PluginRegistry
from src.ingest.discovery import SourceDiscovery
from src.compose.writer import ContentComposer


CONTENT_DIR = Path(__file__).parent.parent.parent / "data" / "content"


class DailyRunner:
    """Orchestrates the daily content pipeline for all channels."""

    def __init__(
        self,
        config: Optional[ConfigLoader] = None,
        db: Optional[Database] = None,
    ):
        self.config = config or ConfigLoader()
        self.db = db or Database()
        self.discovery = SourceDiscovery(self.config)
        self.composer = ContentComposer(self.config)

    def run_daily(self, dry_run: bool = False) -> list[DailyTask]:
        """Run the daily pipeline for all channels.

        Returns:
            List of DailyTask items for human execution.
        """
        channels = self.config.load_all_channels()
        all_tasks: list[DailyTask] = []

        print(f"\n{'═' * 60}")
        print(f"  DAILY PIPELINE — {datetime.now().strftime('%B %d, %Y')}")
        print(f"{'═' * 60}\n")

        for slug, channel_config in channels.items():
            print(f"\n📺 Processing: {channel_config['name']} ({slug})")
            print(f"{'─' * 40}")

            try:
                tasks = self._process_channel(slug, channel_config, dry_run)
                all_tasks.extend(tasks)
            except Exception as e:
                print(f"  ❌ Error: {e}")
                all_tasks.append(DailyTask(
                    channel_slug=slug,
                    channel_name=channel_config["name"],
                    task_type="error",
                    description=f"Pipeline failed: {e}",
                    estimated_minutes=5,
                ))

        # Print human task summary
        self._print_task_summary(all_tasks)

        return all_tasks

    def _process_channel(
        self, slug: str, channel_config: dict, dry_run: bool
    ) -> list[DailyTask]:
        """Process a single channel through the pipeline."""
        tasks: list[DailyTask] = []

        # Check if we already have content for today
        today_pieces = self.db.get_today_pieces(slug)
        if today_pieces:
            print(f"  ✅ Already have {len(today_pieces)} piece(s) for today")
            # Check if any need human action
            for piece_row in today_pieces:
                if piece_row["status"] in (
                    ContentStatus.AWAITING_HUMAN.value,
                    ContentStatus.READY_TO_PUBLISH.value,
                ):
                    tasks.append(self._create_publish_task(
                        slug, channel_config, piece_row
                    ))
            return tasks

        # 1. Find fresh sources
        print(f"  🔍 Finding fresh sources...")
        source_items = self.discovery.find_fresh_sources(slug, needed_count=2)

        if not source_items:
            print(f"  ⚠️ No fresh sources found")
            tasks.append(DailyTask(
                channel_slug=slug,
                channel_name=channel_config["name"],
                task_type="no_sources",
                description="No fresh sources available. Check backup sources or add new ones.",
                estimated_minutes=10,
            ))
            return tasks

        # Filter out already-used sources
        used_hashes = self.db.get_used_source_hashes_for_channel(slug)
        source_items = [
            item for item in source_items
            if item.content_hash not in used_hashes
        ]

        if not source_items:
            print(f"  ⚠️ All available sources already used on this channel")
            return tasks

        print(f"  ✅ Found {len(source_items)} fresh source(s)")
        for item in source_items:
            print(f"     → {item.title[:60]}")

        if dry_run:
            tasks.append(DailyTask(
                channel_slug=slug,
                channel_name=channel_config["name"],
                task_type="dry_run",
                description=f"Would compose from {len(source_items)} source(s)",
                estimated_minutes=0,
            ))
            return tasks

        # 2. Compose content
        print(f"  ✍️ Composing content...")
        channel = Channel(
            slug=slug,
            name=channel_config["name"],
            platform=Platform(channel_config["platform"]),
            format_type=FormatType(channel_config["format"]["plugin"]),
        )

        try:
            piece = self.composer.compose(channel, source_items)
            print(f"  ✅ Draft composed: {piece.title[:60]}")
        except Exception as e:
            print(f"  ❌ Composition failed: {e}")
            tasks.append(DailyTask(
                channel_slug=slug,
                channel_name=channel_config["name"],
                task_type="error",
                description=f"Content composition failed: {e}",
                estimated_minutes=5,
            ))
            return tasks

        # 3. Format content
        print(f"  🎨 Formatting...")
        format_plugin_name = channel_config["format"]["plugin"]
        try:
            formatter = PluginRegistry.create("formatter", format_plugin_name)
            output_dir = CONTENT_DIR / slug / datetime.now().strftime("%Y-%m-%d")
            piece = formatter.format(piece, output_dir)
            print(f"  ✅ Formatted as {format_plugin_name}")
        except Exception as e:
            print(f"  ❌ Formatting failed: {e}")
            # Save draft anyway
            output_dir = CONTENT_DIR / slug / datetime.now().strftime("%Y-%m-%d")
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "draft.md").write_text(piece.draft_content)
            piece.status = ContentStatus.DRAFTED

        # 4. Save to database
        self.db.save_content_piece(piece)
        for item in source_items:
            self.db.save_source_item(
                content_hash=item.content_hash,
                source_id=item.source_id,
                source_type=item.source_type.value,
                url=item.url,
                title=item.title,
                content=item.content[:500],  # Store summary only
                published_at=item.published_at.isoformat() if item.published_at else None,
            )
            self.db.record_source_usage(SourceUsage(
                piece_id=piece.id,
                source_item_hash=item.content_hash,
                source_id=item.source_id,
                channel_slug=slug,
            ))

        # 5. Generate human tasks
        tasks.extend(self._generate_human_tasks(slug, channel_config, piece))

        return tasks

    def _generate_human_tasks(
        self, slug: str, channel_config: dict, piece: ContentPiece
    ) -> list[DailyTask]:
        """Generate the human task list for a processed piece."""
        tasks = []

        # Review draft
        tasks.append(DailyTask(
            channel_slug=slug,
            channel_name=channel_config["name"],
            task_type="review_draft",
            description="Review the composed draft for quality and accuracy",
            file_path=str(CONTENT_DIR / slug / datetime.now().strftime("%Y-%m-%d") / "draft.md"),
            estimated_minutes=3,
        ))

        # NotebookLM step (if applicable)
        format_plugin = channel_config["format"]["plugin"]
        if format_plugin in ("notebooklm_audio", "notebooklm_video"):
            overview_type = "Audio" if "audio" in format_plugin else "Video"
            tasks.append(DailyTask(
                channel_slug=slug,
                channel_name=channel_config["name"],
                task_type="notebooklm",
                description=(
                    f"Open NotebookLM → Upload source doc → "
                    f"Generate {overview_type} Overview → Download"
                ),
                file_path=piece.notebooklm_source_doc_path or "",
                estimated_minutes=5,
            ))

        # Publish
        tasks.append(DailyTask(
            channel_slug=slug,
            channel_name=channel_config["name"],
            task_type="publish",
            description=f"Publish to {channel_config['platform']}",
            command=f"python -m src.cli publish {slug}",
            estimated_minutes=2,
        ))

        return tasks

    def _create_publish_task(
        self, slug: str, channel_config: dict, piece_row: dict
    ) -> DailyTask:
        """Create a task for a piece that needs publishing."""
        return DailyTask(
            channel_slug=slug,
            channel_name=channel_config["name"],
            task_type="publish",
            description=f"Publish pending piece: {piece_row.get('title', 'Untitled')}",
            command=f"python -m src.cli publish {slug}",
            estimated_minutes=2,
        )

    def _print_task_summary(self, tasks: list[DailyTask]) -> None:
        """Print human-readable task summary."""
        total_minutes = sum(t.estimated_minutes for t in tasks)

        print(f"\n{'═' * 60}")
        print(f"  YOUR DAILY TASK LIST")
        print(f"  ⏱  Estimated time: {int(total_minutes)} minutes")
        print(f"{'═' * 60}\n")

        current_channel = None
        task_num = 0

        for task in tasks:
            if task.channel_slug != current_channel:
                current_channel = task.channel_slug
                print(f"\n  📺 {task.channel_name.upper()}")
                print(f"  {'─' * 40}")

            task_num += 1
            icon = {
                "review_draft": "📝",
                "notebooklm": "🎙️",
                "publish": "📤",
                "no_sources": "⚠️",
                "error": "❌",
                "dry_run": "🧪",
            }.get(task.task_type, "📋")

            print(f"  {icon} {task_num}. {task.description}")
            if task.file_path:
                print(f"     📁 {task.file_path}")
            if task.command:
                print(f"     💻 {task.command}")

        print(f"\n{'═' * 60}\n")
