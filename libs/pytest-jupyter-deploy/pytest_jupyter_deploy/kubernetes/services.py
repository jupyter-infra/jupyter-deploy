"""Service inspection helpers for E2E tests."""

import json

from pytest_jupyter_deploy.kubernetes.kubectl import run_kubectl


def get_service_port(name: str, namespace: str) -> tuple[int, str]:
    """The (port, port name) of a single-port Service; raises ValueError if it exposes none or several."""
    result = run_kubectl("get", "service", name, "-n", namespace, "-o", "json", check=True)
    ports = json.loads(result.stdout)["spec"].get("ports", [])
    if len(ports) != 1:
        raise ValueError(f"expected exactly one port on Service '{namespace}/{name}', got {ports}")
    return int(ports[0]["port"]), ports[0].get("name", "")
