import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.handlers.access.user_handler import UsersHandler
from jupyter_deploy.manifest import JupyterDeployManifestV1


class TestUserHandler(unittest.TestCase):
    def get_mock_outputs_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return mock output handler with functions defined as mock."""
        mock_output_handler = Mock()
        return mock_output_handler, {}

    def setUp(self) -> None:
        self.mock_manifest = JupyterDeployManifestV1(
            **{  # type: ignore
                "schema_version": 1,
                "template": {
                    "name": "mock-template-name",
                    "engine": "terraform",
                    "version": "1.0.0",
                },
            }
        )

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    def test_user_handler_reads_the_manifest(self, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_retrieve_manifest.return_value = self.mock_manifest
        handler = UsersHandler()

        mock_retrieve_manifest.assert_called_once()
        self.assertEqual(handler.project_manifest, self.mock_manifest)
        self.assertEqual(handler.engine, self.mock_manifest.get_engine())

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("pathlib.Path.cwd")
    def test_user_handler_can_instantiate_tf_project(
        self, mock_cwd: Mock, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        path = Path("/some/cur/dir")
        mock_cwd.return_value = path
        mock_output_handler = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_retrieve_manifest.return_value = self.mock_manifest

        handler = UsersHandler()
        self.assertEqual(handler._output_handler, mock_output_handler)
        mock_tf_outputs_handler.assert_called_with(project_path=path, project_manifest=self.mock_manifest)
