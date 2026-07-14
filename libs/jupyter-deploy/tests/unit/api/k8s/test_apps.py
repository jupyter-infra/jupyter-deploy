import unittest
from unittest.mock import Mock

from kubernetes.client import AppsV1Api
from kubernetes.client.exceptions import ApiException

from jupyter_deploy.api.k8s.apps import (
    DaemonSetStatus,
    DeploymentInfo,
    DeploymentStatus,
    ResourceInfo,
    StatefulSetStatus,
    get_daemonset,
    get_daemonset_status,
    get_deployment,
    get_deployment_status,
    get_statefulset,
    get_statefulset_status,
    rollout_restart,
)


def _mock_daemonset(
    name: str = "aws-node",
    desired: int = 3,
    ready: int = 3,
    available: int = 3,
    updated: int = 3,
) -> Mock:
    daemonset: Mock = Mock()
    daemonset.metadata.name = name
    daemonset.status.desired_number_scheduled = desired
    daemonset.status.number_ready = ready
    daemonset.status.number_available = available
    daemonset.status.updated_number_scheduled = updated
    return daemonset


def _mock_statefulset(
    name: str = "prometheus",
    total: int = 2,
    ready: int = 2,
    updated: int = 2,
) -> Mock:
    statefulset: Mock = Mock()
    statefulset.metadata.name = name
    statefulset.status.replicas = total
    statefulset.status.ready_replicas = ready
    statefulset.status.updated_replicas = updated
    return statefulset


def _mock_deployment(
    name: str = "traefik",
    ready: int = 1,
    total: int = 1,
    image: str = "traefik:v2.10",
    available: bool = True,
) -> Mock:
    deployment: Mock = Mock()
    deployment.metadata.name = name
    deployment.spec.replicas = total
    deployment.spec.template.spec.containers = [Mock(image=image)]
    deployment.spec.selector.match_labels = {"app": name}
    deployment.status.replicas = total
    deployment.status.ready_replicas = ready

    condition: Mock = Mock()
    condition.type = "Available"
    condition.status = "True" if available else "False"
    condition.message = "Deployment has minimum availability."
    deployment.status.conditions = [condition]

    return deployment


