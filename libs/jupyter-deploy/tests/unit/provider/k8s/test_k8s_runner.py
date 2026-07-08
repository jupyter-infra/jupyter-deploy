import unittest
from unittest.mock import ANY, Mock, patch

from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import InstructionNotFoundError
from jupyter_deploy.provider.k8s.k8s_runner import K8sApiRunner, K8sService
from jupyter_deploy.provider.resolved_argdefs import ResolvedInstructionArgument
from jupyter_deploy.provider.resolved_resultdefs import ResolvedInstructionResult


class TestK8sApiRunner(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sClientFactory")
    def test_init_does_not_create_client(self, mock_factory: Mock) -> None:
        K8sApiRunner(NullDisplay(), kubeconfig_path="/tmp/kubeconfig")
        mock_factory.from_kubeconfig.assert_not_called()

    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sCoreRunner")
    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sClientFactory")
    def test_execute_instantiates_core_runner_and_delegates(
        self, mock_factory: Mock, mock_core_runner_class: Mock
    ) -> None:
        mock_api_client: Mock = Mock()
        mock_factory.from_kubeconfig.return_value = mock_api_client

        mock_core_runner: Mock = Mock()
        mock_core_runner_class.return_value = mock_core_runner
        expected_result = {"result_key": Mock(spec=ResolvedInstructionResult)}
        mock_core_runner.execute_instruction.return_value = expected_result

        runner = K8sApiRunner(NullDisplay(), kubeconfig_path="/tmp/kubeconfig")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"arg1": Mock(spec=ResolvedInstructionArgument)}

        result = runner.execute_instruction(instruction_name="k8s.core.list-nodes", resolved_arguments=resolved_args)

        mock_factory.from_kubeconfig.assert_called_once_with(kubeconfig_path="/tmp/kubeconfig")
        mock_core_runner_class.assert_called_once_with(
            ANY, api_client=mock_api_client, kubeconfig_path="/tmp/kubeconfig"
        )
        mock_core_runner.execute_instruction.assert_called_once_with(
            instruction_name="list-nodes", resolved_arguments=resolved_args
        )
        self.assertEqual(result, expected_result)

    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sCustomRunner")
    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sClientFactory")
    def test_execute_instantiates_custom_runner_and_delegates(
        self, mock_factory: Mock, mock_custom_runner_class: Mock
    ) -> None:
        mock_api_client: Mock = Mock()
        mock_factory.from_kubeconfig.return_value = mock_api_client

        mock_custom_runner: Mock = Mock()
        mock_custom_runner_class.return_value = mock_custom_runner
        expected_result = {"result_key": Mock(spec=ResolvedInstructionResult)}
        mock_custom_runner.execute_instruction.return_value = expected_result

        runner = K8sApiRunner(NullDisplay(), kubeconfig_path="/tmp/kubeconfig")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"arg1": Mock(spec=ResolvedInstructionArgument)}

        result = runner.execute_instruction(instruction_name="k8s.custom.list", resolved_arguments=resolved_args)

        mock_factory.from_kubeconfig.assert_called_once_with(kubeconfig_path="/tmp/kubeconfig")
        mock_custom_runner_class.assert_called_once_with(ANY, api_client=mock_api_client)
        mock_custom_runner.execute_instruction.assert_called_once_with(
            instruction_name="list", resolved_arguments=resolved_args
        )
        self.assertEqual(result, expected_result)

    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sCoreRunner")
    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sClientFactory")
    def test_execute_recycles_service_runner(self, mock_factory: Mock, mock_core_runner_class: Mock) -> None:
        mock_api_client: Mock = Mock()
        mock_factory.from_kubeconfig.return_value = mock_api_client

        mock_core_runner: Mock = Mock()
        mock_core_runner_class.return_value = mock_core_runner

        runner = K8sApiRunner(NullDisplay(), kubeconfig_path="/tmp/kubeconfig")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"arg1": Mock(spec=ResolvedInstructionArgument)}

        runner.execute_instruction(instruction_name="k8s.core.list-nodes", resolved_arguments=resolved_args)
        runner.execute_instruction(instruction_name="k8s.core.get-node", resolved_arguments=resolved_args)

        mock_core_runner_class.assert_called_once()
        self.assertEqual(mock_core_runner.execute_instruction.call_count, 2)
        self.assertEqual(len(runner._service_runners), 1)
        self.assertIn(K8sService.CORE, runner._service_runners)

    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sClientFactory")
    def test_execute_raises_on_unknown_service(self, mock_factory: Mock) -> None:
        mock_factory.from_kubeconfig.return_value = Mock()
        runner = K8sApiRunner(NullDisplay(), kubeconfig_path="/tmp/kubeconfig")

        with self.assertRaises(InstructionNotFoundError) as context:
            runner.execute_instruction(instruction_name="k8s.unknown.command", resolved_arguments={})

        self.assertIn("unknown", str(context.exception))

    def test_execute_raises_on_invalid_instruction_name(self) -> None:
        runner = K8sApiRunner(NullDisplay(), kubeconfig_path="/tmp/kubeconfig")

        invalid_instructions = ["", ".", "k8s", "k8s.", "k8s.core", "k8s.core."]
        for invalid_instruction in invalid_instructions:
            with self.subTest(invalid_instruction=invalid_instruction):
                with self.assertRaises(ValueError) as context:
                    runner.execute_instruction(instruction_name=invalid_instruction, resolved_arguments={})
                self.assertIn(invalid_instruction, str(context.exception))

    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sAppsRunner")
    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sClientFactory")
    def test_execute_instantiates_apps_runner_and_delegates(
        self, mock_factory: Mock, mock_apps_runner_class: Mock
    ) -> None:
        mock_api_client: Mock = Mock()
        mock_factory.from_kubeconfig.return_value = mock_api_client

        mock_apps_runner: Mock = Mock()
        mock_apps_runner_class.return_value = mock_apps_runner
        expected_result = {"result_key": Mock(spec=ResolvedInstructionResult)}
        mock_apps_runner.execute_instruction.return_value = expected_result

        runner = K8sApiRunner(NullDisplay(), kubeconfig_path="/tmp/kubeconfig")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"arg1": Mock(spec=ResolvedInstructionArgument)}

        result = runner.execute_instruction(
            instruction_name="k8s.apps.get-deployment-status", resolved_arguments=resolved_args
        )

        mock_apps_runner_class.assert_called_once_with(ANY, api_client=mock_api_client)
        mock_apps_runner.execute_instruction.assert_called_once_with(
            instruction_name="get-deployment-status", resolved_arguments=resolved_args
        )
        self.assertEqual(result, expected_result)

    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sBatchRunner")
    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sClientFactory")
    def test_execute_instantiates_batch_runner_and_delegates(
        self, mock_factory: Mock, mock_batch_runner_class: Mock
    ) -> None:
        mock_api_client: Mock = Mock()
        mock_factory.from_kubeconfig.return_value = mock_api_client

        mock_batch_runner: Mock = Mock()
        mock_batch_runner_class.return_value = mock_batch_runner
        expected_result = {"result_key": Mock(spec=ResolvedInstructionResult)}
        mock_batch_runner.execute_instruction.return_value = expected_result

        runner = K8sApiRunner(NullDisplay(), kubeconfig_path="/tmp/kubeconfig")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"arg1": Mock(spec=ResolvedInstructionArgument)}

        result = runner.execute_instruction(
            instruction_name="k8s.batch.get-cronjob-status", resolved_arguments=resolved_args
        )

        mock_batch_runner_class.assert_called_once_with(
            ANY, api_client=mock_api_client, kubeconfig_path="/tmp/kubeconfig"
        )
        mock_batch_runner.execute_instruction.assert_called_once_with(
            instruction_name="get-cronjob-status", resolved_arguments=resolved_args
        )
        self.assertEqual(result, expected_result)

    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sCoreRunner")
    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sClientFactory")
    def test_uses_eks_cluster_when_all_params_provided(self, mock_factory: Mock, mock_core_runner_class: Mock) -> None:
        mock_api_client: Mock = Mock()
        mock_factory.from_eks_cluster.return_value = mock_api_client
        mock_core_runner_class.return_value = Mock()

        runner = K8sApiRunner(
            NullDisplay(),
            cluster_endpoint="https://example.eks.amazonaws.com",
            cluster_ca_data="Y2VydA==",
            cluster_name="my-cluster",
            region="us-west-2",
        )
        runner.execute_instruction(instruction_name="k8s.core.list-nodes", resolved_arguments={})

        mock_factory.from_eks_cluster.assert_called_once_with(
            endpoint="https://example.eks.amazonaws.com",
            ca_data_b64="Y2VydA==",
            cluster_name="my-cluster",
            region="us-west-2",
        )
        mock_factory.from_kubeconfig.assert_not_called()

    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sCoreRunner")
    @patch("jupyter_deploy.provider.k8s.k8s_runner.K8sClientFactory")
    def test_falls_back_to_kubeconfig_when_eks_params_incomplete(
        self, mock_factory: Mock, mock_core_runner_class: Mock
    ) -> None:
        mock_api_client: Mock = Mock()
        mock_factory.from_kubeconfig.return_value = mock_api_client
        mock_core_runner_class.return_value = Mock()

        runner = K8sApiRunner(
            NullDisplay(),
            kubeconfig_path="/tmp/kubeconfig",
            cluster_endpoint="https://example.eks.amazonaws.com",
        )
        runner.execute_instruction(instruction_name="k8s.core.list-nodes", resolved_arguments={})

        mock_factory.from_kubeconfig.assert_called_once_with(kubeconfig_path="/tmp/kubeconfig")
        mock_factory.from_eks_cluster.assert_not_called()
