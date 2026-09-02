"""E2E test configuration for the aws-ec2-jupyterlab template.

The pytest-jupyter-deploy plugin provides the fixtures these tests use automatically:
- e2e_config: load configuration from the suite
- e2e_deployment: deploy / configure infrastructure
- client_proxy_app: JupyterLab reached through the local client proxy (no OAuth)

This template's configuration tests need AWS credentials but NO test env vars (no domain,
OAuth, or email) — that is the point of the template.
"""

import re
from pathlib import Path
from typing import Any

import pytest


def pytest_collection_modifyitems(items: list) -> None:
    """Automatically mark all tests in this directory as e2e tests."""
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Any:
    """Save page HTML content on browser-test failures for debugging.

    Mirrors the base template's hook but keys on the ``client_proxy_app`` fixture, since this
    template reaches JupyterLab through the local proxy rather than GitHub OAuth.
    """
    outcome = yield
    report = outcome.get_result()

    if report.when != "call" or not report.failed:
        return

    page = None
    if "client_proxy_app" in item.fixturenames:  # type: ignore[attr-defined]
        client_proxy_app = item.funcargs.get("client_proxy_app")  # type: ignore[attr-defined]
        if client_proxy_app is not None and hasattr(client_proxy_app, "page"):
            page = client_proxy_app.page

    if page is None:
        return

    try:
        # Match pytest-playwright's screenshot directory naming convention.
        browser_name = page.context.browser.browser_type.name if page.context.browser else "unknown"
        test_name = item.nodeid.replace("/", "-").replace(".py::", "-py-").replace("_", "-")
        test_name = re.sub(r"\[.*?\]", "", test_name)

        test_dir = Path("test-results") / f"{test_name}-{browser_name}"
        test_dir.mkdir(parents=True, exist_ok=True)

        (test_dir / "test-failed.html").write_text(page.content(), encoding="utf-8")
        (test_dir / "test-failed-metadata.txt").write_text(
            f"URL: {page.url}\nTitle: {page.title()}\n", encoding="utf-8"
        )

        console_messages = page.console_messages()
        console_text = (
            "\n".join(f"[{msg.type}] {msg.text}" for msg in console_messages)
            if console_messages
            else "No console messages captured.\n"
        )
        (test_dir / "test-failed-console.txt").write_text(console_text, encoding="utf-8")

        print(f"\n📄 Saved page artifacts to: {test_dir}/")
    except Exception as e:
        print(f"\n⚠️  Could not save page artifacts: {e}")
