"""
pytest configuration
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: integration tests requiring real API keys")


@pytest.fixture(autouse=True)
def _mock_pendo_track(monkeypatch):
    """Prevent real Pendo HTTP calls in all tests."""
    monkeypatch.setattr("harness.pendo.track", lambda *args, **kwargs: None)
