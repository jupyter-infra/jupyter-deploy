"""E2E tests for end-user discovery RBAC on WorkspaceTemplates / AccessStrategies.

The web-app editor discovers templates + access strategies in both the user's own
namespace AND the shared namespace Union(userNs, sharedNs), using the user's own token,
to populate its dropdowns — without letting users mutate those resources. The read grant
comes from two different Roles in the `github-rbac` chart:

- shared namespace: `github-shared-discovery-reader`, a read-only (get/list) Role scoped
  to templates + access strategies (shared-discovery-role.yaml).
- own namespace(s): the existing `github-workspace-role` (role.yaml), whose
  `resources: ["*"]` get/list/watch rule covers templates + access strategies read while
  granting write only on `workspaces`.

Two negatives with different durability:
- SHARED namespace write-denial is a hard security invariant: end users must never mutate
  the shared, admin-owned config, regardless of future policy.
- OWN namespace write-denial reflects CURRENT policy only. We may later let some users
  author templates in their own namespace; if that lands, that test loosens — but the
  shared-namespace invariant above stays.

Auth model mirrors test_workspace.py:
- the impersonated identity is github:<JD_E2E_USER> in the github:<org>:<team> group that
  the RoleBindings are bound to (the configured oauth_allowed_teams).
"""

import os

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.kubernetes.kubectl import run_kubectl
from pytest_jupyter_deploy.kubernetes.rbac import impersonated_user_can
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set

pytestmark = pytest.mark.usefixtures("kubernetes_cluster_login")

# The namespaced CRDs the web-app editor discovers (read-only for end users today).
DISCOVERY_RESOURCES = ["workspacetemplates", "workspaceaccessstrategies"]
# Verbs an end user must NOT have on the discovery resources.
WRITE_VERBS = ["create", "update", "patch", "delete"]
# The user's own RBAC namespace (matches test_workspace.py / workspace_rbac_namespaces default).
OWN_NAMESPACE = "default"


def _get_user_a() -> str:
    user = os.getenv("JD_E2E_USER")
    if not user:
        raise RuntimeError("JD_E2E_USER must be set")
    return f"github:{user}"


def _get_impersonation_group() -> str:
    org = os.getenv("JD_E2E_ORG")
    team = os.getenv("JD_E2E_RBAC_TEAM")
    if not org or not team:
        raise RuntimeError("JD_E2E_ORG and JD_E2E_RBAC_TEAM must be set")
    return f"github:{org}:{team}"


def _assert_cannot_write(namespace: str, as_user: str, as_group: str) -> None:
    for resource in DISCOVERY_RESOURCES:
        for verb in WRITE_VERBS:
            assert not impersonated_user_can(verb, resource, namespace, as_user=as_user, as_groups=[as_group]), (
                f"user should NOT be able to {verb} {resource} in {namespace}, but RBAC allows it"
            )


# ── Shared namespace (github-shared-discovery-reader) ────────────────────────


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_can_list_and_describe_shared_discovery_resources(
    e2e_deployment: EndToEndDeployment, shared_namespace: str
) -> None:
    """An end user can list and describe shared templates + access strategies (drives the editor dropdowns)."""
    e2e_deployment.ensure_deployed()
    user_a = _get_user_a()
    group = _get_impersonation_group()
    namespace = shared_namespace

    for resource in DISCOVERY_RESOURCES:
        # list — non-empty (the deployment seeds a default template + access strategy)
        result = run_kubectl("get", resource, "-n", namespace, "-o", "name", as_user=user_a, as_groups=[group])
        assert result.returncode == 0, f"user cannot list {resource} in {namespace}:\n{result.stderr}"
        names = result.stdout.split()
        assert names, f"expected at least one {resource} in {namespace}, got none"

        # describe (get) each named object — proves read of the object body, not just list
        for name in names:
            described = run_kubectl("describe", name, "-n", namespace, as_user=user_a, as_groups=[group])
            assert described.returncode == 0, f"user cannot describe {name} in {namespace}:\n{described.stderr}"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_cannot_write_shared_discovery_resources(
    e2e_deployment: EndToEndDeployment, shared_namespace: str
) -> None:
    """Hard invariant: an end user can NEVER create, edit, or delete resources in the shared namespace."""
    e2e_deployment.ensure_deployed()
    _assert_cannot_write(shared_namespace, as_user=_get_user_a(), as_group=_get_impersonation_group())


# ── Own namespace (github-workspace-role) ────────────────────────────────────


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_can_read_own_namespace_discovery_resources(e2e_deployment: EndToEndDeployment) -> None:
    """An end user can read templates + access strategies in their own namespace.

    The default template/access-strategy live only in the shared namespace, so nothing is
    seeded here — assert the read PERMISSION (get/list) rather than a non-empty list.
    """
    e2e_deployment.ensure_deployed()
    user_a = _get_user_a()
    group = _get_impersonation_group()

    for resource in DISCOVERY_RESOURCES:
        for verb in ("get", "list"):
            assert impersonated_user_can(verb, resource, OWN_NAMESPACE, as_user=user_a, as_groups=[group]), (
                f"user should be able to {verb} {resource} in {OWN_NAMESPACE}, but RBAC denies it"
            )


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_cannot_write_own_namespace_discovery_resources(e2e_deployment: EndToEndDeployment) -> None:
    """Current policy: an end user cannot create/edit/delete templates + access strategies in their own namespace.

    github-workspace-role grants write only on `workspaces`. This may loosen if we later
    let users author their own templates — unlike the shared-namespace write-denial, which
    is a permanent invariant.
    """
    e2e_deployment.ensure_deployed()
    _assert_cannot_write(OWN_NAMESPACE, as_user=_get_user_a(), as_group=_get_impersonation_group())
