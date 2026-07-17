import unittest
from unittest.mock import Mock

from kubernetes.client import ApiextensionsV1Api
from kubernetes.client.exceptions import ApiException

from jupyter_deploy.api.k8s.apiextensions import get_crd

_NOT_FOUND = ApiException(status=404, reason="Not Found")


def _mock_version(name: str, served: bool, storage: bool) -> Mock:
    version = Mock()
    version.name = name
    version.served = served
    version.storage = storage
    return version


def _mock_condition(cond_type: str, status: str) -> Mock:
    condition = Mock()
    condition.type = cond_type
    condition.status = status
    return condition


def _mock_crd(
    name: str = "workspaces.workspace.jupyter.org",
    group: str = "workspace.jupyter.org",
    versions: list[Mock] | None = None,
    conditions: list[Mock] | None = None,
) -> Mock:
    crd = Mock()
    crd.metadata = Mock()
    crd.metadata.name = name
    crd.spec = Mock()
    crd.spec.group = group
    crd.spec.versions = versions if versions is not None else []
    crd.status = Mock()
    crd.status.conditions = conditions
    return crd


class TestGetCrd(unittest.TestCase):
    def _make_api(self, crd: Mock) -> Mock:
        mock_api: Mock = Mock(spec=ApiextensionsV1Api)
        mock_api.read_custom_resource_definition.return_value = crd
        mock_api.api_client = Mock()
        mock_api.api_client.sanitize_for_serialization.return_value = {
            "metadata": {"name": crd.metadata.name},
            "spec": {"group": crd.spec.group},
        }
        return mock_api

    def test_returns_typed_detail(self) -> None:
        crd = _mock_crd(
            versions=[_mock_version("v1alpha1", served=True, storage=True)],
            conditions=[_mock_condition("Established", "True")],
        )
        mock_api = self._make_api(crd)

        info = get_crd(mock_api, name="workspaces.workspace.jupyter.org")

        self.assertEqual(info.name, "workspaces.workspace.jupyter.org")
        self.assertEqual(info.group, "workspace.jupyter.org")
        self.assertTrue(info.established)
        self.assertEqual(info.served_versions, ["v1alpha1"])
        self.assertEqual(info.stored_version, "v1alpha1")
        self.assertEqual(info.resource["spec"]["group"], "workspace.jupyter.org")
        mock_api.read_custom_resource_definition.assert_called_once_with(name="workspaces.workspace.jupyter.org")

    def test_established_false_when_condition_absent(self) -> None:
        crd = _mock_crd(conditions=None)
        mock_api = self._make_api(crd)

        info = get_crd(mock_api, name="workspaces.workspace.jupyter.org")

        self.assertFalse(info.established)

    def test_established_false_when_condition_not_true(self) -> None:
        crd = _mock_crd(conditions=[_mock_condition("Established", "False")])
        mock_api = self._make_api(crd)

        info = get_crd(mock_api, name="workspaces.workspace.jupyter.org")

        self.assertFalse(info.established)

    def test_filters_served_versions_and_picks_stored(self) -> None:
        crd = _mock_crd(
            versions=[
                _mock_version("v1alpha1", served=True, storage=False),
                _mock_version("v1beta1", served=True, storage=True),
                _mock_version("v1alpha0", served=False, storage=False),
            ],
            conditions=[_mock_condition("Established", "True")],
        )
        mock_api = self._make_api(crd)

        info = get_crd(mock_api, name="workspaces.workspace.jupyter.org")

        self.assertEqual(info.served_versions, ["v1alpha1", "v1beta1"])
        self.assertEqual(info.stored_version, "v1beta1")

    def test_raises_on_api_error(self) -> None:
        mock_api: Mock = Mock(spec=ApiextensionsV1Api)
        mock_api.read_custom_resource_definition.side_effect = _NOT_FOUND

        with self.assertRaises(ApiException):
            get_crd(mock_api, name="nonexistent")
