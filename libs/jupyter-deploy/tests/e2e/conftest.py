"""E2E test configuration for jupyter-deploy CLI smoke tests."""

import pytest


def pytest_collection_modifyitems(items: list) -> None:
    """Automatically mark all tests in this directory as e2e tests."""
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "bare: tests that require the bare install track (no AWS deps)")
