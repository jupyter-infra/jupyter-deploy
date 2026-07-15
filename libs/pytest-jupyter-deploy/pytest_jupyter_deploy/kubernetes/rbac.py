"""RBAC assertion helpers for E2E tests.

Template-agnostic: callers pass the impersonated identity (user + groups), the verb,
resource and namespace they care about. Uses `kubectl auth can-i`, which resolves RBAC
authoritatively WITHOUT performing the action — the safe way to assert that a write is
denied (no risk of mutating a live resource) or that a read is allowed (no dependency on
a resource actually existing in the namespace).
"""

from pytest_jupyter_deploy.kubernetes.kubectl import run_kubectl


def impersonated_user_can(
    verb: str,
    resource: str,
    namespace: str,
    as_user: str,
    as_groups: list[str] | None = None,
) -> bool:
    """Whether an impersonated user is authorized for a verb on a resource in a namespace.

    Args:
        verb: RBAC verb (e.g. "get", "list", "create", "update", "patch", "delete")
        resource: Resource type (e.g. "workspacetemplates", "workspaces")
        namespace: Kubernetes namespace to scope the check to
        as_user: Impersonate this user (--as flag)
        as_groups: Impersonate these groups (--as-group flags)

    Returns:
        True if kubectl auth can-i answers "yes", False otherwise. (can-i exits non-zero
        on "no", so the answer is read from stdout, not the return code.)
    """
    result = run_kubectl("auth", "can-i", verb, resource, "-n", namespace, as_user=as_user, as_groups=as_groups)
    return result.stdout.strip() == "yes"
