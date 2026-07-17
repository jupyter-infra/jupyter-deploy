import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.component_app import component_app
from jupyter_deploy.handlers.payloads import ComponentDetail, ComponentInfo


class TestComponentApp(unittest.TestCase):
    def test_help_command(self) -> None:
        self.assertTrue(len(component_app.info.help or "") > 0, "help should not be empty")

        runner = CliRunner()
        result = runner.invoke(component_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        for cmd in ["list", "status", "show", "logs", "restart", "trigger", "reconcile"]:
            self.assertTrue(result.stdout.index(cmd) > 0, f"missing command: {cmd}")

    def test_no_arg_defaults_to_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(component_app, [])

        self.assertIn(result.exit_code, (0, 2))
        self.assertTrue(len(result.stdout) > 0)


class TestComponentListCommand(unittest.TestCase):
    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_list_shows_table(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.list_components.return_value = [
            ComponentInfo(name="traefik", type="Deployment", description="Ingress controller"),
            ComponentInfo(name="dex", type="Deployment", description="Identity provider"),
            ComponentInfo(name="jwt-rotator", type="CronJob", description="Rotates JWT keys"),
        ]
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["list"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.list_components.assert_called_once()
        self.assertIn("traefik", result.stdout)
        self.assertIn("Deployment", result.stdout)
        self.assertIn("Ingress controller", result.stdout)
        self.assertIn("jwt-rotator", result.stdout)
        self.assertIn("CronJob", result.stdout)

    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_list_json_output(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.list_components.return_value = [
            ComponentInfo(name="traefik", type="Deployment", description="Ingress controller"),
            ComponentInfo(name="dex", type="Deployment", description="Identity provider"),
        ]
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["list", "--json"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('"name"', result.stdout)
        self.assertIn('"type"', result.stdout)
        self.assertIn('"description"', result.stdout)
        self.assertIn("traefik", result.stdout)

    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_list_text_output(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.list_components.return_value = [
            ComponentInfo(name="traefik", type="Deployment", description="Ingress controller"),
            ComponentInfo(name="dex", type="Deployment", description="Identity provider"),
        ]
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["list", "--text"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("traefik,dex", result.stdout)

    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_list_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.list_components.return_value = []
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["list", "--path", "/my/project"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/my/project"))

    def test_list_rejects_json_and_text_together(self) -> None:
        runner = CliRunner()
        result = runner.invoke(component_app, ["list", "--json", "--text"])

        self.assertNotEqual(result.exit_code, 0)


class TestComponentStatusCommand(unittest.TestCase):
    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_status_prints_result(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.get_component_status.return_value = "Ready"
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["status", "--name", "traefik"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.get_component_status.assert_called_once_with(name="traefik")
        self.assertIn("Ready", result.stdout)

    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_status_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.get_component_status.return_value = "Ready"
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["status", "--name", "traefik", "--path", "/my/project"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/my/project"))

    def test_status_requires_name(self) -> None:
        runner = CliRunner()
        result = runner.invoke(component_app, ["status"])

        self.assertNotEqual(result.exit_code, 0)


class TestComponentShowCommand(unittest.TestCase):
    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_show_calls_show_component(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.show_component.return_value = ComponentDetail(name="traefik", resource={"image": "traefik:v2.10"})
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["show", "--name", "traefik"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.show_component.assert_called_once_with(name="traefik")

    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_show_description_outputs_text(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.get_component_description.return_value = "Ingress controller and reverse proxy"
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["show", "--name", "traefik", "--description"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.get_component_description.assert_called_once_with(name="traefik")
        self.assertIn("Ingress controller and reverse proxy", result.stdout)
        mock_handler.show_component.assert_not_called()

    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_show_json_output(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.show_component.return_value = ComponentDetail(
            name="traefik", resource={"image": "traefik:v2.10", "replicas": 1}
        )
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["show", "--name", "traefik", "--json"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('"name"', result.stdout)
        self.assertIn('"traefik"', result.stdout)
        self.assertIn('"replicas"', result.stdout)

    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_show_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.show_component.return_value = ComponentDetail(name="traefik")
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["show", "--name", "traefik", "--path", "/my/project"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/my/project"))

    def test_show_rejects_description_and_json_together(self) -> None:
        runner = CliRunner()
        result = runner.invoke(component_app, ["show", "--name", "dex", "--description", "--json"])

        self.assertNotEqual(result.exit_code, 0)


class TestComponentLogsCommand(unittest.TestCase):
    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_logs_calls_get_component_logs(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.get_component_logs.return_value = "log line 1\nlog line 2"
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["logs", "--name", "traefik"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.get_component_logs.assert_called_once_with(name="traefik", extra=[])
        self.assertIn("log line 1", result.stdout)

    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_logs_passes_extra_args(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.get_component_logs.return_value = "filtered"
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["logs", "--name", "traefik", "--", "--tail=50"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.get_component_logs.assert_called_once_with(name="traefik", extra=["--tail=50"])

    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_logs_prints_warning_when_empty(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.get_component_logs.return_value = ""
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["logs", "--name", "traefik"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.get_component_logs.assert_called_once_with(name="traefik", extra=[])
        self.assertIn("no logs", result.stdout)


class TestComponentLogsPathCommand(unittest.TestCase):
    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_logs_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.get_component_logs.return_value = "log"
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["logs", "--name", "traefik", "--path", "/my/project"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/my/project"))


class TestComponentRestartCommand(unittest.TestCase):
    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_restart_calls_restart_component(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["restart", "--name", "traefik"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.restart_component.assert_called_once_with(name="traefik")
        self.assertIn("Restarted", result.stdout)

    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_restart_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["restart", "--name", "traefik", "--path", "/my/project"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/my/project"))


class TestComponentReconcileCommand(unittest.TestCase):
    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_reconcile_calls_reconcile_component(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.reconcile_component.return_value = "service/foo configured"
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["reconcile", "--name", "workspace-router-chart"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.reconcile_component.assert_called_once_with(name="workspace-router-chart")
        self.assertIn("Reconciled", result.stdout)

    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_reconcile_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.reconcile_component.return_value = ""
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(
            component_app, ["reconcile", "--name", "workspace-router-chart", "--path", "/my/project"]
        )

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/my/project"))


class TestComponentTriggerCommand(unittest.TestCase):
    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_trigger_calls_trigger_component(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.trigger_component.return_value = "jwt-rotator-manual-20250514"
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["trigger", "--name", "jwt-rotator"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.trigger_component.assert_called_once_with(name="jwt-rotator")
        self.assertIn("jwt-rotator-manual-20250514", result.stdout)

    @patch("jupyter_deploy.handlers.resource.component_handler.ComponentHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_trigger_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.trigger_component.return_value = "jwt-rotator-manual-20250514"
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(component_app, ["trigger", "--name", "jwt-rotator", "--path", "/my/project"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/my/project"))
