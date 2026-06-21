"""
pytest configuration
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: integration tests requiring real API keys")
