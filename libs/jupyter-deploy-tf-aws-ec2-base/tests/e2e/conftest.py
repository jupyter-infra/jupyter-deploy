"""E2E test configuration for aws-ec2-base template.

The pytest-jupyter-deploy plugin provides these fixtures automatically:
- e2e_config: Load configuration from suite.yaml
- e2e_deployment: Deploy infrastructure once per session
- github_oauth_app: GitHub OAuth2 Proxy authentication helper
"""

import contextlib
import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.plugin import handle_browser_context_args


def pytest_collection_modifyitems(items: list) -> None:
    """Automatically mark all tests in this directory as e2e tests."""
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Any:
    """Save page HTML content on test failures for debugging.

    This hook captures the full HTML of the page when a test fails,
    which is useful for debugging issues that aren't visible in screenshots alone
    (e.g., checking if 'Server Connection Error' text is actually in the DOM).
    """
    # Execute the test
    outcome = yield
    report = outcome.get_result()

    # Only process failures during the 'call' phase (actual test execution)
    if report.when == "call" and report.failed:
        # Check if the test has access to a playwright page
        page = None
        if "github_oauth_app" in item.fixturenames:  # type: ignore[attr-defined]
            github_oauth_app = item.funcargs.get("github_oauth_app")  # type: ignore[attr-defined]
            if github_oauth_app and hasattr(github_oauth_app, "page"):
                page = github_oauth_app.page

        if page:
            # Save debugging artifacts in the same directory where pytest-playwright saves screenshots
            # Match pytest-playwright's directory naming convention exactly
            try:
                # Get browser name
                browser_name = page.context.browser.browser_type.name if page.context.browser else "unknown"

                # Replicate pytest-playwright's sanitization logic:
                # 1. Replace / with -
                # 2. Replace .py:: with -py-
                # 3. Replace _ with -
                # 4. Remove [parameterization] brackets
                # 5. Append -browser_name
                test_name = item.nodeid
                test_name = test_name.replace("/", "-")
                test_name = test_name.replace(".py::", "-py-")
                test_name = test_name.replace("_", "-")
                # Remove parameterization like [firefox]
                test_name = re.sub(r"\[.*?\]", "", test_name)

                # Create directory matching pytest-playwright's structure
                test_results_dir = Path("test-results")
                test_dir = test_results_dir / f"{test_name}-{browser_name}"
                test_dir.mkdir(parents=True, exist_ok=True)

                # Save HTML content
                html_path = test_dir / "test-failed.html"
                html_content = page.content()
                html_path.write_text(html_content, encoding="utf-8")

                # Save page metadata (URL, title)
                metadata_path = test_dir / "test-failed-metadata.txt"
                metadata = f"URL: {page.url}\nTitle: {page.title()}\n"
                metadata_path.write_text(metadata, encoding="utf-8")

                # Save console messages
                console_path = test_dir / "test-failed-console.txt"
                console_messages = page.console_messages()
                if console_messages:
                    console_text = "\n".join([f"[{msg.type}] {msg.text}" for msg in console_messages])
                    console_path.write_text(console_text, encoding="utf-8")
                else:
                    console_path.write_text("No console messages captured.\n", encoding="utf-8")

                print(f"\n📄 Saved page artifacts to: {test_dir}/")
                print("   - test-failed.html (page HTML)")
                print("   - test-failed-metadata.txt (URL, title)")
                print("   - test-failed-console.txt (console messages)")
            except Exception as e:
                print(f"\n⚠️  Could not save page artifacts: {e}")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any], request: pytest.FixtureRequest) -> dict[str, Any]:
    """Configure browser context to load saved authentication state.

    This fixture overrides pytest-playwright's browser_context_args to load
    saved GitHub OAuth cookies from .auth/github-oauth-state.json.
    """
    return handle_browser_context_args(browser_context_args, request)


