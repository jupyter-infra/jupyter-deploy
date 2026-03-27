"""Pytest plugin - defines fixtures for E2E testing."""

import contextlib
import os
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any, TypeVar

import pytest
from playwright.sync_api import Page

from pytest_jupyter_deploy import constants
from pytest_jupyter_deploy.constants import DEPLOY_TIMEOUT_SECONDS, DESTROY_TIMEOUT_SECONDS
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.oauth2_proxy.ci_credentials import fetch_ci_credentials
from pytest_jupyter_deploy.oauth2_proxy.github import GitHubOAuth2ProxyApplication
from pytest_jupyter_deploy.suite_config import SuiteConfig

# Type variable for function decorators
F = TypeVar("F", bound=Callable[..., Any])


def pytest_configure(config: Any) -> None:
    """Register custom markers.

    Args:
        config: Pytest config object
    """
    config.addinivalue_line(
        "markers",
        "mutating: mark test as mutating (changes infrastructure config like instance type or volume size)",
    )
    config.addinivalue_line(
        "markers",
        "full_deployment: mark test as requiring full deployment from scratch",
    )


def skip_if_testvars_not_set(required_vars: list[str]) -> Callable[[F], F]:
    """Decorator that skips the test if any required vars are missing."""

    def decorator(func: F) -> F:
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            reason = f"Test requires environment variables: {', '.join(missing_vars)}"
            # pytest.mark.skip returns a wrapper function with the same signature
            return pytest.mark.skip(reason=reason)(func)  # type: ignore[return-value,no-any-return]

        return func

    return decorator


def pytest_addoption(parser: Any) -> None:
    """Add custom command-line options.

    Args:
        parser: Pytest parser object
    """

    # Helper to add option only if it doesn't exist
    def add_option_if_not_exists(option_name: str, **kwargs: Any) -> None:
        # Option already exists (e.g., in pytester inline runs) - suppress the ValueError
        with contextlib.suppress(ValueError):
            parser.addoption(option_name, **kwargs)

    add_option_if_not_exists(
        "--e2e-tests-dir",
        action="store",
        default=f"{constants.TESTS_DIR}/{constants.E2E_TESTS_DIR}",
        help="Path to E2E tests directory",
    )
    add_option_if_not_exists(
        "--e2e-config-name",
        action="store",
        default=constants.CONFIGURATION_DEFAULT_NAME,
        help=f"Configuration name to use from {constants.CONFIGURATIONS_DIR}/ directory",
    )
    add_option_if_not_exists(
        "--e2e-existing-project",
        action="store",
        default=None,
        help="Path to existing jupyter-deploy project (skips deployment, uses existing infrastructure)",
    )
    add_option_if_not_exists(
        "--deploy-timeout-seconds",
        action="store",
        type=int,
        default=DEPLOY_TIMEOUT_SECONDS,
        help=f"Timeout in seconds for deployment (default: {DEPLOY_TIMEOUT_SECONDS})",
    )
    add_option_if_not_exists(
        "--destroy-timeout-seconds",
        action="store",
        type=int,
        default=DESTROY_TIMEOUT_SECONDS,
        help=f"Timeout in seconds for destroy (default: {DESTROY_TIMEOUT_SECONDS})",
    )
    add_option_if_not_exists(
        "--ci",
        action="store_true",
        default=False,
        help="CI mode: automated authentication via 2FA using CI infrastructure project (requires --ci-dir)",
    )
    add_option_if_not_exists(
        "--ci-dir",
        action="store",
        default=None,
        help="Path to CI infrastructure project (required with --ci for credential fetching)",
    )
    add_option_if_not_exists(
        "--with-mutating-cases",
        action="store_true",
        default=False,
        help="Include mutating tests (tests that change infrastructure config)",
    )
    add_option_if_not_exists(
        "--destroy-after",
        action="store_true",
        default=False,
        help="Destroy deployment after tests complete (only for deployments from scratch)",
    )


def pytest_collection_modifyitems(config: Any, items: list) -> None:
    """Skip full_deployment and mutating tests when appropriate.

    Tests marked with @pytest.mark.full_deployment are only run when deploying
    from scratch (no --e2e-existing-project flag). This allows full deployment
    lifecycle tests to be automatically skipped when testing against existing
    infrastructure.

    Tests marked with @pytest.mark.mutating are only run when:
    - Deploying from scratch (no --e2e-existing-project), OR
    - Explicitly requested with --with-mutating-cases flag

    Args:
        config: Pytest config object
        items: List of collected test items
    """
    existing_project = config.getoption("--e2e-existing-project")
    with_mutating_cases = config.getoption("--with-mutating-cases")

    if existing_project:
        # Using existing project - skip deployment tests
        skip_deployment = pytest.mark.skip(reason="Skipping full deployment test (using existing project)")
        for item in items:
            if "full_deployment" in item.keywords:
                item.add_marker(skip_deployment)

        # Also skip mutating tests unless explicitly requested
        if not with_mutating_cases:
            skip_mutating = pytest.mark.skip(reason="Skipping mutating test (use --with-mutating-cases to include)")
            for item in items:
                if "mutating" in item.keywords:
                    item.add_marker(skip_mutating)


@pytest.fixture(scope="session")
def e2e_suite_dir(request: pytest.FixtureRequest) -> Path:
    """Get E2E tests directory path.

    This fixture returns the path specified by the --e2e-tests-dir option.
    This option must be provided when running e2e tests (typically via justfile).

    Args:
        request: Pytest fixture request

    Returns:
        Path to E2E tests directory
    """
    tests_dir = request.config.getoption("--e2e-tests-dir")
    return Path(tests_dir)


