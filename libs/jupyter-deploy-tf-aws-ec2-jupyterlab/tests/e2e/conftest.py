"""E2E test configuration for the aws-ec2-jupyterlab template.

The pytest-jupyter-deploy plugin provides the fixtures these tests use automatically:
- e2e_config: load configuration from the suite
- e2e_deployment: deploy / configure infrastructure
- client_proxy_app: JupyterLab reached through the local client proxy (no OAuth)

This template's configuration tests need AWS credentials but NO test env vars (no domain,
OAuth, or email) — that is the point of the template. The only env vars any test here needs
are the instance types / retention value the mutating pass switches between.
"""

import contextlib
import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pytest_jupyter_deploy.auth_sidecars.aws_auth_sidecar import caller_principal as parse_caller_principal
from pytest_jupyter_deploy.cli import JDCli
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.undeployed_project import undeployed_project


def pytest_collection_modifyitems(items: list) -> None:
    """Automatically mark all tests in this directory as e2e tests.

    The `cli` + `mutating` exclusion is enforced by the plugin's own hook, for every suite at once.
    """
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


# --------------------------------------------------------------------------- mutating-pass config


@pytest.fixture(scope="session")
def cpu_instance_type() -> str:
    """Return the CPU instance type the second in-place apply switches back to.

    Raises:
        ValueError: If JD_E2E_CPU_INSTANCE is not set.
    """
    cpu_instance = os.getenv("JD_E2E_CPU_INSTANCE")
    if not cpu_instance:
        raise ValueError("JD_E2E_CPU_INSTANCE environment variable must be set")
    return cpu_instance


@pytest.fixture(scope="session")
def gpu_instance_type() -> str:
    """Return the GPU instance type the first in-place apply switches to.

    Raises:
        ValueError: If JD_E2E_GPU_INSTANCE is not set.
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
        ValueError: If JD_E2E_AVAILABILITY_ZONE is not set.
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
        ValueError: If JD_E2E_ALT_AVAILABILITY_ZONE is not set.
    """
    alt_zone = os.getenv("JD_E2E_ALT_AVAILABILITY_ZONE")
    if not alt_zone:
        raise ValueError("JD_E2E_ALT_AVAILABILITY_ZONE environment variable must be set")
    return alt_zone


@pytest.fixture(scope="session")
def larger_log_retention_days() -> int:
    """Return a log-retention value distinct from the default, for the config-change assertion.

    Raises:
        ValueError: If JD_E2E_LARGER_LOG_RETENTION_DAYS is not set.
    """
    retention_days = os.getenv("JD_E2E_LARGER_LOG_RETENTION_DAYS")
    if not retention_days:
        raise ValueError("JD_E2E_LARGER_LOG_RETENTION_DAYS environment variable must be set")
    return int(retention_days)


# --------------------------------------------------------------------------- deployment identity


@pytest.fixture(scope="session")
def caller_principal() -> tuple[str, str]:
    """Return the calling AWS identity as ``(kind, name)`` — "role"/"user" plus the IAM name.

    Session-scoped: the identity the test process runs as cannot change mid-run. Every auth
    test dispatches on this rather than hard-coding `jd teams` or `jd users`, because the
    sidecar matches an assumed-role caller against the role allowlist and an IAM-user caller
    against the user allowlist.
    """
    return parse_caller_principal()


@pytest.fixture(scope="session")
def deployment_id(e2e_deployment: EndToEndDeployment) -> str:
    """Return the deployment id, which is also the auth-sidecar binding id (``x-k8s-aws-id``)."""
    e2e_deployment.ensure_deployed()
    return e2e_deployment.cli.get_str_output("deployment_id")


@pytest.fixture(scope="session")
def aws_region(e2e_deployment: EndToEndDeployment) -> str:
    """Return the region the deployment lives in (read from the template output, not the env)."""
    e2e_deployment.ensure_deployed()
    return e2e_deployment.cli.get_str_output("region")


