import subprocess
import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.exceptions import InstructionError, InvalidKubernetesClusterTargetError
from jupyter_deploy.provider.k8s.kubeconfig_verify import verify_kubeconfig_context

_RUN = "jupyter_deploy.provider.k8s.kubeconfig_verify.cmd_utils.run_cmd_and_capture_output"
_ARN = "arn:aws:eks:us-west-2:123:cluster/jupyter-deploy-eks-abcd1234"


class TestVerifyKubeconfigContext(unittest.TestCase):
    @patch(_RUN)
    def test_passes_when_context_matches(self, mock_run: Mock) -> None:
        mock_run.return_value = f"{_ARN}\n"

        # should not raise
        verify_kubeconfig_context(_ARN)

        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd, ["kubectl", "config", "current-context"])

    @patch(_RUN)
    def test_passes_kubeconfig_flag_when_path_set(self, mock_run: Mock) -> None:
        mock_run.return_value = _ARN

        verify_kubeconfig_context(_ARN, kubeconfig_path="/tmp/kc")

        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd, ["kubectl", "config", "current-context", "--kubeconfig", "/tmp/kc"])

    @patch(_RUN)
    def test_raises_invalid_target_on_mismatch(self, mock_run: Mock) -> None:
        mock_run.return_value = "arn:aws:eks:us-west-2:123:cluster/some-other-cluster"

        with self.assertRaises(InvalidKubernetesClusterTargetError) as ctx:
            verify_kubeconfig_context(_ARN)

        self.assertEqual(ctx.exception.expected_cluster_config, _ARN)
        self.assertEqual(ctx.exception.current_context, "arn:aws:eks:us-west-2:123:cluster/some-other-cluster")

    @patch(_RUN)
    def test_raises_instruction_error_when_context_unreadable(self, mock_run: Mock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["kubectl"], stderr="error: current-context is not set"
        )

        with self.assertRaises(InstructionError) as ctx:
            verify_kubeconfig_context(_ARN)
        self.assertNotIsInstance(ctx.exception, InvalidKubernetesClusterTargetError)

    @patch(_RUN)
    def test_skips_when_expected_config_empty(self, mock_run: Mock) -> None:
        # No expected config declared -> skip (backward compatible).
        verify_kubeconfig_context(None)
        verify_kubeconfig_context("")

        mock_run.assert_not_called()