@pytest.fixture(scope="session")
def logged_user() -> str:
    """Return GitHub username the browser is logged in as

    Raises:
        ValueError: If JD_E2E_USER is not set
    """
    user = os.getenv("JD_E2E_USER")
    if not user:
        raise ValueError("JD_E2E_USER environment variable must be set")
    return user


@pytest.fixture(scope="session")
def safe_user() -> str:
    """Returns a trusted GitHub username the browser is not logged in as.

    Raises:
        ValueError: If JD_E2E_SAFE_USER is not set
    """
    user = os.getenv("JD_E2E_SAFE_USER")
    if not user:
        raise ValueError("JD_E2E_SAFE_USER environment variable must be set")
    return user


@pytest.fixture(scope="session")
def safe_org() -> str:
    """Returns a safe organization name for testing.

    Raises:
        ValueError: If JD_E2E_SAFE_ORG is not set
    """
    org = os.getenv("JD_E2E_SAFE_ORG")
    if not org:
        raise ValueError("JD_E2E_SAFE_ORG environment variable must be set")
    return org


@pytest.fixture(scope="session")
def logged_org() -> str:
    """Return GitHub organization the browser user belongs to.

    Raises:
        ValueError: If JD_E2E_ORG is not set
    """
    org = os.getenv("JD_E2E_ORG")
    if not org:
        raise ValueError("JD_E2E_ORG environment variable must be set")
    return org


@pytest.fixture(scope="session")
def logged_team() -> str:
    """Return GitHub team the browser user belongs to.

    Raises:
        ValueError: If JD_E2E_TEAM is not set
    """
    team = os.getenv("JD_E2E_TEAM")
    if not team:
        raise ValueError("JD_E2E_TEAM environment variable must be set")
    return team


@pytest.fixture(scope="session")
def safe_team() -> str:
    """Returns a safe team name the logged user does not belong to.

    Raises:
        ValueError: If JD_E2E_SAFE_TEAM is not set
    """
    team = os.getenv("JD_E2E_SAFE_TEAM")
    if not team:
        raise ValueError("JD_E2E_SAFE_TEAM environment variable must be set")
    return team


@pytest.fixture(scope="session")
def larger_instance_type() -> str:
    """Returns a larger instance type for upgrade tests.

    Raises:
        ValueError: If JD_E2E_LARGER_INSTANCE is not set
    """
    larger_instance_type = os.getenv("JD_E2E_LARGER_INSTANCE")
    if not larger_instance_type:
        raise ValueError("JD_E2E_LARGER_INSTANCE environment variable must be set")
    return larger_instance_type


@pytest.fixture(scope="session")
def larger_log_retention_days() -> int:
    """Returns a larger log retention days value for config change tests.

    Raises:
        ValueError: If JD_E2E_LARGER_LOG_RETENTION_DAYS is not set
    """
    larger_log_retention_days = os.getenv("JD_E2E_LARGER_LOG_RETENTION_DAYS")
    if not larger_log_retention_days:
        raise ValueError("JD_E2E_LARGER_LOG_RETENTION_DAYS environment variable must be set")
    return int(larger_log_retention_days)


@pytest.fixture(scope="session")
def gpu_instance_type() -> str:
    """Returns a GPU instance type for GPU deployment tests.

    Raises:
        ValueError: If JD_E2E_GPU_INSTANCE is not set
    """
    gpu_instance = os.getenv("JD_E2E_GPU_INSTANCE")
    if not gpu_instance:
        raise ValueError("JD_E2E_GPU_INSTANCE environment variable must be set")
    return gpu_instance


@pytest.fixture(scope="session")
def base_availability_zone() -> str:
    """Return the zone the suite deploys into, which the volume tests pin the deployment back to.

    Read from the same env var the suite's variables config expands, so "the base zone" cannot mean
    two different things in the same run.

    Raises:
        ValueError: If JD_E2E_AVAILABILITY_ZONE is not set
    """
    base_zone = os.getenv("JD_E2E_AVAILABILITY_ZONE")
    if not base_zone:
        raise ValueError("JD_E2E_AVAILABILITY_ZONE environment variable must be set")
    return base_zone


