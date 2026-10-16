"""E2E test configuration for the EKS OIDC template."""

import os
from collections.abc import Generator
from typing import Any
from urllib.parse import urlparse

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.kubernetes.kubectl import resource_absent, run_kubectl
from pytest_jupyter_deploy.plugin import handle_browser_context_args
from pytest_jupyter_deploy.workspaces.kubectl import (
    kubectl_apply_workspace,
    kubectl_delete_workspace,
    kubectl_poll_workspace_status,
)
from pytest_jupyter_deploy.workspaces.template import get_min_idle_timeout, set_min_idle_timeout

from .constants import (
    ADMIN_WORKSPACES,
    DEFAULT_WORKSPACE_TEMPLATE,
    GPU_NODEPOOL,
    IMPERSONATED_USER,
    NS_A,
    NS_B,
    NS_ONLY_A_TEAM,
    NS_ONLY_B_TEAM,
    NS_ONLY_DEFAULT_TEAM,
    NS_SMALL_TEMPLATE,
    NS_SMALL_TEMPLATE_CONFIG,
    ROUTER_NAMESPACE,
    SEEDED_WORKSPACES,
    WORKSPACE_NAMESPACE,
    WORKSPACES_DIR,
)


@pytest.fixture
def gpu_pool_required(e2e_deployment: EndToEndDeployment, kubernetes_cluster_login: None) -> None:
    """Skip the test unless the deployment currently has the GPU pool.

    JD_E2E_GPU_ENABLED alone does not imply the pool exists: CI sets it against
    deployments with enable_default_gpu_pool off, and the GPU module enables
    the pool itself.
    """
    e2e_deployment.ensure_deployed()
    if resource_absent("nodepools.karpenter.sh", GPU_NODEPOOL):
        pytest.skip("Deployment does not have the workspace-gpu NodePool (enable_default_gpu_pool off)")


def _get_impersonation_group() -> str | None:
    """Build the impersonation group from env vars (github:<org>:<team>).

    Uses JD_E2E_RBAC_TEAM — the team with workspace CRUD permissions via the
    github-rbac Helm chart RoleBinding. This is distinct from JD_E2E_TEAM which
    controls OAuth app access.
    """
    org = os.getenv("JD_E2E_ORG")
    team = os.getenv("JD_E2E_RBAC_TEAM")
    if org and team:
        return f"github:{org}:{team}"
    return None


def pytest_collection_modifyitems(items: list) -> None:
    """Automatically mark all tests in this directory as e2e tests."""
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any], request: pytest.FixtureRequest) -> dict[str, Any]:
    """Configure browser context to load saved authentication state."""
    return handle_browser_context_args(browser_context_args, request)


@pytest.fixture(scope="session")
def seeded_cluster(
    kubernetes_cluster_login: None, e2e_deployment: EndToEndDeployment
) -> Generator[dict[str, list[str]], None, None]:
    """Seed the cluster with admin and impersonated workspaces.

    Creates:
    - Admin workspaces (as the current IAM identity)
    - Impersonated workspaces (as a synthetic user via --as/--as-group)

    Yields a dict: {"admin": [...], "seeded": [...]}
    Tears down all workspaces on session end.

    These workspaces are long-lived (session-scoped) and must not be mutated or
    deleted by tests. Tests in test_workspace.py use separate, self-contained
    workspace names (e2e-ws-*) with their own create/delete lifecycle.
    """
    group = _get_impersonation_group()
    if not group:
        pytest.skip("JD_E2E_ORG and JD_E2E_RBAC_TEAM required for cluster seeding")

    created: dict[str, list[str]] = {"admin": [], "seeded": []}

    # Create admin workspaces
    for name in ADMIN_WORKSPACES:
        kubectl_apply_workspace(name, WORKSPACES_DIR)
        created["admin"].append(name)

    # Create impersonated workspaces
    groups = [group]
    for name in SEEDED_WORKSPACES:
        kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=IMPERSONATED_USER, as_groups=groups)
        created["seeded"].append(name)

    # Wait for all workspaces to be Running
    all_workspaces = created["admin"] + created["seeded"]
    for name in all_workspaces:
        e2e_deployment.cli.poll_scoped_server_status(name, "Running", timeout_s=300)

    yield created

    e2e_deployment.cli.run_command(["jupyter-deploy", "cluster", "login"])
    for name in all_workspaces:
        kubectl_delete_workspace(name)


@pytest.fixture(scope="module")
def e2e_workspace(seeded_cluster: dict[str, list[str]]) -> str:
    """Return the admin workspace name — always Running, used for logs/exec/status tests."""
    return seeded_cluster["admin"][0]


