"""E2E test utilities for the EKS OIDC template."""

import contextlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.kubernetes.kubectl import run_kubectl
from pytest_jupyter_deploy.workspaces.kubectl import kubectl_list_workspace_pods

# Relative to the pytest working directory, like the sibling suites' failure artifacts:
# the justfile mounts ./test-results into the container and the e2e job uploads it.
START_PHASES_DIR = Path("test-results") / "start-phases"

# The jupyter-k8s operator names the workspace's application container "workspace"
# (PrimaryContainerName in internal/controller/constants.go).
PRIMARY_CONTAINER = "workspace"

StartPhaseRecord = dict[str, Any]


def utc_now() -> datetime:
    return datetime.now(UTC)


def get_workspace_pod(name: str, namespace: str) -> dict[str, Any]:
    """Return the JSON of the one live pod backing a workspace."""
    pods = kubectl_list_workspace_pods(name, namespace)
    assert len(pods) == 1, f"Expected one live pod for workspace {name}, found {len(pods)}"
    return pods[0]


def record_workspace_start(
    case: str,
    e2e_deployment: EndToEndDeployment,
    workspace: str,
    namespace: str,
    requested: datetime,
    pod: dict[str, Any],
) -> StartPhaseRecord:
    """Write and return the start-phase record of a workspace that just reached Running.

    `requested` is the test runner's clock; the pod and Workspace timestamps come from
    the cluster. ContainersReady is the TCP readiness probe passing, so the gap after
    the container start is the image's environment sync before the server listens.
    """
    record = _build_start_phase_record(
        case=case,
        workspace=workspace,
        deployment_id=_deployment_id_or_none(e2e_deployment),
        requested=requested,
        pod=pod,
        workspace_available=_workspace_condition_time(workspace, namespace, "Available"),
    )
    write_start_phase_record(record)
    return record


def write_start_phase_record(record: StartPhaseRecord) -> Path:
    """Write the record as test-results/start-phases/<case>.json and return the path."""
    START_PHASES_DIR.mkdir(parents=True, exist_ok=True)
    path = START_PHASES_DIR / f"{record['case']}.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def _build_start_phase_record(
    case: str,
    workspace: str,
    deployment_id: str | None,
    requested: datetime,
    pod: dict[str, Any],
    workspace_available: datetime | None,
) -> StartPhaseRecord:
    pod_scheduled = _pod_condition_time(pod, "PodScheduled")
    pod_initialized = _pod_condition_time(pod, "Initialized")
    container_started = _container_started_time(pod, PRIMARY_CONTAINER)
    containers_ready = _pod_condition_time(pod, "ContainersReady")
    return {
        "case": case,
        "workspace": workspace,
        "deployment_id": deployment_id,
        "node": pod["spec"].get("nodeName"),
        "timestamps": {
            "requested": _isoformat(requested),
            "pod_scheduled": _isoformat(pod_scheduled),
            "pod_initialized": _isoformat(pod_initialized),
            "container_started": _isoformat(container_started),
            "containers_ready": _isoformat(containers_ready),
            "workspace_available": _isoformat(workspace_available),
        },
        "durations_s": {
            "requested_to_pod_scheduled": _seconds_between(requested, pod_scheduled),
            "pod_scheduled_to_container_started": _seconds_between(pod_scheduled, container_started),
            "container_started_to_containers_ready": _seconds_between(container_started, containers_ready),
            "containers_ready_to_workspace_available": _seconds_between(containers_ready, workspace_available),
            "requested_to_workspace_available": _seconds_between(requested, workspace_available),
        },
    }


def _deployment_id_or_none(e2e_deployment: EndToEndDeployment) -> str | None:
    with contextlib.suppress(Exception):
        return e2e_deployment.cli.get_str_output("deployment_id")
    return None


def _workspace_condition_time(name: str, namespace: str, condition_type: str) -> datetime | None:
    result = run_kubectl("get", "workspace", name, "-n", namespace, "-o", "json", check=True)
    conditions = json.loads(result.stdout).get("status", {}).get("conditions", [])
    return _condition_time(conditions, condition_type)


def _pod_condition_time(pod: dict[str, Any], condition_type: str) -> datetime | None:
    return _condition_time(pod["status"].get("conditions", []), condition_type)


def _condition_time(conditions: list[dict[str, Any]], condition_type: str) -> datetime | None:
    for condition in conditions:
        if condition["type"] == condition_type and condition["status"] == "True":
            return _parse_k8s_time(condition.get("lastTransitionTime"))
    return None


def _container_started_time(pod: dict[str, Any], container: str) -> datetime | None:
    for status in pod["status"].get("containerStatuses", []):
        if status["name"] == container:
            return _parse_k8s_time(status.get("state", {}).get("running", {}).get("startedAt"))
    return None


def _parse_k8s_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def _seconds_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return round((end - start).total_seconds(), 1)
