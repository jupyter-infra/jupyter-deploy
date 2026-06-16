"""Kubectl operations for Workspace custom resources."""

import json
import subprocess
import time
from pathlib import Path


def kubectl_apply_workspace(
    name: str,
    workspaces_dir: Path,
    as_user: str | None = None,
    as_groups: list[str] | None = None,
) -> None:
    """Apply a Workspace CR from the given directory.

    Args:
        name: Workspace name (maps to {name}.yaml in workspaces_dir)
        workspaces_dir: Directory containing workspace YAML manifests
        as_user: Impersonate this user (--as flag)
        as_groups: Impersonate these groups (--as-group flags)
    """
    manifest_path = workspaces_dir / f"{name}.yaml"
    cmd = ["kubectl", "apply", "-f", str(manifest_path)]
    if as_user:
        cmd += ["--as", as_user]
    for group in as_groups or []:
        cmd += ["--as-group", group]
    subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
    )


def kubectl_delete_workspace(name: str, namespace: str = "default") -> None:
    """Delete a Workspace CR via kubectl (ignores not-found errors).

    Args:
        name: Workspace resource name
        namespace: Kubernetes namespace
    """
    subprocess.run(
        ["kubectl", "delete", "workspace", name, "-n", namespace, "--ignore-not-found"],
        check=True,
        capture_output=True,
        text=True,
    )


