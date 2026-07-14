import unittest
from unittest.mock import Mock, patch

from kubernetes.client.exceptions import ApiException

from jupyter_deploy.api.k8s.apps import (
    DaemonSetStatus,
    DeploymentInfo,
    DeploymentStatus,
    ResourceInfo,
    StatefulSetStatus,
)
from jupyter_deploy.exceptions import InstructionNotFoundError
from jupyter_deploy.provider.k8s.k8s_apps_runner import K8sAppsRunner
from jupyter_deploy.provider.resolved_argdefs import StrResolvedInstructionArgument


def _build_args(name: str = "traefik", scope: str = "kube-system") -> dict:
    return {
        "name": StrResolvedInstructionArgument(argument_name="name", value=name),
        "scope": StrResolvedInstructionArgument(argument_name="scope", value=scope),
    }


class TestK8sAppsRunnerGetDeploymentStatus(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_deployment_oldest_pod")
    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_deployment_status")
    def test_returns_ready_status(self, mock_get_status: Mock, mock_oldest_pod: Mock) -> None:
        mock_get_status.return_value = DeploymentStatus(
            name="traefik", available=True, ready_replicas=1, total_replicas=1, conditions=[]
        )
        mock_oldest_pod.return_value = None
        display_manager: Mock = Mock()
        runner = K8sAppsRunner(display_manager=display_manager, api_client=Mock())

        result = runner.execute_instruction("get-deployment-status", _build_args())

        self.assertEqual(result["Status"].value, "Ready")
        self.assertEqual(result["Details"].value, "1/1 replicas")
        self.assertIn("SubComponent", result)

    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_deployment_oldest_pod")
    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_deployment_status")
    def test_returns_degraded_status(self, mock_get_status: Mock, mock_oldest_pod: Mock) -> None:
        mock_get_status.return_value = DeploymentStatus(
            name="traefik", available=False, ready_replicas=0, total_replicas=1, conditions=[]
        )
        mock_oldest_pod.return_value = None
        display_manager: Mock = Mock()
        runner = K8sAppsRunner(display_manager=display_manager, api_client=Mock())

        result = runner.execute_instruction("get-deployment-status", _build_args())

        self.assertEqual(result["Status"].value, "Degraded")
        self.assertEqual(result["Details"].value, "0/1 replicas")


class TestK8sAppsRunnerGetDeploymentStatusApiError(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_deployment_status")
    def test_api_exception_bubbles_up(self, mock_get_status: Mock) -> None:
        mock_get_status.side_effect = ApiException(status=404, reason="Not Found")
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        with self.assertRaises(ApiException):
            runner.execute_instruction("get-deployment-status", _build_args())


class TestK8sAppsRunnerGetDaemonsetStatus(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_daemonset_status")
    def test_returns_ready_status(self, mock_get_status: Mock) -> None:
        mock_get_status.return_value = DaemonSetStatus(
            name="aws-node", ready=True, ready_pods=3, desired_pods=3, updated_pods=3
        )
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        result = runner.execute_instruction("get-daemonset-status", _build_args(name="aws-node"))

        self.assertEqual(result["Status"].value, "Ready")
        self.assertEqual(result["Details"].value, "3/3 nodes")
        self.assertIn("SubComponent", result)

    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_daemonset_status")
    def test_returns_updating_status(self, mock_get_status: Mock) -> None:
        mock_get_status.return_value = DaemonSetStatus(
            name="aws-node", ready=False, ready_pods=2, desired_pods=3, updated_pods=2
        )
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        result = runner.execute_instruction("get-daemonset-status", _build_args(name="aws-node"))

        self.assertEqual(result["Status"].value, "Updating")
        self.assertEqual(result["Details"].value, "2/3 nodes")

    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_daemonset_status")
    def test_returns_degraded_status(self, mock_get_status: Mock) -> None:
        mock_get_status.return_value = DaemonSetStatus(
            name="aws-node", ready=False, ready_pods=2, desired_pods=3, updated_pods=3
        )
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        result = runner.execute_instruction("get-daemonset-status", _build_args(name="aws-node"))

        self.assertEqual(result["Status"].value, "Degraded")

    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_daemonset_status")
    def test_api_exception_bubbles_up(self, mock_get_status: Mock) -> None:
        mock_get_status.side_effect = ApiException(status=404, reason="Not Found")
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        with self.assertRaises(ApiException):
            runner.execute_instruction("get-daemonset-status", _build_args())


class TestK8sAppsRunnerGetStatefulsetStatus(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_statefulset_status")
    def test_returns_ready_status(self, mock_get_status: Mock) -> None:
        mock_get_status.return_value = StatefulSetStatus(
            name="prometheus", ready=True, ready_replicas=2, total_replicas=2, updated_replicas=2
        )
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        result = runner.execute_instruction("get-statefulset-status", _build_args(name="prometheus"))

        self.assertEqual(result["Status"].value, "Ready")
        self.assertEqual(result["Details"].value, "2/2 replicas")

    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_statefulset_status")
    def test_returns_updating_status(self, mock_get_status: Mock) -> None:
        mock_get_status.return_value = StatefulSetStatus(
            name="prometheus", ready=False, ready_replicas=1, total_replicas=2, updated_replicas=1
        )
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        result = runner.execute_instruction("get-statefulset-status", _build_args(name="prometheus"))

        self.assertEqual(result["Status"].value, "Updating")

    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_statefulset_status")
    def test_returns_degraded_status(self, mock_get_status: Mock) -> None:
        mock_get_status.return_value = StatefulSetStatus(
            name="prometheus", ready=False, ready_replicas=1, total_replicas=2, updated_replicas=2
        )
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        result = runner.execute_instruction("get-statefulset-status", _build_args(name="prometheus"))

        self.assertEqual(result["Status"].value, "Degraded")

    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_statefulset_status")
    def test_api_exception_bubbles_up(self, mock_get_status: Mock) -> None:
        mock_get_status.side_effect = ApiException(status=404, reason="Not Found")
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        with self.assertRaises(ApiException):
            runner.execute_instruction("get-statefulset-status", _build_args())


class TestK8sAppsRunnerGetDeployment(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_deployment")
    def test_returns_resource_json(self, mock_get: Mock) -> None:
        mock_get.return_value = DeploymentInfo(
            name="traefik",
            image="traefik:v2.10",
            replicas=1,
            ready_replicas=1,
            conditions=[],
            resource={"kind": "Deployment"},
        )
        display_manager: Mock = Mock()
        runner = K8sAppsRunner(display_manager=display_manager, api_client=Mock())

        result = runner.execute_instruction("get-deployment", _build_args())

        self.assertEqual(result["Name"].value, "traefik")
        self.assertIn("Deployment", result["Resource"].value)


class TestK8sAppsRunnerGetDeploymentApiError(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_deployment")
    def test_api_exception_bubbles_up(self, mock_get: Mock) -> None:
        mock_get.side_effect = ApiException(status=404, reason="Not Found")
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        with self.assertRaises(ApiException):
            runner.execute_instruction("get-deployment", _build_args())


class TestK8sAppsRunnerGetDaemonset(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_daemonset")
    def test_returns_resource_json(self, mock_get: Mock) -> None:
        mock_get.return_value = ResourceInfo(name="aws-node", resource={"kind": "DaemonSet"})
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        result = runner.execute_instruction("get-daemonset", _build_args(name="aws-node"))

        self.assertEqual(result["Name"].value, "aws-node")
        self.assertIn("DaemonSet", result["Resource"].value)

    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_daemonset")
    def test_api_exception_bubbles_up(self, mock_get: Mock) -> None:
        mock_get.side_effect = ApiException(status=404, reason="Not Found")
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        with self.assertRaises(ApiException):
            runner.execute_instruction("get-daemonset", _build_args())


class TestK8sAppsRunnerGetStatefulset(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_statefulset")
    def test_returns_resource_json(self, mock_get: Mock) -> None:
        mock_get.return_value = ResourceInfo(name="prometheus", resource={"kind": "StatefulSet"})
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        result = runner.execute_instruction("get-statefulset", _build_args(name="prometheus"))

        self.assertEqual(result["Name"].value, "prometheus")
        self.assertIn("StatefulSet", result["Resource"].value)

    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.get_statefulset")
    def test_api_exception_bubbles_up(self, mock_get: Mock) -> None:
        mock_get.side_effect = ApiException(status=404, reason="Not Found")
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        with self.assertRaises(ApiException):
            runner.execute_instruction("get-statefulset", _build_args())


class TestK8sAppsRunnerRolloutRestart(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.rollout_restart")
    def test_calls_rollout_restart(self, mock_restart: Mock) -> None:
        display_manager: Mock = Mock()
        runner = K8sAppsRunner(display_manager=display_manager, api_client=Mock())

        result = runner.execute_instruction("rollout-restart", _build_args())

        mock_restart.assert_called_once()
        self.assertEqual(result, {})


class TestK8sAppsRunnerRolloutRestartApiError(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_apps_runner.k8s_apps.rollout_restart")
    def test_api_exception_bubbles_up(self, mock_restart: Mock) -> None:
        mock_restart.side_effect = ApiException(status=403, reason="Forbidden")
        runner = K8sAppsRunner(display_manager=Mock(), api_client=Mock())

        with self.assertRaises(ApiException):
            runner.execute_instruction("rollout-restart", _build_args())


class TestK8sAppsRunnerUnknownInstruction(unittest.TestCase):
    def test_raises_instruction_not_found(self) -> None:
        display_manager: Mock = Mock()
        runner = K8sAppsRunner(display_manager=display_manager, api_client=Mock())

        with self.assertRaises(InstructionNotFoundError):
            runner.execute_instruction("unknown-instruction", _build_args())
