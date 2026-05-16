"""E2E tests for server (workspace) commands on the EKS OIDC template.

Relies on `seeded_cluster` (session-scoped) for pagination and scope filtering.
Uses `e2e_workspace` (admin, always Running) for list/status/show/logs/exec tests.
Uses `other_user_workspace` (private, owned by a different user) for stop/start —
verifying that an admin can manage another user's private workspace.
"""

import json
import subprocess

import pytest
from pytest_jupyter_deploy.cli import JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.workspaces.kubectl import (
    kubectl_get_workspace_owner,
    kubectl_get_workspace_ownership_type,
)

from .conftest import IMPERSONATED_USER


def _list_servers_json(
    e2e_deployment: EndToEndDeployment,
    scope: str | None = None,
    limit: int | None = None,
    continue_from: str | None = None,
) -> dict:
    cmd = ["jupyter-deploy", "server", "list", "--json"]
    if scope is not None:
        cmd.extend(["--scope", scope])
    if limit is not None:
        cmd.extend(["-n", str(limit)])
    if continue_from is not None:
        cmd.extend(["--continue-from", continue_from])
    result = e2e_deployment.cli.run_command(cmd)
    return json.loads(result.stdout)


# ── server list ─────────────────────────────────────────────────────────────


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_server_list_contains_workspace(
    e2e_deployment: EndToEndDeployment, e2e_workspace: str, seeded_cluster: dict[str, list[str]]
) -> None:
    """Verify that server list includes the test workspace and seeded workspaces."""
    data = _list_servers_json(e2e_deployment)
    assert e2e_workspace in data["servers"], f"Expected '{e2e_workspace}' in: {data['servers']}"
    for ws in seeded_cluster["seeded"]:
        assert ws in data["servers"], f"Expected '{ws}' in: {data['servers']}"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_server_list__with_scope_contains_workspace(
    e2e_deployment: EndToEndDeployment, e2e_workspace: str, seeded_cluster: dict[str, list[str]]
) -> None:
    """Verify that server list with --scope includes the test workspace and seeded workspaces."""
    data = _list_servers_json(e2e_deployment, "default")
    assert e2e_workspace in data["servers"], f"Expected '{e2e_workspace}' in: {data['servers']}"
    for ws in seeded_cluster["seeded"]:
        assert ws in data["servers"], f"Expected '{ws}' in: {data['servers']}"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_server_list_json(
    e2e_deployment: EndToEndDeployment, e2e_workspace: str, seeded_cluster: dict[str, list[str]]
) -> None:
    """Verify that server list --json returns valid JSON with expected structure."""
    data = _list_servers_json(e2e_deployment)
    assert "servers" in data, f"Expected 'servers' key in JSON, got: {list(data.keys())}"
    assert isinstance(data["servers"], list), f"Expected list, got {type(data['servers'])}"
    total = len(seeded_cluster["seeded"]) + len(seeded_cluster["admin"])
    assert len(data["servers"]) >= total, f"Expected at least {total} servers, got {len(data['servers'])}"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_server_list_with_scope(
    e2e_deployment: EndToEndDeployment, e2e_workspace: str, seeded_cluster: dict[str, list[str]]
) -> None:
    """Verify that --scope filters server list."""
    data = _list_servers_json(e2e_deployment, scope="default")
    assert e2e_workspace in data["servers"], f"Expected workspace in default scope: {data['servers']}"

    data = _list_servers_json(e2e_deployment, scope="nonexistent-ns")
    assert len(data["servers"]) == 0, f"Expected empty list for nonexistent scope, got: {data['servers']}"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_server_list_paginate_full(
    e2e_deployment: EndToEndDeployment, e2e_workspace: str, seeded_cluster: dict[str, list[str]]
) -> None:
    """Paginate through servers one at a time and verify distinct results."""
    # Page 1
    page1 = _list_servers_json(e2e_deployment, limit=1)
    assert len(page1["servers"]) == 1, f"Expected 1 server on page 1, got {len(page1['servers'])}"
    token1 = page1.get("continue_from")
    assert token1, "Expected a pagination token after requesting 1 of 3+ servers"

    # Page 2
    page2 = _list_servers_json(e2e_deployment, limit=1, continue_from=token1)
    assert len(page2["servers"]) == 1, f"Expected 1 server on page 2, got {len(page2['servers'])}"
    assert page2["servers"][0] != page1["servers"][0], (
        f"Page 2 returned the same server as page 1: {page2['servers'][0]}"
    )
    token2 = page2.get("continue_from")
    assert token2, "Expected a pagination token after requesting 2 of 3+ servers"

    # Page 3
    page3 = _list_servers_json(e2e_deployment, continue_from=token2)
    assert len(page3["servers"]) >= 1, f"Expected at least 1 server on page 3, got {len(page3['servers'])}"
    seen = {page1["servers"][0], page2["servers"][0]}
    assert page3["servers"][0] not in seen, f"Page 3 first server '{page3['servers'][0]}' was already seen: {seen}"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_server_list_paginate_token_hint(
    e2e_deployment: EndToEndDeployment, e2e_workspace: str, seeded_cluster: dict[str, list[str]]
) -> None:
    """Verify the plain-text pagination hint includes the continuation token."""
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "list", "--scope", "default", "-n", "1"])
    output = result.stdout

    assert "--continue-from" in output, f"Expected pagination hint in output:\n{output}"
    for line in output.splitlines():
        if "--continue-from" in line:
            parts = line.split("--continue-from")
            assert len(parts) == 2, f"Expected exactly one --continue-from in hint line: {line}"
            token = parts[1].strip()
            assert token, f"Expected non-empty token after --continue-from in: {line}"
            break


