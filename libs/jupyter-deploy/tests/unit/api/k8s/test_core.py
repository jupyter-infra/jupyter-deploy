import unittest
from unittest.mock import Mock, patch

from kubernetes.client import CoreV1Api
from kubernetes.client.exceptions import ApiException

from jupyter_deploy.api.k8s.core import (
    ExecResult,
    NodeConditionStatus,
    PodPhase,
    exec_pod,
    get_node,
    get_pod,
    list_nodes,
    list_pods,
)

_NOT_FOUND = ApiException(status=404, reason="Not Found")


def _mock_node(name: str, ready: str = "True") -> Mock:
    node: Mock = Mock()
    node.metadata.name = name
    condition: Mock = Mock()
    condition.type = "Ready"
    condition.status = ready
    node.status.conditions = [condition]
    return node


def _mock_node_list(nodes: list[Mock], continue_token: str | None = None) -> Mock:
    metadata: Mock = Mock()
    metadata._continue = continue_token
    return Mock(items=nodes, metadata=metadata)


def _mock_container(name: str) -> Mock:
    container: Mock = Mock()
    container.name = name
    return container


def _mock_pod(name: str, phase: str = "Running", containers: tuple[str, ...] = ("app",)) -> Mock:
    pod: Mock = Mock()
    pod.metadata.name = name
    pod.status.phase = phase
    pod.spec.containers = [_mock_container(container) for container in containers]
    return pod


def _mock_pod_list(pods: list[Mock], continue_token: str | None = None) -> Mock:
    metadata: Mock = Mock()
    metadata._continue = continue_token
    return Mock(items=pods, metadata=metadata)


