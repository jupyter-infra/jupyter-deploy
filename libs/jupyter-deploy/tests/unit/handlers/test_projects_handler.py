import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from jupyter_deploy.enum import StoreType
from jupyter_deploy.exceptions import (
    InvalidStoreTypeError,
    ProjectNotFoundInStoreError,
    StoreTypeNotSpecifiedError,
)
from jupyter_deploy.handlers.projects_handler import ProjectsHandler
from jupyter_deploy.preferences import JupyterDeployPreferencesV1
from jupyter_deploy.provider.store.store_manager import ProjectDetails, ProjectSummary, StoreInfo

_RETRIEVE_PREFERENCES = "jupyter_deploy.handlers.preferences_handler.retrieve_preferences"


class TestProjectsHandler(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_display = Mock()
        self.projects = [
            ProjectSummary(project_id="template-abc123", last_modified=datetime(2026, 3, 1), file_count=10),
            ProjectSummary(project_id="template-xyz789", last_modified=datetime(2026, 3, 5), file_count=15),
        ]

    @patch("jupyter_deploy.handlers.projects_handler.StoreManagerFactory")
    def test_list_projects(self, mock_factory: Mock) -> None:
        mock_store_manager = Mock()
        mock_store_manager.list_projects.return_value = self.projects
        mock_factory.get_manager.return_value = mock_store_manager

        handler = ProjectsHandler(display_manager=self.mock_display, store_type=StoreType.S3_ONLY)
        result = handler.list_projects()

        self.assertEqual(result, self.projects)
        mock_store_manager.list_projects.assert_called_once_with(self.mock_display)
        mock_factory.get_manager.assert_called_once_with(store_type=StoreType.S3_ONLY, store_id=None)

    @patch("jupyter_deploy.handlers.projects_handler.StoreManagerFactory")
    def test_list_projects_with_store_id(self, mock_factory: Mock) -> None:
        mock_store_manager = Mock()
        mock_store_manager.list_projects.return_value = []
        mock_factory.get_manager.return_value = mock_store_manager

        handler = ProjectsHandler(display_manager=self.mock_display, store_type=StoreType.S3_DDB, store_id="my-bucket")
        handler.list_projects()

        mock_factory.get_manager.assert_called_once_with(store_type=StoreType.S3_DDB, store_id="my-bucket")

    @patch("jupyter_deploy.handlers.projects_handler.StoreManagerFactory")
    def test_show_project_delegates_to_get_project(self, mock_factory: Mock) -> None:
        mock_store_manager = Mock()
        expected = ProjectDetails(
            project_id="template-abc123",
            last_modified=datetime(2026, 3, 1),
            file_count=10,
            template_name="base-template",
            template_version="1.0.0",
            engine="terraform",
            variables={"region": "us-east-1", "instance_type": "t3.medium"},
        )
        mock_store_manager.get_project.return_value = expected
        mock_factory.get_manager.return_value = mock_store_manager

        handler = ProjectsHandler(display_manager=self.mock_display, store_type=StoreType.S3_ONLY)
        result = handler.show_project("template-abc123")

        self.assertEqual(result, expected)
        self.assertEqual(result.template_name, "base-template")
        self.assertEqual(result.variables, {"region": "us-east-1", "instance_type": "t3.medium"})
        mock_store_manager.get_project.assert_called_once_with("template-abc123", self.mock_display)

    @patch("jupyter_deploy.handlers.projects_handler.StoreManagerFactory")
    def test_show_project_not_found(self, mock_factory: Mock) -> None:
        mock_store_manager = Mock()
        mock_store_manager.get_project.side_effect = ProjectNotFoundInStoreError("nonexistent-project")
        mock_factory.get_manager.return_value = mock_store_manager

        handler = ProjectsHandler(display_manager=self.mock_display, store_type=StoreType.S3_ONLY)

        with self.assertRaises(ProjectNotFoundInStoreError) as ctx:
            handler.show_project("nonexistent-project")

        self.assertEqual(ctx.exception.project_id, "nonexistent-project")

    @patch("jupyter_deploy.handlers.projects_handler.StoreManagerFactory")
    def test_delete_project(self, mock_factory: Mock) -> None:
        mock_store_manager = Mock()
        mock_factory.get_manager.return_value = mock_store_manager

        handler = ProjectsHandler(display_manager=self.mock_display, store_type=StoreType.S3_ONLY)
        handler.delete_project("template-abc123")

        mock_store_manager.delete_project.assert_called_once_with("template-abc123", self.mock_display)

    @patch("jupyter_deploy.handlers.projects_handler.StoreManagerFactory")
    def test_store_id_delegates_to_resolve_store(self, mock_factory: Mock) -> None:
        mock_store_manager = Mock()
        mock_store_manager.resolve_store.return_value = StoreInfo(
            store_type=StoreType.S3_ONLY, store_id="jd-bucket-abc", location="us-east-1"
        )
        mock_factory.get_manager.return_value = mock_store_manager

        handler = ProjectsHandler(display_manager=self.mock_display, store_type=StoreType.S3_ONLY)

        self.assertEqual(handler.store_id, "jd-bucket-abc")
        mock_store_manager.resolve_store.assert_called_once()


class TestProjectsHandlerStoreTypeResolution(unittest.TestCase):
    """The handler resolves the store type so that every consumer gets the same fallback."""

    def setUp(self) -> None:
        self.mock_display = Mock()

    @patch(_RETRIEVE_PREFERENCES)
    @patch("jupyter_deploy.handlers.projects_handler.StoreManagerFactory")
    def test_uses_the_given_store_type(self, mock_factory: Mock, mock_prefs: Mock) -> None:
        ProjectsHandler(display_manager=self.mock_display, store_type=StoreType.S3_ONLY)

        mock_factory.get_manager.assert_called_once_with(store_type=StoreType.S3_ONLY, store_id=None)
        mock_prefs.assert_not_called()

    @patch(_RETRIEVE_PREFERENCES)
    @patch("jupyter_deploy.handlers.projects_handler.StoreManagerFactory")
    def test_falls_back_to_the_preferred_store_type(self, mock_factory: Mock, mock_prefs: Mock) -> None:
        mock_prefs.return_value = JupyterDeployPreferencesV1(default_store_type="s3-ddb")

        handler = ProjectsHandler(display_manager=self.mock_display)

        self.assertEqual(handler.store_type, StoreType.S3_DDB)
        mock_factory.get_manager.assert_called_once_with(store_type=StoreType.S3_DDB, store_id=None)

    @patch(_RETRIEVE_PREFERENCES)
    @patch("jupyter_deploy.handlers.projects_handler.StoreManagerFactory")
    def test_given_store_type_beats_the_preference(self, mock_factory: Mock, mock_prefs: Mock) -> None:
        mock_prefs.return_value = JupyterDeployPreferencesV1(default_store_type="s3-ddb")

        ProjectsHandler(display_manager=self.mock_display, store_type=StoreType.S3_ONLY)

        mock_factory.get_manager.assert_called_once_with(store_type=StoreType.S3_ONLY, store_id=None)

    @patch(_RETRIEVE_PREFERENCES)
    @patch("jupyter_deploy.handlers.projects_handler.StoreManagerFactory")
    def test_raises_when_neither_is_available(self, mock_factory: Mock, mock_prefs: Mock) -> None:
        mock_prefs.return_value = JupyterDeployPreferencesV1()

        with self.assertRaises(StoreTypeNotSpecifiedError) as ctx:
            ProjectsHandler(display_manager=self.mock_display)

        self.assertEqual(ctx.exception.valid_store_types, ["s3-only", "s3-ddb"])
        mock_factory.get_manager.assert_not_called()

    @patch(_RETRIEVE_PREFERENCES)
    @patch("jupyter_deploy.handlers.projects_handler.StoreManagerFactory")
    def test_raises_on_an_unrecognized_preference(self, mock_factory: Mock, mock_prefs: Mock) -> None:
        mock_prefs.return_value = JupyterDeployPreferencesV1(default_store_type="dynamodb")

        with self.assertRaises(InvalidStoreTypeError):
            ProjectsHandler(display_manager=self.mock_display)

        mock_factory.get_manager.assert_not_called()
