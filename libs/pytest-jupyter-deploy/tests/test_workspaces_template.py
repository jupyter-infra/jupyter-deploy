"""Unit tests for the WorkspaceTemplate helpers: the object getter."""

import json
import subprocess
import unittest
from unittest.mock import Mock, patch

from pytest_jupyter_deploy.workspaces.template import get_template


class TestGetTemplate(unittest.TestCase):
    @patch("pytest_jupyter_deploy.workspaces.template.run_kubectl")
    def test_returns_the_object(self, mock_run_kubectl: Mock) -> None:
        template = {"metadata": {"name": "vscode", "namespace": "default"}, "spec": {"defaultImage": "img"}}
        mock_run_kubectl.return_value = subprocess.CompletedProcess([], 0, stdout=json.dumps(template), stderr="")

        self.assertEqual(get_template("vscode", "default"), template)
        mock_run_kubectl.assert_called_once_with("get", "workspacetemplate", "vscode", "-n", "default", "-o", "json")

    @patch("pytest_jupyter_deploy.workspaces.template.run_kubectl")
    def test_fails_naming_the_missing_template(self, mock_run_kubectl: Mock) -> None:
        mock_run_kubectl.return_value = subprocess.CompletedProcess([], 1, stdout="", stderr="not found")

        with self.assertRaisesRegex(AssertionError, "vscode WorkspaceTemplate missing in default"):
            get_template("vscode", "default")
