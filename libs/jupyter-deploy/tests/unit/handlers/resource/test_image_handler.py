import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import CommandNotImplementedError, ImageNotFoundError, ImageTagNotFoundError
from jupyter_deploy.handlers.payloads import ImageDetail, ImageInfo, ImageVulnerabilitiesResult
from jupyter_deploy.handlers.resource.image_handler import ImageHandler
from jupyter_deploy.manifest import JupyterDeployManifest, JupyterDeployManifestV1


class TestImageHandler(unittest.TestCase):
    mock_full_manifest: JupyterDeployManifest

    @classmethod
    def setUpClass(cls) -> None:
        full_manifest_path = Path(__file__).parent.parent.parent / "mock_manifest.yaml"
        with open(full_manifest_path) as f:
            manifest_content = f.read()
        manifest_parsed_content = yaml.safe_load(manifest_content)
        cls.mock_full_manifest = JupyterDeployManifestV1(
            **manifest_parsed_content  # type: ignore
        )

    def get_mock_manifest_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        mock_manifest = Mock()
        mock_get_engine = Mock(return_value=EngineType.TERRAFORM)
        mock_get_images = Mock()
        mock_get_image = Mock()
        mock_get_command = Mock(return_value=Mock())

        mock_manifest.get_engine = mock_get_engine
        mock_manifest.get_images = mock_get_images
        mock_manifest.get_image = mock_get_image
        mock_manifest.get_command = mock_get_command

        return mock_manifest, {
            "get_engine": mock_get_engine,
            "get_images": mock_get_images,
            "get_image": mock_get_image,
            "get_command": mock_get_command,
        }

    def get_mock_outputs_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        mock_output_handler = Mock()
        mock_get_full_project_outputs = Mock()
        mock_output_handler.get_full_project_outputs = mock_get_full_project_outputs

        mock_get_full_project_outputs.return_value = {
            "ecr_repository_name": StrTemplateOutputDefinition(
                output_name="ecr_repository_name", value="my-app/jupyterlab"
            ),
            "jupyterlab_image_tag": StrTemplateOutputDefinition(output_name="jupyterlab_image_tag", value="v1"),
            "aws_region": StrTemplateOutputDefinition(output_name="aws_region", value="us-west-2"),
        }

        return mock_output_handler, {
            "get_full_project_outputs": mock_get_full_project_outputs,
        }

    def get_mock_manifest_cmd_runner_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        mock_cmd_runner = Mock()
        mock_run_command_sequence = Mock()
        mock_get_result_value = Mock()
        mock_get_result_value_with_fallback = Mock(return_value="")

        mock_cmd_runner.run_command_sequence = mock_run_command_sequence
        mock_cmd_runner.get_result_value = mock_get_result_value
        mock_cmd_runner.get_result_value_with_fallback = mock_get_result_value_with_fallback

        return mock_cmd_runner, {
            "run_command_sequence": mock_run_command_sequence,
            "get_result_value": mock_get_result_value,
            "get_result_value_with_fallback": mock_get_result_value_with_fallback,
        }

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("pathlib.Path.cwd")
    def test_can_instantiate_terraform_project(
        self,
        mock_cwd: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        path = Path("/some/cur/dir")
        mock_cwd.return_value = path
        mock_output_handler = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_tf_variables_handler.return_value = Mock()

        mock_manifest, _ = self.get_mock_manifest_and_fns()
        mock_retrieve_manifest.return_value = mock_manifest

        handler = ImageHandler(display_manager=NullDisplay())

        mock_retrieve_manifest.assert_called_once()
        mock_tf_outputs_handler.assert_called_once_with(project_path=path, project_manifest=mock_manifest)
        self.assertEqual(handler._output_handler, mock_output_handler)
        self.assertEqual(handler.engine, EngineType.TERRAFORM)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_list_images_returns_image_info(
        self, mock_tf_variables_handler: Mock, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()
        mock_retrieve_manifest.return_value = self.mock_full_manifest

        handler = ImageHandler(display_manager=NullDisplay())
        images = handler.list_images()

        self.assertEqual(len(images), 1)
        self.assertIsInstance(images[0], ImageInfo)
        self.assertEqual(images[0].name, "jupyterlab")
        self.assertEqual(images[0].description, "JupyterLab workspace image")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_list_images_raises_when_no_images_declared(
        self, mock_tf_variables_handler: Mock, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        no_images_manifest = JupyterDeployManifestV1(
            **{  # type: ignore
                "schema_version": 1,
                "template": {"name": "mock", "engine": "terraform", "version": "1.0.0"},
            }
        )
        mock_retrieve_manifest.return_value = no_images_manifest

        handler = ImageHandler(display_manager=NullDisplay())

        with self.assertRaises(CommandNotImplementedError):
            handler.list_images()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_resolve_name_returns_single_image(
        self, mock_tf_variables_handler: Mock, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()
        mock_retrieve_manifest.return_value = self.mock_full_manifest

        handler = ImageHandler(display_manager=NullDisplay())

        self.assertEqual(handler.resolve_name(None), "jupyterlab")
        self.assertEqual(handler.resolve_name("jupyterlab"), "jupyterlab")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_resolve_name_passes_through_provided_name(
        self, mock_tf_variables_handler: Mock, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()
        mock_retrieve_manifest.return_value = self.mock_full_manifest

        handler = ImageHandler(display_manager=NullDisplay())

        self.assertEqual(handler.resolve_name("anything"), "anything")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_show_image_raises_image_not_found(
        self, mock_tf_variables_handler: Mock, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()
        mock_retrieve_manifest.return_value = self.mock_full_manifest

        handler = ImageHandler(display_manager=NullDisplay())

        with self.assertRaises(ImageNotFoundError) as ctx:
            handler.show_image("nonexistent")

        self.assertEqual(ctx.exception.image_name, "nonexistent")
        self.assertIn("jupyterlab", ctx.exception.valid_images)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_show_image_resolves_outputs_and_runs_command(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()
        mock_retrieve_manifest.return_value = self.mock_full_manifest

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_fns["get_result_value_with_fallback"].return_value = ""
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ImageHandler(display_manager=NullDisplay())
        result = handler.show_image("jupyterlab")

        self.assertIsInstance(result, ImageDetail)
        self.assertEqual(result.name, "jupyterlab")
        self.assertEqual(result.tag, "v1")
        mock_cmd_runner_fns["run_command_sequence"].assert_called_once()

        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("repository_name", cli_paramdefs)
        self.assertIn("image_tag", cli_paramdefs)
        self.assertEqual(cli_paramdefs["repository_name"].value, "my-app/jupyterlab")
        self.assertEqual(cli_paramdefs["image_tag"].value, "v1")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_get_vulnerabilities_uses_default_tag(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()
        mock_retrieve_manifest.return_value = self.mock_full_manifest

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_fns["get_result_value_with_fallback"].return_value = ""
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ImageHandler(display_manager=NullDisplay())
        result = handler.get_vulnerabilities("jupyterlab")

        self.assertIsInstance(result, ImageVulnerabilitiesResult)
        self.assertEqual(result.tag, "v1")

        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["image_tag"].value, "v1")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_get_vulnerabilities_uses_provided_tag(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()
        mock_retrieve_manifest.return_value = self.mock_full_manifest

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_fns["get_result_value_with_fallback"].return_value = ""
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ImageHandler(display_manager=NullDisplay())
        result = handler.get_vulnerabilities("jupyterlab", tag="v2")

        self.assertEqual(result.tag, "v2")
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["image_tag"].value, "v2")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_get_vulnerabilities_reraises_tag_not_found_with_image_name(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()
        mock_retrieve_manifest.return_value = self.mock_full_manifest

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_fns["run_command_sequence"].side_effect = ImageTagNotFoundError("my-app/jupyterlab", "v99")
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ImageHandler(display_manager=NullDisplay())

        with self.assertRaises(ImageTagNotFoundError) as ctx:
            handler.get_vulnerabilities("jupyterlab", tag="v99")

        self.assertEqual(ctx.exception.image_name, "jupyterlab")
        self.assertEqual(ctx.exception.tag, "v99")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_get_status_available(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()
        mock_retrieve_manifest.return_value = self.mock_full_manifest

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()

        # list_tags reads ".tags"; image.status reads ".status"/".status_category".
        def fallback(command: Mock, key: str, _type: type, default: str) -> str:
            if key.endswith(".tags"):
                return (
                    '[{"tag": "v2", "pushed_at": "", "digest": ""}, {"tag": "latest", "pushed_at": "", "digest": ""}]'
                )
            if key.endswith(".status"):
                return "Available"
            if key.endswith(".status_category"):
                return "healthy"
            return default

        mock_cmd_runner_fns["get_result_value_with_fallback"].side_effect = fallback
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ImageHandler(display_manager=NullDisplay())
        result = handler.get_status("jupyterlab")

        self.assertEqual(result.name, "jupyterlab")
        self.assertEqual(result.status, "Available")
        self.assertEqual(result.status_category, "healthy")
        self.assertEqual(result.latest_tag, "v2")  # 'latest' excluded

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_get_status_missing(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()
        mock_retrieve_manifest.return_value = self.mock_full_manifest

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_fns["get_result_value_with_fallback"].return_value = "[]"

        # list_tags succeeds (empty), then image.status raises ImageTagNotFoundError.
        mock_cmd_runner_fns["run_command_sequence"].side_effect = [None, ImageTagNotFoundError("repo", "v1")]
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ImageHandler(display_manager=NullDisplay())
        result = handler.get_status("jupyterlab")

        self.assertEqual(result.status, "Missing")
        self.assertEqual(result.status_category, "degraded")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_list_tags_runs_command(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()
        mock_retrieve_manifest.return_value = self.mock_full_manifest

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_fns["get_result_value_with_fallback"].return_value = "[]"
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ImageHandler(display_manager=NullDisplay())
        result = handler.list_tags("jupyterlab")

        self.assertIsInstance(result, list)
        mock_cmd_runner_fns["run_command_sequence"].assert_called_once()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_methods_raise_if_run_command_raises(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()
        mock_retrieve_manifest.return_value = self.mock_full_manifest

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_fns["run_command_sequence"].side_effect = RuntimeError("API error")
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ImageHandler(display_manager=NullDisplay())

        with self.assertRaises(RuntimeError):
            handler.show_image("jupyterlab")

        with self.assertRaises(RuntimeError):
            handler.list_tags("jupyterlab")

        with self.assertRaises(RuntimeError):
            handler.get_vulnerabilities("jupyterlab")

        with self.assertRaises(RuntimeError):
            handler.get_status("jupyterlab")