def test_server_list_invalid_continuation_token(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that an invalid continuation token fails gracefully."""
    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(
            ["jupyter-deploy", "server", "list", "--scope", "default", "--continue-from", "invalid-token"]
        )


# ── server status ───────────────────────────────────────────────────────────


def test_server_status_running(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that server status returns Running for the test workspace."""
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "status", "--name", e2e_workspace])
    assert "Running" in result.stdout, f"Expected 'Running' in output:\n{result.stdout}"


def test_server_status_not_found(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that server status for a nonexistent workspace fails."""
    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "server", "status", "--name", "i-do-not-exist"])

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(
            ["jupyter-deploy", "server", "status", "--name", e2e_workspace, "--scope", "i-do-not-exist"]
        )


# ── server show ─────────────────────────────────────────────────────────────


def test_server_show_happy_case(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that server show show returns details."""
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "show", "--name", e2e_workspace])
    assert result.stdout, f"Expected non-empty output for server show {e2e_workspace}"


def test_server_show_json(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that server show --json returns valid JSON with expected fields."""
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "show", "--name", e2e_workspace, "--json"])
    data = json.loads(result.stdout)
    assert "name" in data, f"Expected 'name' in JSON, got: {list(data.keys())}"
    assert "resource" in data, f"Expected 'resource' in JSON, got: {list(data.keys())}"
    assert data["name"] == e2e_workspace


def test_server_show_not_found(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that server show for a nonexistent workspace fails."""
    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "server", "show", "--name", "i-do-not-exist"])

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(
            ["jupyter-deploy", "server", "show", "--name", e2e_workspace, "--scope", "i-do-not-exist"]
        )


# ── server logs ─────────────────────────────────────────────────────────────


def test_server_logs_happy(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that server logs returns non-empty output for a running workspace."""
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "logs", "--name", e2e_workspace])
    assert result.stdout.strip(), f"Expected non-empty log output for {e2e_workspace}"


def test_server_logs_with_tail(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that -- --tail=5 limits log output."""
    full_result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "logs", "--name", e2e_workspace])
    tail_result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "server", "logs", "--name", e2e_workspace, "--", "--tail=5"]
    )
    assert tail_result.stdout.strip(), "Expected non-empty output with --tail=5"
    assert len(tail_result.stdout) <= len(full_result.stdout), "Expected --tail=5 to produce less or equal output"


def test_server_logs_bad_flag(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify logs with an invalid kubectl flag fails with a clean error."""
    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(["jupyter-deploy", "server", "logs", "--name", e2e_workspace, "--", "--head=20"])
    assert "unknown flag" in str(exc_info.value).lower(), (
        f"Expected 'unknown flag' in error message, got: {exc_info.value}"
    )


def test_server_logs_not_found(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that server logs for a nonexistent workspace fails."""
    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "server", "logs", "--name", "i-do-not-exist"])

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(
            ["jupyter-deploy", "server", "logs", "--name", e2e_workspace, "--scope", "i-do-not-exist"]
        )


# ── server exec ─────────────────────────────────────────────────────────────


def test_server_exec_simple_command(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that server exec runs a command and returns stdout."""
    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "server", "exec", "--name", e2e_workspace, "--scope", "default", "--", "whoami"]
    )
    assert result.stdout.strip(), "Expected non-empty stdout from 'whoami'"


def test_server_exec_failed_command(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that exec with a nonexistent command fails with proper error surfacing."""
    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(
            [
                "jupyter-deploy",
                "server",
                "exec",
                "--name",
                e2e_workspace,
                "--",
                "command_that_does_not_exist",
            ]
        )

    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, subprocess.CalledProcessError)
    assert exc_info.value.__cause__.returncode != 0


def test_server_exec_nonzero_exit(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that server exec with a failing command exits non-zero."""
    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--name", e2e_workspace, "--", "false"])


def test_server_exec_not_found(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that server exec for a nonexistent workspace fails."""
    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--name", "i-do-not-exist", "--", "whoami"])

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(
            [
                "jupyter-deploy",
                "server",
                "exec",
                "--name",
                e2e_workspace,
                "--scope",
                "i-do-not-exist",
                "--",
                "whoami",
            ]
        )


# ── server stop / start ─────────────────────────────────────────────────────


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_server_stop_then_start(
    e2e_deployment: EndToEndDeployment, other_user_workspace: str, seeded_cluster: dict[str, list[str]]
) -> None:
    """Admin stops and starts a private workspace owned by a different user."""
    # Verify the workspace is OwnerOnly and belongs to the impersonated user —
    # this guarantees the admin is bypassing ownership permissions
    owner = kubectl_get_workspace_owner(other_user_workspace)
    assert owner == IMPERSONATED_USER, f"Expected owner '{IMPERSONATED_USER}', got '{owner}'"

    ownership_type = kubectl_get_workspace_ownership_type(other_user_workspace)
    assert ownership_type == "OwnerOnly", f"Expected ownershipType 'OwnerOnly', got '{ownership_type}'"

    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "stop", "--name", other_user_workspace])
    e2e_deployment.cli.poll_scoped_server_status(other_user_workspace, "Stopped", timeout_s=180)

    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "start", "--name", other_user_workspace])
    e2e_deployment.cli.poll_scoped_server_status(other_user_workspace, "Running", timeout_s=300)
