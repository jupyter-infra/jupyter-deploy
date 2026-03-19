import unittest
from datetime import datetime
from unittest.mock import Mock, PropertyMock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.app import runner as app_runner
from jupyter_deploy.enum import StoreType
from jupyter_deploy.exceptions import ProjectNotFoundInStoreError, ProjectStoreNotFoundError
from jupyter_deploy.provider.store.store_manager import ProjectDetails, ProjectSummary

_HANDLER = "jupyter_deploy.cli.projects_app.ProjectsHandler"


def _mock_handler_with_projects(projects: list[ProjectSummary]) -> Mock:
    mock_handler = Mock()
    type(mock_handler).store_id = PropertyMock(return_value="jd-bucket-abc")
    mock_handler.list_projects.return_value = projects
    return mock_handler


class TestProjectsListCommand(unittest.TestCase):
    @patch(_HANDLER)
    def test_list_projects_shows_table(self, mock_handler_cls: Mock) -> None:
        projects = [
            ProjectSummary(project_id="tpl-abc123", last_modified=datetime(2026, 3, 1, 12, 0), file_count=10),
            ProjectSummary(project_id="tpl-xyz789", last_modified=datetime(2026, 3, 5, 14, 30), file_count=15),
        ]
        mock_handler_cls.return_value = _mock_handler_with_projects(projects)

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["projects", "list", "--store-type", "s3-only"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("tpl-abc123", result.output)
        self.assertIn("tpl-xyz789", result.output)
        self.assertIn("jd-bucket-abc", result.output)
        call_kwargs = mock_handler_cls.call_args.kwargs
        self.assertEqual(call_kwargs["store_type"], StoreType.S3_ONLY)
        self.assertIsNone(call_kwargs["store_id"])

    @patch(_HANDLER)
    def test_list_projects_with_store_id(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = _mock_handler_with_projects([])

        runner = CliRunner()
        result = runner.invoke(
            app_runner.app, ["projects", "list", "--store-type", "s3-ddb", "--store-id", "my-bucket"]
        )

        self.assertEqual(result.exit_code, 0)
        call_kwargs = mock_handler_cls.call_args.kwargs
        self.assertEqual(call_kwargs["store_type"], StoreType.S3_DDB)
        self.assertEqual(call_kwargs["store_id"], "my-bucket")

    @patch(_HANDLER)
    def test_list_projects_empty(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = _mock_handler_with_projects([])

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["projects", "list", "--store-type", "s3-only"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No projects found", result.output)
        self.assertIn("jd-bucket-abc", result.output)

    @patch(_HANDLER)
    def test_list_projects_empty_text_mode(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = _mock_handler_with_projects([])

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["projects", "list", "--store-type", "s3-only", "--text"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output.strip(), "[]")

    @patch(_HANDLER)
    def test_list_projects_text_mode_shows_ids_only(self, mock_handler_cls: Mock) -> None:
        projects = [
            ProjectSummary(project_id="tpl-abc123", last_modified=datetime(2026, 3, 1, 12, 0), file_count=10),
            ProjectSummary(project_id="tpl-xyz789", last_modified=datetime(2026, 3, 5, 14, 30), file_count=15),
        ]
        mock_handler_cls.return_value = _mock_handler_with_projects(projects)

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["projects", "list", "--store-type", "s3-only", "--text"])

        self.assertEqual(result.exit_code, 0)
        lines = result.output.strip().split("\n")
        self.assertEqual(lines, ["tpl-abc123", "tpl-xyz789"])

    @patch(_HANDLER)
    def test_list_projects_respects_n_flag(self, mock_handler_cls: Mock) -> None:
        projects = [
            ProjectSummary(project_id=f"tpl-{i}", last_modified=datetime(2026, 3, 1), file_count=i) for i in range(5)
        ]
        mock_handler_cls.return_value = _mock_handler_with_projects(projects)

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["projects", "list", "--store-type", "s3-only", "-n", "2", "--text"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("tpl-0", result.output)
        self.assertIn("tpl-1", result.output)
        self.assertNotIn("tpl-2", result.output)

    @patch(_HANDLER)
    def test_list_projects_respects_skip_flag(self, mock_handler_cls: Mock) -> None:
        projects = [
            ProjectSummary(project_id=f"tpl-{i}", last_modified=datetime(2026, 3, 1), file_count=i) for i in range(5)
        ]
        mock_handler_cls.return_value = _mock_handler_with_projects(projects)

        runner = CliRunner()
        result = runner.invoke(
            app_runner.app, ["projects", "list", "--store-type", "s3-only", "-s", "2", "-n", "2", "--text"]
        )

        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("tpl-0", result.output)
        self.assertNotIn("tpl-1", result.output)
        self.assertIn("tpl-2", result.output)
        self.assertIn("tpl-3", result.output)
        self.assertNotIn("tpl-4", result.output)

    @patch(_HANDLER)
    def test_list_projects_store_not_found(self, mock_handler_cls: Mock) -> None:
        mock_handler = Mock()
        mock_handler.list_projects.side_effect = ProjectStoreNotFoundError("No store found")
        mock_handler_cls.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["projects", "list", "--store-type", "s3-only"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("No store found", result.output)

    def test_list_projects_missing_store_type(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["projects", "list"])

        self.assertNotEqual(result.exit_code, 0)


class TestProjectsShowCommand(unittest.TestCase):
    @patch(_HANDLER)
    def test_show_project(self, mock_handler_cls: Mock) -> None:
        mock_handler = Mock()
        type(mock_handler).store_id = PropertyMock(return_value="jd-bucket-abc")
        mock_handler.show_project.return_value = ProjectDetails(
            project_id="tpl-abc123",
            last_modified=datetime(2026, 3, 1, 12, 0),
            file_count=10,
            template_name="base-template",
            template_version="1.2.0",
            engine="terraform",
            variables={"region": "us-east-1", "instance_type": "t3.medium"},
        )
        mock_handler_cls.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["projects", "show", "tpl-abc123", "--store-type", "s3-only"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("tpl-abc123", result.output)
        self.assertIn("jd-bucket-abc", result.output)
        self.assertIn("10", result.output)
        self.assertIn("base-template", result.output)
        self.assertIn("1.2.0", result.output)
        self.assertIn("terraform", result.output)
        self.assertIn("region", result.output)
        self.assertIn("us-east-1", result.output)
        self.assertIn("instance_type", result.output)
        self.assertIn("t3.medium", result.output)

    @patch(_HANDLER)
    def test_show_project_text_mode(self, mock_handler_cls: Mock) -> None:
        mock_handler = Mock()
        type(mock_handler).store_id = PropertyMock(return_value="jd-bucket-abc")
        mock_handler.show_project.return_value = ProjectDetails(
            project_id="tpl-abc123",
            last_modified=datetime(2026, 3, 1, 12, 0),
            file_count=10,
            template_name="base-template",
            template_version="1.2.0",
            engine="terraform",
            variables={"region": "us-east-1", "secret_key": "****"},
        )
        mock_handler_cls.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["projects", "show", "tpl-abc123", "--store-type", "s3-only", "--text"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("project-id: tpl-abc123", result.output)
        self.assertIn("store-id: jd-bucket-abc", result.output)
        self.assertIn("template-name: base-template", result.output)
        self.assertIn("template-version: 1.2.0", result.output)
        self.assertIn("engine: terraform", result.output)
        self.assertIn("file-count: 10", result.output)
        self.assertIn("var:region: us-east-1", result.output)
        self.assertIn("var:secret_key: ****", result.output)

    @patch(_HANDLER)
    def test_show_project_text_mode_none_fields(self, mock_handler_cls: Mock) -> None:
        mock_handler = Mock()
        type(mock_handler).store_id = PropertyMock(return_value="jd-bucket-abc")
        mock_handler.show_project.return_value = ProjectDetails(
            project_id="tpl-abc123", last_modified=datetime(2026, 3, 1, 12, 0), file_count=10
        )
        mock_handler_cls.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["projects", "show", "tpl-abc123", "--store-type", "s3-only", "--text"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("template-name: N/A", result.output)
        self.assertIn("template-version: N/A", result.output)
        self.assertIn("engine: N/A", result.output)

    @patch(_HANDLER)
    def test_show_project_not_found(self, mock_handler_cls: Mock) -> None:
        mock_handler = Mock()
        mock_handler.show_project.side_effect = ProjectNotFoundInStoreError(
            "nonexistent", store_type="s3-only", store_id="my-bucket"
        )
        mock_handler_cls.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["projects", "show", "nonexistent", "--store-type", "s3-only"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("nonexistent", result.output)
        self.assertIn("jd projects list --store-type s3-only --store-id my-bucket", result.output)


class TestProjectsDeleteCommand(unittest.TestCase):
    @patch(_HANDLER)
    def test_delete_project_with_yes_flag(self, mock_handler_cls: Mock) -> None:
        mock_handler = Mock()
        type(mock_handler).store_id = PropertyMock(return_value="jd-bucket-abc")
        mock_handler_cls.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["projects", "delete", "tpl-abc123", "--store-type", "s3-only", "-y"])

        self.assertEqual(result.exit_code, 0)
        mock_handler.delete_project.assert_called_once_with("tpl-abc123")
        self.assertIn("deleted", result.output)
        self.assertIn("jd-bucket-abc", result.output)

    @patch(_HANDLER)
    def test_delete_project_with_confirmation(self, mock_handler_cls: Mock) -> None:
        mock_handler = Mock()
        type(mock_handler).store_id = PropertyMock(return_value="jd-bucket-abc")
        mock_handler_cls.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(
            app_runner.app, ["projects", "delete", "tpl-abc123", "--store-type", "s3-only"], input="y\n"
        )

        self.assertEqual(result.exit_code, 0)
        mock_handler.delete_project.assert_called_once_with("tpl-abc123")

    @patch(_HANDLER)
    def test_delete_project_aborted(self, mock_handler_cls: Mock) -> None:
        mock_handler = Mock()
        mock_handler_cls.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(
            app_runner.app, ["projects", "delete", "tpl-abc123", "--store-type", "s3-only"], input="n\n"
        )

        self.assertEqual(result.exit_code, 0)
        mock_handler.delete_project.assert_not_called()
        self.assertIn("Aborted", result.output)

    @patch(_HANDLER)
    def test_delete_project_store_not_found(self, mock_handler_cls: Mock) -> None:
        mock_handler = Mock()
        mock_handler.delete_project.side_effect = ProjectStoreNotFoundError("No store found")
        mock_handler_cls.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["projects", "delete", "tpl-abc123", "--store-type", "s3-only", "-y"])

        self.assertNotEqual(result.exit_code, 0)
