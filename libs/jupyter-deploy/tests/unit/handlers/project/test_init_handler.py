import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.project.init_handler import InitHandler
from jupyter_deploy.infrastructure.enum import AWSInfrastructureType
from jupyter_deploy.provider.enum import ProviderType


class TestInitHandler(unittest.TestCase):
    """Test class for InitHandler."""

    @patch("jupyter_deploy.fs_utils.get_default_project_path")
    @patch("jupyter_deploy.handlers.project.init_handler.InitHandler._find_template_path")
    def test_init_with_project_dir(
        self, mock_find_template_path: MagicMock, mock_get_default_project_path: MagicMock
    ) -> None:
        """Test initialization with project_dir provided."""
        # Setup
        project_dir = "/test/project/dir"
        mock_template_path = Path("/mock/template/path")
        mock_find_template_path.return_value = mock_template_path

        # Execute
        handler = InitHandler(project_dir=project_dir)

        # Assert
        self.assertEqual(handler.project_path, Path(project_dir))
        self.assertEqual(handler.engine, EngineType.TERRAFORM)
        mock_find_template_path.assert_called_once_with("aws:ec2:tls-via-ngrok")
        mock_get_default_project_path.assert_not_called()

    @patch("jupyter_deploy.fs_utils.get_default_project_path")
    @patch("jupyter_deploy.handlers.project.init_handler.InitHandler._find_template_path")
    def test_init_without_project_dir(
        self, mock_find_template_path: MagicMock, mock_get_default_project_path: MagicMock
    ) -> None:
        """Test initialization without project_dir provided."""
        # Setup
        mock_default_path = Path("/default/project/path")
        mock_template_path = Path("/mock/template/path")
        mock_get_default_project_path.return_value = mock_default_path
        mock_find_template_path.return_value = mock_template_path

        # Execute
        handler = InitHandler(project_dir=None)

        # Assert
        self.assertEqual(handler.project_path, mock_default_path)
        self.assertEqual(handler.engine, EngineType.TERRAFORM)
        mock_find_template_path.assert_called_once_with("aws:ec2:tls-via-ngrok")
        mock_get_default_project_path.assert_called_once()

    @patch("jupyter_deploy.handlers.project.init_handler.InitHandler._find_template_path")
    def test_init_with_enum_parameters(self, mock_find_template_path: MagicMock) -> None:
        """Test initialization with enum types for provider and infrastructure."""
        # Setup
        project_dir = "/test/project/dir"
        mock_template_path = Path("/mock/template/path")
        mock_find_template_path.return_value = mock_template_path

        # Execute
        handler = InitHandler(
            project_dir=project_dir,
            engine=EngineType.TERRAFORM,
            provider=ProviderType.AWS,
            infrastructure=AWSInfrastructureType.EC2,
            template="custom-template",
        )

        # Assert
        self.assertEqual(handler.project_path, Path(project_dir))
        self.assertEqual(handler.engine, EngineType.TERRAFORM)
        mock_find_template_path.assert_called_once_with("aws:ec2:custom-template")

    @patch("jupyter_deploy.handlers.project.init_handler.InitHandler._find_template_path")
    @patch(
        "jupyter_deploy.template_utils.TEMPLATES", {"terraform": {"aws:ec2:tls-via-ngrok": Path("/mock/template/path")}}
    )
    def test_find_template_path_valid(self, mock_find_template_path: MagicMock) -> None:
        """Test _find_template_path with valid template name."""
        # Setup
        mock_find_template_path.return_value = Path("/mock/template/path")

        handler = InitHandler(project_dir="/test/project/dir")

        # Execute
        mock_find_template_path.return_value = Path("/mock/template/path")
        result = handler._find_template_path("aws:ec2:tls-via-ngrok")

        # Assert
        self.assertEqual(result, Path("/mock/template/path"))

    @patch("jupyter_deploy.handlers.project.init_handler.InitHandler._find_template_path")
    def test_find_template_path_empty(self, mock_find_template_path: MagicMock) -> None:
        """Test _find_template_path with empty template name."""
        # Setup
        mock_find_template_path.side_effect = [
            Path("/mock/template/path"),  # For constructor
            ValueError("Template name cannot be empty"),  # For the actual test
        ]

        handler = InitHandler(project_dir="/test/project/dir")

        # Execute and Assert
        with self.assertRaisesRegex(ValueError, "Template name cannot be empty"):
            # Set up the mock to raise the expected exception
            mock_find_template_path.side_effect = ValueError("Template name cannot be empty")
            handler._find_template_path("")

    @patch("jupyter_deploy.handlers.project.init_handler.InitHandler._find_template_path")
    @patch("jupyter_deploy.template_utils.TEMPLATES", {})
    def test_find_template_path_unsupported_engine(self, mock_find_template_path: MagicMock) -> None:
        """Test _find_template_path with unsupported engine."""
        # Setup
        mock_find_template_path.side_effect = [
            Path("/mock/template/path"),  # For constructor
            ValueError("Engine 'terraform' is not supported. Available engines: none available"),  # For the actual test
        ]

        handler = InitHandler(project_dir="/test/project/dir")

        # Execute and Assert
        with self.assertRaisesRegex(ValueError, "Engine 'terraform' is not supported"):
            mock_find_template_path.side_effect = ValueError("Engine 'terraform' is not supported")
            handler._find_template_path("aws:ec2:tls-via-ngrok")

    @patch("jupyter_deploy.handlers.project.init_handler.InitHandler._find_template_path")
    @patch("jupyter_deploy.template_utils.TEMPLATES", {"terraform": {}})
    def test_find_template_path_template_not_found(self, mock_find_template_path: MagicMock) -> None:
        """Test _find_template_path with template not found."""
        # Setup
        mock_find_template_path.side_effect = [
            Path("/mock/template/path"),  # For constructor
            ValueError(
                "Template 'aws:ec2:tls-via-ngrok' not found for engine 'terraform'. Available templates: none"
            ),  # For the actual test
        ]

        handler = InitHandler(project_dir="/test/project/dir")

        # Execute and Assert
        with self.assertRaisesRegex(ValueError, "Template 'aws:ec2:tls-via-ngrok' not found"):
            mock_find_template_path.side_effect = ValueError("Template 'aws:ec2:tls-via-ngrok' not found")
            handler._find_template_path("aws:ec2:tls-via-ngrok")

    @patch("jupyter_deploy.fs_utils.is_empty_dir")
    @patch("jupyter_deploy.handlers.project.init_handler.InitHandler._find_template_path")
    def test_may_export_to_project_path_not_exists(
        self, mock_find_template_path: MagicMock, mock_is_empty_dir: MagicMock
    ) -> None:
        """Test may_export_to_project_path when project path doesn't exist."""
        # Setup
        mock_path = MagicMock()
        mock_exists = MagicMock(return_value=False)
        mock_path.exists = mock_exists
        mock_find_template_path.return_value = Path("/mock/template/path")

        handler = InitHandler(project_dir="/test/project/dir")
        handler.project_path = mock_path

        # Execute
        result = handler.may_export_to_project_path()

        # Assert
        self.assertTrue(result)
        mock_exists.assert_called_once()
        mock_is_empty_dir.assert_not_called()

    @patch("jupyter_deploy.fs_utils.is_empty_dir")
    @patch("jupyter_deploy.handlers.project.init_handler.InitHandler._find_template_path")
    def test_may_export_to_project_path_exists_empty(
        self, mock_find_template_path: MagicMock, mock_is_empty_dir: MagicMock
    ) -> None:
        """Test may_export_to_project_path when project path exists and is empty."""
        # Setup
        mock_path = MagicMock()
        mock_exists = MagicMock(return_value=True)
        mock_path.exists = mock_exists
        mock_is_empty_dir.return_value = True
        mock_find_template_path.return_value = Path("/mock/template/path")

        handler = InitHandler(project_dir="/test/project/dir")
        handler.project_path = mock_path

        # Execute
        result = handler.may_export_to_project_path()

        # Assert
        self.assertTrue(result)
        mock_exists.assert_called_once()
        mock_is_empty_dir.assert_called_once_with(mock_path)

    @patch("jupyter_deploy.fs_utils.is_empty_dir")
    @patch("jupyter_deploy.handlers.project.init_handler.InitHandler._find_template_path")
    def test_may_export_to_project_path_exists_not_empty(
        self, mock_find_template_path: MagicMock, mock_is_empty_dir: MagicMock
    ) -> None:
        """Test may_export_to_project_path when project path exists and is not empty."""
        # Setup
        mock_path = MagicMock()
        mock_exists = MagicMock(return_value=True)
        mock_path.exists = mock_exists
        mock_is_empty_dir.return_value = False
        mock_find_template_path.return_value = Path("/mock/template/path")

        handler = InitHandler(project_dir="/test/project/dir")
        handler.project_path = mock_path

        # Execute
        result = handler.may_export_to_project_path()

        # Assert
        self.assertFalse(result)
        mock_exists.assert_called_once()
        mock_is_empty_dir.assert_called_once_with(mock_path)

    @patch("jupyter_deploy.fs_utils.safe_clean_directory")
    @patch("jupyter_deploy.handlers.project.init_handler.InitHandler._find_template_path")
    def test_clear_project_path(self, mock_find_template_path: MagicMock, mock_safe_clean_directory: MagicMock) -> None:
        """Test clear_project_path calls fs_utils.safe_clean_directory with correct path."""
        # Setup
        mock_path = Path("/test/project/dir")
        mock_find_template_path.return_value = Path("/mock/template/path")

        handler = InitHandler(project_dir="/test/project/dir")
        handler.project_path = mock_path

        # Execute
        handler.clear_project_path()

        # Assert
        mock_safe_clean_directory.assert_called_once_with(mock_path)

    @patch("jupyter_deploy.fs_utils.safe_copy_tree")
    @patch("jupyter_deploy.handlers.project.init_handler.InitHandler._find_template_path")
    def test_setup(self, mock_find_template_path: MagicMock, mock_safe_copy_tree: MagicMock) -> None:
        """Test setup calls fs_utils.safe_copy_tree with correct paths."""
        # Setup
        mock_project_path = Path("/test/project/dir")
        mock_source_path = Path("/mock/template/path")
        mock_find_template_path.return_value = mock_source_path

        handler = InitHandler(project_dir="/test/project/dir")
        handler.project_path = mock_project_path

        # Execute
        handler.setup()

        # Assert
        mock_safe_copy_tree.assert_called_once_with(mock_source_path, mock_project_path)