class TestListNodes(unittest.TestCase):
    def test_returns_node_names_and_statuses(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.list_node.return_value = _mock_node_list([_mock_node("node-1"), _mock_node("node-2")])

        nodes, next_token = list_nodes(mock_api)

        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0].name, "node-1")
        self.assertEqual(nodes[0].status, NodeConditionStatus.READY)
        self.assertIsNone(next_token)
        mock_api.list_node.assert_called_once_with(label_selector=None, limit=None, _continue=None)

    def test_returns_not_ready_status(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.list_node.return_value = _mock_node_list([_mock_node("node-1", ready="False")])

        nodes, _ = list_nodes(mock_api)

        self.assertEqual(nodes[0].status, NodeConditionStatus.NOT_READY)

    def test_passes_label_selector(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.list_node.return_value = _mock_node_list([])

        list_nodes(mock_api, label_selector="role=worker")

        mock_api.list_node.assert_called_once_with(label_selector="role=worker", limit=None, _continue=None)

    def test_passes_limit_and_continue(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.list_node.return_value = _mock_node_list([_mock_node("node-1")], continue_token="next-abc")

        _, next_token = list_nodes(mock_api, limit=1, _continue="start-abc")

        self.assertEqual(next_token, "next-abc")
        mock_api.list_node.assert_called_once_with(label_selector=None, limit=1, _continue="start-abc")

    def test_returns_unknown_when_no_conditions(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        node: Mock = Mock()
        node.metadata.name = "node-1"
        node.status.conditions = None
        mock_api.list_node.return_value = _mock_node_list([node])

        nodes, _ = list_nodes(mock_api)

        self.assertEqual(nodes[0].status, NodeConditionStatus.UNKNOWN)

    def test_raises_on_api_error(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.list_node.side_effect = _NOT_FOUND

        with self.assertRaises(ApiException):
            list_nodes(mock_api)


class TestGetNode(unittest.TestCase):
    @patch("jupyter_deploy.api.k8s.core.ApiClient")
    def test_returns_node_info(self, mock_api_client_cls: Mock) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.read_node.return_value = _mock_node("node-1")
        mock_api_client_cls.return_value.sanitize_for_serialization.return_value = {"metadata": {"name": "node-1"}}

        result = get_node(mock_api, name="node-1")

        self.assertEqual(result.name, "node-1")
        self.assertEqual(result.status, NodeConditionStatus.READY)
        self.assertEqual(result.resource, {"metadata": {"name": "node-1"}})
        mock_api.read_node.assert_called_once_with(name="node-1")

    def test_raises_on_api_error(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.read_node.side_effect = _NOT_FOUND

        with self.assertRaises(ApiException):
            get_node(mock_api, name="nonexistent")


class TestListPods(unittest.TestCase):
    def test_returns_pod_names_and_phases(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.list_namespaced_pod.return_value = _mock_pod_list([_mock_pod("pod-1"), _mock_pod("pod-2")])

        pods, next_token = list_pods(mock_api, namespace="default")

        self.assertEqual(len(pods), 2)
        self.assertEqual(pods[0].name, "pod-1")
        self.assertEqual(pods[0].phase, PodPhase.RUNNING)
        self.assertIsNone(next_token)
        mock_api.list_namespaced_pod.assert_called_once_with(
            namespace="default", label_selector=None, limit=None, _continue=None
        )

    def test_returns_container_names_in_spec_order(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.list_namespaced_pod.return_value = _mock_pod_list(
            [_mock_pod("pod-1", containers=("workspace", "ws-proxy"))]
        )

        pods, _ = list_pods(mock_api, namespace="default")

        self.assertEqual(pods[0].containers, ("workspace", "ws-proxy"))

    def test_passes_label_selector(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.list_namespaced_pod.return_value = _mock_pod_list([])

        list_pods(mock_api, namespace="default", label_selector="app=web")

        mock_api.list_namespaced_pod.assert_called_once_with(
            namespace="default", label_selector="app=web", limit=None, _continue=None
        )

    def test_passes_limit_and_continue(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.list_namespaced_pod.return_value = _mock_pod_list([_mock_pod("pod-1")], continue_token="next-xyz")

        _, next_token = list_pods(mock_api, namespace="default", limit=1, _continue="start-xyz")

        self.assertEqual(next_token, "next-xyz")
        mock_api.list_namespaced_pod.assert_called_once_with(
            namespace="default", label_selector=None, limit=1, _continue="start-xyz"
        )

    def test_returns_unknown_phase_for_unrecognized_value(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.list_namespaced_pod.return_value = _mock_pod_list([_mock_pod("pod-1", phase="SomethingNew")])

        pods, _ = list_pods(mock_api, namespace="default")

        self.assertEqual(pods[0].phase, PodPhase.UNKNOWN)

    def test_raises_on_api_error(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.list_namespaced_pod.side_effect = _NOT_FOUND

        with self.assertRaises(ApiException):
            list_pods(mock_api, namespace="default")


class TestGetPod(unittest.TestCase):
    def test_returns_pod_info(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.read_namespaced_pod.return_value = _mock_pod("pod-1", phase="Pending")

        result = get_pod(mock_api, name="pod-1", namespace="default")

        self.assertEqual(result.name, "pod-1")
        self.assertEqual(result.phase, PodPhase.PENDING)
        self.assertEqual(result.containers, ("app",))
        mock_api.read_namespaced_pod.assert_called_once_with(name="pod-1", namespace="default")

    def test_raises_on_api_error(self) -> None:
        mock_api: Mock = Mock(spec=CoreV1Api)
        mock_api.read_namespaced_pod.side_effect = _NOT_FOUND

        with self.assertRaises(ApiException):
            get_pod(mock_api, name="nonexistent", namespace="default")


class TestExecPod(unittest.TestCase):
    @patch("jupyter_deploy.api.k8s.core.k8s_stream")
    def test_returns_exec_result(self, mock_stream: Mock) -> None:
        mock_resp: Mock = Mock()
        mock_resp.read_stdout.return_value = "hello"
        mock_resp.read_stderr.return_value = ""
        mock_resp.returncode = 0
        mock_stream.return_value = mock_resp
        mock_api: Mock = Mock(spec=CoreV1Api)

        result = exec_pod(mock_api, name="pod-1", namespace="default", command=["echo", "hello"])

        self.assertEqual(result, ExecResult(stdout="hello", stderr="", returncode=0))
        mock_stream.assert_called_once_with(
            mock_api.connect_get_namespaced_pod_exec,
            name="pod-1",
            namespace="default",
            command=["echo", "hello"],
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=False,
        )

    @patch("jupyter_deploy.api.k8s.core.k8s_stream")
    def test_passes_container(self, mock_stream: Mock) -> None:
        mock_resp: Mock = Mock()
        mock_resp.read_stdout.return_value = ""
        mock_resp.read_stderr.return_value = ""
        mock_resp.returncode = 0
        mock_stream.return_value = mock_resp
        mock_api: Mock = Mock(spec=CoreV1Api)

        exec_pod(mock_api, name="pod-1", namespace="default", command=["ls"], container="main")

        mock_stream.assert_called_once_with(
            mock_api.connect_get_namespaced_pod_exec,
            name="pod-1",
            namespace="default",
            command=["ls"],
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=False,
            container="main",
        )

    @patch("jupyter_deploy.api.k8s.core.k8s_stream")
    def test_returns_stderr_and_nonzero_returncode(self, mock_stream: Mock) -> None:
        mock_resp: Mock = Mock()
        mock_resp.read_stdout.return_value = ""
        mock_resp.read_stderr.return_value = "error"
        mock_resp.returncode = 1
        mock_stream.return_value = mock_resp
        mock_api: Mock = Mock(spec=CoreV1Api)

        result = exec_pod(mock_api, name="pod-1", namespace="default", command=["false"])

        self.assertEqual(result, ExecResult(stdout="", stderr="error", returncode=1))