def kubectl_patch_workspace(
    name: str,
    patch: str,
    namespace: str = "default",
    as_user: str | None = None,
    as_groups: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Patch a Workspace CR via kubectl (merge strategy).

    Args:
        name: Workspace resource name
        patch: JSON merge patch string
        namespace: Kubernetes namespace
        as_user: Impersonate this user (--as flag)
        as_groups: Impersonate these groups (--as-group flags)

    Returns:
        CompletedProcess (caller checks returncode for permission tests)
    """
    cmd = ["kubectl", "patch", "workspace", name, "-n", namespace, "--type=merge", "-p", patch]
    if as_user:
        cmd += ["--as", as_user]
    for group in as_groups or []:
        cmd += ["--as-group", group]
    return subprocess.run(cmd, capture_output=True, text=True)


def kubectl_workspace_exists(name: str, namespace: str = "default") -> bool:
    """Check if a Workspace CR exists via kubectl."""
    result = subprocess.run(
        ["kubectl", "get", "workspace", name, "-n", namespace],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def ensure_workspace_no_longer_exists(name: str, namespace: str = "default", timeout_s: int = 60) -> None:
    """Poll until a Workspace CR no longer exists.

    Raises AssertionError if the workspace still exists after timeout_s.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not kubectl_workspace_exists(name, namespace):
            return
        time.sleep(5)
    raise AssertionError(f"Workspace '{name}' still exists after {timeout_s}s")


def kubectl_get_workspace(
    name: str,
    namespace: str = "default",
    as_user: str | None = None,
    as_groups: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Get a Workspace CR via kubectl.

    Args:
        name: Workspace resource name
        namespace: Kubernetes namespace
        as_user: Impersonate this user (--as flag)
        as_groups: Impersonate these groups (--as-group flags)

    Returns:
        CompletedProcess (caller checks returncode for permission tests)
    """
    cmd = ["kubectl", "get", "workspace", name, "-n", namespace]
    if as_user:
        cmd += ["--as", as_user]
    for group in as_groups or []:
        cmd += ["--as-group", group]
    return subprocess.run(cmd, capture_output=True, text=True)


def kubectl_get_workspace_status(
    name: str,
    namespace: str = "default",
    as_user: str | None = None,
    as_groups: list[str] | None = None,
) -> str:
    """Derive workspace status from conditions via kubectl.

    Evaluates the same condition logic as the jd CLI status rules:
    - Degraded condition True → "Degraded"
    - Stopped condition True → "Stopped"
    - Available condition True → "Running"
    - Progressing condition True → "Starting" or "Stopping" (based on desiredStatus)
    - Otherwise → "Unknown"

    Args:
        name: Workspace resource name
        namespace: Kubernetes namespace
        as_user: Impersonate this user (--as flag)
        as_groups: Impersonate these groups (--as-group flags)

    Returns:
        Derived status string (e.g., "Running", "Stopped", "Starting", "Degraded")

    Raises:
        subprocess.CalledProcessError: If kubectl fails (e.g., workspace not found)
        ValueError: If conditions cannot be parsed
    """
    cmd = [
        "kubectl",
        "get",
        "workspace",
        name,
        "-n",
        namespace,
        "-o",
        "json",
    ]
    if as_user:
        cmd += ["--as", as_user]
    for group in as_groups or []:
        cmd += ["--as-group", group]
    result = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
    )
    resource = json.loads(result.stdout)
    conditions = resource.get("status", {}).get("conditions", [])
    desired_status = resource.get("spec", {}).get("desiredStatus", "")

    condition_map: dict[str, str] = {}
    for c in conditions:
        condition_map[c["type"]] = c["status"]

    if condition_map.get("Degraded") == "True":
        return "Degraded"
    if condition_map.get("Stopped") == "True":
        return "Stopped"
    if condition_map.get("Available") == "True":
        return "Running"
    if condition_map.get("Progressing") == "True":
        return "Stopping" if desired_status == "Stopped" else "Starting"

    return "Unknown"


def _kubectl_get_workspace_field(name: str, jsonpath: str, field_label: str, namespace: str = "default") -> str:
    result = subprocess.run(
        ["kubectl", "get", "workspace", name, "-n", namespace, "-o", f"jsonpath={jsonpath}"],
        check=True,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    if not value:
        raise ValueError(f"Workspace '{name}' has no {field_label}")
    return value


def kubectl_get_workspace_jsonpath(
    name: str,
    jsonpath: str,
    namespace: str = "default",
    as_user: str | None = None,
    as_groups: list[str] | None = None,
) -> str:
    """Get a workspace field via jsonpath expression (with optional impersonation)."""
    cmd = ["kubectl", "get", "workspace", name, "-n", namespace, "-o", f"jsonpath={jsonpath}"]
    if as_user:
        cmd += ["--as", as_user]
    for group in as_groups or []:
        cmd += ["--as-group", group]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def kubectl_get_workspace_owner(name: str, namespace: str = "default") -> str:
    """Get the workspace owner from the created-by annotation."""
    return _kubectl_get_workspace_field(
        name,
        r"{.metadata.annotations['workspace\.jupyter\.org/created-by']}",
        "workspace.jupyter.org/created-by annotation",
        namespace,
    )


def kubectl_get_workspace_ownership_type(name: str, namespace: str = "default") -> str:
    """Get the workspace ownershipType from spec (e.g., "OwnerOnly", "Public")."""
    return _kubectl_get_workspace_field(
        name,
        "{.spec.ownershipType}",
        "spec.ownershipType",
        namespace,
    )


def kubectl_get_workspace_access_url(name: str, namespace: str = "default") -> str:
    """Get workspace accessURL from status via kubectl."""
    return _kubectl_get_workspace_field(
        name,
        "{.status.accessURL}",
        ".status.accessURL",
        namespace,
    )


def kubectl_poll_workspace_status(
    name: str,
    target_status: str,
    namespace: str = "default",
    timeout_s: int = 180,
    interval_s: int = 10,
    as_user: str | None = None,
    as_groups: list[str] | None = None,
) -> None:
    """Poll workspace status via kubectl until it matches target or timeout.

    Args:
        name: Workspace resource name
        target_status: Expected status (e.g., "Running", "Stopped")
        namespace: Kubernetes namespace
        timeout_s: Maximum wait time in seconds
        interval_s: Seconds between polls
        as_user: Impersonate this user (--as flag)
        as_groups: Impersonate these groups (--as-group flags)

    Raises:
        TimeoutError: If workspace does not reach target_status within timeout_s
    """
    deadline = time.time() + timeout_s
    last_status = ""
    while time.time() < deadline:
        try:
            last_status = kubectl_get_workspace_status(name, namespace, as_user=as_user, as_groups=as_groups)
            if last_status == target_status:
                return
        except (subprocess.CalledProcessError, ValueError):
            pass
        time.sleep(interval_s)
    raise TimeoutError(
        f"Workspace '{name}' did not reach status '{target_status}' within {timeout_s}s (last: {last_status})"
    )
