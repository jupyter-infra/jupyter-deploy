import subprocess
import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.api.k8s.core import ExecResult, NodeConditionStatus, NodeInfo, PodInfo, PodPhase
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import (
    InstructionError,
    InstructionNotFoundError,
    InteractiveSessionError,
    InteractiveSessionTimeoutError,
)
from jupyter_deploy.provider.k8s.k8s_core_runner import K8sCoreRunner
from jupyter_deploy.provider.resolved_argdefs import StrResolvedInstructionArgument


class TestK8sCoreRunner(unittest.TestCase):
    def _make_runner(self, kubeconfig_path: str | None = None) -> K8sCoreRunner:
        mock_api_client: Mock = Mock()
        with patch("jupyter_deploy.provider.k8s.k8s_core_runner.client") as mock_client_mod:
            mock_client_mod.CoreV1Api.return_value = Mock()
            mock_client_mod.AppsV1Api.return_value = Mock()
            return K8sCoreRunner(NullDisplay(), api_client=mock_api_client, kubeconfig_path=kubeconfig_path)

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_list_nodes_returns_names_and_count(self, mock_k8s_core: Mock) -> None:
        runner = self._make_runner()
        mock_k8s_core.list_nodes.return_value = (
            [
                NodeInfo(name="node-1", status=NodeConditionStatus.READY),
                NodeInfo(name="node-2", status=NodeConditionStatus.READY),
            ],
            None,
        )

        result = runner.execute_instruction(instruction_name="list-nodes", resolved_arguments={})

        self.assertEqual(result["NodeNames"].value, ["node-1", "node-2"])
        self.assertEqual(result["NextToken"].value, "")
        mock_k8s_core.list_nodes.assert_called_once_with(
            runner.core_api, label_selector=None, limit=None, _continue=None
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_list_nodes_with_label_selector(self, mock_k8s_core: Mock) -> None:
        runner = self._make_runner()
        mock_k8s_core.list_nodes.return_value = ([], None)

        runner.execute_instruction(
            instruction_name="list-nodes",
            resolved_arguments={
                "query": StrResolvedInstructionArgument(argument_name="query", value="role=worker"),
            },
        )

        mock_k8s_core.list_nodes.assert_called_once_with(
            runner.core_api, label_selector="role=worker", limit=None, _continue=None
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_list_nodes_with_pagination(self, mock_k8s_core: Mock) -> None:
        runner = self._make_runner()
        mock_k8s_core.list_nodes.return_value = (
            [NodeInfo(name="node-1", status=NodeConditionStatus.READY)],
            "abc123",
        )

        result = runner.execute_instruction(
            instruction_name="list-nodes",
            resolved_arguments={
                "page_size": StrResolvedInstructionArgument(argument_name="page_size", value="1"),
            },
        )

        self.assertEqual(result["NextToken"].value, "abc123")
        mock_k8s_core.list_nodes.assert_called_once_with(runner.core_api, label_selector=None, limit=1, _continue=None)

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_list_nodes_with_pagination_token(self, mock_k8s_core: Mock) -> None:
        runner = self._make_runner()
        mock_k8s_core.list_nodes.return_value = ([], None)

        runner.execute_instruction(
            instruction_name="list-nodes",
            resolved_arguments={
                "pagination_token": StrResolvedInstructionArgument(argument_name="pagination_token", value="abc123"),
            },
        )

        mock_k8s_core.list_nodes.assert_called_once_with(
            runner.core_api, label_selector=None, limit=None, _continue="abc123"
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_get_node_ready(self, mock_k8s_core: Mock) -> None:
        runner = self._make_runner()
        mock_k8s_core.get_node.return_value = NodeInfo(
            name="node-1", status=NodeConditionStatus.READY, resource={"metadata": {"name": "node-1"}}
        )

        result = runner.execute_instruction(
            instruction_name="get-node",
            resolved_arguments={
                "name": StrResolvedInstructionArgument(argument_name="name", value="node-1"),
            },
        )

        self.assertEqual(result["Name"].value, "node-1")
        self.assertEqual(result["Status"].value, "Ready")
        self.assertEqual(result["Resource"].value, '{"metadata": {"name": "node-1"}}')

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_get_node_not_ready(self, mock_k8s_core: Mock) -> None:
        runner = self._make_runner()
        mock_k8s_core.get_node.return_value = NodeInfo(name="node-1", status=NodeConditionStatus.NOT_READY)

        result = runner.execute_instruction(
            instruction_name="get-node",
            resolved_arguments={
                "name": StrResolvedInstructionArgument(argument_name="name", value="node-1"),
            },
        )

        self.assertEqual(result["Status"].value, "NotReady")
        self.assertEqual(result["Resource"].value, "{}")

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_list_pods_returns_names_and_count(self, mock_k8s_core: Mock) -> None:
        runner = self._make_runner()
        mock_k8s_core.list_pods.return_value = (
            [
                PodInfo(name="pod-1", phase=PodPhase.RUNNING),
                PodInfo(name="pod-2", phase=PodPhase.RUNNING),
            ],
            None,
        )

        result = runner.execute_instruction(
            instruction_name="list-pods",
            resolved_arguments={
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="default"),
            },
        )

        self.assertEqual(result["PodNames"].value, "pod-1,pod-2")
        self.assertEqual(result["NextToken"].value, "")
        mock_k8s_core.list_pods.assert_called_once_with(
            runner.core_api, namespace="default", label_selector=None, limit=None, _continue=None
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_list_pods_with_pagination(self, mock_k8s_core: Mock) -> None:
        runner = self._make_runner()
        mock_k8s_core.list_pods.return_value = (
            [PodInfo(name="pod-1", phase=PodPhase.RUNNING)],
            "xyz789",
        )

        result = runner.execute_instruction(
            instruction_name="list-pods",
            resolved_arguments={
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="default"),
                "page_size": StrResolvedInstructionArgument(argument_name="page_size", value="1"),
            },
        )

        self.assertEqual(result["NextToken"].value, "xyz789")
        mock_k8s_core.list_pods.assert_called_once_with(
            runner.core_api, namespace="default", label_selector=None, limit=1, _continue=None
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_list_pods_with_pagination_token(self, mock_k8s_core: Mock) -> None:
        runner = self._make_runner()
        mock_k8s_core.list_pods.return_value = ([], None)

        runner.execute_instruction(
            instruction_name="list-pods",
            resolved_arguments={
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="default"),
                "pagination_token": StrResolvedInstructionArgument(argument_name="pagination_token", value="xyz789"),
            },
        )

        mock_k8s_core.list_pods.assert_called_once_with(
            runner.core_api, namespace="default", label_selector=None, limit=None, _continue="xyz789"
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_get_pod_running(self, mock_k8s_core: Mock) -> None:
        runner = self._make_runner()
        mock_k8s_core.get_pod.return_value = PodInfo(name="pod-1", phase=PodPhase.RUNNING)

        result = runner.execute_instruction(
            instruction_name="get-pod",
            resolved_arguments={
                "name": StrResolvedInstructionArgument(argument_name="name", value="pod-1"),
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="default"),
            },
        )

        self.assertEqual(result["Name"].value, "pod-1")
        self.assertEqual(result["Phase"].value, "Running")

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.cmd_utils")
    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_deployment_logs_returns_logs(self, mock_k8s_core: Mock, mock_cmd_utils: Mock) -> None:
        runner = self._make_runner()
        mock_deployment: Mock = Mock()
        mock_deployment.spec.selector.match_labels = {"app": "web"}
        mock_apps_api: Mock = runner.apps_api  # type: ignore[assignment]
        mock_apps_api.read_namespaced_deployment.return_value = mock_deployment
        mock_k8s_core.list_pods.return_value = (
            [PodInfo(name="web-pod-abc", phase=PodPhase.RUNNING)],
            None,
        )
        mock_cmd_utils.run_cmd_and_capture_output.return_value = "log output"

        result = runner.execute_instruction(
            instruction_name="deployment-logs",
            resolved_arguments={
                "name": StrResolvedInstructionArgument(argument_name="name", value="my-deploy"),
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="default"),
            },
        )

        self.assertEqual(result["Logs"].value, "log output")
        mock_cmd_utils.run_cmd_and_capture_output.assert_called_once_with(
            ["kubectl", "logs", "web-pod-abc", "--namespace", "default", "--tail", "1000"]
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.cmd_utils")
    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_deployment_logs_passes_container_and_extra(self, mock_k8s_core: Mock, mock_cmd_utils: Mock) -> None:
        runner = self._make_runner(kubeconfig_path="/tmp/kubeconfig")
        mock_deployment: Mock = Mock()
        mock_deployment.spec.selector.match_labels = {"app": "web"}
        mock_apps_api: Mock = runner.apps_api  # type: ignore[assignment]
        mock_apps_api.read_namespaced_deployment.return_value = mock_deployment
        mock_k8s_core.list_pods.return_value = (
            [PodInfo(name="web-pod-abc", phase=PodPhase.RUNNING)],
            None,
        )
        mock_cmd_utils.run_cmd_and_capture_output.return_value = "log"

        runner.execute_instruction(
            instruction_name="deployment-logs",
            resolved_arguments={
                "name": StrResolvedInstructionArgument(argument_name="name", value="my-deploy"),
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="ns"),
                "container": StrResolvedInstructionArgument(argument_name="container", value="main"),
                "extra": StrResolvedInstructionArgument(argument_name="extra", value="--tail=50 --since=1h"),
            },
        )

        mock_cmd_utils.run_cmd_and_capture_output.assert_called_once_with(
            [
                "kubectl",
                "logs",
                "web-pod-abc",
                "--namespace",
                "ns",
                "--kubeconfig",
                "/tmp/kubeconfig",
                "-c",
                "main",
                "--tail=50",
                "--since=1h",
            ]
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.cmd_utils")
    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_deployment_logs_user_tail_overrides_default(self, mock_k8s_core: Mock, mock_cmd_utils: Mock) -> None:
        runner = self._make_runner()
        mock_deployment: Mock = Mock()
        mock_deployment.spec.selector.match_labels = {"app": "web"}
        mock_apps_api: Mock = runner.apps_api  # type: ignore[assignment]
        mock_apps_api.read_namespaced_deployment.return_value = mock_deployment
        mock_k8s_core.list_pods.return_value = (
            [PodInfo(name="web-pod-abc", phase=PodPhase.RUNNING)],
            None,
        )
        mock_cmd_utils.run_cmd_and_capture_output.return_value = "log"

        runner.execute_instruction(
            instruction_name="deployment-logs",
            resolved_arguments={
                "name": StrResolvedInstructionArgument(argument_name="name", value="my-deploy"),
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="default"),
                "extra": StrResolvedInstructionArgument(argument_name="extra", value="--tail=5"),
            },
        )

        # A user-supplied --tail suppresses the default; no duplicate --tail is added.
        mock_cmd_utils.run_cmd_and_capture_output.assert_called_once_with(
            ["kubectl", "logs", "web-pod-abc", "--namespace", "default", "--tail=5"]
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.cmd_utils")
    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_deployment_logs_since_overrides_default(self, mock_k8s_core: Mock, mock_cmd_utils: Mock) -> None:
        runner = self._make_runner()
        mock_deployment: Mock = Mock()
        mock_deployment.spec.selector.match_labels = {"app": "web"}
        mock_apps_api: Mock = runner.apps_api  # type: ignore[assignment]
        mock_apps_api.read_namespaced_deployment.return_value = mock_deployment
        mock_k8s_core.list_pods.return_value = (
            [PodInfo(name="web-pod-abc", phase=PodPhase.RUNNING)],
            None,
        )
        mock_cmd_utils.run_cmd_and_capture_output.return_value = "log"

        runner.execute_instruction(
            instruction_name="deployment-logs",
            resolved_arguments={
                "name": StrResolvedInstructionArgument(argument_name="name", value="my-deploy"),
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="default"),
                "extra": StrResolvedInstructionArgument(argument_name="extra", value="--since 1h"),
            },
        )

        # A --since bound also suppresses the default --tail.
        mock_cmd_utils.run_cmd_and_capture_output.assert_called_once_with(
            ["kubectl", "logs", "web-pod-abc", "--namespace", "default", "--since", "1h"]
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.cmd_utils")
    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_deployment_logs_default_tail_added_with_unrelated_extra(
        self, mock_k8s_core: Mock, mock_cmd_utils: Mock
    ) -> None:
        runner = self._make_runner()
        mock_deployment: Mock = Mock()
        mock_deployment.spec.selector.match_labels = {"app": "web"}
        mock_apps_api: Mock = runner.apps_api  # type: ignore[assignment]
        mock_apps_api.read_namespaced_deployment.return_value = mock_deployment
        mock_k8s_core.list_pods.return_value = (
            [PodInfo(name="web-pod-abc", phase=PodPhase.RUNNING)],
            None,
        )
        mock_cmd_utils.run_cmd_and_capture_output.return_value = "log"

        runner.execute_instruction(
            instruction_name="deployment-logs",
            resolved_arguments={
                "name": StrResolvedInstructionArgument(argument_name="name", value="my-deploy"),
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="default"),
                "extra": StrResolvedInstructionArgument(argument_name="extra", value="--timestamps"),
            },
        )

        # An extra flag that does not bound volume still gets the default --tail prepended.
        mock_cmd_utils.run_cmd_and_capture_output.assert_called_once_with(
            ["kubectl", "logs", "web-pod-abc", "--namespace", "default", "--tail", "1000", "--timestamps"]
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_exec_pod_with_deployment_name_resolves_pod(self, mock_k8s_core: Mock) -> None:
        runner = self._make_runner()
        mock_deployment: Mock = Mock()
        mock_deployment.spec.selector.match_labels = {"app": "ws"}
        mock_apps_api: Mock = runner.apps_api  # type: ignore[assignment]
        mock_apps_api.read_namespaced_deployment.return_value = mock_deployment
        mock_k8s_core.list_pods.return_value = (
            [PodInfo(name="ws-pod-abc", phase=PodPhase.RUNNING)],
            None,
        )
        mock_k8s_core.exec_pod.return_value = ExecResult(stdout="ok", stderr="", returncode=0)

        result = runner.execute_instruction(
            instruction_name="exec-pod",
            resolved_arguments={
                "deployment_name": StrResolvedInstructionArgument(argument_name="deployment_name", value="my-deploy"),
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="default"),
                "command": StrResolvedInstructionArgument(argument_name="command", value="echo hello"),
            },
        )

        self.assertEqual(result["Stdout"].value, "ok")
        self.assertEqual(result["Stderr"].value, "")
        self.assertEqual(result["ReturnCode"].value, "0")
        mock_apps_api.read_namespaced_deployment.assert_called_once_with(name="my-deploy", namespace="default")
        mock_k8s_core.list_pods.assert_called_once_with(
            runner.core_api,
            namespace="default",
            label_selector="app=ws",
            limit=1,
        )
        mock_k8s_core.exec_pod.assert_called_once_with(
            runner.core_api,
            name="ws-pod-abc",
            namespace="default",
            command=["echo", "hello"],
            container=None,
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_exec_pod_with_name_uses_pod_directly(self, mock_k8s_core: Mock) -> None:
        runner = self._make_runner()
        mock_apps_api: Mock = runner.apps_api  # type: ignore[assignment]
        mock_k8s_core.exec_pod.return_value = ExecResult(stdout="ok", stderr="", returncode=0)

        result = runner.execute_instruction(
            instruction_name="exec-pod",
            resolved_arguments={
                "name": StrResolvedInstructionArgument(argument_name="name", value="pod-1"),
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="default"),
                "command": StrResolvedInstructionArgument(argument_name="command", value="ls"),
            },
        )

        self.assertEqual(result["Stdout"].value, "ok")
        mock_apps_api.read_namespaced_deployment.assert_not_called()
        mock_k8s_core.exec_pod.assert_called_once_with(
            runner.core_api, name="pod-1", namespace="default", command=["ls"], container=None
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_exec_pod_raises_when_neither_name_nor_deployment(self, mock_k8s_core: Mock) -> None:
        runner = self._make_runner()

        with self.assertRaises(ValueError):
            runner.execute_instruction(
                instruction_name="exec-pod",
                resolved_arguments={
                    "scope": StrResolvedInstructionArgument(argument_name="scope", value="ns"),
                    "command": StrResolvedInstructionArgument(argument_name="command", value="ls"),
                },
            )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_exec_pod_passes_container(self, mock_k8s_core: Mock) -> None:
        runner = self._make_runner()
        mock_k8s_core.exec_pod.return_value = ExecResult(stdout="", stderr="", returncode=0)

        runner.execute_instruction(
            instruction_name="exec-pod",
            resolved_arguments={
                "name": StrResolvedInstructionArgument(argument_name="name", value="pod-1"),
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="ns"),
                "command": StrResolvedInstructionArgument(argument_name="command", value="ls"),
                "container": StrResolvedInstructionArgument(argument_name="container", value="app"),
            },
        )

        mock_k8s_core.exec_pod.assert_called_once_with(
            runner.core_api, name="pod-1", namespace="ns", command=["ls"], container="app"
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.cmd_utils")
    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_exec_pod_interactive_with_deployment_name(self, mock_k8s_core: Mock, mock_cmd_utils: Mock) -> None:
        runner = self._make_runner(kubeconfig_path="/tmp/kubeconfig")
        mock_deployment: Mock = Mock()
        mock_deployment.spec.selector.match_labels = {"app": "ws"}
        mock_apps_api: Mock = runner.apps_api  # type: ignore[assignment]
        mock_apps_api.read_namespaced_deployment.return_value = mock_deployment
        mock_k8s_core.list_pods.return_value = (
            [PodInfo(name="ws-pod-abc", phase=PodPhase.RUNNING)],
            None,
        )
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, False)

        result = runner.execute_instruction(
            instruction_name="exec-pod-interactive",
            resolved_arguments={
                "deployment_name": StrResolvedInstructionArgument(argument_name="deployment_name", value="my-deploy"),
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="default"),
            },
        )

        self.assertEqual(result, {})
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(
            [
                "kubectl",
                "exec",
                "-it",
                "ws-pod-abc",
                "-n",
                "default",
                "--kubeconfig",
                "/tmp/kubeconfig",
                "--",
                "/bin/bash",
            ]
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.cmd_utils")
    def test_exec_pod_interactive_with_pod_name_and_container(self, mock_cmd_utils: Mock) -> None:
        runner = self._make_runner()
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, False)

        result = runner.execute_instruction(
            instruction_name="exec-pod-interactive",
            resolved_arguments={
                "name": StrResolvedInstructionArgument(argument_name="name", value="pod-1"),
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="ns"),
                "container": StrResolvedInstructionArgument(argument_name="container", value="app"),
                "command": StrResolvedInstructionArgument(argument_name="command", value="sh"),
            },
        )

        self.assertEqual(result, {})
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(
            ["kubectl", "exec", "-it", "pod-1", "-n", "ns", "-c", "app", "--", "sh"]
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.cmd_utils")
    def test_exec_pod_interactive_timeout_raises(self, mock_cmd_utils: Mock) -> None:
        runner = self._make_runner()
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, True)

        with self.assertRaises(InteractiveSessionTimeoutError):
            runner.execute_instruction(
                instruction_name="exec-pod-interactive",
                resolved_arguments={
                    "name": StrResolvedInstructionArgument(argument_name="name", value="pod-1"),
                    "scope": StrResolvedInstructionArgument(argument_name="scope", value="ns"),
                },
            )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.cmd_utils")
    def test_exec_pod_interactive_nonzero_retcode_raises(self, mock_cmd_utils: Mock) -> None:
        runner = self._make_runner()
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (1, False)

        with self.assertRaises(InteractiveSessionError):
            runner.execute_instruction(
                instruction_name="exec-pod-interactive",
                resolved_arguments={
                    "name": StrResolvedInstructionArgument(argument_name="name", value="pod-1"),
                    "scope": StrResolvedInstructionArgument(argument_name="scope", value="ns"),
                },
            )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.cmd_utils")
    def test_exec_pod_interactive_filters_default_container(self, mock_cmd_utils: Mock) -> None:
        runner = self._make_runner()
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, False)

        runner.execute_instruction(
            instruction_name="exec-pod-interactive",
            resolved_arguments={
                "name": StrResolvedInstructionArgument(argument_name="name", value="pod-1"),
                "scope": StrResolvedInstructionArgument(argument_name="scope", value="ns"),
                "container": StrResolvedInstructionArgument(argument_name="container", value="default"),
            },
        )

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(
            ["kubectl", "exec", "-it", "pod-1", "-n", "ns", "--", "/bin/bash"]
        )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.cmd_utils")
    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_deployment_logs_unknown_flag_raises_instruction_error(
        self, mock_k8s_core: Mock, mock_cmd_utils: Mock
    ) -> None:
        runner = self._make_runner()
        mock_deployment: Mock = Mock()
        mock_deployment.spec.selector.match_labels = {"app": "web"}
        mock_apps_api: Mock = runner.apps_api  # type: ignore[assignment]
        mock_apps_api.read_namespaced_deployment.return_value = mock_deployment
        mock_k8s_core.list_pods.return_value = (
            [PodInfo(name="web-pod-abc", phase=PodPhase.RUNNING)],
            None,
        )
        mock_cmd_utils.run_cmd_and_capture_output.side_effect = subprocess.CalledProcessError(
            1, "kubectl", stderr="Error: unknown flag: --head=3"
        )

        with self.assertRaises(InstructionError):
            runner.execute_instruction(
                instruction_name="deployment-logs",
                resolved_arguments={
                    "name": StrResolvedInstructionArgument(argument_name="name", value="my-deploy"),
                    "scope": StrResolvedInstructionArgument(argument_name="scope", value="default"),
                    "extra": StrResolvedInstructionArgument(argument_name="extra", value="--head=3"),
                },
            )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.cmd_utils")
    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_deployment_logs_invalid_argument_raises_instruction_error(
        self, mock_k8s_core: Mock, mock_cmd_utils: Mock
    ) -> None:
        runner = self._make_runner()
        mock_deployment: Mock = Mock()
        mock_deployment.spec.selector.match_labels = {"app": "web"}
        mock_apps_api: Mock = runner.apps_api  # type: ignore[assignment]
        mock_apps_api.read_namespaced_deployment.return_value = mock_deployment
        mock_k8s_core.list_pods.return_value = (
            [PodInfo(name="web-pod-abc", phase=PodPhase.RUNNING)],
            None,
        )
        mock_cmd_utils.run_cmd_and_capture_output.side_effect = subprocess.CalledProcessError(
            1,
            "kubectl",
            stderr='invalid argument "abc" for "--tail" flag: strconv.ParseInt: parsing "abc": invalid syntax',
        )

        with self.assertRaises(InstructionError):
            runner.execute_instruction(
                instruction_name="deployment-logs",
                resolved_arguments={
                    "name": StrResolvedInstructionArgument(argument_name="name", value="my-deploy"),
                    "scope": StrResolvedInstructionArgument(argument_name="scope", value="default"),
                    "extra": StrResolvedInstructionArgument(argument_name="extra", value="--tail=abc"),
                },
            )

    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.cmd_utils")
    @patch("jupyter_deploy.provider.k8s.k8s_core_runner.k8s_core")
    def test_deployment_logs_other_error_bubbles_up(self, mock_k8s_core: Mock, mock_cmd_utils: Mock) -> None:
        runner = self._make_runner()
        mock_deployment: Mock = Mock()
        mock_deployment.spec.selector.match_labels = {"app": "web"}
        mock_apps_api: Mock = runner.apps_api  # type: ignore[assignment]
        mock_apps_api.read_namespaced_deployment.return_value = mock_deployment
        mock_k8s_core.list_pods.return_value = (
            [PodInfo(name="web-pod-abc", phase=PodPhase.RUNNING)],
            None,
        )
        mock_cmd_utils.run_cmd_and_capture_output.side_effect = subprocess.CalledProcessError(
            1, "kubectl", stderr="error: pod web-pod-abc is not running"
        )

        with self.assertRaises(subprocess.CalledProcessError):
            runner.execute_instruction(
                instruction_name="deployment-logs",
                resolved_arguments={
                    "name": StrResolvedInstructionArgument(argument_name="name", value="my-deploy"),
                    "scope": StrResolvedInstructionArgument(argument_name="scope", value="default"),
                },
            )

    def test_unknown_instruction_raises_error(self) -> None:
        runner = self._make_runner()

        with self.assertRaises(InstructionNotFoundError):
            runner.execute_instruction(instruction_name="unknown", resolved_arguments={})
