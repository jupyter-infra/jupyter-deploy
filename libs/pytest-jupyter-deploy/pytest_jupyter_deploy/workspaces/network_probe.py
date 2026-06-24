"""Probe workspace network reachability to verify NetworkPolicy enforcement.

Runs a throwaway `curl` pod in a chosen namespace and attempts a TCP/HTTP
connection to a workspace Service. A NetworkPolicy that denies the source
manifests as a connection timeout; an allowed source connects (any HTTP status,
including 404, counts as reachable).

Requires NetworkPolicy enforcement to be active on the cluster (on EKS, the VPC
CNI addon must set enableNetworkPolicy=true) — otherwise every probe is allowed.
"""

import json
import subprocess
import time

# Operator-generated Service name for a workspace: "workspace-<name>-service".
_WORKSPACE_SERVICE_FMT = "workspace-{name}-service"
_CURL_IMAGE = "curlimages/curl:latest"
# curl exit 28 == operation timeout → the connection was blocked (denied).
_CURL_TIMEOUT_EXIT = 28


def workspace_service_host(workspace_name: str, namespace: str = "default") -> str:
    """Return the in-cluster DNS host for a workspace's Service."""
    service = _WORKSPACE_SERVICE_FMT.format(name=workspace_name)
    return f"{service}.{namespace}.svc.cluster.local"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def _wait_for_terminated_exit_code(pod_name: str, namespace: str, timeout_s: int) -> int:
    """Poll until the pod's container terminates; return its exit code."""
    deadline = time.time() + timeout_s
    jsonpath = "{.status.containerStatuses[0].state.terminated.exitCode}"
    while time.time() < deadline:
        result = _run(["kubectl", "get", "pod", pod_name, "-n", namespace, "-o", f"jsonpath={jsonpath}"])
        code = result.stdout.strip()
        if code != "":
            return int(code)
        time.sleep(2)
    raise RuntimeError(f"probe pod '{pod_name}' in ns '{namespace}' did not terminate within {timeout_s}s")


def probe_workspace(
    workspace_name: str,
    *,
    from_namespace: str,
    workspace_namespace: str = "default",
    port: int = 8888,
    pod_labels: dict[str, str] | None = None,
    connect_timeout_s: int = 8,
    pod_name: str = "netpol-probe",
) -> bool:
    """Attempt to reach a workspace Service from a pod in from_namespace.

    Runs a one-shot curl pod (optionally carrying pod_labels, to prove the policy
    does not key on pod labels), connects to the workspace Service on port, then
    reads the container's terminated exit code (not kubectl's, which is
    unreliable for run --rm). The pod is always deleted on the way out.

    Returns:
        True if the connection was allowed (curl reached the endpoint),
        False if it was denied (connection timed out).

    Raises:
        RuntimeError: if curl failed for a reason other than a connect timeout
            (e.g. DNS failure, image pull error) — an ambiguous result that must
            not be silently read as "denied".
    """
    host = workspace_service_host(workspace_name, workspace_namespace)
    url = f"http://{host}:{port}/"

    overrides: dict = {"spec": {"restartPolicy": "Never"}}
    if pod_labels:
        overrides["metadata"] = {"labels": pod_labels}

    create = _run(
        [
            "kubectl",
            "run",
            pod_name,
            "-n",
            from_namespace,
            "--image",
            _CURL_IMAGE,
            "--restart=Never",
            f"--overrides={json.dumps(overrides)}",
            "--command",
            "--",
            "curl",
            "-s",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            "--connect-timeout",
            str(connect_timeout_s),
            "--max-time",
            str(connect_timeout_s * 2),
            url,
        ]
    )
    if create.returncode != 0:
        raise RuntimeError(f"failed to create probe pod '{pod_name}' in ns '{from_namespace}': {create.stderr!r}")

    try:
        exit_code = _wait_for_terminated_exit_code(pod_name, from_namespace, timeout_s=connect_timeout_s * 6)
    finally:
        delete_probe_pod(pod_name, from_namespace)

    if exit_code == 0:
        return True
    if exit_code == _CURL_TIMEOUT_EXIT:
        return False
    raise RuntimeError(
        f"probe to {url} from ns '{from_namespace}' failed ambiguously (curl exit {exit_code}) — "
        "not a clean allow (0) or deny (28)"
    )


def delete_probe_pod(pod_name: str, namespace: str) -> None:
    """Best-effort cleanup of a probe pod."""
    _run(["kubectl", "delete", "pod", pod_name, "-n", namespace, "--ignore-not-found", "--wait=false"])
