"""
YouTube Transcript Ingester

Downloads transcripts from YouTube channels using yt-dlp.
Parses auto-generated subtitles into clean text.
"""

import json
import re
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.core.models import Source, SourceItem, SourceType
from src.core.registry import PluginRegistry
from .base import BaseIngester


@PluginRegistry.register("ingester", "youtube")
class YouTubeIngester(BaseIngester):
    """Ingests transcripts from YouTube channels via yt-dlp."""

    def fetch_latest(
        self, source: Source, max_items: int = 5,
        since_hours: Optional[int] = None
    ) -> list[SourceItem]:
        """Fetch latest video transcripts from a YouTube channel."""
        # Get video list from channel (respects source.tab for streams vs videos)
        tab = getattr(source, 'tab', 'videos')
        videos = self._list_channel_videos(source.url, max_items, tab=tab)

        items = []
        for video in videos:
            # Filter by date if requested
            if since_hours and video.get("upload_date"):
                upload_dt = datetime.strptime(video["upload_date"], "%Y%m%d")
                cutoff = datetime.utcnow() - timedelta(hours=since_hours)
                if upload_dt < cutoff:
                    continue

            # Download transcript
            item = self._download_transcript(video, source)
            if item:
                items.append(item)

        return items[:max_items]

    def fetch_item(self, url: str, source: Source) -> Optional[SourceItem]:
        """Fetch transcript for a single YouTube video."""
        video_info = self._get_video_info(url)
        if not video_info:
            return None
        return self._download_transcript(video_info, source)

    def _list_channel_videos(
        self, channel_url: str, max_items: int = 10,
        tab: str = "videos"
    ) -> list[dict]:
        """List latest videos from a channel without downloading.

        Args:
            tab: YouTube tab — 'videos' (default) or 'streams' (lives only)
        """
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--print", "%(id)s|||%(title)s|||%(upload_date)s|||%(url)s",
            "--playlist-end", str(max_items),
            f"{channel_url}/{tab}",
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                print(f"yt-dlp list failed: {result.stderr[:200]}")
                return []

            videos = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("|||")
                if len(parts) >= 3:
                    videos.append({
                        "id": parts[0],
                        "title": parts[1],
                        "upload_date": parts[2] if parts[2] != "NA" else None,
                        "url": f"https://www.youtube.com/watch?v={parts[0]}",
                    })
            return videos

        except subprocess.TimeoutExpired:
            print(f"yt-dlp timed out for {channel_url}")
            return []

    def _get_video_info(self, url: str) -> Optional[dict]:
        """Get metadata for a single video."""
        cmd = [
            "yt-dlp",
            "--print", "%(id)s|||%(title)s|||%(upload_date)s",
            "--skip-download",
            url,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return None
            parts = result.stdout.strip().split("|||")
            if len(parts) >= 2:
                return {
                    "id": parts[0],
                    "title": parts[1],
                    "upload_date": parts[2] if len(parts) > 2 and parts[2] != "NA" else None,
                    "url": url,
                }
        except subprocess.TimeoutExpired:
            pass
        return None

    def _download_transcript(
        self, video: dict, source: Source
    ) -> Optional[SourceItem]:
        """Download and parse the transcript for a video."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_template = str(Path(tmpdir) / "%(id)s")

            cmd = [
                "yt-dlp",
                "--write-auto-sub",
                "--sub-langs", "en",
                "--sub-format", "json3",
                "--skip-download",
                "--output", output_template,
                video["url"],
            ]

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=60
                )
                if result.returncode != 0:
                    # Try vtt format as fallback
                    return self._download_transcript_vtt(video, source)

                # Find the subtitle file
                sub_files = list(Path(tmpdir).glob("*.json3"))
                if not sub_files:
                    return self._download_transcript_vtt(video, source)

                # Parse JSON3 subtitles
                transcript = self._parse_json3(sub_files[0])

            except (subprocess.TimeoutExpired, Exception) as e:
                print(f"Transcript download failed for {video['id']}: {e}")
                return None

        if not transcript:
            return None

        published_at = None
        if video.get("upload_date"):
            try:
                published_at = datetime.strptime(video["upload_date"], "%Y%m%d")
            except ValueError:
                pass

        return SourceItem(
            source_id=source.id,
            source_type=SourceType.YOUTUBE,
            url=video["url"],
            title=video.get("title", ""),
            content=transcript,
            published_at=published_at,
            metadata={
                "video_id": video["id"],
                "channel_url": source.url,
            },
        )

    def _download_transcript_vtt(
        self, video: dict, source: Source
    ) -> Optional[SourceItem]:
        """Fallback: download VTT subtitles and parse to plain text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_template = str(Path(tmpdir) / "%(id)s")

            cmd = [
                "yt-dlp",
                "--write-auto-sub",
                "--sub-langs", "en",
                "--sub-format", "vtt",
                "--skip-download",
                "--output", output_template,
                video["url"],
            ]

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=60
                )
                if result.returncode != 0:
                    return None

                vtt_files = list(Path(tmpdir).glob("*.vtt"))
                if not vtt_files:
                    return None

                transcript = self._parse_vtt(vtt_files[0])

            except Exception:
                return None

        if not transcript:
            return None

        published_at = None
        if video.get("upload_date"):
            try:
                published_at = datetime.strptime(video["upload_date"], "%Y%m%d")
            except ValueError:
                pass

        return SourceItem(
            source_id=source.id,
            source_type=SourceType.YOUTUBE,
            url=video["url"],
            title=video.get("title", ""),
            content=transcript,
            published_at=published_at,
            metadata={
                "video_id": video["id"],
                "channel_url": source.url,
                "format": "vtt",
            },
        )

    def _parse_json3(self, path: Path) -> str:
        """Parse YouTube JSON3 subtitle format into clean text."""
        with open(path, "r") as f:
            data = json.load(f)

        segments = []
        for event in data.get("events", []):
            segs = event.get("segs", [])
            text = "".join(s.get("utf8", "") for s in segs).strip()
            if text and text != "\n":
                segments.append(text)

        # Deduplicate consecutive identical segments
        deduped = []
        for seg in segments:
            if not deduped or seg != deduped[-1]:
                deduped.append(seg)

        return " ".join(deduped)

    def _parse_vtt(self, path: Path) -> str:
        """Parse VTT subtitle file into clean text."""
        with open(path, "r") as f:
            content = f.read()

        # Remove VTT header and timestamps
        lines = content.split("\n")
        text_lines = []
        for line in lines:
            line = line.strip()
            # Skip headers, timestamps, and empty lines
            if not line or line.startswith("WEBVTT") or line.startswith("Kind:"):
                continue
            if line.startswith("Language:") or line.startswith("NOTE"):
                continue
            if re.match(r"^\d{2}:\d{2}:\d{2}", line):
                continue
            if re.match(r"^\d+$", line):
                continue
            # Remove HTML tags
            line = re.sub(r"<[^>]+>", "", line)
            if line:
                text_lines.append(line)

        # Deduplicate
        deduped = []
        for line in text_lines:
            if not deduped or line != deduped[-1]:
                deduped.append(line)

        return " ".join(deduped)
