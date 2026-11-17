from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from kubernetes.client import ApiClient, CoreV1Api
from kubernetes.stream import stream as k8s_stream


class NodeConditionStatus(str, Enum):
    READY = "Ready"
    NOT_READY = "NotReady"
    UNKNOWN = "Unknown"


class PodPhase(str, Enum):
    RUNNING = "Running"
    PENDING = "Pending"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class NodeInfo:
    name: str
    status: NodeConditionStatus
    resource: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PodInfo:
    name: str
    phase: PodPhase
    # Container names in spec order; the first is the pod's main container.
    containers: tuple[str, ...] = ()


def _parse_node_status(node: object) -> NodeConditionStatus:
    status = getattr(node, "status", None)
    conditions = getattr(status, "conditions", None) if status else None
    if conditions:
        for condition in conditions:
            if condition.type == "Ready":
                return NodeConditionStatus.READY if condition.status == "True" else NodeConditionStatus.NOT_READY
    return NodeConditionStatus.UNKNOWN


def _container_names(pod: object) -> tuple[str, ...]:
    spec = getattr(pod, "spec", None)
    return tuple(container.name for container in (getattr(spec, "containers", None) or []))


def _parse_pod_phase(pod: object) -> PodPhase:
    status = getattr(pod, "status", None)
    phase = getattr(status, "phase", None) if status else None
    try:
        return PodPhase(phase) if phase else PodPhase.UNKNOWN
    except ValueError:
        return PodPhase.UNKNOWN


def list_nodes(
    api: CoreV1Api,
    label_selector: str | None = None,
    limit: int | None = None,
    _continue: str | None = None,
) -> tuple[list[NodeInfo], str | None]:
    node_list = api.list_node(
        label_selector=label_selector or None,
        limit=limit or None,
        _continue=_continue or None,
    )

    nodes = []
    for node in node_list.items:
        name = (node.metadata.name or "") if node.metadata else ""
        nodes.append(NodeInfo(name=name, status=_parse_node_status(node)))

    next_token = node_list.metadata._continue if node_list.metadata else None
    return nodes, next_token or None


def get_node(api: CoreV1Api, name: str) -> NodeInfo:
    node = api.read_node(name=name)
    node_name = (node.metadata.name or "") if node.metadata else ""
    resource: dict[str, Any] = ApiClient().sanitize_for_serialization(node)
    return NodeInfo(name=node_name, status=_parse_node_status(node), resource=resource)


def list_pods(
    api: CoreV1Api,
    namespace: str,
    label_selector: str | None = None,
    limit: int | None = None,
    _continue: str | None = None,
) -> tuple[list[PodInfo], str | None]:
    pod_list = api.list_namespaced_pod(
        namespace=namespace,
        label_selector=label_selector or None,
        limit=limit or None,
        _continue=_continue or None,
    )

    pods = []
    for pod in pod_list.items:
        name = (pod.metadata.name or "") if pod.metadata else ""
        pods.append(PodInfo(name=name, phase=_parse_pod_phase(pod), containers=_container_names(pod)))

    next_token = pod_list.metadata._continue if pod_list.metadata else None
    return pods, next_token or None


def get_pod(api: CoreV1Api, name: str, namespace: str) -> PodInfo:
    pod = api.read_namespaced_pod(name=name, namespace=namespace)
    pod_name = (pod.metadata.name or "") if pod.metadata else ""
    return PodInfo(name=pod_name, phase=_parse_pod_phase(pod), containers=_container_names(pod))


@dataclass(frozen=True)
class ExecResult:
    stdout: str
    stderr: str
    returncode: int


def exec_pod(
    api: CoreV1Api,
    name: str,
    namespace: str,
    command: list[str],
    container: str | None = None,
) -> ExecResult:
    kwargs: dict[str, object] = {
        "name": name,
        "namespace": namespace,
        "command": command,
        "stderr": True,
        "stdin": False,
        "stdout": True,
        "tty": False,
        "_preload_content": False,
    }
    if container:
        kwargs["container"] = container

    resp = k8s_stream(api.connect_get_namespaced_pod_exec, **kwargs)
    resp.run_forever(timeout=60)

    stdout = resp.read_stdout() or ""
    stderr = resp.read_stderr() or ""
    returncode = resp.returncode if hasattr(resp, "returncode") and resp.returncode is not None else 0
    return ExecResult(stdout=stdout, stderr=stderr, returncode=returncode)