class TestGetDeploymentStatus(unittest.TestCase):
    def test_returns_ready_when_available(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_deployment.return_value = _mock_deployment()

        result = get_deployment_status(mock_api, name="traefik", namespace="kube-system")

        self.assertIsInstance(result, DeploymentStatus)
        self.assertEqual(result.name, "traefik")
        self.assertTrue(result.available)
        self.assertEqual(result.ready_replicas, 1)
        self.assertEqual(result.total_replicas, 1)

    def test_returns_not_available_when_degraded(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_deployment.return_value = _mock_deployment(ready=0, available=False)

        result = get_deployment_status(mock_api, name="traefik", namespace="kube-system")

        self.assertFalse(result.available)
        self.assertEqual(result.ready_replicas, 0)

    def test_passes_name_and_namespace(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_deployment.return_value = _mock_deployment()

        get_deployment_status(mock_api, name="dex", namespace="auth")

        mock_api.read_namespaced_deployment.assert_called_once_with(name="dex", namespace="auth")

    def test_raises_on_not_found(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_deployment.side_effect = ApiException(status=404, reason="Not Found")

        with self.assertRaises(ApiException):
            get_deployment_status(mock_api, name="missing", namespace="default")


class TestGetDaemonsetStatus(unittest.TestCase):
    def test_returns_ready_when_all_scheduled(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_daemon_set.return_value = _mock_daemonset()

        result = get_daemonset_status(mock_api, name="aws-node", namespace="kube-system")

        self.assertIsInstance(result, DaemonSetStatus)
        self.assertEqual(result.name, "aws-node")
        self.assertTrue(result.ready)
        self.assertEqual(result.ready_pods, 3)
        self.assertEqual(result.desired_pods, 3)

    def test_not_ready_when_ready_below_desired(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_daemon_set.return_value = _mock_daemonset(ready=2, available=2)

        result = get_daemonset_status(mock_api, name="aws-node", namespace="kube-system")

        self.assertFalse(result.ready)
        self.assertEqual(result.ready_pods, 2)

    def test_not_ready_when_zero_desired(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_daemon_set.return_value = _mock_daemonset(desired=0, ready=0, available=0, updated=0)

        result = get_daemonset_status(mock_api, name="aws-node", namespace="kube-system")

        self.assertFalse(result.ready)

    def test_passes_name_and_namespace(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_daemon_set.return_value = _mock_daemonset()

        get_daemonset_status(mock_api, name="kube-proxy", namespace="kube-system")

        mock_api.read_namespaced_daemon_set.assert_called_once_with(name="kube-proxy", namespace="kube-system")

    def test_raises_on_not_found(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_daemon_set.side_effect = ApiException(status=404, reason="Not Found")

        with self.assertRaises(ApiException):
            get_daemonset_status(mock_api, name="missing", namespace="default")


class TestGetStatefulsetStatus(unittest.TestCase):
    def test_returns_ready_when_all_replicas_ready(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_stateful_set.return_value = _mock_statefulset()

        result = get_statefulset_status(mock_api, name="prometheus", namespace="monitoring")

        self.assertIsInstance(result, StatefulSetStatus)
        self.assertEqual(result.name, "prometheus")
        self.assertTrue(result.ready)
        self.assertEqual(result.ready_replicas, 2)
        self.assertEqual(result.total_replicas, 2)

    def test_not_ready_when_ready_below_total(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_stateful_set.return_value = _mock_statefulset(ready=1)

        result = get_statefulset_status(mock_api, name="prometheus", namespace="monitoring")

        self.assertFalse(result.ready)
        self.assertEqual(result.ready_replicas, 1)

    def test_not_ready_when_zero_replicas(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_stateful_set.return_value = _mock_statefulset(total=0, ready=0, updated=0)

        result = get_statefulset_status(mock_api, name="prometheus", namespace="monitoring")

        self.assertFalse(result.ready)

    def test_raises_on_not_found(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_stateful_set.side_effect = ApiException(status=404, reason="Not Found")

        with self.assertRaises(ApiException):
            get_statefulset_status(mock_api, name="missing", namespace="default")


def _mock_apps_api(serialized: dict) -> Mock:
    """AppsV1Api mock whose api_client.sanitize_for_serialization returns `serialized`.

    api_client is an instance attribute, so it is not on the class spec and must be
    attached explicitly."""
    mock_api: Mock = Mock(spec=AppsV1Api)
    mock_api.api_client = Mock()
    mock_api.api_client.sanitize_for_serialization.return_value = serialized
    return mock_api


class TestGetDeployment(unittest.TestCase):
    def test_returns_deployment_info(self) -> None:
        mock_api = _mock_apps_api({"kind": "Deployment"})
        mock_api.read_namespaced_deployment.return_value = _mock_deployment(image="dex:v2.36")

        result = get_deployment(mock_api, name="dex", namespace="auth")

        self.assertIsInstance(result, DeploymentInfo)
        self.assertEqual(result.name, "traefik")
        self.assertEqual(result.image, "dex:v2.36")
        self.assertEqual(result.replicas, 1)
        self.assertEqual(result.ready_replicas, 1)
        self.assertIsInstance(result.resource, dict)

    def test_raises_on_not_found(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_deployment.side_effect = ApiException(status=404, reason="Not Found")

        with self.assertRaises(ApiException):
            get_deployment(mock_api, name="missing", namespace="default")


class TestGetDaemonset(unittest.TestCase):
    def test_returns_resource_info(self) -> None:
        mock_api = _mock_apps_api({"kind": "DaemonSet"})
        mock_api.read_namespaced_daemon_set.return_value = _mock_daemonset(name="aws-node")

        result = get_daemonset(mock_api, name="aws-node", namespace="kube-system")

        self.assertIsInstance(result, ResourceInfo)
        self.assertEqual(result.name, "aws-node")
        self.assertEqual(result.resource, {"kind": "DaemonSet"})

    def test_raises_on_not_found(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_daemon_set.side_effect = ApiException(status=404, reason="Not Found")

        with self.assertRaises(ApiException):
            get_daemonset(mock_api, name="missing", namespace="default")


class TestGetStatefulset(unittest.TestCase):
    def test_returns_resource_info(self) -> None:
        mock_api = _mock_apps_api({"kind": "StatefulSet"})
        mock_api.read_namespaced_stateful_set.return_value = _mock_statefulset(name="prometheus")

        result = get_statefulset(mock_api, name="prometheus", namespace="monitoring")

        self.assertIsInstance(result, ResourceInfo)
        self.assertEqual(result.name, "prometheus")
        self.assertEqual(result.resource, {"kind": "StatefulSet"})

    def test_raises_on_not_found(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_stateful_set.side_effect = ApiException(status=404, reason="Not Found")

        with self.assertRaises(ApiException):
            get_statefulset(mock_api, name="missing", namespace="default")


class TestRolloutRestart(unittest.TestCase):
    def test_patches_deployment_with_annotation(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)

        rollout_restart(mock_api, name="traefik", namespace="kube-system")

        mock_api.patch_namespaced_deployment.assert_called_once()
        call_kwargs = mock_api.patch_namespaced_deployment.call_args
        self.assertEqual(call_kwargs.kwargs["name"], "traefik")
        self.assertEqual(call_kwargs.kwargs["namespace"], "kube-system")
        body = call_kwargs.kwargs["body"]
        annotations = body["spec"]["template"]["metadata"]["annotations"]
        self.assertIn("kubectl.kubernetes.io/restartedAt", annotations)

    def test_raises_on_api_error(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.patch_namespaced_deployment.side_effect = ApiException(status=403, reason="Forbidden")

        with self.assertRaises(ApiException):
            rollout_restart(mock_api, name="traefik", namespace="kube-system")