@pytest.fixture(scope="module")
def other_user_workspace(seeded_cluster: dict[str, list[str]]) -> str:
    """Return a private workspace owned by a different user — used to test admin stop/start."""
    return seeded_cluster["seeded"][1]


@pytest.fixture(scope="session")
def getting_started_url(e2e_deployment: EndToEndDeployment) -> str:
    """Return the web UI URL."""
    e2e_deployment.ensure_deployed()
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--output", "get_started_url", "--text"])
    return result.stdout.strip()


@pytest.fixture(scope="session")
def eks_domain(getting_started_url: str) -> str:
    """Return the full domain for this EKS deployment."""
    parsed = urlparse(getting_started_url)
    return parsed.netloc


@pytest.fixture(scope="session")
def shared_namespace(e2e_deployment: EndToEndDeployment) -> str:
    """Return the shared namespace where the access strategies live."""
    e2e_deployment.ensure_deployed()
    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "show", "--output", "workspace_shared_namespace", "--text"]
    )
    return result.stdout.strip()


@pytest.fixture(scope="session")
def default_workspace_namespace(e2e_deployment: EndToEndDeployment) -> str:
    """Return the default workspace namespace, which holds its own copy of the templates."""
    e2e_deployment.ensure_deployed()
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--output", "server_default_scope", "--text"])
    return result.stdout.strip()


@pytest.fixture(scope="module")
def relaxed_idle_floor(kubernetes_cluster_login: None, default_workspace_namespace: str) -> Generator[None, None, None]:
    """Lower the default template's idle-timeout floor to 1 minute for a test.

    The floor (spec.idleShutdownOverrides.minIdleTimeoutInMinutes) is an
    IaC-managed value that the operator's validating webhook enforces: a Workspace
    with a sub-floor idle timeout is rejected at admission. Idle-shutdown tests need
    a 1-minute timeout, so this patches the live template down to 1 and restores the
    original floor on teardown — making the test self-contained rather than
    dependent on the deployment having been created with a low floor. Pairs with the
    fast_idle_operator fixture, which speeds up the operator poll interval the same way.
    """
    original = get_min_idle_timeout(DEFAULT_WORKSPACE_TEMPLATE, default_workspace_namespace)
    set_min_idle_timeout(DEFAULT_WORKSPACE_TEMPLATE, default_workspace_namespace, 1)
    try:
        yield
    finally:
        set_min_idle_timeout(DEFAULT_WORKSPACE_TEMPLATE, default_workspace_namespace, original)


@pytest.fixture(scope="module")
def coding_agents_workspace(
    e2e_deployment: EndToEndDeployment, kubernetes_cluster_login: None
) -> Generator[str, None, None]:
    """A workspace created in the default namespace once Bedrock is enabled there.

    Enables Bedrock first if the deployment has it off, globally or for the default
    namespace's entry. The workspace is created afterwards because the operator only
    assigns the service account and the template env at creation: a workspace older
    than the configuration would never get credentials.
    """
    e2e_deployment.ensure_deployed()
    enabled = e2e_deployment.get_bool_variable_value("workspace_bedrock_enabled")
    namespaces = e2e_deployment.get_list_of_maps_variable_value("workspace_namespaces")
    opted_out = any(e["name"] == WORKSPACE_NAMESPACE and e.get("bedrock") == "false" for e in namespaces)
    # Not a mutating case, though this branch redeploys and does not restore: Bedrock in the
    # default namespace is the template's default, so this only puts back the configuration
    # the tests are written against. CI deployments never take it; it catches a local project
    # whose owner turned Bedrock off, which would otherwise fail every case below.
    if not enabled or opted_out:
        overrides: dict[str, Any] = {"workspace_bedrock_enabled": True}
        if opted_out:
            overrides["workspace_namespaces"] = [
                {k: v for k, v in e.items() if not (e["name"] == WORKSPACE_NAMESPACE and k == "bedrock")}
                for e in namespaces
            ]
        e2e_deployment.ensure_deployed_with_overrides(overrides)

    name = "e2e-coding-agents"
    kubectl_apply_workspace(name, WORKSPACES_DIR)
    try:
        kubectl_poll_workspace_status(name, "Running", namespace=WORKSPACE_NAMESPACE, timeout_s=600)
        e2e_deployment.cli.wait_for_workspace_pod_exec_ready(name, scope=WORKSPACE_NAMESPACE, timeout_s=60)
        yield name
    finally:
        kubectl_delete_workspace(name, namespace=WORKSPACE_NAMESPACE)


# ── Workspace namespaces ──────────────────────────────────────────────────────

# The variables the workspace-namespace modules rewrite.
_NAMESPACE_MAPPING_VARIABLES = ["workspace_namespaces", "workspace_templates", "workspace_nodepools"]


