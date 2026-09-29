"""E2E tests for workspace home volume persistence on the EKS OIDC template.

Verifies that data written to the home volume persists across workspace
stop/start cycles — both plain files and the uv environment the workspace
image bootstraps into ``/home/jovyan``.
"""

from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.files import (
    verify_file_exists_on_server,
    verify_file_or_dir_does_not_exist_on_server,
)

SENTINEL_FILE = "e2e-persistence-test.txt"

# Small, pure-Python and not in the image's baked dependency set, so its presence
# after a restart can only come from the user's own `uv add`.
USER_PACKAGE = "ipywidgets"

# `uv add` resolves and downloads from PyPI, so it needs more headroom than an exec
# that only touches the filesystem.
_UV_TIMEOUT_SECONDS = 300


def _restart_workspace(e2e_deployment: EndToEndDeployment, name: str) -> None:
    """Stop a workspace, start it again, and wait until its pod accepts exec."""
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "stop", "--name", name])
    e2e_deployment.cli.poll_scoped_server_status(name, "Stopped", timeout_s=180)

    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "start", "--name", name])
    e2e_deployment.cli.poll_scoped_server_status(name, "Running", timeout_s=300)
    e2e_deployment.cli.wait_for_workspace_pod_exec_ready(name)


def test_home_volume_persists_across_restart(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Write a file, stop workspace, restart, verify file still exists."""
    name = e2e_workspace

    # Write a sentinel file to the home volume. The seeded workspace is only polled
    # to "Running" (not exec-readiness), so this first exec can still race with a
    # container that isn't accepting connections yet — retry on transient errors.
    e2e_deployment.cli.run_exec_with_retry(
        [
            "jupyter-deploy",
            "server",
            "exec",
            "--name",
            name,
            "--",
            f"sh -c 'echo persistence-ok > /home/jovyan/{SENTINEL_FILE}'",
        ]
    )
    verify_file_exists_on_server(e2e_deployment, f"/home/jovyan/{SENTINEL_FILE}", name=name)

    _restart_workspace(e2e_deployment, name)

    # Verify content persisted. Every exec below runs against a container that
    # just restarted and can still flap ("container not found") even after the
    # readiness gate above, so route them through run_exec_with_retry.
    result = e2e_deployment.cli.run_exec_with_retry(
        [
            "jupyter-deploy",
            "server",
            "exec",
            "--name",
            name,
            "--",
            "cat",
            f"/home/jovyan/{SENTINEL_FILE}",
        ]
    )
    assert "persistence-ok" in result.stdout

    # Cleanup
    e2e_deployment.cli.run_exec_with_retry(
        [
            "jupyter-deploy",
            "server",
            "exec",
            "--name",
            name,
            "--",
            "rm",
            "-f",
            f"/home/jovyan/{SENTINEL_FILE}",
        ]
    )
    verify_file_or_dir_does_not_exist_on_server(e2e_deployment, f"/home/jovyan/{SENTINEL_FILE}", name=name)


def test_uv_packages_persist_across_restart(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """A package the user installs with `uv add` survives a workspace stop/start.

    Asserted separately from the sentinel-file test above: the home volume can persist
    files correctly while the workspace still loses the environment, because the start
    script owns `pyproject.toml`/`uv.lock` and runs `uv sync --locked` on every boot.
    Seeding those manifests unconditionally (rather than only when absent) resets the
    user's dependency list and prunes their packages back out of `.venv` — a silent
    data loss whose only symptom is an ImportError in a notebook.
    """
    name = e2e_workspace
    exec_prefix = ["jupyter-deploy", "server", "exec", "--name", name, "--"]

    try:
        # The seeded workspace is only polled to "Running" (not exec-readiness), so this
        # first exec can still race with a container that isn't accepting connections yet.
        e2e_deployment.cli.run_exec_with_retry(
            [*exec_prefix, f"sh -c 'cd /home/jovyan && uv add {USER_PACKAGE}'"],
            timeout_seconds=_UV_TIMEOUT_SECONDS,
        )
        # Exits non-zero when the package is absent, so the call itself is the assertion.
        e2e_deployment.cli.run_exec_with_retry([*exec_prefix, "uv", "pip", "show", USER_PACKAGE])

        _restart_workspace(e2e_deployment, name)

        e2e_deployment.cli.run_exec_with_retry([*exec_prefix, "uv", "pip", "show", USER_PACKAGE])
    finally:
        # The workspace is session-scoped and shared with other modules, so put its
        # environment back the way it was found even when the assertions above fail.
        e2e_deployment.cli.run_exec_with_retry(
            [*exec_prefix, f"sh -c 'cd /home/jovyan && uv remove {USER_PACKAGE}'"],
            timeout_seconds=_UV_TIMEOUT_SECONDS,
        )
