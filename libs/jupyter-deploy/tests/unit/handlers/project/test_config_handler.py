import unittest
from pathlib import Path
from unittest.mock import ANY, Mock, patch

from jupyter_deploy.constants import MASKED_SECRET_VALUE
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.enum import StoreType
from jupyter_deploy.exceptions import (
    CommandNotImplementedError,
    InvalidPresetError,
    ProjectStoreNotFoundError,
    SecretNotFoundError,
)
from jupyter_deploy.handlers.project.config_handler import ConfigHandler
from jupyter_deploy.manifest import JupyterDeployManifestV1, JupyterDeployProjectStoreV1
from jupyter_deploy.provider.store.store_manager import StoreInfo
from jupyter_deploy.store_config import JupyterDeployStoreConfigV1
from jupyter_deploy.variables_config import JupyterDeployVariablesConfig
from jupyter_deploy.verify_utils import ToolRequiredError


class TestConfigHandler(unittest.TestCase):
    def get_mock_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return mocked config handler."""
        mock_handler = Mock()
        mock_has_recorded_variables = Mock()
        mock_verify_preset = Mock()
        mock_list_presets = Mock()
        mock_reset_recorded_variables = Mock()
        mock_reset_recorded_secrets = Mock()
        mock_configure = Mock()
        mock_record = Mock()

        mock_handler.has_recorded_variables = mock_has_recorded_variables
        mock_handler.verify_preset_exists = mock_verify_preset
        mock_handler.list_presets = mock_list_presets
        mock_handler.reset_recorded_variables = mock_reset_recorded_variables
        mock_handler.reset_recorded_secrets = mock_reset_recorded_secrets
        mock_handler.configure = mock_configure
        mock_handler.record = mock_record

        mock_has_recorded_variables.return_value = False
        mock_verify_preset.return_value = True
        mock_configure.return_value = True
        mock_list_presets.return_value = ["all", "base", "none"]

        return (
            mock_handler,
            {
                "has_recorded_variables": mock_has_recorded_variables,
                "verify_preset_exists": mock_verify_preset,
                "list_presets": mock_list_presets,
                "reset_recorded_variables": mock_reset_recorded_variables,
                "reset_recorded_secrets": mock_reset_recorded_secrets,
                "configure": mock_configure,
                "record": mock_record,
            },
        )

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
    def test_config_handler_reads_the_manifest(self, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        handler = ConfigHandler(display_manager=NullDisplay())
        mock_retrieve_manifest.assert_called_once()
        self.assertEqual(handler.project_manifest, self.mock_manifest)
        self.assertEqual(handler.engine, self.mock_manifest.get_engine())

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    @patch("pathlib.Path.cwd")
    def test_config_handler_correctly_implements_tf_engine(
        self, mock_cwd: Mock, mock_tf_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        path = Path("/some/cur/dir")
        mock_cwd.return_value = path
        mock_retrieve_manifest.return_value = self.mock_manifest

        # right now, it defaults to terraform
        # in the future, it should infer it from the project
        handler = ConfigHandler(display_manager=NullDisplay())

        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        self.assertIsNone(handler.preset_name)
        mock_tf_handler.assert_called_once_with(
            project_path=path,
            project_manifest=self.mock_manifest,
            command_history_handler=ANY,
            output_filename=None,
            display_manager=ANY,
        )
        tf_mock_configure.assert_not_called()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_has_recorded_variables_delegates_to_handler(
        self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_has_recorded = tf_fns["has_recorded_variables"]
        tf_mock_has_recorded.return_value = True
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        result = handler.has_recorded_variables()

        self.assertTrue(result)
        tf_mock_has_recorded.assert_called_once()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_verify_preset_exists_delegates_to_handler(
        self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_verify_preset = tf_fns["verify_preset_exists"]
        tf_mock_verify_preset.return_value = True
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        result = handler.verify_preset_exists("all")

        self.assertTrue(result)
        tf_mock_verify_preset.assert_called_once_with("all")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_list_presets_delegates_to_handler(self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_list_presets = tf_fns["list_presets"]
        tf_mock_list_presets.return_value = ["all", "base", "none"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        result = handler.list_presets()

        self.assertEqual(result, ["all", "base", "none"])
        tf_mock_list_presets.assert_called_once()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_set_preset_sets_instance_variable(self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, _ = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        self.assertIsNone(handler.preset_name)

        handler.set_preset("all")
        self.assertEqual(handler.preset_name, "all")

        handler.set_preset(None)
        self.assertIsNone(handler.preset_name)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_validate_preset_succeeds_for_valid_preset(
        self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_verify_preset = tf_fns["verify_preset_exists"]
        tf_mock_verify_preset.return_value = True
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        # Should not raise
        handler.validate_preset("all")
        tf_mock_verify_preset.assert_called_once_with("all")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_validate_preset_raises_for_invalid_preset(
        self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_verify_preset = tf_fns["verify_preset_exists"]
        tf_mock_list_presets = tf_fns["list_presets"]
        tf_mock_verify_preset.return_value = False
        tf_mock_list_presets.return_value = ["all", "base", "none"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        with self.assertRaises(InvalidPresetError) as context:
            handler.validate_preset("invalid")

        self.assertEqual(context.exception.preset_name, "invalid")
        self.assertEqual(context.exception.valid_presets, ["all", "base", "none"])
        tf_mock_verify_preset.assert_called_once_with("invalid")
        tf_mock_list_presets.assert_called_once()

    @patch("jupyter_deploy.verify_utils.verify_tools_installation")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_verify_calls_verify_utils(
        self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock, mock_verify: Mock
    ) -> None:
        mock_req1 = Mock()
        mock_req2 = Mock()

        with patch.object(self.mock_manifest, "get_requirements", return_value=[mock_req1, mock_req2]):
            mock_retrieve_manifest.return_value = self.mock_manifest
            tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
            tf_mock_configure = tf_fns["configure"]
            mock_tf_handler.return_value = tf_mock_handler_instance

            handler = ConfigHandler(display_manager=NullDisplay())
            handler.verify_requirements()

            mock_verify.assert_called_once_with([mock_req1, mock_req2])
            tf_mock_configure.assert_not_called()

    @patch("jupyter_deploy.verify_utils.verify_tools_installation")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_verify_surfaces_verify_utils_exception(
        self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock, mock_verify: Mock
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, _ = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance
        mock_verify.side_effect = ToolRequiredError("terraform", None, None)

        handler = ConfigHandler(display_manager=NullDisplay())
        with self.assertRaises(ToolRequiredError):
            handler.verify_requirements()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_reset_variables_calls_underlying_handler_method(
        self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        ConfigHandler(display_manager=NullDisplay())

        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_reset_vars = tf_fns["reset_recorded_variables"]
        tf_mock_reset_secrets = tf_fns["reset_recorded_secrets"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        handler.reset_recorded_variables()

        tf_mock_reset_vars.assert_called_once()
        tf_mock_reset_secrets.assert_not_called()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_reset_secrets_calls_underlying_handler_method(
        self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_reset_vars = tf_fns["reset_recorded_variables"]
        tf_mock_reset_secrets = tf_fns["reset_recorded_secrets"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        handler.reset_recorded_secrets()

        tf_mock_reset_vars.assert_not_called()
        tf_mock_reset_secrets.assert_called_once()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_configure_calls_underlying_handler_method(
        self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        result = handler.configure()

        self.assertTrue(result)
        tf_mock_configure.assert_called_once_with(preset_name=None, variable_overrides=None)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_configure_passes_the_preset(self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        handler.set_preset("all")
        result = handler.configure()

        self.assertTrue(result)
        tf_mock_configure.assert_called_once_with(preset_name="all", variable_overrides=None)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_configure_passes_the_variables(self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        handler.set_preset("all")

        overrides = {"var1": Mock()}
        result = handler.configure(variable_overrides=overrides)  # type: ignore

        self.assertTrue(result)
        tf_mock_configure.assert_called_once_with(preset_name="all", variable_overrides=overrides)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_configure_surfaces_underlying_method_exception(
        self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        error = RuntimeError("another-error")
        tf_mock_configure.side_effect = error

        handler = ConfigHandler(display_manager=NullDisplay())

        with self.assertRaisesRegex(RuntimeError, "another-error"):
            handler.configure()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_record_delegates_to_handler(self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_record = tf_fns["record"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        handler.record()
        tf_mock_record.assert_called_once()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_record_surfaces_underlying_exception(self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_record = tf_fns["record"]
        mock_tf_handler.return_value = tf_mock_handler_instance
        tf_mock_record.side_effect = RuntimeError("Cannot record!")

        handler = ConfigHandler(display_manager=NullDisplay())
        with self.assertRaises(RuntimeError):
            handler.record()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_store_config", return_value=None)
    @patch("jupyter_deploy.handlers.project.config_handler.write_store_config")
    @patch("jupyter_deploy.handlers.project.config_handler.StoreManagerFactory")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_ensure_store_resolves_from_manifest(
        self,
        mock_tf_handler: Mock,
        mock_retrieve_manifest: Mock,
        mock_store_factory: Mock,
        mock_write_config: Mock,
        mock_retrieve_store_config: Mock,
    ) -> None:
        project_store = JupyterDeployProjectStoreV1(**{"store-type": "s3-ddb"})  # type: ignore
        manifest = JupyterDeployManifestV1(
            **{  # type: ignore
                "schema_version": 1,
                "template": {"name": "test", "engine": "terraform", "version": "1.0.0"},
                "project_store": project_store,
            }
        )
        mock_retrieve_manifest.return_value = manifest

        mock_store_manager = Mock()
        mock_store_info = StoreInfo(store_type=StoreType.S3_DDB, store_id="discovered-bucket", location="us-east-1")
        mock_store_manager.ensure_store.return_value = mock_store_info
        mock_store_factory.get_manager.return_value = mock_store_manager

        tf_mock_handler_instance, _ = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        result = handler.ensure_store()

        mock_store_factory.get_manager.assert_called_once_with(store_type=StoreType.S3_DDB, store_id=None)
        mock_store_manager.ensure_store.assert_called_once()
        mock_write_config.assert_called_once_with(
            ANY, store_type="s3-ddb", store_id="discovered-bucket", project_id=None
        )
        self.assertEqual(result, mock_store_info)

    @patch("jupyter_deploy.handlers.project.config_handler.write_store_config")
    @patch("jupyter_deploy.handlers.project.config_handler.StoreManagerFactory")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_ensure_store_with_explicit_store_id_calls_find_store(
        self,
        mock_tf_handler: Mock,
        mock_retrieve_manifest: Mock,
        mock_store_factory: Mock,
        mock_write_config: Mock,
    ) -> None:
        project_store = JupyterDeployProjectStoreV1(**{"store-type": "s3-ddb"})  # type: ignore
        manifest = JupyterDeployManifestV1(
            **{  # type: ignore
                "schema_version": 1,
                "template": {"name": "test", "engine": "terraform", "version": "1.0.0"},
                "project_store": project_store,
            }
        )
        mock_retrieve_manifest.return_value = manifest

        mock_store_manager = Mock()
        mock_store_info = StoreInfo(store_type=StoreType.S3_DDB, store_id="my-bucket", location="us-east-1")
        mock_store_manager.find_store.return_value = mock_store_info
        mock_store_factory.get_manager.return_value = mock_store_manager

        tf_mock_handler_instance, _ = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        handler.ensure_store(store_type=StoreType.S3_DDB, store_id="my-bucket")

        mock_store_factory.get_manager.assert_called_once_with(store_type=StoreType.S3_DDB, store_id="my-bucket")
        mock_store_manager.find_store.assert_called_once()
        mock_store_manager.ensure_store.assert_not_called()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_store_config", return_value=None)
    @patch("jupyter_deploy.handlers.project.config_handler.write_store_config")
    @patch("jupyter_deploy.handlers.project.config_handler.StoreManagerFactory")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_ensure_store_without_store_warns_and_returns_none(
        self,
        mock_tf_handler: Mock,
        mock_retrieve_manifest: Mock,
        mock_store_factory: Mock,
        mock_write_config: Mock,
        mock_retrieve_store_config: Mock,
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, _ = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        mock_display = Mock()
        handler = ConfigHandler(display_manager=mock_display)
        result = handler.ensure_store()

        self.assertIsNone(result)
        mock_display.warning.assert_called_once()
        mock_store_factory.get_manager.assert_not_called()
        mock_write_config.assert_not_called()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_store_config")
    @patch("jupyter_deploy.handlers.project.config_handler.write_store_config")
    @patch("jupyter_deploy.handlers.project.config_handler.StoreManagerFactory")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_ensure_store_stale_store_id_propagates_error(
        self,
        mock_tf_handler: Mock,
        mock_retrieve_manifest: Mock,
        mock_store_factory: Mock,
        mock_write_config: Mock,
        mock_retrieve_store_config: Mock,
    ) -> None:
        """When store-id from .jd/store.yaml is stale, find_store error propagates."""
        project_store = JupyterDeployProjectStoreV1(**{"store-type": "s3-only"})  # type: ignore
        manifest = JupyterDeployManifestV1(
            **{  # type: ignore
                "schema_version": 1,
                "template": {"name": "test", "engine": "terraform", "version": "1.0.0"},
                "project_store": project_store,
            }
        )
        mock_retrieve_manifest.return_value = manifest

        # Simulate .jd/store.yaml with a stale store-id
        mock_retrieve_store_config.return_value = JupyterDeployStoreConfigV1(
            store_type="s3-only", store_id="deleted-bucket"
        )

        mock_store_manager = Mock()
        mock_store_manager.find_store.side_effect = ProjectStoreNotFoundError(
            "S3 bucket not found: deleted-bucket",
            hint="run 'jd config --reset-store-id' to clear it and rediscover the store.",
        )
        mock_store_factory.get_manager.return_value = mock_store_manager

        tf_mock_handler_instance, _ = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())

        with self.assertRaises(ProjectStoreNotFoundError) as ctx:
            handler.ensure_store()

        self.assertIsNotNone(ctx.exception.hint)
        self.assertIn("--reset-store-id", ctx.exception.hint)  # type: ignore[arg-type]
        mock_write_config.assert_not_called()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_store_config")
    @patch("jupyter_deploy.handlers.project.config_handler.write_store_config")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_reset_store_id_clears_store_id_preserving_store_type(
        self,
        mock_tf_handler: Mock,
        mock_retrieve_manifest: Mock,
        mock_write_config: Mock,
        mock_retrieve_store_config: Mock,
    ) -> None:
        """reset_store_id writes store.yaml with store-type but no store-id."""
        project_store = JupyterDeployProjectStoreV1(**{"store-type": "s3-only"})  # type: ignore
        manifest = JupyterDeployManifestV1(
            **{  # type: ignore
                "schema_version": 1,
                "template": {"name": "test", "engine": "terraform", "version": "1.0.0"},
                "project_store": project_store,
            }
        )
        mock_retrieve_manifest.return_value = manifest

        # .jd/store.yaml has both store-type and store-id
        mock_retrieve_store_config.return_value = JupyterDeployStoreConfigV1(
            store_type="s3-only", store_id="old-bucket"
        )

        tf_mock_handler_instance, _ = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        handler.reset_store_id()

        mock_write_config.assert_called_once_with(ANY, store_type="s3-only", store_id=None, project_id=None)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_mask_secrets_delegates_to_variables_handler(
        self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, _ = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        handler.mask_secrets()

        tf_mock_handler_instance.variables_handler.mask_secrets.assert_called_once()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_restore_secrets_raises_for_invalid_variable_name(
        self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, _ = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        # Set up variables_handler to return a config with no sensitive vars
        mock_vars_config = JupyterDeployVariablesConfig(
            schema_version=1,
            required={"domain": "example.com"},
            required_sensitive={},
        )
        tf_mock_handler_instance.variables_handler.variables_config = mock_vars_config

        handler = ConfigHandler(display_manager=NullDisplay())
        with self.assertRaises(SecretNotFoundError):
            handler.restore_secrets(restore_names=["nonexistent_var"])

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_restore_secrets_raises_when_no_reveal_command(
        self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, _ = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        mock_vars_config = JupyterDeployVariablesConfig(
            schema_version=1,
            required={},
            required_sensitive={"my_secret": MASKED_SECRET_VALUE},
        )
        tf_mock_handler_instance.variables_handler.variables_config = mock_vars_config

        handler = ConfigHandler(display_manager=NullDisplay())
        with self.assertRaises(CommandNotImplementedError):
            handler.restore_secrets(restore_all=True)

    @patch("jupyter_deploy.handlers.project.config_handler.ManifestCommandRunner")
    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler._create_outputs_handler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_restore_secrets_fetches_and_writes_secret(
        self,
        mock_tf_handler: Mock,
        mock_retrieve_manifest: Mock,
        mock_create_outputs: Mock,
        mock_cmd_runner_class: Mock,
    ) -> None:
        # Build manifest with secrets and secret.reveal command
        manifest_data = {
            "schema_version": 1,
            "template": {"name": "test", "engine": "terraform", "version": "1.0.0"},
            "secrets": [{"name": "oauth_secret", "source": "output", "source-key": "secret_arn"}],
            "commands": [
                {
                    "cmd": "secret.reveal",
                    "sequence": [
                        {
                            "api-name": "aws.secretsmanager.get-secret-value",
                            "arguments": [{"api-attribute": "secret-id", "source": "cli", "source-key": "secret-id"}],
                        }
                    ],
                    "results": [{"result-name": "secret-value", "source": "result", "source-key": "[0].SecretString"}],
                }
            ],
        }
        manifest = JupyterDeployManifestV1(**manifest_data)  # type: ignore
        mock_retrieve_manifest.return_value = manifest

        tf_mock_handler_instance, _ = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        mock_vars_config = JupyterDeployVariablesConfig(
            schema_version=1,
            required={},
            required_sensitive={"oauth_secret": MASKED_SECRET_VALUE},
        )
        tf_mock_handler_instance.variables_handler.variables_config = mock_vars_config

        # Mock outputs handler with secret ARN
        mock_outputs_handler: Mock = Mock()
        mock_output_def: Mock = Mock()
        mock_output_def.value = "arn:aws:secretsmanager:us-west-2:123:secret:test"
        mock_outputs_handler.get_full_project_outputs.return_value = {
            "secret_arn": mock_output_def,
        }
        mock_create_outputs.return_value = mock_outputs_handler

        # Mock command runner
        mock_runner: Mock = Mock()
        mock_cmd_runner_class.return_value = mock_runner
        mock_runner.run_command_sequence.return_value = (True, {})
        mock_runner.get_result_value.return_value = "the-real-secret"

        handler = ConfigHandler(display_manager=NullDisplay())
        handler.restore_secrets(restore_all=True)

        mock_runner.run_command_sequence.assert_called_once()
        mock_runner.get_result_value.assert_called_once()
        tf_mock_handler_instance.variables_handler.sync_project_variables_config.assert_called_once_with(
            {"oauth_secret": "the-real-secret"}
        )

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_restore_secrets_noop_when_no_flags(self, mock_tf_handler: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        tf_mock_handler_instance, _ = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(display_manager=NullDisplay())
        # Should return immediately without error
        handler.restore_secrets()
