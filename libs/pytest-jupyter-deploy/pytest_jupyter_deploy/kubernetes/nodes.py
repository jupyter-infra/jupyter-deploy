"""Node inspection helpers for E2E tests (counting, allocatable CPU).

Template-agnostic: callers pass the node label selector that identifies the pool they
care about (e.g. jupyter-deploy/role=components, inference/role=system), so these work
for any template's node grouping.
"""

import subprocess


def get_node_names(label_selector: str) -> list[str]:
    """Names of Ready nodes matching a label selector (e.g. 'jupyter-deploy/role=components')."""
    result = subprocess.run(
        ["kubectl", "get", "nodes", "-l", label_selector, "-o", "jsonpath={.items[*].metadata.name}"],
        capture_output=True,
        text=True,
        check=False,
    )
    out = result.stdout.strip()
    return out.split() if out else []


def parse_cpu_to_millicores(quantity: str) -> int:
    """Parse a Kubernetes CPU quantity ('2', '1930m') to integer millicores."""
    quantity = quantity.strip()
    if quantity.endswith("m"):
        return int(quantity[:-1])
    return int(float(quantity) * 1000)


def get_node_allocatable_cpu_millicores(node_name: str) -> int:
    """Allocatable CPU (millicores) of a node — the per-node sizing unit for ballast tests.

    Deriving ballast CPU requests from this keeps a scale-up test independent of the node's
    instance type: a hardcoded request would either never trigger scale-up on a large SKU
    or over-trigger on a small one.
    """
    result = subprocess.run(
        ["kubectl", "get", "node", node_name, "-o", "jsonpath={.status.allocatable.cpu}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return parse_cpu_to_millicores(result.stdout.strip())
