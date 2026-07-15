"""Unit tests for the kubernetes.kubectl runner."""

import subprocess
import unittest
from unittest.mock import Mock, patch

from pytest_jupyter_deploy.kubernetes.kubectl import run_kubectl


class TestRunKubectl(unittest.TestCase):
    @patch("pytest_jupyter_deploy.kubernetes.kubectl.subprocess.run")
    def test_builds_plain_command(self, mock_run: Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        run_kubectl("get", "pods", "-n", "default")
        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd, ["kubectl", "get", "pods", "-n", "default"])
        self.assertFalse(mock_run.call_args.kwargs["check"])

    @patch("pytest_jupyter_deploy.kubernetes.kubectl.subprocess.run")
    def test_appends_impersonation_flags(self, mock_run: Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        run_kubectl(
            "get",
            "workspacetemplates",
            as_user="github:alice",
            as_groups=["github:org:team-a", "github:org:team-b"],
        )
        cmd = mock_run.call_args.args[0]
        self.assertEqual(
            cmd,
            [
                "kubectl",
                "get",
                "workspacetemplates",
                "--as",
                "github:alice",
                "--as-group",
                "github:org:team-a",
                "--as-group",
                "github:org:team-b",
            ],
        )

    @patch("pytest_jupyter_deploy.kubernetes.kubectl.subprocess.run")
    def test_no_groups_omits_as_group_flag(self, mock_run: Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        run_kubectl("get", "pods", as_user="github:u")
        cmd = mock_run.call_args.args[0]
        self.assertNotIn("--as-group", cmd)

    @patch("pytest_jupyter_deploy.kubernetes.kubectl.subprocess.run")
    def test_check_flag_threads_through(self, mock_run: Mock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        run_kubectl("cluster-info", check=True)
        self.assertTrue(mock_run.call_args.kwargs["check"])
