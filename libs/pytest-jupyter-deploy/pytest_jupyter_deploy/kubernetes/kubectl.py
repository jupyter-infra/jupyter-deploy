"""Generic kubectl runner for E2E tests.

Template- and resource-agnostic: callers pass raw kubectl args and optionally an
impersonated identity. Returns the CompletedProcess so callers choose what to assert on
— stdout (read tests), returncode (permission tests) — rather than the runner deciding.
For workspace-CR-specific helpers see workspaces/kubectl.py; for RBAC assertions see
kubernetes/rbac.py.
"""

import subprocess


def run_kubectl(
    *args: str,
    as_user: str | None = None,
    as_groups: list[str] | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a kubectl command, optionally impersonating a user/groups.

    Args:
        *args: kubectl arguments (e.g. "get", "workspacetemplates", "-n", "default")
        as_user: Impersonate this user (--as flag)
        as_groups: Impersonate these groups (--as-group flags)
        check: Raise CalledProcessError on non-zero exit (default False, so permission
            tests can inspect returncode)

    Returns:
        The CompletedProcess (stdout/stderr captured as text).
    """
    cmd = ["kubectl", *args]
    if as_user:
        cmd += ["--as", as_user]
    for group in as_groups or []:
        cmd += ["--as-group", group]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)
