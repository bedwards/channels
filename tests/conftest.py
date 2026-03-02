"""Pytest configuration for the channels test suite."""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests requiring the graphyard database on studio (192.168.4.50)",
    )
