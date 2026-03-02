"""
YAML Configuration Loader

Reads and validates YAML config files for the channel network.
Supports merging defaults, per-channel overrides, and hot-reload.
"""

import os
from pathlib import Path
from typing import Any, Optional

import yaml


CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class ConfigLoader:
    """Loads and manages YAML configuration for the channel network."""

    _cache: dict[str, Any] = {}

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or CONFIG_DIR
        self._cache = {}

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """Load a single YAML file."""
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}

    def load(self, name: str, use_cache: bool = True) -> dict[str, Any]:
        """Load a config file by name (without .yml extension)."""
        if use_cache and name in self._cache:
            return self._cache[name]

        path = self.config_dir / f"{name}.yml"
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        data = self._load_yaml(path)
        self._cache[name] = data
        return data

    def load_network(self) -> dict[str, Any]:
        """Load global network configuration."""
        return self.load("network")

    def load_voice(self) -> dict[str, Any]:
        """Load writing voice configuration."""
        return self.load("voice")

    def load_stances(self) -> dict[str, Any]:
        """Load source stance configuration."""
        return self.load("stances")

    def load_charts_config(self) -> dict[str, Any]:
        """Load chart generation configuration from network.yml."""
        network = self.load_network()
        return network.get("charts", {
            "enabled": False,
            "default_theme": "publication",
            "output_formats": ["png", "svg"],
            "output_width": 680,
            "output_height": 420,
            "output_dpi": 150,
        })

    def load_channel(self, channel_slug: str) -> dict[str, Any]:
        """Load a specific channel configuration."""
        path = self.config_dir / "channels" / f"{channel_slug}.yml"
        if not path.exists():
            raise FileNotFoundError(f"Channel config not found: {path}")

        cache_key = f"channels/{channel_slug}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        data = self._load_yaml(path)
        self._cache[cache_key] = data
        return data

    def load_all_channels(self) -> dict[str, dict[str, Any]]:
        """Load all channel configurations."""
        channels_dir = self.config_dir / "channels"
        if not channels_dir.exists():
            return {}

        channels = {}
        for yml_file in sorted(channels_dir.glob("*.yml")):
            slug = yml_file.stem
            channels[slug] = self.load_channel(slug)
        return channels

    def load_sources(self, source_type: str) -> dict[str, Any]:
        """Load source definitions by type (youtube, substack, web)."""
        return self.load(f"sources/{source_type}")

    def get_stance_for_source(self, source_id: str) -> dict[str, Any]:
        """Get the stance configuration for a specific source."""
        stances = self.load_stances()
        for level_name, level_data in stances.get("stances", {}).items():
            for source in level_data.get("sources", []):
                if source.get("id") == source_id:
                    return {
                        "level_name": level_name,
                        "level": level_data.get("level", 3),
                        "description": level_data.get("description", ""),
                        "composition_notes": level_data.get("composition_notes", ""),
                        "source_notes": source.get("notes", ""),
                    }
        # Default: neutral
        return {
            "level_name": "unknown",
            "level": 3,
            "description": "Unknown source — treat with neutral skepticism.",
            "composition_notes": "Engage critically, verify claims.",
            "source_notes": "",
        }

    def reload(self) -> None:
        """Clear cache and force reload on next access."""
        self._cache.clear()

    def get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable (from .env or system)."""
        return os.environ.get(key, default)

    def require_env(self, key: str) -> str:
        """Get required environment variable, raise if missing."""
        value = os.environ.get(key)
        if not value:
            raise EnvironmentError(
                f"Required environment variable {key} is not set. "
                f"Copy .env.example to .env and fill in your keys."
            )
        return value
