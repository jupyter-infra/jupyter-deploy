import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.image_app import image_app
from jupyter_deploy.exceptions import ImageNotFoundError, ImageTagNotFoundError
from jupyter_deploy.handlers.payloads import (
    ImageDetail,
    ImageInfo,
    ImageStatusResult,
    ImageTag,
    ImageVulnerabilitiesResult,
    ImageVulnerability,
)


class TestImageApp(unittest.TestCase):
    def test_help_command(self) -> None:
        self.assertTrue(len(image_app.info.help or "") > 0, "help should not be empty")

        runner = CliRunner()
        result = runner.invoke(image_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        for cmd in ["list", "show", "tags", "vulnerabilities"]:
            self.assertTrue(result.stdout.index(cmd) > 0, f"missing command: {cmd}")

    def test_no_arg_defaults_to_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(image_app, [])

        self.assertIn(result.exit_code, (0, 2))
        self.assertTrue(len(result.stdout) > 0)


class TestImageListCommand(unittest.TestCase):
    def get_mock_image_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_list_images = Mock()
        mock_handler = Mock()

        mock_handler.list_images = mock_list_images
        mock_list_images.return_value = [
            ImageInfo(name="jupyterlab", description="JupyterLab workspace image"),
        ]

        return mock_handler, {
            "list_images": mock_list_images,
        }

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_handler_and_calls_list(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, mock_fns = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["list"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_class.assert_called_once()
        mock_fns["list_images"].assert_called_once()
        self.assertIn("jupyterlab", result.stdout)
        self.assertIn("JupyterLab workspace image", result.stdout)

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_list_json_output(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, _ = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["list", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data[0]["name"], "jupyterlab")

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_list_text_output(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler = Mock()
        mock_handler.list_images.return_value = [
            ImageInfo(name="jupyterlab", description=""),
            ImageInfo(name="worker", description=""),
        ]
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["list", "--text"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("jupyterlab,worker", result.stdout)

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_list_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, _ = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["list", "--path", "/my/project"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/my/project"))

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_handler_raises(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, mock_fns = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_fns["list_images"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["list"])

        self.assertNotEqual(result.exit_code, 0)


class TestImageStatusCommand(unittest.TestCase):
    def get_mock_image_handler(self, status: str = "Available") -> tuple[Mock, dict[str, Mock]]:
        mock_get_status = Mock()
        mock_handler = Mock()
        mock_handler.get_status = mock_get_status
        mock_get_status.return_value = ImageStatusResult(
            name="jupyterlab",
            status=status,
            status_category="healthy" if status == "Available" else "degraded",
            latest_tag="v2",
        )
        return mock_handler, {"get_status": mock_get_status}

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_renders_available_one_liner(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, mock_fns = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["status", "--name", "jupyterlab"])

        self.assertEqual(result.exit_code, 0)
        mock_fns["get_status"].assert_called_once_with("jupyterlab")
        self.assertIn("jupyterlab status:", result.stdout)
        self.assertIn("Available", result.stdout)

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_renders_missing(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, _ = self.get_mock_image_handler(status="Missing")
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["status"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Missing", result.stdout)

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_image_not_found_error(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler = Mock()
        mock_handler.get_status.side_effect = ImageNotFoundError("bad", ["jupyterlab"])
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["status", "--name", "bad"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("bad", result.stdout)
        self.assertIn("jupyterlab", result.stdout)

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_handler_raises(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler = Mock()
        mock_handler.get_status.side_effect = Exception("Test error")
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["status"])

        self.assertNotEqual(result.exit_code, 0)

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_status_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, _ = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["status", "--path", "/my/project"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/my/project"))


class TestImageShowCommand(unittest.TestCase):
    def get_mock_image_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_show_image = Mock()
        mock_handler = Mock()

        mock_handler.show_image = mock_show_image
        mock_show_image.return_value = ImageDetail(
            name="jupyterlab",
            tag="v1",
            repository_uri="123456.dkr.ecr.us-west-2.amazonaws.com/my-app/jupyterlab",
            scanner_type="Inspector Enhanced",
            last_scanned="2026-06-18T16:21:23+00:00",
            scan_status="ACTIVE",
        )

        return mock_handler, {
            "show_image": mock_show_image,
        }

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_handler_and_calls_show(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, mock_fns = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["show", "--name", "jupyterlab"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_class.assert_called_once()
        mock_fns["show_image"].assert_called_once_with("jupyterlab")
        self.assertIn("Inspector Enhanced", result.stdout)
        self.assertIn("ACTIVE", result.stdout)

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_show_passes_none_when_no_name(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, mock_fns = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["show"])

        self.assertEqual(result.exit_code, 0)
        mock_fns["show_image"].assert_called_once_with(None)

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_show_json_output(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, _ = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["show", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["name"], "jupyterlab")
        self.assertEqual(data["scanner_type"], "Inspector Enhanced")

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_show_image_not_found_error(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler = Mock()
        mock_handler.show_image.side_effect = ImageNotFoundError("bad", ["jupyterlab"])
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["show", "--name", "bad"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("bad", result.stdout)
        self.assertIn("jupyterlab", result.stdout)

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_show_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, _ = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["show", "--path", "/test/project/path"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))


class TestImageTagsCommand(unittest.TestCase):
    def get_mock_image_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_list_tags = Mock()
        mock_handler = Mock()

        mock_handler.list_tags = mock_list_tags
        mock_list_tags.return_value = [
            ImageTag(tag="v1", pushed_at="2026-06-18T15:49:18+00:00", digest="sha256:abc123"),
            ImageTag(tag="latest", pushed_at="2026-06-18T15:49:18+00:00", digest="sha256:abc123"),
        ]

        return mock_handler, {
            "list_tags": mock_list_tags,
        }

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_handler_and_calls_tags(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, mock_fns = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["tags"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_class.assert_called_once()
        mock_fns["list_tags"].assert_called_once_with(None)
        self.assertIn("v1", result.stdout)
        self.assertIn("latest", result.stdout)
        self.assertIn("sha256:abc123", result.stdout)

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_tags_text_output(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, _ = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["tags", "--text"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("v1,latest", result.stdout)

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_tags_json_output(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, _ = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["tags", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["tag"], "v1")
        self.assertEqual(data[0]["digest"], "sha256:abc123")

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_tags_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, _ = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["tags", "--path", "/test/project/path"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_handler_raises(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, mock_fns = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_fns["list_tags"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["tags"])

        self.assertNotEqual(result.exit_code, 0)


class TestImageVulnerabilitiesCommand(unittest.TestCase):
    def get_mock_image_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_get_vulnerabilities = Mock()
        mock_handler = Mock()

        mock_handler.get_vulnerabilities = mock_get_vulnerabilities
        mock_get_vulnerabilities.return_value = ImageVulnerabilitiesResult(
            name="jupyterlab",
            tag="v1",
            last_scanned="2026-06-18T16:21:23+00:00",
            scanner_type="Inspector Enhanced",
            critical_count=1,
            high_count=2,
            vulnerabilities=[
                ImageVulnerability(
                    cve="CVE-2026-1234",
                    type="OS",
                    package="openssl",
                    severity="CRITICAL",
                    installed_version="3.0.18",
                    fixed_version="3.0.19",
                    score=8.3,
                    epss_score=0.42,
                ),
                ImageVulnerability(
                    cve="CVE-2026-5678",
                    type="OS",
                    package="perl",
                    severity="HIGH",
                    installed_version="5.36.0",
                    fixed_version="",
                    score=7.5,
                    epss_score=None,
                ),
                ImageVulnerability(
                    cve="CVE-2026-9999",
                    type="NODE",
                    package="curl",
                    severity="HIGH",
                    installed_version="7.88.0",
                    fixed_version="7.88.1",
                    score=6.1,
                    epss_score=0.01,
                ),
            ],
        )

        return mock_handler, {
            "get_vulnerabilities": mock_get_vulnerabilities,
        }

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_handler_and_calls_vulnerabilities(
        self, mock_project_dir: Mock, mock_handler_class: Mock
    ) -> None:
        mock_handler, mock_fns = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["vulnerabilities"], env={"COLUMNS": "200"})

        self.assertEqual(result.exit_code, 0)
        mock_handler_class.assert_called_once()
        mock_fns["get_vulnerabilities"].assert_called_once_with(None, None)
        self.assertIn("1 CRITICAL, 2 HIGH", result.stdout)
        self.assertIn("CVE-2026-1234", result.stdout)
        self.assertIn("openssl", result.stdout)
        self.assertIn("Inspector Enhanced", result.stdout)
        # EPSS column: percentage when present, n/a when absent.
        self.assertIn("42%", result.stdout)
        self.assertIn("n/a", result.stdout)

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_vulnerabilities_passes_tag(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, mock_fns = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["vulnerabilities", "--tag", "v2"])

        self.assertEqual(result.exit_code, 0)
        mock_fns["get_vulnerabilities"].assert_called_once_with(None, "v2")

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_vulnerabilities_no_findings(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler = Mock()
        mock_handler.get_vulnerabilities.return_value = ImageVulnerabilitiesResult(
            name="jupyterlab",
            tag="v1",
            last_scanned="2026-06-18T16:21:23+00:00",
            scanner_type="ECR Basic",
            critical_count=0,
            high_count=0,
            vulnerabilities=[],
        )
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["vulnerabilities"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No HIGH or CRITICAL vulnerabilities", result.stdout)

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_vulnerabilities_json_output(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, _ = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["vulnerabilities", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["image"], "jupyterlab")
        self.assertEqual(data["tag"], "v1")
        self.assertEqual(data["summary"]["critical"], 1)
        self.assertEqual(data["summary"]["high"], 2)
        self.assertEqual(len(data["vulnerabilities"]), 3)
        self.assertEqual(data["vulnerabilities"][0]["cve"], "CVE-2026-1234")

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_vulnerabilities_tag_not_found_error(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler = Mock()
        mock_handler.get_vulnerabilities.side_effect = ImageTagNotFoundError("jupyterlab", "v99")
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["vulnerabilities", "--tag", "v99"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("v99", result.stdout)
        self.assertIn("jupyterlab", result.stdout)

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_vulnerabilities_switches_dir_with_path(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, _ = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["vulnerabilities", "--path", "/test/project/path"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

    @patch("jupyter_deploy.handlers.resource.image_handler.ImageHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_handler_raises(self, mock_project_dir: Mock, mock_handler_class: Mock) -> None:
        mock_handler, mock_fns = self.get_mock_image_handler()
        mock_handler_class.return_value = mock_handler
        mock_fns["get_vulnerabilities"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(image_app, ["vulnerabilities"])

        self.assertNotEqual(result.exit_code, 0)