@pytest.fixture(scope="session")
def alt_availability_zone() -> str:
    """Return a zone the deployment is NOT in, for the volume-preserving zone swap.

    Must be a zone the default VPC has a subnet in, since the template selects its subnet by zone.
    Not derived from the current zone by incrementing a letter: not every account has a subnet in
    every zone, and a swap into a zone with no subnet fails in a way that looks like a template bug.

    Raises:
        ValueError: If JD_E2E_ALT_AVAILABILITY_ZONE is not set
    """
    alt_zone = os.getenv("JD_E2E_ALT_AVAILABILITY_ZONE")
    if not alt_zone:
        raise ValueError("JD_E2E_ALT_AVAILABILITY_ZONE environment variable must be set")
    return alt_zone


# --------------------------------------------------------------------------- allowlist safety net


@pytest.fixture(scope="module")
def restore_allowlist(e2e_deployment: EndToEndDeployment, logged_user: str) -> Iterator[None]:
    """Put the allowlist back to the deployment's baseline on teardown: the logged user, nothing else.

    Mandatory, not optional, for any module that edits the allowlist through the variables: a
    failure between a grant and its revoke would leave a probe entry in place and change what every
    later access test is asserting against. Recovery runs over SSM, which is independent of the
    OAuth path, so it works even if the app itself is unreachable.

    Restores to a BASELINE rather than to a snapshot of whatever was there. Same convention as every
    other module in this suite, which declares the allowlist it needs at setup (`ensure_authorized`)
    instead of inheriting one — and it costs two SSM round-trips instead of six.

    Users are restored first because update-auth.sh refuses an operation that would leave nobody
    authorized at all -- `organization unset` on an empty user list is exactly that.

    Touches the file on the instance only. The terraform variables are deliberately left as the test
    left them: rewriting them would mean a `jd config` + `jd up` in fixture teardown, and a failure
    there would be reported against whichever test happened to be last.
    """
    e2e_deployment.ensure_deployed()
    try:
        yield
    finally:
        # Suppressed as a whole: a teardown that fails because the deployment is broken must not
        # replace the real test failure with its own.
        with contextlib.suppress(Exception):
            e2e_deployment.ensure_authorized([logged_user], "", [])
            # ensure_authorized no-ops on empty args, so the probe team needs an explicit clear.
            e2e_deployment.ensure_no_org_nor_teams_allowlisted()


# --------------------------------------------------------------------------- coding agents


@pytest.fixture(scope="module")
def bedrock_enabled_project(e2e_deployment: EndToEndDeployment, request: pytest.FixtureRequest) -> Iterator[None]:
    """A project with bedrock_enabled set to true.

    That is the default, so this only acts on an existing project that turned it off: there it
    changes the project, which only happens where mutating cases may run, and the module restores
    the previous value afterwards. Elsewhere the module is skipped.
    """
    e2e_deployment.ensure_deployed()
    if e2e_deployment.get_bool_variable_value("bedrock_enabled"):
        yield
        return

    existing_project = request.config.getoption("--e2e-existing-project")
    if existing_project and not request.config.getoption("--with-mutating-cases"):
        pytest.skip(
            "bedrock_enabled is false on this project: pass --with-mutating-cases to turn it on for this module"
        )

    previous = e2e_deployment.read_override_value("bedrock_enabled")
    e2e_deployment.ensure_deployed_with_overrides({"bedrock_enabled": True})
    try:
        yield
    finally:
        if previous is None:
            e2e_deployment.ensure_deployed_with(["--reset-variable", "bedrock_enabled"])
        else:
            e2e_deployment.ensure_deployed_with_overrides({"bedrock_enabled": previous})
