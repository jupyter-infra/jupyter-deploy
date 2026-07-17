import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.cluster_app import cluster_app
from jupyter_deploy.handlers.payloads import ClusterDetail


class TestClusterApp(unittest.TestCase):
    def test_help_command(self) -> None:
        self.assertTrue(len(cluster_app.info.help or "") > 0, "help should not be empty")

        runner = CliRunner()
        result = runner.invoke(cluster_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        for cmd in ["login", "status", "show"]:
            self.assertTrue(result.stdout.index(cmd) > 0, f"missing command: {cmd}")

    def test_no_arg_defaults_to_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cluster_app, [])

        self.assertIn(result.exit_code, (0, 2))
        self.assertTrue(len(result.stdout) > 0)


class TestClusterLoginCommand(unittest.TestCase):
    @patch("jupyter_deploy.handlers.resource.cluster_handler.ClusterHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_calls_login_and_prints_output(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler: Mock = Mock()
        mock_handler.login.return_value = "Updated context for cluster my-cluster"
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(cluster_app, ["login"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_class.assert_called_once()
        mock_handler.login.assert_called_once()
        self.assertIn("Updated context for cluster my-cluster", result.stdout)

    @patch("jupyter_deploy.handlers.resource.cluster_handler.ClusterHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler: Mock = Mock()
        mock_handler.login.return_value = "ok"
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(cluster_app, ["login", "--path", "/my/project"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/my/project"))

    @patch("jupyter_deploy.handlers.resource.cluster_handler.ClusterHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_handler_raises(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler: Mock = Mock()
        mock_handler.login.side_effect = Exception("Test error")
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(cluster_app, ["login"])

        self.assertNotEqual(result.exit_code, 0)


class TestClusterStatusCommand(unittest.TestCase):
    @patch("jupyter_deploy.handlers.resource.cluster_handler.ClusterHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_calls_get_cluster_status(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler: Mock = Mock()
        mock_handler.get_cluster_status.return_value = "ACTIVE"
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(cluster_app, ["status"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_class.assert_called_once()
        mock_handler.get_cluster_status.assert_called_once()

    @patch("jupyter_deploy.handlers.resource.cluster_handler.ClusterHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_displays_title_case(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler: Mock = Mock()
        mock_handler.get_cluster_status.return_value = "ACTIVE"
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(cluster_app, ["status"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Active", result.stdout)
        self.assertNotIn("ACTIVE", result.stdout)

    @patch("jupyter_deploy.handlers.resource.cluster_handler.ClusterHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_title_case_multi_word(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler: Mock = Mock()
        mock_handler.get_cluster_status.return_value = "CREATING"
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(cluster_app, ["status"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Creating", result.stdout)
        self.assertNotIn("CREATING", result.stdout)

    @patch("jupyter_deploy.handlers.resource.cluster_handler.ClusterHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler: Mock = Mock()
        mock_handler.get_cluster_status.return_value = "ACTIVE"
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(cluster_app, ["status", "--path", "/my/project"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/my/project"))

    @patch("jupyter_deploy.handlers.resource.cluster_handler.ClusterHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_handler_raises(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler: Mock = Mock()
        mock_handler.get_cluster_status.side_effect = Exception("Test error")
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(cluster_app, ["status"])

        self.assertNotEqual(result.exit_code, 0)


class TestClusterShowCommand(unittest.TestCase):
    @patch("jupyter_deploy.handlers.resource.cluster_handler.ClusterHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_calls_show_cluster(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler: Mock = Mock()
        mock_handler.show_cluster.return_value = ClusterDetail(name="my-cluster", status="ACTIVE", version="1.30")
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(cluster_app, ["show"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_class.assert_called_once()
        mock_handler.show_cluster.assert_called_once()

    @patch("jupyter_deploy.handlers.resource.cluster_handler.ClusterHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_default_output_contains_details(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler: Mock = Mock()
        mock_handler.show_cluster.return_value = ClusterDetail(name="my-cluster", status="ACTIVE", version="1.30")
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(cluster_app, ["show"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("my-cluster", result.stdout)
        self.assertIn("ACTIVE", result.stdout)
        self.assertIn("1.30", result.stdout)

    @patch("jupyter_deploy.handlers.resource.cluster_handler.ClusterHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_json_output(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler: Mock = Mock()
        mock_handler.show_cluster.return_value = ClusterDetail(name="my-cluster", status="ACTIVE", version="1.30")
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(cluster_app, ["show", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["name"], "my-cluster")
        self.assertEqual(data["status"], "ACTIVE")
        self.assertEqual(data["version"], "1.30")

    @patch("jupyter_deploy.handlers.resource.cluster_handler.ClusterHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler: Mock = Mock()
        mock_handler.show_cluster.return_value = ClusterDetail(name="c", status="ACTIVE")
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(cluster_app, ["show", "--path", "/my/project"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/my/project"))

    @patch("jupyter_deploy.handlers.resource.cluster_handler.ClusterHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_handler_raises(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler: Mock = Mock()
        mock_handler.show_cluster.side_effect = Exception("Test error")
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(cluster_app, ["show"])

        self.assertNotEqual(result.exit_code, 0)
