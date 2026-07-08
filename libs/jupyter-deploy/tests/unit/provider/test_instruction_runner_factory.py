import importlib
import sys
import unittest
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import ANY, Mock, patch

from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.provider import instruction_runner_factory
from jupyter_deploy.provider.enum import ApiGroup
from jupyter_deploy.provider.instruction_runner import InstructionRunner


class TestInstructionRunnerFactory(unittest.TestCase):
    def setUp(self) -> None:
        # aws provider module mocks
        self.mock_aws_api_runner = Mock(spec=InstructionRunner)
        self.mock_aws_api_runner_cls = Mock()
        self.mock_aws_api_runner_cls.return_value = self.mock_aws_api_runner

        self.mock_aws_runner_module = Mock()
        self.mock_aws_runner_module.AwsApiRunner = self.mock_aws_api_runner_cls

        # k8s provider module mocks
        self.mock_k8s_api_runner = Mock(spec=InstructionRunner)
        self.mock_k8s_api_runner_cls = Mock()
        self.mock_k8s_api_runner_cls.return_value = self.mock_k8s_api_runner

        self.mock_k8s_runner_module = Mock()
        self.mock_k8s_runner_module.K8sApiRunner = self.mock_k8s_api_runner_cls

        # helm provider module mocks
        self.mock_helm_api_runner = Mock(spec=InstructionRunner)
        self.mock_helm_api_runner_cls = Mock()
        self.mock_helm_api_runner_cls.return_value = self.mock_helm_api_runner

        self.mock_helm_runner_module = Mock()
        self.mock_helm_runner_module.HelmApiRunner = self.mock_helm_api_runner_cls

        # outputs handler mock
        self.mock_outputs_handler = Mock(spec=EngineOutputsHandler)
        self.mock_str_template_output_def = Mock(spec=StrTemplateOutputDefinition)
        self.mock_str_template_output_def.value = "us-west-2"
        self.mock_get_declared_output_def = Mock()
        self.mock_get_declared_output_def.return_value = self.mock_str_template_output_def
        self.mock_outputs_handler.get_declared_output_def = self.mock_get_declared_output_def

    @contextmanager
    def patch_provider_runner_modules(self) -> Generator:
        """Patch all provider runner modules from the correct import location.

        This is subtle:
            - when running the global `uv run pytest`, the provider modules are already imported
            - when running `uv run pytest /path/to/this/test_module.py, they are not (runtime import)

        This results in different behavior where test may pass when run in isolation, and fail
        when run globally - obviously we do not want that.
        """
        modules_to_patch: dict[str, Mock] = {}
        attrs_to_patch: dict[str, Mock] = {}

        aws_mod = "jupyter_deploy.provider.aws.aws_runner"
        k8s_mod = "jupyter_deploy.provider.k8s.k8s_runner"
        helm_mod = "jupyter_deploy.provider.helm.helm_runner"

        if aws_mod not in sys.modules:
            modules_to_patch[aws_mod] = self.mock_aws_runner_module
        else:
            attrs_to_patch[aws_mod] = self.mock_aws_runner_module

        if k8s_mod not in sys.modules:
            modules_to_patch[k8s_mod] = self.mock_k8s_runner_module
        else:
            attrs_to_patch[k8s_mod] = self.mock_k8s_runner_module

        if helm_mod not in sys.modules:
            modules_to_patch[helm_mod] = self.mock_helm_runner_module
        else:
            attrs_to_patch[helm_mod] = self.mock_helm_runner_module

        with patch.dict(sys.modules, modules_to_patch):
            patches = [patch(key, val) for key, val in attrs_to_patch.items()]
            for p in patches:
                p.start()
            try:
                yield
            finally:
                for p in patches:
                    p.stop()

    def test_does_not_create_any_runner_provider_on_class_setup(self) -> None:
        with self.patch_provider_runner_modules():
            importlib.reload(instruction_runner_factory)
            InstructionRunnerFactory = instruction_runner_factory.InstructionRunnerFactory
            InstructionRunnerFactory._api_group_runner_map = {}

            self.mock_aws_api_runner_cls.assert_not_called()

            # Verify that the provider runner map is empty
            self.assertEqual({}, InstructionRunnerFactory._api_group_runner_map)

    def test_imports_aws_provider_at_runtime_only_and_return_it(self) -> None:
        # Execute
        with self.patch_provider_runner_modules():
            importlib.reload(instruction_runner_factory)
            InstructionRunnerFactory = instruction_runner_factory.InstructionRunnerFactory
            InstructionRunnerFactory._api_group_runner_map = {}

            runner = InstructionRunnerFactory.get_provider_instruction_runner(
                "aws", self.mock_outputs_handler, NullDisplay()
            )

            # Verify
            self.mock_get_declared_output_def.assert_called_once_with("aws_region", StrTemplateOutputDefinition)

            self.assertEqual(self.mock_aws_api_runner, runner)
            self.assertEqual({ApiGroup.AWS: self.mock_aws_api_runner}, InstructionRunnerFactory._api_group_runner_map)
            # Verify the runner was called with display_manager and region_name
            # Note: ANY is used for display_manager since it's a NullDisplay() instance
            self.mock_aws_api_runner_cls.assert_called_once_with(display_manager=ANY, region_name="us-west-2")

    def test_aws_provider_raises_if_output_provider_cannot_get_the_region(self) -> None:
        # Setup
        mock_outputs_handler = Mock(spec=EngineOutputsHandler)
        mock_outputs_handler.get_declared_output_def.side_effect = ValueError("Region not found")

        # Execute and verify
        with self.assertRaises(ValueError) as context, self.patch_provider_runner_modules():
            importlib.reload(instruction_runner_factory)
            InstructionRunnerFactory = instruction_runner_factory.InstructionRunnerFactory
            InstructionRunnerFactory._api_group_runner_map = {}

            InstructionRunnerFactory.get_provider_instruction_runner("aws", mock_outputs_handler, NullDisplay())

            self.assertEqual("Region not found", str(context.exception))
            self.mock_get_declared_output_def.assert_called_once_with("aws_region", StrTemplateOutputDefinition)
            self.mock_aws_api_runner_cls.assert_not_called()

    def test_recycle_aws_runner_provider_for_same_output_handler(self) -> None:
        with self.patch_provider_runner_modules():
            importlib.reload(instruction_runner_factory)
            InstructionRunnerFactory = instruction_runner_factory.InstructionRunnerFactory
            InstructionRunnerFactory._api_group_runner_map = {}

            # First call
            first_result = InstructionRunnerFactory.get_provider_instruction_runner(
                "aws", self.mock_outputs_handler, NullDisplay()
            )

            # Second call with same output handler
            second_result = InstructionRunnerFactory.get_provider_instruction_runner(
                "aws", self.mock_outputs_handler, NullDisplay()
            )

            # Verify
            self.assertEqual(first_result, second_result)
            self.assertEqual({ApiGroup.AWS: self.mock_aws_api_runner}, InstructionRunnerFactory._api_group_runner_map)
            self.mock_aws_api_runner_cls.assert_called_once()

    def test_recycle_aws_runner_provider_for_different_output_handler(self) -> None:
        # Setup
        mock_outputs_handler2 = Mock(spec=EngineOutputsHandler)
        mock_str_template_output_def2 = Mock(spec=StrTemplateOutputDefinition)
        mock_str_template_output_def2.value = "us-west-2"  # Same region
        mock_outputs_handler2.get_declared_output_def.return_value = mock_str_template_output_def2

        with self.patch_provider_runner_modules():
            importlib.reload(instruction_runner_factory)
            InstructionRunnerFactory = instruction_runner_factory.InstructionRunnerFactory
            InstructionRunnerFactory._api_group_runner_map = {}

            # First call
            first_result = InstructionRunnerFactory.get_provider_instruction_runner(
                "aws", self.mock_outputs_handler, NullDisplay()
            )

            # Second call with same output handler
            second_result = InstructionRunnerFactory.get_provider_instruction_runner(
                "aws", mock_outputs_handler2, NullDisplay()
            )

            # Verify
            self.assertEqual(first_result, second_result)
            self.assertEqual({ApiGroup.AWS: self.mock_aws_api_runner}, InstructionRunnerFactory._api_group_runner_map)
            self.mock_aws_api_runner_cls.assert_called_once()

    def test_imports_k8s_provider_with_eks_outputs_and_return_it(self) -> None:
        mock_outputs_handler = Mock(spec=EngineOutputsHandler)

        def _mock_get_declared(name: str, value_type: type) -> Mock:
            values = {
                "cluster_endpoint": "https://example.eks.amazonaws.com",
                "cluster_ca_certificate": "Y2VydA==",
                "cluster_name": "my-cluster",
                "aws_region": "us-west-2",
            }
            mock_def = Mock(spec=StrTemplateOutputDefinition)
            mock_def.value = values[name]
            return mock_def

        mock_outputs_handler.get_declared_output_def.side_effect = _mock_get_declared

        with self.patch_provider_runner_modules():
            importlib.reload(instruction_runner_factory)
            InstructionRunnerFactory = instruction_runner_factory.InstructionRunnerFactory
            InstructionRunnerFactory._api_group_runner_map = {}

            runner = InstructionRunnerFactory.get_provider_instruction_runner(
                "k8s", mock_outputs_handler, NullDisplay()
            )

            self.assertEqual(self.mock_k8s_api_runner, runner)
            self.mock_k8s_api_runner_cls.assert_called_once_with(
                display_manager=ANY,
                kubeconfig_path=None,
                cluster_endpoint="https://example.eks.amazonaws.com",
                cluster_ca_data="Y2VydA==",
                cluster_name="my-cluster",
                region="us-west-2",
            )

    def test_imports_k8s_provider_falls_back_to_kubeconfig(self) -> None:
        mock_outputs_handler = Mock(spec=EngineOutputsHandler)

        def _mock_get_declared(name: str, value_type: type) -> Mock:
            if name == "kubeconfig_path":
                mock_def = Mock(spec=StrTemplateOutputDefinition)
                mock_def.value = "/tmp/kubeconfig"
                return mock_def
            raise NotImplementedError(f"No value: {name}")

        mock_outputs_handler.get_declared_output_def.side_effect = _mock_get_declared

        with self.patch_provider_runner_modules():
            importlib.reload(instruction_runner_factory)
            InstructionRunnerFactory = instruction_runner_factory.InstructionRunnerFactory
            InstructionRunnerFactory._api_group_runner_map = {}

            runner = InstructionRunnerFactory.get_provider_instruction_runner(
                "k8s", mock_outputs_handler, NullDisplay()
            )

            self.assertEqual(self.mock_k8s_api_runner, runner)
            self.mock_k8s_api_runner_cls.assert_called_once_with(
                display_manager=ANY,
                kubeconfig_path="/tmp/kubeconfig",
                cluster_endpoint=None,
                cluster_ca_data=None,
                cluster_name=None,
                region=None,
            )

    def test_imports_helm_provider_with_eks_outputs_and_return_it(self) -> None:
        # With full in-memory EKS creds the kubeconfig fallback is not read, so the helm
        # runner gets kubeconfig_path=None and relies on the ambient kubeconfig.
        mock_outputs_handler = Mock(spec=EngineOutputsHandler)

        def _mock_get_declared(name: str, value_type: type) -> Mock:
            values = {
                "cluster_endpoint": "https://example.eks.amazonaws.com",
                "cluster_ca_certificate": "Y2VydA==",
                "cluster_name": "my-cluster",
                "aws_region": "us-west-2",
            }
            mock_def = Mock(spec=StrTemplateOutputDefinition)
            mock_def.value = values[name]
            return mock_def

        mock_outputs_handler.get_declared_output_def.side_effect = _mock_get_declared

        with self.patch_provider_runner_modules():
            importlib.reload(instruction_runner_factory)
            InstructionRunnerFactory = instruction_runner_factory.InstructionRunnerFactory
            InstructionRunnerFactory._api_group_runner_map = {}

            runner = InstructionRunnerFactory.get_provider_instruction_runner(
                "helm", mock_outputs_handler, NullDisplay()
            )

            self.assertEqual(self.mock_helm_api_runner, runner)
            self.assertEqual({ApiGroup.HELM: self.mock_helm_api_runner}, InstructionRunnerFactory._api_group_runner_map)
            # helm runner only takes display_manager + kubeconfig_path (no in-memory creds).
            self.mock_helm_api_runner_cls.assert_called_once_with(display_manager=ANY, kubeconfig_path=None)

    def test_imports_helm_provider_falls_back_to_kubeconfig(self) -> None:
        mock_outputs_handler = Mock(spec=EngineOutputsHandler)

        def _mock_get_declared(name: str, value_type: type) -> Mock:
            if name == "kubeconfig_path":
                mock_def = Mock(spec=StrTemplateOutputDefinition)
                mock_def.value = "/tmp/kubeconfig"
                return mock_def
            raise NotImplementedError(f"No value: {name}")

        mock_outputs_handler.get_declared_output_def.side_effect = _mock_get_declared

        with self.patch_provider_runner_modules():
            importlib.reload(instruction_runner_factory)
            InstructionRunnerFactory = instruction_runner_factory.InstructionRunnerFactory
            InstructionRunnerFactory._api_group_runner_map = {}

            runner = InstructionRunnerFactory.get_provider_instruction_runner(
                "helm", mock_outputs_handler, NullDisplay()
            )

            self.assertEqual(self.mock_helm_api_runner, runner)
            self.mock_helm_api_runner_cls.assert_called_once_with(
                display_manager=ANY, kubeconfig_path="/tmp/kubeconfig"
            )

    def test_recycle_helm_runner_provider_for_same_output_handler(self) -> None:
        mock_outputs_handler = Mock(spec=EngineOutputsHandler)

        def _mock_get_declared(name: str, value_type: type) -> Mock:
            if name == "kubeconfig_path":
                mock_def = Mock(spec=StrTemplateOutputDefinition)
                mock_def.value = "/tmp/kubeconfig"
                return mock_def
            raise NotImplementedError(f"No value: {name}")

        mock_outputs_handler.get_declared_output_def.side_effect = _mock_get_declared

        with self.patch_provider_runner_modules():
            importlib.reload(instruction_runner_factory)
            InstructionRunnerFactory = instruction_runner_factory.InstructionRunnerFactory
            InstructionRunnerFactory._api_group_runner_map = {}

            first = InstructionRunnerFactory.get_provider_instruction_runner(
                "helm", mock_outputs_handler, NullDisplay()
            )
            second = InstructionRunnerFactory.get_provider_instruction_runner(
                "helm", mock_outputs_handler, NullDisplay()
            )

            self.assertEqual(first, second)
            self.mock_helm_api_runner_cls.assert_called_once()

    def test_raise_not_value_error_on_unmatched_provider(self) -> None:
        mock_outputs_handler = Mock(spec=EngineOutputsHandler)

        with (
            self.patch_provider_runner_modules(),
            self.assertRaises(ValueError),
        ):
            importlib.reload(instruction_runner_factory)
            InstructionRunnerFactory = instruction_runner_factory.InstructionRunnerFactory
            InstructionRunnerFactory._api_group_runner_map = {}

            InstructionRunnerFactory.get_provider_instruction_runner("onpremises", mock_outputs_handler, NullDisplay())
            self.mock_aws_api_runner_cls.assert_not_called()
            self.mock_get_declared_output_def.assert_not_called()
