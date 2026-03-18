"""E2E test configuration for tf-aws-iam-ci template."""

import pytest


def pytest_collection_modifyitems(items: list) -> None:
    """Automatically mark all tests in this directory as e2e tests."""
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
