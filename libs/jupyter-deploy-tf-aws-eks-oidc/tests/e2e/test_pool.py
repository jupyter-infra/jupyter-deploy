"""E2E tests for jd pool commands on the EKS OIDC template.

Covers the three jd pool subcommands added with the Karpenter autoscaling work:
  - jd pool list       — lists all NodePools with node count and resource limits
  - jd pool status     — detailed health for a named NodePool
  - jd pool scaling    — recent Karpenter provision/consolidation events

These commands read Karpenter NodePool/NodeClaim CRDs via the manifest's
k8s.custom.list-cluster / k8s.custom.get-cluster API calls.
"""

import json

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment

# NodePools declared in the eks-oidc karpenter-nodepools chart.
EXPECTED_NODEPOOLS = {"routing", "workspaces"}


# ── pool list ─────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_pool_list_includes_routing_and_workspaces_nodepools(e2e_deployment: EndToEndDeployment) -> None:
    """jd pool list must return at least the routing and workspaces NodePools."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "list"])
    output = result.stdout

    for name in EXPECTED_NODEPOOLS:
        assert name in output, f"Expected NodePool '{name}' in pool list output:\n{output}"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_pool_list_json_contains_nodepool_objects(e2e_deployment: EndToEndDeployment) -> None:
    """jd pool list --json must return a list of NodePool objects with expected fields."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "list", "--json"])
    pools = json.loads(result.stdout)

    assert isinstance(pools, list), f"Expected list, got {type(pools)}: {pools}"
    assert len(pools) >= 2, f"Expected at least 2 NodePools, got {len(pools)}"

    pool_names = {p["metadata"]["name"] for p in pools if "metadata" in p}
    for name in EXPECTED_NODEPOOLS:
        assert name in pool_names, f"Expected NodePool '{name}' in JSON output, got: {pool_names}"


# ── pool status ───────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("kubernetes_cluster_login")
@pytest.mark.parametrize("nodepool_name", ["routing", "workspaces"])
def test_pool_status_returns_named_nodepool_details(e2e_deployment: EndToEndDeployment, nodepool_name: str) -> None:
    """jd pool status must return details for each named NodePool."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "status", "--name", nodepool_name])
    output = result.stdout

    assert nodepool_name in output, f"Expected NodePool name '{nodepool_name}' in status output:\n{output}"


@pytest.mark.usefixtures("kubernetes_cluster_login")
@pytest.mark.parametrize("nodepool_name", ["routing", "workspaces"])
def test_pool_status_json_contains_name_and_spec(e2e_deployment: EndToEndDeployment, nodepool_name: str) -> None:
    """jd pool status --json must return a NodePool object with spec and status fields."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "pool", "status", "--name", nodepool_name, "--json"]
    )
    data = json.loads(result.stdout)

    # jd pool status returns {name, resource} where resource is the full NodePool object.
    assert "resource" in data, f"Expected 'resource' in pool status JSON, got: {list(data.keys())}"
    resource = data["resource"]
    assert "metadata" in resource, f"Expected 'metadata' in NodePool resource, got: {list(resource.keys())}"
    assert "spec" in resource, f"Expected 'spec' in NodePool resource, got: {list(resource.keys())}"
    assert resource["metadata"]["name"] == nodepool_name, (
        f"Expected name '{nodepool_name}', got '{resource['metadata']['name']}'"
    )


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_pool_status_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """jd pool status for a non-existent NodePool must fail gracefully."""
    e2e_deployment.ensure_deployed()

    from pytest_jupyter_deploy.cli import JDCliError

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "status", "--name", "does-not-exist"])


# ── pool scaling ──────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_pool_scaling_succeeds_on_quiet_cluster(e2e_deployment: EndToEndDeployment) -> None:
    """jd pool scaling must return output without error (events list may be empty on a quiet cluster)."""
    e2e_deployment.ensure_deployed()

    # No assertion on content — Karpenter event history may be empty on a fresh cluster.
    # The goal is that the command completes without error and returns parseable output.
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "scaling"])
    assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}:\n{result.stdout}"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_pool_scaling_json_returns_list(e2e_deployment: EndToEndDeployment) -> None:
    """jd pool scaling --json must return a list (empty or populated with NodeClaim events)."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "scaling", "--json"])
    data = json.loads(result.stdout)

    assert isinstance(data, list), f"Expected list from pool scaling --json, got {type(data)}: {data}"
