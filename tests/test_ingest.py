"""Tests for source ingestion pipeline."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.models import Source, SourceType, SourceItem


class TestYouTubeIngester:
    """Tests for YouTube transcript ingester."""

    def test_imports(self):
        """Verify the YouTube ingester can be imported."""
        from src.ingest.youtube import YouTubeIngester
        ingester = YouTubeIngester()
        assert ingester is not None

    def test_parse_vtt_cleanup(self):
        """Test VTT subtitle cleanup removes timestamps and duplicates."""
        from src.ingest.youtube import YouTubeIngester
        ingester = YouTubeIngester()

        # Create a temporary VTT file
        import tempfile
        vtt_content = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000
Hello world

00:00:02.000 --> 00:00:04.000
Hello world

00:00:04.000 --> 00:00:06.000
This is a test
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".vtt", delete=False
        ) as f:
            f.write(vtt_content)
            vtt_path = Path(f.name)

        try:
            result = ingester._parse_vtt(vtt_path)
            assert "Hello world" in result
            assert "This is a test" in result
            # Should not have duplicate "Hello world"
            assert result.count("Hello world") == 1
        finally:
            vtt_path.unlink()

    def test_source_needs_check(self):
        """Test source freshness checking."""
        source = Source(
            id="test",
            source_type=SourceType.YOUTUBE,
            url="https://www.youtube.com/@test",
        )
        assert source.needs_check() is True


class TestSubstackIngester:
    """Tests for Substack feed ingester."""

    def test_imports(self):
        """Verify the Substack ingester can be imported."""
        from src.ingest.substack import SubstackIngester
        ingester = SubstackIngester()
        assert ingester is not None

    def test_get_feed_url(self):
        """Test feed URL derivation from various Substack URL formats."""
        from src.ingest.substack import SubstackIngester
        ingester = SubstackIngester()

        assert ingester._get_feed_url("https://example.substack.com") == \
            "https://example.substack.com/feed"
        assert ingester._get_feed_url("https://example.substack.com/") == \
            "https://example.substack.com/feed"
        assert ingester._get_feed_url("https://example.substack.com/feed") == \
            "https://example.substack.com/feed"

    def test_html_to_text(self):
        """Test HTML to text conversion."""
        from src.ingest.substack import SubstackIngester
        ingester = SubstackIngester()

        html = "<p>Hello <b>world</b></p><p>Second paragraph</p>"
        text = ingester._html_to_text(html)
        assert "Hello world" in text
        assert "Second paragraph" in text
        assert "<p>" not in text
        assert "<b>" not in text


class TestWebIngester:
    """Tests for web scraper ingester."""

    def test_imports(self):
        """Verify the web ingester can be imported."""
        from src.ingest.web import WebIngester
        ingester = WebIngester()
        assert ingester is not None

    def test_html_to_text(self):
        """Test HTML to text conversion."""
        from src.ingest.web import WebIngester
        ingester = WebIngester()

        html = "<script>var x = 1;</script><p>Content</p>"
        text = ingester._html_to_text(html)
        assert "Content" in text
        assert "var x" not in text


class TestSourceItem:
    """Tests for SourceItem model."""

    def test_content_hash(self):
        """Test automatic content hashing."""
        item = SourceItem(
            source_id="test",
            source_type=SourceType.YOUTUBE,
            url="https://example.com",
            title="Test",
            content="Hello world",
        )
        assert item.content_hash != ""
        assert len(item.content_hash) == 16

    def test_different_content_different_hash(self):
        """Test that different content produces different hashes."""
        item1 = SourceItem(
            source_id="test",
            source_type=SourceType.YOUTUBE,
            url="https://example.com",
            title="Test",
            content="Hello world",
        )
        item2 = SourceItem(
            source_id="test",
            source_type=SourceType.YOUTUBE,
            url="https://example.com",
            title="Test",
            content="Different content",
        )
        assert item1.content_hash != item2.content_hash
