import unittest
from unittest.mock import Mock

from kubernetes.client import CustomObjectsApi
from kubernetes.client.exceptions import ApiException

from jupyter_deploy.api.k8s.custom import (
    CustomResourceRef,
    get_cluster,
    get_namespaced,
    list_cluster,
    list_namespaced,
    patch_namespaced,
)

_NOT_FOUND = ApiException(status=404, reason="Not Found")

REF = CustomResourceRef(group="workspace.jupyter.org", version="v1alpha1", plural="workspaces")


class TestListNamespaced(unittest.TestCase):
    def test_returns_items_and_no_next_token(self) -> None:
        mock_api: Mock = Mock(spec=CustomObjectsApi)
        mock_api.list_namespaced_custom_object.return_value = {
            "items": [{"metadata": {"name": "ws-1"}}, {"metadata": {"name": "ws-2"}}],
            "metadata": {},
        }

        items, next_token = list_namespaced(mock_api, ref=REF, namespace="default")

        self.assertEqual(len(items), 2)
        self.assertIsNone(next_token)
        mock_api.list_namespaced_custom_object.assert_called_once_with(
            group="workspace.jupyter.org", version="v1alpha1", namespace="default", plural="workspaces"
        )

    def test_returns_empty_for_no_items(self) -> None:
        mock_api: Mock = Mock(spec=CustomObjectsApi)
        mock_api.list_namespaced_custom_object.return_value = {"items": [], "metadata": {}}

        items, next_token = list_namespaced(mock_api, ref=REF, namespace="default")

        self.assertEqual(items, [])
        self.assertIsNone(next_token)

    def test_passes_limit_and_continue(self) -> None:
        mock_api: Mock = Mock(spec=CustomObjectsApi)
        mock_api.list_namespaced_custom_object.return_value = {
            "items": [{"metadata": {"name": "ws-1"}}],
            "metadata": {"continue": "next-abc"},
        }

        items, next_token = list_namespaced(mock_api, ref=REF, namespace="default", limit=1, _continue="start-abc")

        self.assertEqual(len(items), 1)
        self.assertEqual(next_token, "next-abc")
        mock_api.list_namespaced_custom_object.assert_called_once_with(
            group="workspace.jupyter.org",
            version="v1alpha1",
            namespace="default",
            plural="workspaces",
            limit=1,
            _continue="start-abc",
        )

    def test_raises_on_api_error(self) -> None:
        mock_api: Mock = Mock(spec=CustomObjectsApi)
        mock_api.list_namespaced_custom_object.side_effect = _NOT_FOUND

        with self.assertRaises(ApiException):
            list_namespaced(mock_api, ref=REF, namespace="default")


class TestListCluster(unittest.TestCase):
    def test_returns_items_and_no_next_token(self) -> None:
        mock_api: Mock = Mock(spec=CustomObjectsApi)
        mock_api.list_cluster_custom_object.return_value = {
            "items": [{"metadata": {"name": "cr-1"}}],
            "metadata": {},
        }

        items, next_token = list_cluster(mock_api, ref=REF)

        self.assertEqual(len(items), 1)
        self.assertIsNone(next_token)
        mock_api.list_cluster_custom_object.assert_called_once_with(
            group="workspace.jupyter.org", version="v1alpha1", plural="workspaces"
        )

    def test_passes_limit_and_continue(self) -> None:
        mock_api: Mock = Mock(spec=CustomObjectsApi)
        mock_api.list_cluster_custom_object.return_value = {
            "items": [{"metadata": {"name": "cr-1"}}],
            "metadata": {"continue": "next-xyz"},
        }

        items, next_token = list_cluster(mock_api, ref=REF, limit=1, _continue="start-xyz")

        self.assertEqual(len(items), 1)
        self.assertEqual(next_token, "next-xyz")
        mock_api.list_cluster_custom_object.assert_called_once_with(
            group="workspace.jupyter.org", version="v1alpha1", plural="workspaces", limit=1, _continue="start-xyz"
        )

    def test_raises_on_api_error(self) -> None:
        mock_api: Mock = Mock(spec=CustomObjectsApi)
        mock_api.list_cluster_custom_object.side_effect = _NOT_FOUND

        with self.assertRaises(ApiException):
            list_cluster(mock_api, ref=REF)


