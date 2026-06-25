import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.health_app import _format_sub_component, health_app
from jupyter_deploy.enum import StatusCategory
from jupyter_deploy.handlers.payloads import ConnectionResult, HealthLayer, HealthLayerResult


class TestFormatSubComponent(unittest.TestCase):
    def test_empty_renders_dash(self) -> None:
        self.assertEqual(_format_sub_component(""), "-")

    def test_dash_passthrough(self) -> None:
        self.assertEqual(_format_sub_component("-"), "-")

    def test_plain_text_passthrough(self) -> None:
        self.assertEqual(_format_sub_component("1 critical, 1 high"), "1 critical, 1 high")

    def test_empty_json_renders_dash(self) -> None:
        self.assertEqual(_format_sub_component("{}"), "-")

    def test_json_item_formatted(self) -> None:
        self.assertEqual(_format_sub_component('{"name": "pod", "status": "Running"}'), "pod: Running")


class TestHealthApp(unittest.TestCase):
    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_all_layers(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_all.return_value = (
            [
                HealthLayerResult(
                    layer=HealthLayer.CLUSTER,
                    name="AWS EKS cluster",
                    status_category=StatusCategory.HEALTHY,
                    status_text="Active",
                    detail="v1.30",
                ),
                HealthLayerResult(
                    layer=HealthLayer.LOAD_BALANCER,
                    name="AWS NLB",
                    status_category=StatusCategory.HEALTHY,
                    status_text="Active",
                    detail="2/2 targets healthy",
                ),
                HealthLayerResult(
                    layer=HealthLayer.COMPONENTS,
                    name="traefik",
                    status_category=StatusCategory.HEALTHY,
                    status_text="Running",
                    detail="3/3 pods ready",
                ),
            ],
            ConnectionResult(
                status_category=StatusCategory.HEALTHY,
                detail="app.example.com -> 1.2.3.4, status=302",
            ),
        )
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, [])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("cluster", result.stdout)
        self.assertIn("load-balancer", result.stdout)
        self.assertIn("components", result.stdout)
        self.assertIn("EKS", result.stdout)
        self.assertIn("Active", result.stdout)
        self.assertIn("Connection active", result.stdout)
        self.assertIn("app.example.com", result.stdout)

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_json_output(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_all.return_value = (
            [
                HealthLayerResult(
                    layer=HealthLayer.CLUSTER,
                    name="AWS EKS cluster",
                    status_category=StatusCategory.HEALTHY,
                    status_text="Active",
                    detail="v1.30",
                ),
            ],
            ConnectionResult(
                status_category=StatusCategory.HEALTHY,
                detail="app.example.com -> 1.2.3.4, status=302",
            ),
        )
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertIn("layers", data)
        self.assertIn("connection", data)
        self.assertEqual(data["layers"][0]["name"], "AWS EKS cluster")
        self.assertEqual(data["connection"]["status_category"], "healthy")
        self.assertEqual(data["connection"]["detail"], "app.example.com -> 1.2.3.4, status=302")

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_json_skipped_connection(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_all.return_value = (
            [
                HealthLayerResult(
                    layer=HealthLayer.CLUSTER,
                    name="AWS EKS cluster",
                    status_category=StatusCategory.HEALTHY,
                    status_text="Active",
                    detail="v1.30",
                ),
            ],
            ConnectionResult(status_category=StatusCategory.HEALTHY, detail="", skipped=True),
        )
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertTrue(data["connection"]["skipped"])

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_cluster_flag(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_layer.return_value = [
            HealthLayerResult(
                layer=HealthLayer.CLUSTER,
                name="AWS EKS cluster",
                status_category=StatusCategory.HEALTHY,
                status_text="Active",
                detail="v1.30",
            )
        ]
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--cluster"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.check_layer.assert_called_once_with(HealthLayer.CLUSTER)
        self.assertIn("cluster", result.stdout)

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_components_flag(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_layer.return_value = [
            HealthLayerResult(
                layer=HealthLayer.COMPONENTS,
                name="traefik",
                status_category=StatusCategory.HEALTHY,
                status_text="Ready",
                detail="1/1 replicas",
            )
        ]
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--components"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.check_layer.assert_called_once_with(HealthLayer.COMPONENTS)
        self.assertIn("components", result.stdout)

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_load_balancer_flag(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_layer.return_value = [
            HealthLayerResult(
                layer=HealthLayer.LOAD_BALANCER,
                name="AWS NLB",
                status_category=StatusCategory.HEALTHY,
                status_text="Active",
                detail="internet-facing",
            )
        ]
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--load-balancer"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.check_layer.assert_called_once_with(HealthLayer.LOAD_BALANCER)
        self.assertIn("load-balancer", result.stdout)

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_images_flag(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_layer.return_value = [
            HealthLayerResult(
                layer=HealthLayer.IMAGES,
                name="jupyterlab",
                status_category=StatusCategory.HEALTHY,
                status_text="Available",
                detail="v1",
                sub_component="1 critical, 1 high",
            )
        ]
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--images"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.check_layer.assert_called_once_with(HealthLayer.IMAGES)
        self.assertIn("images", result.stdout)
        self.assertIn("Available", result.stdout)
        # A non-zero vulnerability count surfaces the drill-down hint.
        self.assertIn("Hint:", result.stdout)
        self.assertIn("jd image vulnerabilities --name jupyterlab --tag v1", result.stdout)

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_images_clean_has_no_hint(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_layer.return_value = [
            HealthLayerResult(
                layer=HealthLayer.IMAGES,
                name="jupyterlab",
                status_category=StatusCategory.HEALTHY,
                status_text="Available",
                detail="v1",
                sub_component="",
            )
        ]
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--images"])

        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("Hint:", result.stdout)

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_renders_custom_resource_components(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_all.return_value = (
            [
                HealthLayerResult(
                    layer=HealthLayer.COMPONENTS,
                    name="workspace-crd",
                    status_category=StatusCategory.HEALTHY,
                    status_text="Present",
                    detail="v1alpha1",
                ),
                HealthLayerResult(
                    layer=HealthLayer.COMPONENTS,
                    name="oauth-access-strategy",
                    status_category=StatusCategory.HEALTHY,
                    status_text="Present",
                    detail="jupyter-k8s-shared",
                    sub_component="access-resources: 2",
                ),
                HealthLayerResult(
                    layer=HealthLayer.COMPONENTS,
                    name="jupyterlab-template",
                    status_category=StatusCategory.HEALTHY,
                    status_text="Present",
                    detail="jupyter-k8s-shared",
                    sub_component="access-strategy: oauth-access-strategy",
                ),
                HealthLayerResult(
                    layer=HealthLayer.IMAGES,
                    name="jupyterlab",
                    status_category=StatusCategory.HEALTHY,
                    status_text="Available",
                    detail="v1",
                    sub_component="1 critical, 1 high",
                ),
            ],
            ConnectionResult(status_category=StatusCategory.HEALTHY, detail="", skipped=True),
        )
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, [], env={"COLUMNS": "200"})

        self.assertEqual(result.exit_code, 0)
        for token in [
            "workspace-crd",
            "v1alpha1",
            "oauth-access-strategy",
            "access-resources: 2",
            "jupyterlab-template",
            "Present",
            "Available",
        ]:
            self.assertIn(token, result.stdout)
        self.assertIn("Hint:", result.stdout)

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_connection_flag(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_connection.return_value = ConnectionResult(
            status_category=StatusCategory.HEALTHY,
            detail="app.example.com -> 1.2.3.4, status=302",
        )
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--connection"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.check_connection.assert_called_once()
        self.assertIn("Connection active", result.stdout)
        self.assertIn("app.example.com", result.stdout)

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_connection_flag_json(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_connection.return_value = ConnectionResult(
            status_category=StatusCategory.DEGRADED,
            detail="app.example.com does not resolve",
        )
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--connection", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertIn("connection", data)
        self.assertEqual(data["layers"], [])
        self.assertEqual(data["connection"]["status_category"], "degraded")

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_connection_failed(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_connection.return_value = ConnectionResult(
            status_category=StatusCategory.DEGRADED,
            detail="app.example.com does not resolve",
        )
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--connection"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Connection failed", result.stdout)
        self.assertIn("does not resolve", result.stdout)

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_shows_skipped(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_all.return_value = (
            [
                HealthLayerResult(
                    layer=HealthLayer.CLUSTER,
                    name="",
                    status_category=StatusCategory.HEALTHY,
                    status_text="",
                    detail="",
                    skipped=True,
                ),
            ],
            ConnectionResult(status_category=StatusCategory.HEALTHY, detail="", skipped=True),
        )
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, [])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("skipped", result.stdout)

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_shows_failure(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_all.return_value = (
            [
                HealthLayerResult(
                    layer=HealthLayer.LOAD_BALANCER,
                    name="AWS NLB",
                    status_category=StatusCategory.DEGRADED,
                    status_text="Not Found",
                    detail="no load balancer found",
                ),
            ],
            ConnectionResult(status_category=StatusCategory.HEALTHY, detail="", skipped=True),
        )
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, [])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Not Found", result.stdout)
        self.assertIn("no load balancer found", result.stdout)

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_all.return_value = (
            [],
            ConnectionResult(status_category=StatusCategory.HEALTHY, detail="", skipped=True),
        )
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--path", "/my/project"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/my/project"))

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_multiple_layer_flags(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_layer.side_effect = [
            [
                HealthLayerResult(
                    layer=HealthLayer.CLUSTER,
                    name="AWS EKS cluster",
                    status_category=StatusCategory.HEALTHY,
                    status_text="Active",
                    detail="v1.30",
                )
            ],
            [
                HealthLayerResult(
                    layer=HealthLayer.LOAD_BALANCER,
                    name="AWS NLB",
                    status_category=StatusCategory.HEALTHY,
                    status_text="Active",
                    detail="internet-facing",
                )
            ],
        ]
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--cluster", "--load-balancer"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(mock_handler.check_layer.call_count, 2)
        mock_handler.check_layer.assert_any_call(HealthLayer.CLUSTER)
        mock_handler.check_layer.assert_any_call(HealthLayer.LOAD_BALANCER)
        mock_handler.check_all.assert_not_called()
        mock_handler.check_connection.assert_not_called()
        self.assertIn("cluster", result.stdout)
        self.assertIn("load-balancer", result.stdout)

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_multiple_layer_flags_json(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_layer.side_effect = [
            [
                HealthLayerResult(
                    layer=HealthLayer.CLUSTER,
                    name="AWS EKS cluster",
                    status_category=StatusCategory.HEALTHY,
                    status_text="Active",
                    detail="v1.30",
                )
            ],
            [
                HealthLayerResult(
                    layer=HealthLayer.COMPONENTS,
                    name="traefik",
                    status_category=StatusCategory.HEALTHY,
                    status_text="Running",
                    detail="3/3 pods ready",
                )
            ],
        ]
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--cluster", "--components", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["layers"]), 2)
        self.assertEqual(data["layers"][0]["layer"], "cluster")
        self.assertEqual(data["layers"][1]["layer"], "components")
        self.assertNotIn("connection", data)

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_layer_and_connection_flags(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_layer.return_value = [
            HealthLayerResult(
                layer=HealthLayer.CLUSTER,
                name="AWS EKS cluster",
                status_category=StatusCategory.HEALTHY,
                status_text="Active",
                detail="v1.30",
            )
        ]
        mock_handler.check_connection.return_value = ConnectionResult(
            status_category=StatusCategory.HEALTHY,
            detail="app.example.com -> 1.2.3.4, status=302",
        )
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--cluster", "--connection"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.check_layer.assert_called_once_with(HealthLayer.CLUSTER)
        mock_handler.check_connection.assert_called_once()
        mock_handler.check_all.assert_not_called()
        self.assertIn("cluster", result.stdout)
        self.assertIn("Connection active", result.stdout)

    @patch("jupyter_deploy.handlers.health_handler.HealthHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_health_layer_and_connection_flags_json(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_project_dir.return_value.__enter__ = Mock(return_value=None)
        mock_project_dir.return_value.__exit__ = Mock(return_value=None)
        mock_handler: Mock = Mock()
        mock_handler.check_layer.return_value = [
            HealthLayerResult(
                layer=HealthLayer.CLUSTER,
                name="AWS EKS cluster",
                status_category=StatusCategory.HEALTHY,
                status_text="Active",
                detail="v1.30",
            )
        ]
        mock_handler.check_connection.return_value = ConnectionResult(
            status_category=StatusCategory.DEGRADED,
            detail="app.example.com does not resolve",
        )
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(health_app, ["--cluster", "--connection", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["layers"]), 1)
        self.assertEqual(data["layers"][0]["layer"], "cluster")
        self.assertIn("connection", data)
        self.assertEqual(data["connection"]["status_category"], "degraded")
