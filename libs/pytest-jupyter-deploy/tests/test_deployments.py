"""Unit tests for the kubernetes.deployments helpers."""

import subprocess
import unittest
from unittest.mock import Mock, patch

from pytest_jupyter_deploy.kubernetes.deployments import get_ready_replica_count


class TestGetReadyReplicaCount(unittest.TestCase):
    @patch("pytest_jupyter_deploy.kubernetes.deployments.subprocess.run")
    def test_single_deployment(self, mock_run: Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="2", stderr="")
        self.assertEqual(get_ready_replica_count("app=x", namespace="kube-system"), 2)

    @patch("pytest_jupyter_deploy.kubernetes.deployments.subprocess.run")
    def test_multiple_deployments_summed(self, mock_run: Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="2 1 3", stderr="")
        self.assertEqual(get_ready_replica_count("app=x", namespace="ns"), 6)

    @patch("pytest_jupyter_deploy.kubernetes.deployments.subprocess.run")
    def test_no_match_returns_zero(self, mock_run: Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        self.assertEqual(get_ready_replica_count("app=missing", namespace="ns"), 0)

    @patch("pytest_jupyter_deploy.kubernetes.deployments.subprocess.run")
    def test_passes_selector_and_namespace(self, mock_run: Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="1", stderr="")
        get_ready_replica_count("app.kubernetes.io/instance=cluster-autoscaler", namespace="kube-system")
        args = mock_run.call_args.args[0]
        self.assertIn("app.kubernetes.io/instance=cluster-autoscaler", args)
        self.assertIn("kube-system", args)