@pytest.fixture(scope="session")
def e2e_config(e2e_suite_dir: Path, request: pytest.FixtureRequest) -> SuiteConfig:
    """Load E2E test configuration from suite.yaml.

    Args:
        e2e_suite_dir: E2E tests directory path
        request: Pytest fixture request

    Returns:
        SuiteConfig instance with loaded configuration
    """
    existing_project = request.config.getoption("--e2e-existing-project")

    existing_project_dir = Path(existing_project) if isinstance(existing_project, str) and existing_project else None
    return SuiteConfig(suite_dir=e2e_suite_dir, existing_project_dir=existing_project_dir)


@pytest.fixture(scope="session")
def e2e_deployment(
    e2e_config: SuiteConfig, request: pytest.FixtureRequest
) -> Generator[EndToEndDeployment, None, None]:
    """Deploy infrastructure once per test session.

    This fixture:
    1. Creates a sandbox directory ({SANDBOX_E2E_DIR}/<template-name>/<timestamp>/)
    2. Manages deployment lifecycle (init, config, up, down)
    3. Yields an EndToEndDeployment instance
    4. Handles cleanup based on test results and configuration

    The deployment is lazy - it only deploys when ensure_deployed() is called.
    This allows tests to opt-in to using the deployment.

    Args:
        e2e_config: E2E configuration fixture
        e2e_suite_dir: E2E tests directory path
        request: Pytest fixture request

    Yields:
        EndToEndDeployment instance
    """
    # Get configuration options
    deploy_timeout = request.config.getoption("--deploy-timeout-seconds")
    destroy_timeout = request.config.getoption("--destroy-timeout-seconds")
    config_name = request.config.getoption("--e2e-config-name")

    # to keep mypy happy
    deploy_timeout_seconds = deploy_timeout if isinstance(deploy_timeout, int) else DEPLOY_TIMEOUT_SECONDS
    destroy_timeout_seconds = destroy_timeout if isinstance(destroy_timeout, int) else DESTROY_TIMEOUT_SECONDS
    config_name_str = config_name if isinstance(config_name, str) else constants.CONFIGURATION_DEFAULT_NAME

    # Create deployment manager (does not deploy yet)
    deployment = EndToEndDeployment(
        suite_config=e2e_config,
        config_name=config_name_str,
        deploy_timeout_seconds=deploy_timeout_seconds,
        destroy_timeout_seconds=destroy_timeout_seconds,
    )

    yield deployment

    # Cleanup only projects created by the deployment when --destroy-after is set.
    # Never cleanup existing projects (referenced by --e2e-existing-project).
    destroy_after = request.config.getoption("--destroy-after")

    if destroy_after and not e2e_config.references_existing_project():
        deployment.ensure_destroyed()


def handle_browser_context_args(browser_context_args: dict[str, Any], request: pytest.FixtureRequest) -> dict[str, Any]:
    """Configure browser context to load saved authentication state.

    This helper function should be called from test suite's conftest.py browser_context_args fixture.
    It loads the saved storage state if available, allowing tests to reuse authentication
    without re-authenticating.

    Args:
        browser_context_args: The base browser context args from pytest-playwright
        request: Pytest fixture request

    Returns:
        Updated browser context args with storage_state if available
    """
    # Always load storage state if available (both CI and local try cookies first)
    storage_state_path = Path.cwd() / constants.AUTH_DIR / constants.GITHUB_OAUTH_STATE_FILE

    if storage_state_path.exists():
        return {
            **browser_context_args,
            "storage_state": str(storage_state_path),
        }

    return {**browser_context_args}


@pytest.fixture(scope="function")
def github_oauth_app(
    page: Page, e2e_deployment: EndToEndDeployment, request: pytest.FixtureRequest
) -> GitHubOAuth2ProxyApplication:
    """Create a GitHub OAuth2 Proxy application helper.

    This fixture provides a helper for authenticating through GitHub OAuth2 Proxy
    using passkeys. It requires the 'page' fixture from pytest-playwright.

    The browser storage state (cookies, localStorage) is saved to `.auth/github-oauth-state.json`
    after successful authentication, allowing reuse across test runs.

    Note: This is function-scoped to match the 'page' fixture scope from pytest-playwright.

    Args:
        page: Playwright Page fixture (from pytest-playwright plugin)
        e2e_deployment: E2E deployment fixture
        request: Pytest fixture request

    Returns:
        GitHubOAuth2ProxyApplication instance configured with the JupyterLab URL
    """
    e2e_deployment.ensure_deployed()
    jupyterlab_url = e2e_deployment.cli.get_jupyterlab_url()

    # Define storage state path for persisting authentication
    storage_state_path = Path.cwd() / constants.AUTH_DIR / constants.GITHUB_OAUTH_STATE_FILE

    # Get CI mode from pytest option
    is_ci = request.config.getoption("--ci", default=False)

    ci_email: str | None = None
    ci_password: str | None = None
    ci_totp_fn: Callable[[], str] | None = None
    if is_ci:
        ci_dir = request.config.getoption("--ci-dir")
        if not ci_dir:
            raise pytest.UsageError("--ci requires --ci-dir <path> for credential fetching")
        ci_email, ci_password, ci_totp_fn = fetch_ci_credentials(ci_dir)

    return GitHubOAuth2ProxyApplication(
        page=page,
        jupyterlab_url=jupyterlab_url,
        storage_state_path=storage_state_path,
        is_ci=is_ci,
        ci_email=ci_email,
        ci_password=ci_password,
        ci_totp_fn=ci_totp_fn,
    )