class TestGetNamespaced(unittest.TestCase):
    def test_returns_name_and_resource(self) -> None:
        mock_api: Mock = Mock(spec=CustomObjectsApi)
        resource = {"metadata": {"name": "ws-1"}, "spec": {"image": "jupyter/base-notebook"}}
        mock_api.get_namespaced_custom_object.return_value = resource

        result = get_namespaced(mock_api, ref=REF, namespace="default", name="ws-1")

        self.assertEqual(result.name, "ws-1")
        self.assertEqual(result.resource["spec"]["image"], "jupyter/base-notebook")
        mock_api.get_namespaced_custom_object.assert_called_once_with(
            group="workspace.jupyter.org", version="v1alpha1", namespace="default", plural="workspaces", name="ws-1"
        )

    def test_raises_on_api_error(self) -> None:
        mock_api: Mock = Mock(spec=CustomObjectsApi)
        mock_api.get_namespaced_custom_object.side_effect = _NOT_FOUND

        with self.assertRaises(ApiException):
            get_namespaced(mock_api, ref=REF, namespace="default", name="nonexistent")


class TestGetCluster(unittest.TestCase):
    CRD_REF = CustomResourceRef(group="apiextensions.k8s.io", version="v1", plural="customresourcedefinitions")

    def test_returns_name_and_resource(self) -> None:
        mock_api: Mock = Mock(spec=CustomObjectsApi)
        resource = {
            "metadata": {"name": "workspaces.workspace.jupyter.org"},
            "spec": {"group": "workspace.jupyter.org"},
        }
        mock_api.get_cluster_custom_object.return_value = resource

        result = get_cluster(mock_api, ref=self.CRD_REF, name="workspaces.workspace.jupyter.org")

        self.assertEqual(result.name, "workspaces.workspace.jupyter.org")
        self.assertEqual(result.resource["spec"]["group"], "workspace.jupyter.org")
        mock_api.get_cluster_custom_object.assert_called_once_with(
            group="apiextensions.k8s.io",
            version="v1",
            plural="customresourcedefinitions",
            name="workspaces.workspace.jupyter.org",
        )

    def test_returns_empty_name_when_metadata_absent(self) -> None:
        mock_api: Mock = Mock(spec=CustomObjectsApi)
        mock_api.get_cluster_custom_object.return_value = {}

        result = get_cluster(mock_api, ref=self.CRD_REF, name="workspaces.workspace.jupyter.org")

        self.assertEqual(result.name, "")
        self.assertEqual(result.resource, {})

    def test_raises_on_api_error(self) -> None:
        mock_api: Mock = Mock(spec=CustomObjectsApi)
        mock_api.get_cluster_custom_object.side_effect = _NOT_FOUND

        with self.assertRaises(ApiException):
            get_cluster(mock_api, ref=self.CRD_REF, name="nonexistent")


class TestPatchNamespaced(unittest.TestCase):
    def test_returns_patched_resource(self) -> None:
        mock_api: Mock = Mock(spec=CustomObjectsApi)
        patched = {"metadata": {"name": "ws-1"}, "spec": {"replicas": 2}}
        mock_api.patch_namespaced_custom_object.return_value = patched

        body = {"spec": {"replicas": 2}}
        result = patch_namespaced(mock_api, ref=REF, namespace="default", name="ws-1", body=body)

        self.assertEqual(result.name, "ws-1")
        self.assertEqual(result.resource["spec"]["replicas"], 2)
        mock_api.patch_namespaced_custom_object.assert_called_once_with(
            group="workspace.jupyter.org",
            version="v1alpha1",
            namespace="default",
            plural="workspaces",
            name="ws-1",
            body=body,
        )

    def test_raises_on_api_error(self) -> None:
        mock_api: Mock = Mock(spec=CustomObjectsApi)
        mock_api.patch_namespaced_custom_object.side_effect = _NOT_FOUND

        with self.assertRaises(ApiException):
            patch_namespaced(mock_api, ref=REF, namespace="default", name="ws-1", body={})
