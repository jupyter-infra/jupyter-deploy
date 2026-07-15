"""Unit tests for the kubernetes.rbac helpers."""

import subprocess
import unittest
from unittest.mock import Mock, patch

from pytest_jupyter_deploy.kubernetes.rbac import impersonated_user_can


class TestImpersonatedUserCan(unittest.TestCase):
    @patch("pytest_jupyter_deploy.kubernetes.rbac.run_kubectl")
    def test_yes_returns_true(self, mock_run_kubectl: Mock) -> None:
        mock_run_kubectl.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="yes\n", stderr="")
        self.assertTrue(impersonated_user_can("get", "workspacetemplates", "jupyter-k8s-shared", as_user="github:u"))

    @patch("pytest_jupyter_deploy.kubernetes.rbac.run_kubectl")
    def test_no_returns_false(self, mock_run_kubectl: Mock) -> None:
        # can-i exits non-zero on "no"; the answer must come from stdout, not returncode.
        mock_run_kubectl.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="no\n", stderr="")
        self.assertFalse(
            impersonated_user_can("delete", "workspacetemplates", "jupyter-k8s-shared", as_user="github:u")
        )

    @patch("pytest_jupyter_deploy.kubernetes.rbac.run_kubectl")
    def test_passes_can_i_args_and_impersonation(self, mock_run_kubectl: Mock) -> None:
        mock_run_kubectl.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="yes", stderr="")
        impersonated_user_can(
            "list",
            "workspaceaccessstrategies",
            "default",
            as_user="github:alice",
            as_groups=["github:org:team-a"],
        )
        self.assertEqual(
            mock_run_kubectl.call_args.args,
            ("auth", "can-i", "list", "workspaceaccessstrategies", "-n", "default"),
        )
        self.assertEqual(mock_run_kubectl.call_args.kwargs["as_user"], "github:alice")
        self.assertEqual(mock_run_kubectl.call_args.kwargs["as_groups"], ["github:org:team-a"])