@pytest.fixture
def connect_bundle(e2e_deployment: EndToEndDeployment) -> dict:
    """Return a fresh ``jd proxy connect-info`` bundle (host, port, ca_cert, headers, expires_at).

    Function-scoped on purpose: the token inside expires in ~60s, and ``host`` is the
    instance's public IP, which changes across a host stop/start. A session-scoped bundle
    would go stale mid-run in both dimensions.
    """
    e2e_deployment.ensure_host_running()
    return e2e_deployment.cli.get_connect_bundle()


# --------------------------------------------------------------------------- shared proxy


@pytest.fixture
def running_proxy(e2e_deployment: EndToEndDeployment) -> Iterator[str]:
    """Start a detached proxy and yield its loopback origin, stopping it on teardown.

    **Function-scoped, deliberately.** An earlier draft made this module-scoped to share one
    `jd proxy start` (a ``connect-info`` round-trip plus a bind, ~5s) across the read-only proxy
    tests. That is unsound: the proxy is a per-project singleton, and the lifecycle tests in the
    same file legitimately call `jd proxy stop`, which terminates *every* live proxy for the
    project — including one a module-scoped fixture owns. The fixture would then keep handing out
    a cached URL to a dead port, and every later test would fail with a connection refused whose
    cause is three tests upstream. ~5s per test is the correct price for a singleton resource.
    """
    e2e_deployment.ensure_server_running()
    url = e2e_deployment.cli.start_proxy(replace=True)
    try:
        yield url
    finally:
        e2e_deployment.cli.stop_proxy_if_running()


# --------------------------------------------------------------------------- undeployed projects


@pytest.fixture(scope="module")
def initialized_project(e2e_deployment: EndToEndDeployment) -> Iterator[tuple[Path, JDCli]]:
    """Yield one ``jd init``-ed (not configured) throwaway project shared by the module.

    Module-scoped so read-only assertions about generated files share a single init. Tests
    that mutate or corrupt the project must open their own ``undeployed_project()`` instead.
    """
    with undeployed_project(e2e_deployment.suite_config) as project:
        yield project


@pytest.fixture(scope="module")
def configured_project(e2e_deployment: EndToEndDeployment) -> Iterator[tuple[Path, JDCli]]:
    """Yield one ``jd init`` + ``jd config``-ed throwaway project shared by the module.

    A `jd config` is a ``terraform init`` + ``plan``, the most expensive thing in this suite,
    so the tests that only read its results share one.
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.configure_project(cli=cli)
        yield project_path, cli


# --------------------------------------------------------------------------- allowlist safety net


@pytest.fixture(scope="module")
def restore_allowlist(e2e_deployment: EndToEndDeployment) -> Iterator[None]:
    """Snapshot both IAM allowlists and restore them on teardown.

    Mandatory, not optional, for any module that edits the allowlist: the revocation tests
    deliberately lock the caller out of the app, and a failure between revoke and restore
    would 403 every later test in the file. Recovery runs over SSM, which the `jd users` /
    `jd teams` commands use and which is entirely independent of the proxy/auth path — so it
    works even while the caller has no access to JupyterLab itself.
    """
    e2e_deployment.ensure_deployed()
    teams = e2e_deployment.get_allowlisted_teams()
    users = e2e_deployment.get_allowlisted_users()
    try:
        yield
    finally:
        with contextlib.suppress(Exception):
            _restore_group(e2e_deployment, "teams", teams)
        with contextlib.suppress(Exception):
            _restore_group(e2e_deployment, "users", users)


def _restore_group(e2e_deployment: EndToEndDeployment, group: str, names: list[str]) -> None:
    """Set ``group``'s allowlist back to ``names`` (``jd <group> remove`` clears it if empty)."""
    current = e2e_deployment.get_allowlisted_teams() if group == "teams" else e2e_deployment.get_allowlisted_users()
    if sorted(n.lower() for n in current) == sorted(n.lower() for n in names):
        return
    if names:
        e2e_deployment.cli.run_command(["jupyter-deploy", group, "set", *names])
    elif current:
        e2e_deployment.cli.run_command(["jupyter-deploy", group, "remove", *current])


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
