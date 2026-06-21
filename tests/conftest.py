"""
pytest configuration
"""



def pytest_configure(config):
    config.addinivalue_line("markers", "integration: integration tests requiring real API keys")
