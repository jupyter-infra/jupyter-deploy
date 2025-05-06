import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.project.project_handler import ProjectHandler
from jupyter_deploy.presets.path import PRESET_ROOT_PATH


class TestProjectHandler(unittest.TestCase):
    """Test class for ProjectHandler class."""

    @patch("jupyter_deploy.fs_utils.get_default_project_path")
    def test_project_handler_no_project_path(self, mock_get_default_project_path: Mock):
        """Test that ProjectHandler uses default project path when no path is provided."""
        # Setup
        mock_default_path = Path("/default/project/path")
        mock_get_default_project_path.return_value = mock_default_path

        # Execute
        handler = ProjectHandler(project_dir=None)

        # Assert
        self.assertEqual(handler.project_path, mock_default_path)
        mock_get_default_project_path.assert_called_once()
        self.assertEqual(handler.engine, EngineType.TERRAFORM)
        self.assertEqual(handler.source_path, Path(PRESET_ROOT_PATH / "terraform"))

    def test_project_handler_with_project_path(self):
        """Test that ProjectHandler uses provided project path."""
        # Setup
        project_dir = "/custom/project/path"
        expected_path = Path(project_dir)

        # Execute
        handler = ProjectHandler(project_dir=project_dir)

        # Assert
        self.assertEqual(handler.project_path, expected_path)
        self.assertEqual(handler.engine, EngineType.TERRAFORM)
        self.assertEqual(handler.source_path, Path(PRESET_ROOT_PATH / "terraform"))

    def test__find_template_path_constructs_path(self):
        """Test that _find_template_path correctly constructs the template path."""
        # Setup
        handler = ProjectHandler(project_dir=None)
        template_name = "aws:ec2:tls-via-ngrok"
        expected_path = Path(PRESET_ROOT_PATH / "terraform" / "aws" / "ec2" / "tls-via-ngrok")

        # Execute
        result = handler._find_template_path(template_name)

        # Assert
        self.assertEqual(result, expected_path)

    def test__find_template_path_empty_template(self):
        """Test that _find_template_path handles empty template name."""
        # Setup
        handler = ProjectHandler(project_dir=None)
        template_name = ""
        expected_path = Path(PRESET_ROOT_PATH / "terraform")

        # Execute
        result = handler._find_template_path(template_name)

        # Assert
        self.assertEqual(result, expected_path)

    @patch("pathlib.Path.exists")
    @patch("jupyter_deploy.fs_utils.is_empty_dir")
    def test_may_export_to_project_path_when_exists_return_false(self, mock_is_empty_dir: Mock, mock_exists: Mock):
        """Test that may_export_to_project_path returns False when project path exists and is not empty."""
        # Setup
        handler = ProjectHandler(project_dir="/test/path")
        mock_exists.return_value = True
        mock_is_empty_dir.return_value = False

        # Execute
        result = handler.may_export_to_project_path()

        # Assert
        self.assertFalse(result)
        mock_exists.assert_called_once()
        mock_is_empty_dir.assert_called_once_with(handler.project_path)

    @patch("pathlib.Path.exists")
    @patch("jupyter_deploy.fs_utils.is_empty_dir")
    def test_may_export_to_project_path_when_not_empty_dir_return_false(
        self, mock_is_empty_dir: Mock, mock_exists: Mock
    ):
        """Test that may_export_to_project_path returns False when project path is not an empty directory."""
        # Setup
        handler = ProjectHandler(project_dir="/test/path")
        mock_exists.return_value = True
        mock_is_empty_dir.return_value = False

        # Execute
        result = handler.may_export_to_project_path()

        # Assert
        self.assertFalse(result)
        mock_exists.assert_called_once()
        mock_is_empty_dir.assert_called_once_with(handler.project_path)

    @patch("pathlib.Path.exists")
    @patch("jupyter_deploy.fs_utils.is_empty_dir")
    def test_may_export_to_project_path_when_empty_dir_return_true(self, mock_is_empty_dir: Mock, mock_exists: Mock):
        """Test that may_export_to_project_path returns True when project path is an empty directory."""
        # Setup
        handler = ProjectHandler(project_dir="/test/path")
        mock_exists.return_value = True
        mock_is_empty_dir.return_value = True

        # Execute
        result = handler.may_export_to_project_path()

        # Assert
        self.assertTrue(result)
        mock_exists.assert_called_once()
        mock_is_empty_dir.assert_called_once_with(handler.project_path)

    @patch("jupyter_deploy.fs_utils.safe_clean_directory")
    def test_clear_project_path_calls_util(self, mock_safe_clean_directory: Mock):
        """Test that clear_project_path calls the appropriate utility function."""
        # Setup
        handler = ProjectHandler(project_dir="/test/path")

        # Execute
        handler.clear_project_path()

        # Assert
        mock_safe_clean_directory.assert_called_once_with(handler.project_path)

    @patch("jupyter_deploy.fs_utils.safe_clean_directory")
    def test_clear_project_path_raises_exception_if_util_fails(self, mock_safe_clean_directory: Mock):
        """Test that clear_project_path surfaces underlying util exception."""
        # Setup
        handler = ProjectHandler(project_dir="/test/path")
        mock_safe_clean_directory.side_effect = RuntimeError("Computer says no")

        # Execute & assert
        with self.assertRaisesRegex(RuntimeError, "Computer says no"):
            handler.clear_project_path()

    @patch("jupyter_deploy.fs_utils.safe_copy_tree")
    def test_setup_calls_util(self, mock_safe_copy_tree: Mock):
        """Test that setup calls the appropriate utility function."""
        # Setup
        handler = ProjectHandler(project_dir="/test/path")

        # Execute
        handler.setup()

        # Assert
        mock_safe_copy_tree.assert_called_once_with(handler.source_path, handler.project_path)

    @patch("jupyter_deploy.fs_utils.safe_copy_tree")
    def test_setup_raises_exception_when_util_fails(self, mock_safe_copy_tree: Mock):
        """Test that setup surfaces underlying util exception."""
        # Setup
        handler = ProjectHandler(project_dir="/test/path")
        mock_safe_copy_tree.side_effect = OSError("Access denied")

        # Execute & Assert
        with self.assertRaisesRegex(OSError, "Access denied"):
            handler.setup()
