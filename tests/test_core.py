"""Tests for core infrastructure."""

import pytest
import tempfile
from pathlib import Path

from src.core.config import ConfigLoader
from src.core.database import Database
from src.core.models import (
    ContentPiece, ContentStatus, FormatType, SourceUsage,
)
from src.core.registry import PluginRegistry


class TestConfigLoader:
    """Tests for YAML configuration loader."""

    def test_load_network(self):
        """Test loading network config."""
        config = ConfigLoader()
        network = config.load_network()
        assert "network" in network
        assert "freshness" in network

    def test_load_voice(self):
        """Test loading voice config."""
        config = ConfigLoader()
        voice = config.load_voice()
        assert "voice" in voice
        assert "system_prompt" in voice["voice"]

    def test_load_stances(self):
        """Test loading stance config."""
        config = ConfigLoader()
        stances = config.load_stances()
        assert "stances" in stances

    def test_get_stance_for_source(self):
        """Test looking up stance by source ID."""
        config = ConfigLoader()
        
        stance = config.get_stance_for_source("sam-harris")
        assert stance["level"] == 1
        assert stance["level_name"] == "disagree_substantially"

        stance = config.get_stance_for_source("nate-b-jones")
        assert stance["level"] == 4
        assert stance["level_name"] == "mostly_agree"

        # Unknown source returns neutral default
        stance = config.get_stance_for_source("nonexistent")
        assert stance["level"] == 3
        assert stance["level_name"] == "unknown"

    def test_load_all_channels(self):
        """Test loading all channel configs."""
        config = ConfigLoader()
        channels = config.load_all_channels()
        assert len(channels) >= 9
        assert "the-second-look" in channels
        assert "carbon-and-ink" in channels

    def test_cache_and_reload(self):
        """Test config caching and reload."""
        config = ConfigLoader()
        # Load twice — should use cache
        config.load_network()
        config.load_network()
        assert "network" in config._cache

        # Reload clears cache
        config.reload()
        assert len(config._cache) == 0


class TestDatabase:
    """Tests for SQLite database."""

    def setup_method(self):
        """Create a temp database for each test."""
        self.tmp = tempfile.mkdtemp()
        self.db = Database(db_path=Path(self.tmp) / "test.db")

    def teardown_method(self):
        """Clean up temp database."""
        self.db.close()

    def test_source_item_tracking(self):
        """Test saving and checking source items."""
        self.db.save_source_item(
            content_hash="abc123",
            source_id="test-source",
            source_type="youtube",
            url="https://example.com",
            title="Test Video",
            content="Sample content",
        )
        assert self.db.has_source_item("abc123")
        assert not self.db.has_source_item("xyz789")

    def test_source_usage_dedup(self):
        """Test that source usage prevents duplicate use on same channel."""
        usage = SourceUsage(
            piece_id="piece-1",
            source_item_hash="abc123",
            source_id="test-source",
            channel_slug="test-channel",
        )
        self.db.record_source_usage(usage)

        assert self.db.is_source_used_on_channel("abc123", "test-channel")
        assert not self.db.is_source_used_on_channel("abc123", "other-channel")
        assert not self.db.is_source_used_on_channel("xyz789", "test-channel")

    def test_get_used_hashes(self):
        """Test getting all used hashes for a channel."""
        for i in range(3):
            self.db.record_source_usage(SourceUsage(
                piece_id=f"piece-{i}",
                source_item_hash=f"hash-{i}",
                source_id="source",
                channel_slug="test-channel",
            ))

        hashes = self.db.get_used_source_hashes_for_channel("test-channel")
        assert len(hashes) == 3
        assert "hash-0" in hashes
        assert "hash-2" in hashes

    def test_content_piece_crud(self):
        """Test saving and querying content pieces."""
        piece = ContentPiece(
            id="test-piece-1",
            channel_slug="test-channel",
            title="Test Title",
            draft_content="Draft content here",
            status=ContentStatus.DRAFTED,
            format_type=FormatType.SUBSTACK_ESSAY,
        )
        self.db.save_content_piece(piece)

        pending = self.db.get_pending_pieces("test-channel")
        assert len(pending) == 1
        assert pending[0]["title"] == "Test Title"

        # Update status
        self.db.update_piece_status("test-piece-1", ContentStatus.PUBLISHED)
        pending = self.db.get_pending_pieces("test-channel")
        assert len(pending) == 0


class TestPluginRegistry:
    """Tests for plugin registry."""

    def test_register_and_get(self):
        """Test registering and retrieving a plugin."""
        @PluginRegistry.register("test_cat", "test_type")
        class TestPlugin:
            pass

        retrieved = PluginRegistry.get("test_cat", "test_type")
        assert retrieved is TestPlugin

    def test_missing_plugin_raises(self):
        """Test that missing plugin raises KeyError."""
        with pytest.raises(KeyError):
            PluginRegistry.get("nonexistent", "nothing")

    def test_create_instance(self):
        """Test creating plugin instances."""
        @PluginRegistry.register("test_cat2", "test_type2")
        class AnotherPlugin:
            def __init__(self):
                self.initialized = True

        instance = PluginRegistry.create("test_cat2", "test_type2")
        assert instance.initialized is True

    def test_list_plugins(self):
        """Test listing registered plugins."""
        @PluginRegistry.register("list_test", "alpha")
        class Alpha:
            pass

        @PluginRegistry.register("list_test", "beta")
        class Beta:
            pass

        plugins = PluginRegistry.list_plugins("list_test")
        assert "alpha" in plugins
        assert "beta" in plugins
