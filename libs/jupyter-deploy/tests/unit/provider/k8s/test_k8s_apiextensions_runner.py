import json
import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.api.k8s.apiextensions import CrdInfo
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import InstructionNotFoundError
from jupyter_deploy.provider.k8s.k8s_apiextensions_runner import K8sApiextensionsRunner
from jupyter_deploy.provider.resolved_argdefs import ResolvedInstructionArgument, StrResolvedInstructionArgument


class TestK8sApiextensionsRunner(unittest.TestCase):
    def _make_runner(self) -> K8sApiextensionsRunner:
        mock_api_client: Mock = Mock()
        with patch("jupyter_deploy.provider.k8s.k8s_apiextensions_runner.client") as mock_client_mod:
            mock_client_mod.ApiextensionsV1Api.return_value = Mock()
            runner = K8sApiextensionsRunner(NullDisplay(), api_client=mock_api_client)
        return runner

    @patch("jupyter_deploy.provider.k8s.k8s_apiextensions_runner.k8s_apiextensions")
    def test_get_crd_returns_typed_results(self, mock_k8s_apiextensions: Mock) -> None:
        runner = self._make_runner()
        resource = {
            "metadata": {"name": "workspaces.workspace.jupyter.org"},
            "spec": {"group": "workspace.jupyter.org"},
        }
        mock_k8s_apiextensions.get_crd.return_value = CrdInfo(
            name="workspaces.workspace.jupyter.org",
            group="workspace.jupyter.org",
            established=True,
            served_versions=["v1alpha1"],
            stored_version="v1alpha1",
            resource=resource,
        )

        args: dict[str, ResolvedInstructionArgument] = {
            "name": StrResolvedInstructionArgument(argument_name="name", value="workspaces.workspace.jupyter.org")
        }
        result = runner.execute_instruction(instruction_name="get-crd", resolved_arguments=args)

        self.assertEqual(result["Name"].value, "workspaces.workspace.jupyter.org")
        self.assertEqual(json.loads(result["Resource"].value)["spec"]["group"], "workspace.jupyter.org")
        self.assertEqual(result["Established"].value, "true")
        self.assertEqual(result["ServedVersions"].value, ["v1alpha1"])
        self.assertEqual(result["StoredVersion"].value, "v1alpha1")
        mock_k8s_apiextensions.get_crd.assert_called_once_with(
            runner.apiextensions_api, name="workspaces.workspace.jupyter.org"
        )

    @patch("jupyter_deploy.provider.k8s.k8s_apiextensions_runner.k8s_apiextensions")
    def test_get_crd_established_false_serializes_false(self, mock_k8s_apiextensions: Mock) -> None:
        runner = self._make_runner()
        mock_k8s_apiextensions.get_crd.return_value = CrdInfo(
            name="workspaces.workspace.jupyter.org",
            group="workspace.jupyter.org",
            established=False,
        )

        args: dict[str, ResolvedInstructionArgument] = {
            "name": StrResolvedInstructionArgument(argument_name="name", value="workspaces.workspace.jupyter.org")
        }
        result = runner.execute_instruction(instruction_name="get-crd", resolved_arguments=args)

        self.assertEqual(result["Established"].value, "false")
        self.assertEqual(result["ServedVersions"].value, [])

    def test_unknown_instruction_raises(self) -> None:
        runner = self._make_runner()

        with self.assertRaises(InstructionNotFoundError):
            runner.execute_instruction(instruction_name="bogus", resolved_arguments={})