def _namespace_entry(
    name: str, teams: list[str], templates: list[str] | None = None, bedrock: bool = True
) -> dict[str, str]:
    entry = {"name": name, "teams": ",".join(dict.fromkeys(teams))}
    if templates:
        entry["templates"] = ",".join(templates)
    if not bedrock:
        entry["bedrock"] = "false"
    return entry


@pytest.fixture(scope="module")
def namespace_base_values(e2e_deployment: EndToEndDeployment, restored_namespace_mapping: None) -> dict[str, Any]:
    """The base workspace_namespaces mapping, plus the template and pool values it needs.

    - default:  every team in oauth_allowed_teams, keeping the cards the empty mapping
                gives it, so its live workspaces keep their templates
    - e2e-ns-a: JD_E2E_RBAC_TEAM + a synthetic "only-a" team, also offering e2e-cpu-small
    - e2e-ns-b: JD_E2E_RBAC_TEAM + a synthetic "only-b" team, opted out of Bedrock

    Also allowlists the synthetic teams (incl. the #409 case's "only-default") in variables.yaml,
    after restored_namespace_mapping has snapshotted the deployment's own allowlist.
    """
    e2e_deployment.ensure_deployed()
    org, rbac_team = os.environ["JD_E2E_ORG"], f"{os.environ['JD_E2E_ORG']}:{os.environ['JD_E2E_RBAC_TEAM']}"
    templates = [
        t
        for t in e2e_deployment.get_list_of_maps_variable_value("workspace_templates")
        if t["name"] != NS_SMALL_TEMPLATE
    ]
    pools = e2e_deployment.get_list_of_maps_variable_value("workspace_nodepools")

    # default keeps every card the pools offer, including the built-in GPU card the flag injects.
    offered = [t for p in pools for t in p.get("templates", "").split(",") if t]
    gpu_flag = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "show", "--variable", "enable_default_gpu_pool", "--text"]
    ).stdout.strip()
    if gpu_flag.lower() == "true":
        offered.append("jupyterlab-gpu")

    # A config renders only where a pool offers it, so the first CPU pool offers the small one.
    pools_with_small = [dict(p) for p in pools]
    cpu_pool = next(p for p in pools_with_small if not p.get("accelerator"))
    cpu_offered = [t for t in cpu_pool.get("templates", "").split(",") if t]
    cpu_pool["templates"] = ",".join(dict.fromkeys([*cpu_offered, NS_SMALL_TEMPLATE]))

    allowed_teams = e2e_deployment.get_list_str_variable_value("oauth_allowed_teams")
    synthetic = [f"{org}:{t}" for t in (NS_ONLY_A_TEAM, NS_ONLY_B_TEAM, NS_ONLY_DEFAULT_TEAM)]
    e2e_deployment.update_required_value("oauth_allowed_teams", [*allowed_teams, *synthetic])
    return {
        "workspace_templates": [*templates, NS_SMALL_TEMPLATE_CONFIG],
        "workspace_nodepools": pools_with_small,
        "workspace_namespaces": [
            _namespace_entry("default", allowed_teams, list(dict.fromkeys(offered))),
            _namespace_entry(NS_A, [rbac_team, f"{org}:{NS_ONLY_A_TEAM}"], [NS_SMALL_TEMPLATE]),
            _namespace_entry(NS_B, [rbac_team, f"{org}:{NS_ONLY_B_TEAM}"], bedrock=False),
        ],
    }


@pytest.fixture(scope="module")
def restored_namespace_mapping(e2e_deployment: EndToEndDeployment) -> Generator[None, None, None]:
    """Snapshot the mapping variables and the allowlist; after the module, restore them and redeploy."""
    e2e_deployment.ensure_deployed()
    snapshot = {key: e2e_deployment.read_override_value(key) for key in _NAMESPACE_MAPPING_VARIABLES}
    allowed_teams = e2e_deployment.get_list_str_variable_value("oauth_allowed_teams")
    yield
    e2e_deployment.update_required_value("oauth_allowed_teams", allowed_teams)
    reset_args: list[str] = []
    for key, value in snapshot.items():
        if value is None:
            reset_args += ["--reset-variable", key]
        else:
            e2e_deployment.update_override_value(key, value)
    e2e_deployment.ensure_deployed_with(reset_args)


@pytest.fixture
def fresh_dex(e2e_deployment: EndToEndDeployment) -> None:
    """Restart dex so it serves the applied allowlist; requested before the browser login.

    Remove once the pinned router chart rolls dex on config changes:
    https://github.com/jupyter-infra/jupyter-k8s-aws/issues/100
    """
    e2e_deployment.cli.run_command(["jupyter-deploy", "component", "restart", "--name", "dex"])
    run_kubectl("rollout", "status", "deployment/dex", "-n", ROUTER_NAMESPACE, "--timeout=300s", check=True)
