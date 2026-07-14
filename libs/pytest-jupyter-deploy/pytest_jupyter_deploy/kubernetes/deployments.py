"""Deployment inspection helpers for E2E tests.

Template-agnostic: callers pass the label selector and namespace, so these work for any
platform component (cluster-autoscaler, router, operator, ...).
"""

import subprocess


def get_ready_replica_count(label_selector: str, namespace: str) -> int:
    """Total ready replicas across the Deployments matching a label selector in a namespace.

    Returns 0 when no Deployment matches or none has ready replicas (readyReplicas is absent
    on a freshly-created Deployment). A selector may match more than one Deployment, so the
    per-Deployment counts are summed.
    """
    result = subprocess.run(
        [
            "kubectl",
            "get",
            "deployment",
            "-n",
            namespace,
            "-l",
            label_selector,
            "-o",
            "jsonpath={.items[*].status.readyReplicas}",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return sum(int(n) for n in result.stdout.split())
