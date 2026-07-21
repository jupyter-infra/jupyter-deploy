"""E2E tests for host (node) commands on the EKS OIDC template."""

import json

import pytest
from pytest_jupyter_deploy.cli import JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment


def _list_hosts_json(
    e2e_deployment: EndToEndDeployment, limit: int | None = None, continue_from: str | None = None
) -> dict:
    cmd = ["jupyter-deploy", "host", "list", "--json"]
    if limit is not None:
        cmd.extend(["-n", str(limit)])
    if continue_from is not None:
        cmd.extend(["--continue-from", continue_from])
    result = e2e_deployment.cli.run_command(cmd)
    return json.loads(result.stdout)


# ── host list ────────────────────────────────────────────────────────────────


def test_host_list_no_pagination(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that the cluster has at least 3 nodes (2 components + 1 workspace)."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "host", "list"])
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) >= 3, f"Expected at least 3 hosts, got {len(lines)}: {lines}"
    assert "--continue-from" not in result.stdout, "Expected no pagination hint when listing all hosts"


def test_host_list_json(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that jd host list --json returns valid JSON with expected keys."""
    e2e_deployment.ensure_deployed()

    data = _list_hosts_json(e2e_deployment)
    assert "hosts" in data, f"Expected 'hosts' key in JSON response, got: {list(data.keys())}"
    assert isinstance(data["hosts"], list), f"Expected 'hosts' to be a list, got {type(data['hosts'])}"
    for host in data["hosts"]:
        assert isinstance(host, str), f"Expected host name to be a string, got {type(host)}: {host}"


def test_host_list_paginate_full(e2e_deployment: EndToEndDeployment) -> None:
    """Paginate through hosts one at a time and verify we get distinct hosts."""
    e2e_deployment.ensure_deployed()

    # Page 1: request 1 host
    page1 = _list_hosts_json(e2e_deployment, limit=1)
    assert len(page1["hosts"]) == 1, f"Expected 1 host on page 1, got {len(page1['hosts'])}"
    token1 = page1.get("continue_from")
    assert token1, "Expected a pagination token after requesting 1 of 3+ hosts"

    # Page 2: continue with token1, still limit 1
    page2 = _list_hosts_json(e2e_deployment, limit=1, continue_from=token1)
    assert len(page2["hosts"]) == 1, f"Expected 1 host on page 2, got {len(page2['hosts'])}"
    assert page2["hosts"][0] != page1["hosts"][0], f"Page 2 returned the same host as page 1: {page2['hosts'][0]}"
    token2 = page2.get("continue_from")
    assert token2, "Expected a pagination token after requesting 2 of 3+ hosts"

    # Page 3: continue with token2, no limit (get the rest)
    page3 = _list_hosts_json(e2e_deployment, continue_from=token2)
    assert len(page3["hosts"]) >= 1, f"Expected at least 1 host on page 3, got {len(page3['hosts'])}"
    seen = {page1["hosts"][0], page2["hosts"][0]}
    assert page3["hosts"][0] not in seen, (
        f"Page 3 first host '{page3['hosts'][0]}' was already seen in pages 1-2: {seen}"
    )


def test_host_list_query_filter(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that --query filters hosts by label selector, returning only matching nodes."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "host", "list", "--json", "--query", "jupyter-deploy/role=platform"]
    )
    filtered = json.loads(result.stdout)

    # Platform MNG always has at least 2 nodes (min_size=2).
    assert len(filtered["hosts"]) >= 2, (
        f"Expected at least 2 platform hosts, got {len(filtered['hosts'])}: {filtered['hosts']}"
    )

    # Every returned node must actually carry the platform role label — verify
    # the filter isn't leaking nodes from other pools (routing, workspaces).
    import subprocess

    for node in filtered["hosts"]:
        role = subprocess.run(
            ["kubectl", "get", "node", node, "-o", "jsonpath={.metadata.labels.jupyter-deploy/role}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert role == "platform", (
            f"Node '{node}' returned by --query platform filter has role '{role}', expected 'platform'"
        )


def test_host_list_query_platform_returns_only_platform_nodes(e2e_deployment: EndToEndDeployment) -> None:
    """--query filters to platform (components) nodes using the node role label.

    The platform MNG always has at least 2 nodes (min_size=2). Result must be
    a strict subset of all nodes — routing/workspace nodes must be excluded.
    """
    e2e_deployment.ensure_deployed()

    all_data = _list_hosts_json(e2e_deployment)
    all_count = len(all_data["hosts"])

    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "host", "list", "--json", "--query", "jupyter-deploy/role=platform"]
    )
    filtered = json.loads(result.stdout)

    assert len(filtered["hosts"]) >= 2, (
        f"Expected at least 2 platform nodes, got {len(filtered['hosts'])}: {filtered['hosts']}"
    )
    assert len(filtered["hosts"]) < all_count, f"Expected query filter to return fewer than all {all_count} nodes"


def test_host_list_query_routing_returns_only_routing_nodes(e2e_deployment: EndToEndDeployment) -> None:
    """--query filters to Karpenter routing nodes using the node role label.

    minReplicas=2 guarantees 2 routing *pods*, not 2 nodes — preferred-only
    anti-affinity lets consolidation bin-pack both pods onto a single node, so
    the routing pool can legitimately run on 1 node. Assert >= 1 and that the
    result is a strict subset of all nodes.
    """
    e2e_deployment.ensure_deployed()

    all_data = _list_hosts_json(e2e_deployment)
    all_count = len(all_data["hosts"])

    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "host", "list", "--json", "--query", "jupyter-deploy/role=routing"]
    )
    filtered = json.loads(result.stdout)

    assert len(filtered["hosts"]) >= 1, (
        f"Expected at least 1 routing node, got {len(filtered['hosts'])}: {filtered['hosts']}"
    )
    assert len(filtered["hosts"]) < all_count, f"Expected query filter to return fewer than all {all_count} nodes"


def test_host_list_query_filters_are_mutually_exclusive(e2e_deployment: EndToEndDeployment) -> None:
    """Nodes returned by platform and routing queries must not overlap."""
    e2e_deployment.ensure_deployed()

    platform_result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "host", "list", "--json", "--query", "jupyter-deploy/role=platform"]
    )
    routing_result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "host", "list", "--json", "--query", "jupyter-deploy/role=routing"]
    )

    platform_hosts = set(json.loads(platform_result.stdout)["hosts"])
    routing_hosts = set(json.loads(routing_result.stdout)["hosts"])

    overlap = platform_hosts & routing_hosts
    assert not overlap, f"Expected no overlap between platform and routing nodes, got: {overlap}"


def test_host_list_invalid_continuation_token(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that an invalid continuation token fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "host", "list", "--continue-from", "invalid-token"])


def test_host_list_paginate_token_hint(e2e_deployment: EndToEndDeployment) -> None:
    """Verify the plain-text pagination hint includes the continuation token."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "host", "list", "-n", "1"])
    output = result.stdout

    assert "--continue-from" in output, f"Expected pagination hint in output:\n{output}"
    # The hint line should contain a base64-encoded token after --continue-from
    for line in output.splitlines():
        if "--continue-from" in line:
            parts = line.split("--continue-from")
            assert len(parts) == 2, f"Expected exactly one --continue-from in hint line: {line}"
            token = parts[1].strip()
            assert token, f"Expected non-empty token after --continue-from in: {line}"
            break


# ── host status ──────────────────────────────────────────────────────────────


def test_host_status_happy_case(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that host status returns a non-empty status for the first node."""
    e2e_deployment.ensure_deployed()

    data = _list_hosts_json(e2e_deployment)
    first_host = data["hosts"][0]

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "host", "status", "--name", first_host])
    assert "Host status:" in result.stdout, f"Expected 'Host status:' in output:\n{result.stdout}"


def test_host_status_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that host status for a non-existent node fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "host", "status", "--name", "i-do-not-exist"])


# ── host show ────────────────────────────────────────────────────────────────


def test_host_show_happy_case(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that host show returns details with expected keys."""
    e2e_deployment.ensure_deployed()

    data = _list_hosts_json(e2e_deployment)
    first_host = data["hosts"][0]

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "host", "show", "--name", first_host])
    assert result.stdout, f"Expected non-empty output for host show {first_host}"


def test_host_show_json(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that host show --json returns valid JSON with expected fields."""
    e2e_deployment.ensure_deployed()

    data = _list_hosts_json(e2e_deployment)
    first_host = data["hosts"][0]

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "host", "show", "--name", first_host, "--json"])
    show_data = json.loads(result.stdout, strict=False)
    assert "name" in show_data, f"Expected 'name' in JSON response, got: {list(show_data.keys())}"
    assert "status" in show_data, "Expected 'status' in JSON response"
    assert "resource" in show_data, "Expected 'resource' in JSON response"
    assert show_data["name"] == first_host


def test_host_show_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that host show for a non-existent node fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "host", "show", "--name", "i-do-not-exist"])
