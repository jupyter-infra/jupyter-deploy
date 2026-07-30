import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.pool_app import pool_app
from jupyter_deploy.handlers.payloads import PoolDetail


class TestPoolApp(unittest.TestCase):
    runner = CliRunner()

    def get_mock_pool_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_handler = Mock()
        mock_list_pools = Mock(return_value=["routing", "workspace-cpu"])
        mock_show_pool = Mock(
            return_value=PoolDetail(
                name="workspace-cpu",
                status="Ready",
                resource={"status": {"conditions": [{"type": "Ready", "status": "True"}]}},
            )
        )
        mock_get_status = Mock(return_value="Ready")

        mock_handler.list_pools = mock_list_pools
        mock_handler.show_pool = mock_show_pool
        mock_handler.get_status = mock_get_status

        return mock_handler, {
            "list_pools": mock_list_pools,
            "show_pool": mock_show_pool,
            "get_status": mock_get_status,
        }

    def test_pool_help(self) -> None:
        result = self.runner.invoke(pool_app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("pools of hosts", result.output)

    @patch("jupyter_deploy.handlers.resource.pool_handler.PoolHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_pool_list(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, mock_fns = self.get_mock_pool_handler()
        mock_handler_class.return_value = mock_handler

        result = self.runner.invoke(pool_app, ["list"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("routing", result.output)
        self.assertIn("workspace-cpu", result.output)
        mock_fns["list_pools"].assert_called_once()

    @patch("jupyter_deploy.handlers.resource.pool_handler.PoolHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_pool_list_json(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, mock_fns = self.get_mock_pool_handler()
        mock_handler_class.return_value = mock_handler

        result = self.runner.invoke(pool_app, ["list", "--json"])

        self.assertEqual(result.exit_code, 0)
        parsed = json.loads(result.output)
        self.assertEqual(parsed, {"pools": ["routing", "workspace-cpu"]})

    @patch("jupyter_deploy.handlers.resource.pool_handler.PoolHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_pool_list_empty(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, _ = self.get_mock_pool_handler()
        mock_handler.list_pools.return_value = []
        mock_handler_class.return_value = mock_handler

        result = self.runner.invoke(pool_app, ["list"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("None", result.output)

    @patch("jupyter_deploy.handlers.resource.pool_handler.PoolHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_pool_show(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, mock_fns = self.get_mock_pool_handler()
        mock_handler_class.return_value = mock_handler

        result = self.runner.invoke(pool_app, ["show", "--name", "workspace-cpu"])

        self.assertEqual(result.exit_code, 0)
        mock_fns["show_pool"].assert_called_once_with(name="workspace-cpu")

    @patch("jupyter_deploy.handlers.resource.pool_handler.PoolHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_pool_show_json(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, _ = self.get_mock_pool_handler()
        mock_handler_class.return_value = mock_handler

        result = self.runner.invoke(pool_app, ["show", "--name", "workspace-cpu", "--json"])

        self.assertEqual(result.exit_code, 0)
        parsed = json.loads(result.output)
        self.assertEqual(parsed["name"], "workspace-cpu")
        self.assertEqual(parsed["status"], "Ready")

    @patch("jupyter_deploy.handlers.resource.pool_handler.PoolHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_pool_status(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, mock_fns = self.get_mock_pool_handler()
        mock_handler_class.return_value = mock_handler

        result = self.runner.invoke(pool_app, ["status", "--name", "workspace-cpu"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Ready", result.output)
        mock_fns["get_status"].assert_called_once_with(name="workspace-cpu")

    @patch("jupyter_deploy.handlers.resource.pool_handler.PoolHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_pool_show_passes_project_dir(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, _ = self.get_mock_pool_handler()
        mock_handler_class.return_value = mock_handler

        result = self.runner.invoke(pool_app, ["show", "--name", "routing", "--path", "/tmp/my-project"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/tmp/my-project"))
