"""Helpers to tune the jupyter-k8s operator Deployment at test time.

Some operator behaviors are controlled by container CLI flags rather than chart
values surfaced to the deployment template (e.g. the idle-check interval, which
is operator-internal tuning we deliberately do NOT expose as a jd variable).
Tests that need a faster cadence patch the controller-manager Deployment
directly and restore it on teardown.
"""

import json
import subprocess

OPERATOR_DEPLOYMENT = "jupyter-k8s-controller-manager"
OPERATOR_CONTAINER = "manager"
OPERATOR_NAMESPACE = "jupyter-k8s-system"

_IDLE_CHECK_FLAG = "--idle-check-interval"


def _container_index(deployment: str, container: str, namespace: str) -> int:
    """Return the index of the named container in the Deployment's pod spec."""
    result = subprocess.run(
        [
            "kubectl",
            "get",
            "deployment",
            deployment,
            "-n",
            namespace,
            "-o",
            "jsonpath={.spec.template.spec.containers[*].name}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    names = result.stdout.split()
    return names.index(container)


def get_operator_args(
    deployment: str = OPERATOR_DEPLOYMENT,
    container: str = OPERATOR_CONTAINER,
    namespace: str = OPERATOR_NAMESPACE,
) -> list[str]:
    """Return the current args list of the operator container."""
    idx = _container_index(deployment, container, namespace)
    result = subprocess.run(
        [
            "kubectl",
            "get",
            "deployment",
            deployment,
            "-n",
            namespace,
            "-o",
            f"jsonpath={{.spec.template.spec.containers[{idx}].args}}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    raw = result.stdout.strip()
    return json.loads(raw) if raw else []


def set_operator_args(
    args: list[str],
    deployment: str = OPERATOR_DEPLOYMENT,
    container: str = OPERATOR_CONTAINER,
    namespace: str = OPERATOR_NAMESPACE,
    wait_timeout_s: int = 180,
) -> None:
    """Replace the operator container's args and wait for the rollout."""
    # A strategic-merge patch matches the container by name and replaces its args.
    patch = json.dumps({"spec": {"template": {"spec": {"containers": [{"name": container, "args": args}]}}}})
    subprocess.run(
        ["kubectl", "patch", "deployment", deployment, "-n", namespace, "--type=strategic", "-p", patch],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["kubectl", "rollout", "status", "deployment", deployment, "-n", namespace, f"--timeout={wait_timeout_s}s"],
        check=True,
        capture_output=True,
        text=True,
    )


def with_idle_check_interval(args: list[str], interval: str) -> list[str]:
    """Return a copy of args with --idle-check-interval set to interval."""
    flag = f"{_IDLE_CHECK_FLAG}={interval}"
    out = [a for a in args if not a.startswith(f"{_IDLE_CHECK_FLAG}=")]
    out.append(flag)
    return out
