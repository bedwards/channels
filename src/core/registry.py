"""
Plugin Registry

Auto-discovers and registers ingester, format, and publisher plugins.
Maps type strings from YAML config to plugin classes.
"""

from __future__ import annotations

from typing import Any, Type


class PluginRegistry:
    """Registry for discovering and instantiating plugins by type string."""

    _registries: dict[str, dict[str, Type]] = {}

    @classmethod
    def register(cls, category: str, type_key: str):
        """Decorator to register a plugin class.

        Usage:
            @PluginRegistry.register("ingester", "youtube")
            class YouTubeIngester(BaseIngester):
                ...
        """
        def decorator(plugin_cls: Type) -> Type:
            if category not in cls._registries:
                cls._registries[category] = {}
            cls._registries[category][type_key] = plugin_cls
            return plugin_cls
        return decorator

    @classmethod
    def get(cls, category: str, type_key: str) -> Type:
        """Get a plugin class by category and type."""
        registry = cls._registries.get(category, {})
        if type_key not in registry:
            available = list(registry.keys())
            raise KeyError(
                f"No plugin registered for {category}/{type_key}. "
                f"Available: {available}"
            )
        return registry[type_key]

    @classmethod
    def create(cls, category: str, type_key: str, **kwargs: Any) -> Any:
        """Create a plugin instance by category and type."""
        plugin_cls = cls.get(category, type_key)
        return plugin_cls(**kwargs)

    @classmethod
    def list_plugins(cls, category: str) -> list[str]:
        """List registered plugin types for a category."""
        return list(cls._registries.get(category, {}).keys())

    @classmethod
    def list_categories(cls) -> list[str]:
        """List all registered plugin categories."""
        return list(cls._registries.keys())


def discover_plugins() -> None:
    """Import all plugin modules to trigger registration.
    
    Called at startup to ensure all @PluginRegistry.register decorators run.
    """
    # Import all plugin modules — registration happens via decorators
    from src.ingest import youtube, substack, web  # noqa: F401
    from src.format import (  # noqa: F401
        notebooklm_audio, notebooklm_video,
        substack_essay, image_gen,
    )
    from src.publish import youtube as pub_youtube, substack as pub_substack  # noqa: F401
    from src.charts import builder as chart_builder  # noqa: F401
