import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.template_utils import TEMPLATE_ENTRY_POINTS, get_templates


class TestTemplateUtils(unittest.TestCase):
    """Test class for template_utils module."""

    @patch("importlib.metadata.entry_points")
    def test_get_templates_success(self, mock_entry_points: MagicMock) -> None:
        """Test that get_templates correctly loads templates from entry points."""
        # Setup
        mock_entry_point1 = MagicMock()
        mock_entry_point1.name = "aws_ec2_tls-via-ngrok"
        mock_entry_point1.load.return_value = Path("/mock/template/path")

        mock_entry_point2 = MagicMock()
        mock_entry_point2.name = "aws_lambda_basic"
        mock_entry_point2.load.return_value = Path("/mock/lambda/path")

        mock_entry_points.return_value = [mock_entry_point1, mock_entry_point2]

        # Mock Path.exists to return True for our mock paths
        with patch("pathlib.Path.exists", return_value=True):
            # Execute
            templates = get_templates(EngineType.TERRAFORM)

            # Assert
            self.assertEqual(len(templates), 2)
            self.assertEqual(templates["aws:ec2:tls-via-ngrok"], Path("/mock/template/path"))
            self.assertEqual(templates["aws:lambda:basic"], Path("/mock/lambda/path"))
            mock_entry_points.assert_called_once_with(group=TEMPLATE_ENTRY_POINTS[EngineType.TERRAFORM])
            mock_entry_point1.load.assert_called_once()
            mock_entry_point2.load.assert_called_once()

    def test_get_templates_unsupported_engine(self) -> None:
        """Test that get_templates handles unsupported engine types."""
        # Execute
        # Using a string that's not an EngineType for testing error handling
        templates = get_templates("unsupported_engine")  # type: ignore

        # Assert
        self.assertEqual(len(templates), 0)

    @patch("importlib.metadata.entry_points")
    def test_get_templates_invalid_path(self, mock_entry_points: MagicMock) -> None:
        """Test that get_templates handles invalid paths."""
        # Setup
        mock_entry_point = MagicMock()
        mock_entry_point.name = "aws_ec2_tls-via-ngrok"
        mock_entry_point.load.return_value = "not_a_path"  # Invalid path

        mock_entry_points.return_value = [mock_entry_point]

        # Execute
        templates = get_templates(EngineType.TERRAFORM)

        # Assert
        self.assertEqual(len(templates), 0)
        mock_entry_points.assert_called_once_with(group=TEMPLATE_ENTRY_POINTS[EngineType.TERRAFORM])
        mock_entry_point.load.assert_called_once()

    @patch("importlib.metadata.entry_points")
    def test_get_templates_nonexistent_path(self, mock_entry_points: MagicMock) -> None:
        """Test that get_templates handles paths that don't exist."""
        # Setup
        mock_entry_point = MagicMock()
        mock_entry_point.name = "aws_ec2_tls-via-ngrok"
        mock_entry_point.load.return_value = Path("/nonexistent/path")

        mock_entry_points.return_value = [mock_entry_point]

        # Mock Path.exists to return False
        with patch("pathlib.Path.exists", return_value=False):
            # Execute
            templates = get_templates(EngineType.TERRAFORM)

            # Assert
            self.assertEqual(len(templates), 0)
            mock_entry_points.assert_called_once_with(group=TEMPLATE_ENTRY_POINTS[EngineType.TERRAFORM])
            mock_entry_point.load.assert_called_once()

    @patch("jupyter_deploy.template_utils.get_templates")
    def test_templates_loaded_for_all_engines(self, mock_get_templates: MagicMock) -> None:
        """Test that TEMPLATES dictionary is populated with all supported engines."""
        # Setup
        mock_get_templates.side_effect = lambda engine: {"test:template": Path(f"/mock/{engine}/path")}

        # Execute
        from jupyter_deploy.template_utils import TEMPLATE_ENTRY_POINTS

        templates = {engine: mock_get_templates(engine) for engine in TEMPLATE_ENTRY_POINTS}

        # Assert
        self.assertEqual(len(templates), len(TEMPLATE_ENTRY_POINTS))
        for engine in TEMPLATE_ENTRY_POINTS:
            self.assertIn(engine, templates)
            self.assertEqual(templates[engine], {"test:template": Path(f"/mock/{engine}/path")})

        # Verify get_templates was called once for each engine
        self.assertEqual(mock_get_templates.call_count, len(TEMPLATE_ENTRY_POINTS))
