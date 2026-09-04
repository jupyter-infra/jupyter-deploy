"""E2E tests for jd pool commands on the EKS OIDC template.

Covers the jd pool subcommands, which surface EVERY pool of hosts through one interface —
blind to the subsystem backing each pool:
  - jd pool list   — lists all pools by name (managed node groups AND Karpenter NodePools)
  - jd pool show   — detailed info for a named pool
  - jd pool status — ready state for a named pool

Two fundamentally different wirings are unified here:
  - The EKS **managed node group** (`platform`) — read via the AWS EKS API
    (aws.eks.list-nodegroups / describe-nodegroup). Its `show` resource is the boto3
    DescribeNodegroup blob: `nodegroupName` + a bare-string `.status` (e.g. "ACTIVE").
  - **Karpenter NodePools** (`routing`, `workspace-cpu`) — read via the k8s custom API
    (k8s.custom.list-cluster / get-cluster). Its `show` resource is the NodePool CRD:
    `metadata` / `spec` / `.status.conditions[type=Ready]`.

The manifest merges both into a flat name list (MNG first) and branches `show`/`status`
by an `is-mng` flag, so the handler stays generic. These constants name one pool of each
kind so the suite can be re-pointed if the template's default pools change.
"""

import json

import pytest
from pytest_jupyter_deploy.cli import JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set

from .test_utils import require_gpu_pool, verify_gpu_pool_listed

# One pool of each underlying kind (swap here if the template's default pools change).
MNG_POOL = "platform"  # EKS managed node group (AWS EKS API)
KARPENTER_POOL = "routing"  # Karpenter NodePool (k8s custom API)

# Every pool jd pool list must surface, MNG first (the manifest lists MNGs before NodePools).
EXPECTED_KARPENTER_NODEPOOLS = {"routing", "workspace-cpu"}
EXPECTED_POOLS = {MNG_POOL, *EXPECTED_KARPENTER_NODEPOOLS}

# Every pool exercised by the happy-path status/show tests, one per underlying wiring.
HAPPY_PATH_POOLS = [MNG_POOL, KARPENTER_POOL]


# ── pool list ─────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_pool_list_includes_managed_and_karpenter_pools(e2e_deployment: EndToEndDeployment) -> None:
    """jd pool list must return the managed node group AND the Karpenter NodePools."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "list"])
    output = result.stdout

    for name in EXPECTED_POOLS:
        assert name in output, f"Expected pool '{name}' in pool list output:\n{output}"


@skip_if_testvars_not_set(["JD_E2E_GPU_ENABLED"])
@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_pool_list_includes_gpu_pool_when_enabled(e2e_deployment: EndToEndDeployment) -> None:
    """enable_default_gpu_pool adds the synthesized workspace-gpu NodePool to jd pool list."""
    e2e_deployment.ensure_deployed()
    require_gpu_pool()

    verify_gpu_pool_listed(e2e_deployment)


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_pool_list_places_managed_nodegroup_first(e2e_deployment: EndToEndDeployment) -> None:
    """The managed node group must head the list (MNGs are concatenated before NodePools)."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "list", "--json"])
    pools = json.loads(result.stdout)["pools"]

    assert pools, f"Expected a non-empty pool list, got: {pools}"
    assert pools[0] == MNG_POOL, f"Expected '{MNG_POOL}' first in pool list, got: {pools}"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_pool_list_json_contains_all_pools(e2e_deployment: EndToEndDeployment) -> None:
    """jd pool list --json must return every pool name under a "pools" key."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "list", "--json"])
    data = json.loads(result.stdout)

    assert "pools" in data, f"Expected 'pools' key, got: {data}"
    pools = data["pools"]
    assert len(pools) >= len(EXPECTED_POOLS), f"Expected at least {len(EXPECTED_POOLS)} pools, got {len(pools)}"

    for name in EXPECTED_POOLS:
        assert name in pools, f"Expected pool '{name}' in JSON output, got: {pools}"


# ── pool status (happy path, both wirings) ──────────────────────────────────────


@pytest.mark.usefixtures("kubernetes_cluster_login")
@pytest.mark.parametrize("pool_name", HAPPY_PATH_POOLS)
def test_pool_status_ready_for_both_wirings(e2e_deployment: EndToEndDeployment, pool_name: str) -> None:
    """jd pool status must report a normalized 'Ready' for the MNG and a Karpenter pool alike.

    Proves the manifest's is-mng branch + status-rule normalization: the MNG's bare-string
    `.status: ACTIVE` and the NodePool's `.status.conditions[type=Ready]` both map to 'Ready'.
    """
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "status", "--name", pool_name])
    output = result.stdout

    assert "Pool status:" in output, f"Expected 'Pool status:' in status output:\n{output}"
    assert "Ready" in output, f"Expected pool '{pool_name}' to be Ready:\n{output}"


# ── pool show (happy path, type-specific resource shapes) ───────────────────────


@pytest.mark.usefixtures("kubernetes_cluster_login")
@pytest.mark.parametrize("pool_name", HAPPY_PATH_POOLS)
def test_pool_show_json_name_matches(e2e_deployment: EndToEndDeployment, pool_name: str) -> None:
    """jd pool show --json must echo the requested name for either wiring.

    The name is coalesced from Karpenter's `Name` or the MNG's `NodegroupName`, so a correct
    name proves the right branch ran and the name-coalesce picked the right field.
    """
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "show", "--name", pool_name, "--json"])
    data = json.loads(result.stdout)

    assert data.get("name") == pool_name, f"Expected name '{pool_name}', got '{data.get('name')}'"
    assert "resource" in data, f"Expected 'resource' in pool show JSON, got: {list(data.keys())}"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_pool_show_karpenter_resource_shape(e2e_deployment: EndToEndDeployment) -> None:
    """A Karpenter pool's resource is the NodePool CRD (metadata / spec)."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "show", "--name", KARPENTER_POOL, "--json"])
    resource = json.loads(result.stdout)["resource"]

    assert "metadata" in resource, f"Expected 'metadata' in NodePool resource, got: {list(resource.keys())}"
    assert "spec" in resource, f"Expected 'spec' in NodePool resource, got: {list(resource.keys())}"
    assert resource["metadata"]["name"] == KARPENTER_POOL, (
        f"Expected NodePool name '{KARPENTER_POOL}', got '{resource['metadata']['name']}'"
    )


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_pool_show_managed_nodegroup_resource_shape(e2e_deployment: EndToEndDeployment) -> None:
    """The managed node group's resource is the DescribeNodegroup blob.

    This is a different shape than the Karpenter NodePool CRD — no metadata/spec — proving
    the AWS EKS branch (aws.eks.describe-nodegroup) ran and its full Resource round-tripped.
    """
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "show", "--name", MNG_POOL, "--json"])
    resource = json.loads(result.stdout)["resource"]

    assert resource.get("nodegroupName") == MNG_POOL, (
        f"Expected nodegroupName '{MNG_POOL}', got '{resource.get('nodegroupName')}'"
    )
    # boto3 DescribeNodegroup exposes a bare-string top-level status (e.g. "ACTIVE").
    assert isinstance(resource.get("status"), str), (
        f"Expected a bare-string MNG '.status', got: {resource.get('status')!r}"
    )


# ── pool status (error path) ────────────────────────────────────────────────────


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_pool_status_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """jd pool status for a non-existent pool must fail gracefully.

    An unknown name is not in platform_mng_names, so is-mng is false and the request falls
    through to the Karpenter branch → a clean k8s not-found error (not a raw traceback).
    """
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "status", "--name", "does-not-exist"])
