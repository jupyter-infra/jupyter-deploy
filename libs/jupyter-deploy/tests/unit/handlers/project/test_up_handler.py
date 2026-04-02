import unittest
from pathlib import Path
from unittest.mock import ANY, Mock, patch

from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.enum import StoreType
from jupyter_deploy.exceptions import (
    ProjectIdNotAvailableError,
    ProjectStoreAccessConfigurationError,
    ProjectStoreNotFoundError,
)
from jupyter_deploy.handlers.project.up_handler import UpHandler
from jupyter_deploy.manifest import JupyterDeployManifestV1, JupyterDeployProjectStoreV1
from jupyter_deploy.provider.store.store_manager import StoreInfo


class TestUpHandler(unittest.TestCase):
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

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_init_creates_terraform_handler(
        self, mock_cwd: Mock, mock_retrieve_manifest: Mock, mock_tf_handler_cls: Mock
    ) -> None:
        mock_cwd.return_value = Path("/mock/cwd")
        mock_retrieve_manifest.return_value = self.mock_manifest
        mock_tf_handler = Mock()
        mock_tf_handler_cls.return_value = mock_tf_handler
        mock_tf_handler.engine_dir_path = Path("/mock/cwd/engine")

        handler = UpHandler(display_manager=NullDisplay())

        # Verify TerraformUpHandler was called with correct arguments
        call_args = mock_tf_handler_cls.call_args
        self.assertEqual(call_args.kwargs["project_path"], Path("/mock/cwd"))
        self.assertEqual(call_args.kwargs["project_manifest"], self.mock_manifest)
        self.assertIsNotNone(call_args.kwargs["command_history_handler"])
        self.assertIsInstance(call_args.kwargs["display_manager"], NullDisplay)
        self.assertEqual(handler._handler, mock_tf_handler)

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_init_passes_display_manager_to_terraform_handler(
        self, mock_cwd: Mock, mock_retrieve_manifest: Mock, mock_tf_handler_cls: Mock
    ) -> None:
        """Test that a non-None display_manager is passed through to TerraformUpHandler."""
        mock_cwd.return_value = Path("/mock/cwd")
        mock_retrieve_manifest.return_value = self.mock_manifest
        mock_tf_handler = Mock()
        mock_tf_handler_cls.return_value = mock_tf_handler
        mock_tf_handler.engine_dir_path = Path("/mock/cwd/engine")

        # Create a mock terminal handler
        mock_display_manager = Mock()

        handler = UpHandler(display_manager=mock_display_manager)

        # Verify TerraformUpHandler was called with the display_manager
        call_args = mock_tf_handler_cls.call_args
        self.assertEqual(call_args.kwargs["project_path"], Path("/mock/cwd"))
        self.assertEqual(call_args.kwargs["project_manifest"], self.mock_manifest)
        self.assertIsNotNone(call_args.kwargs["command_history_handler"])
        self.assertEqual(call_args.kwargs["display_manager"], mock_display_manager)
        self.assertEqual(handler._handler, mock_tf_handler)

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_apply_delegates_to_handler(
        self, mock_cwd: Mock, mock_retrieve_manifest: Mock, mock_tf_handler_cls: Mock
    ) -> None:
        path = Path("/mock/path")
        mock_cwd.return_value = Path("/mock/cwd")
        mock_retrieve_manifest.return_value = self.mock_manifest
        mock_tf_handler = Mock()
        mock_tf_handler_cls.return_value = mock_tf_handler
        mock_tf_handler.engine_dir_path = Path("/mock/cwd/engine")

        handler = UpHandler(display_manager=NullDisplay())
        handler.apply(path, auto_approve=False)

        mock_tf_handler.apply.assert_called_once_with(path, False)

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_apply_propagates_exceptions(
        self, mock_cwd: Mock, mock_retrieve_manifest: Mock, mock_tf_handler_cls: Mock
    ) -> None:
        path = Path("/mock/path")
        mock_cwd.return_value = Path("/mock/cwd")
        mock_retrieve_manifest.return_value = self.mock_manifest
        mock_tf_handler = Mock()
        mock_tf_handler.apply.side_effect = Exception("Apply failed")
        mock_tf_handler.engine_dir_path = Path("/mock/cwd/engine")
        mock_tf_handler_cls.return_value = mock_tf_handler

        handler = UpHandler(display_manager=NullDisplay())

        with self.assertRaises(Exception) as context:
            handler.apply(path)

        self.assertEqual(str(context.exception), "Apply failed")
        mock_tf_handler.apply.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_get_default_config_filename_delegates_to_handler(
        self, mock_cwd: Mock, mock_retrieve_manifest: Mock, mock_tf_handler_cls: Mock
    ) -> None:
        mock_cwd.return_value = Path("/mock/cwd")
        mock_retrieve_manifest.return_value = self.mock_manifest
        mock_tf_handler = Mock()
        mock_tf_handler.engine_dir_path = Path("/mock/cwd/engine")
        mock_tf_handler.get_default_config_filename.return_value = "jdout-tfplan"
        mock_tf_handler_cls.return_value = mock_tf_handler

        handler = UpHandler(display_manager=NullDisplay())
        result = handler.get_default_config_filename()

        mock_tf_handler.get_default_config_filename.assert_called_once()
        self.assertEqual(result, "jdout-tfplan")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_init_raises_value_error_for_unsupported_engine(self, mock_cwd: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_cwd.return_value = Path("/mock/cwd")
        mock_manifest = self.mock_manifest
        # Change the engine to an unsupported one
        mock_manifest.template.engine = "UNSUPPORTED_ENGINE"  # type: ignore
        mock_retrieve_manifest.return_value = mock_manifest

        with self.assertRaises(ValueError):
            UpHandler(display_manager=NullDisplay())

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_get_config_file_path_when_file_exists(
        self,
        mock_cwd: Mock,
        mock_retrieve_manifest: Mock,
        mock_tf_handler_cls: Mock,
    ) -> None:
        mock_cwd.return_value = Path("/mock/cwd")
        mock_retrieve_manifest.return_value = self.mock_manifest
        mock_tf_handler = Mock()
        mock_tf_handler.engine_dir_path = Path("/mock/cwd/engine")
        mock_tf_handler.get_default_config_filename.return_value = "jdout-tfplan"
        mock_tf_handler_cls.return_value = mock_tf_handler

        with patch.object(Path, "exists", return_value=True):
            handler = UpHandler(display_manager=NullDisplay())
            result = handler.get_config_file_path("test-config")

        self.assertEqual(result, Path("/mock/cwd/engine/test-config"))

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_get_config_file_path_when_file_does_not_exist(
        self,
        mock_cwd: Mock,
        mock_retrieve_manifest: Mock,
        mock_tf_handler_cls: Mock,
    ) -> None:
        """Test that FileNotFoundError is raised when config file does not exist."""
        mock_cwd.return_value = Path("/mock/cwd")
        mock_retrieve_manifest.return_value = self.mock_manifest

        mock_tf_handler = Mock()
        mock_tf_handler.engine_dir_path = Path("/mock/cwd/engine")
        mock_tf_handler.get_default_config_filename.return_value = "jdout-tfplan"
        mock_tf_handler_cls.return_value = mock_tf_handler

        with patch.object(Path, "exists", return_value=False):
            handler = UpHandler(display_manager=NullDisplay())
            with self.assertRaises(FileNotFoundError) as context:
                handler.get_config_file_path("test-config")

        # Verify error message contains helpful information
        self.assertIn("test-config", str(context.exception))
        self.assertIn("jd config", str(context.exception))


class TestUpHandlerPushToStore(unittest.TestCase):
    def setUp(self) -> None:
        self.project_store = JupyterDeployProjectStoreV1(**{"store-type": "s3-ddb"})  # type: ignore
        self.mock_manifest = JupyterDeployManifestV1(
            **{  # type: ignore
                "schema_version": 1,
                "template": {"name": "test-template", "engine": "terraform", "version": "1.0.0"},
                "values": [{"name": "deployment_id", "source": "output", "source-key": "deployment_id"}],
                "project_store": self.project_store,
            }
        )
        self.mock_manifest_no_store = JupyterDeployManifestV1(
            **{  # type: ignore
                "schema_version": 1,
                "template": {"name": "test-template", "engine": "terraform", "version": "1.0.0"},
            }
        )

    def _setup_handler(
        self,
        mock_cwd: Mock,
        mock_retrieve_manifest: Mock,
        mock_tf_handler_cls: Mock,
        manifest: JupyterDeployManifestV1 | None = None,
    ) -> UpHandler:
        mock_cwd.return_value = Path("/mock/cwd")
        mock_retrieve_manifest.return_value = manifest or self.mock_manifest
        mock_tf_handler = Mock()
        mock_tf_handler.engine_dir_path = Path("/mock/cwd/engine")
        mock_tf_handler.apply.return_value = None
        mock_tf_handler_cls.return_value = mock_tf_handler

        return UpHandler(display_manager=NullDisplay())

    @patch("jupyter_deploy.handlers.project.up_handler.write_store_config")
    @patch("jupyter_deploy.handlers.project.up_handler.StoreManagerFactory")
    @patch("jupyter_deploy.handlers.project.up_handler.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_push_to_store_pushes(
        self,
        mock_cwd: Mock,
        mock_retrieve_manifest: Mock,
        mock_tf_handler_cls: Mock,
        mock_outputs_cls: Mock,
        mock_store_factory: Mock,
        mock_write_config: Mock,
    ) -> None:
        handler = self._setup_handler(mock_cwd, mock_retrieve_manifest, mock_tf_handler_cls)
        handler._store_access_manager = Mock()
        handler._store_access_manager.is_configured.return_value = True

        mock_store_manager = Mock()
        mock_store_info = StoreInfo(store_type=StoreType.S3_DDB, store_id="discovered-bucket", location="us-east-1")
        mock_store_manager.find_store.return_value = mock_store_info
        mock_store_factory.get_manager.return_value = mock_store_manager

        mock_output_def = StrTemplateOutputDefinition(output_name="deployment_id", value="dep-001")
        mock_outputs_cls.return_value.get_declared_output_def.return_value = mock_output_def

        handler.push_to_store()

        mock_store_factory.get_manager.assert_called_once_with(store_type=StoreType.S3_DDB, store_id=None)
        mock_store_manager.find_store.assert_called_once()
        handler._store_access_manager.configure.assert_not_called()
        mock_store_manager.push.assert_called_once()
        mock_write_config.assert_called_once_with(
            ANY, store_type="s3-ddb", store_id="discovered-bucket", project_id="test-template-dep-001"
        )

    @patch("jupyter_deploy.handlers.project.up_handler.write_store_config")
    @patch("jupyter_deploy.handlers.project.up_handler.StoreManagerFactory")
    @patch("jupyter_deploy.handlers.project.up_handler.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_push_to_store_uses_store_id_from_config(
        self,
        mock_cwd: Mock,
        mock_retrieve_manifest: Mock,
        mock_tf_handler_cls: Mock,
        mock_outputs_cls: Mock,
        mock_store_factory: Mock,
        mock_write_config: Mock,
    ) -> None:
        handler = self._setup_handler(mock_cwd, mock_retrieve_manifest, mock_tf_handler_cls)
        handler._store_access_manager = Mock()
        handler._store_access_manager.is_configured.return_value = True

        # Simulate .jd/store.yaml having a pinned store-id
        with patch.object(type(handler), "get_store_id_from_config", return_value="my-bucket"):
            mock_store_manager = Mock()
            mock_store_info = StoreInfo(store_type=StoreType.S3_DDB, store_id="my-bucket", location="us-east-1")
            mock_store_manager.find_store.return_value = mock_store_info
            mock_store_factory.get_manager.return_value = mock_store_manager

            mock_output_def = StrTemplateOutputDefinition(output_name="deployment_id", value="dep-001")
            mock_outputs_cls.return_value.get_declared_output_def.return_value = mock_output_def

            handler.push_to_store()

        mock_store_factory.get_manager.assert_called_once_with(store_type=StoreType.S3_DDB, store_id="my-bucket")

    @patch("jupyter_deploy.handlers.project.up_handler.StoreManagerFactory")
    @patch("jupyter_deploy.handlers.project.up_handler.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_push_to_store_raises_when_deployment_id_unavailable(
        self,
        mock_cwd: Mock,
        mock_retrieve_manifest: Mock,
        mock_tf_handler_cls: Mock,
        mock_outputs_cls: Mock,
        mock_store_factory: Mock,
    ) -> None:
        handler = self._setup_handler(mock_cwd, mock_retrieve_manifest, mock_tf_handler_cls)

        mock_output_def = StrTemplateOutputDefinition(output_name="deployment_id", value=None)
        mock_outputs_cls.return_value.get_declared_output_def.return_value = mock_output_def

        with self.assertRaises(ProjectIdNotAvailableError):
            handler.push_to_store()

    @patch("jupyter_deploy.handlers.project.up_handler.write_store_config")
    @patch("jupyter_deploy.handlers.project.up_handler.StoreManagerFactory")
    @patch("jupyter_deploy.handlers.project.up_handler.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_push_to_store_configures_backend_on_first_run(
        self,
        mock_cwd: Mock,
        mock_retrieve_manifest: Mock,
        mock_tf_handler_cls: Mock,
        mock_outputs_cls: Mock,
        mock_store_factory: Mock,
        mock_write_config: Mock,
    ) -> None:
        handler = self._setup_handler(mock_cwd, mock_retrieve_manifest, mock_tf_handler_cls)
        handler._store_access_manager = Mock()
        handler._store_access_manager.is_configured.return_value = False

        mock_store_manager = Mock()
        mock_store_info = StoreInfo(store_type=StoreType.S3_DDB, store_id="discovered-bucket", location="us-east-1")
        mock_store_manager.find_store.return_value = mock_store_info
        mock_store_factory.get_manager.return_value = mock_store_manager

        mock_output_def = StrTemplateOutputDefinition(output_name="deployment_id", value="dep-001")
        mock_outputs_cls.return_value.get_declared_output_def.return_value = mock_output_def

        handler.push_to_store()

        handler._store_access_manager.configure.assert_called_once_with(
            mock_store_info,
            "test-template-dep-001",
            handler.display_manager,
        )
        mock_store_manager.push.assert_called_once()

    @patch("jupyter_deploy.handlers.project.up_handler.write_store_config")
    @patch("jupyter_deploy.handlers.project.up_handler.StoreManagerFactory")
    @patch("jupyter_deploy.handlers.project.up_handler.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_push_to_store_raises_on_migration_failure(
        self,
        mock_cwd: Mock,
        mock_retrieve_manifest: Mock,
        mock_tf_handler_cls: Mock,
        mock_outputs_cls: Mock,
        mock_store_factory: Mock,
        mock_write_config: Mock,
    ) -> None:
        handler = self._setup_handler(mock_cwd, mock_retrieve_manifest, mock_tf_handler_cls)
        handler._store_access_manager = Mock()
        handler._store_access_manager.is_configured.return_value = False
        handler._store_access_manager.configure.side_effect = ProjectStoreAccessConfigurationError("migration failed")

        mock_store_manager = Mock()
        mock_store_info = StoreInfo(store_type=StoreType.S3_DDB, store_id="discovered-bucket", location="us-east-1")
        mock_store_manager.find_store.return_value = mock_store_info
        mock_store_factory.get_manager.return_value = mock_store_manager

        mock_output_def = StrTemplateOutputDefinition(output_name="deployment_id", value="dep-001")
        mock_outputs_cls.return_value.get_declared_output_def.return_value = mock_output_def

        with self.assertRaises(ProjectStoreAccessConfigurationError):
            handler.push_to_store()

        mock_store_manager.push.assert_not_called()

    @patch("jupyter_deploy.handlers.project.up_handler.StoreManagerFactory")
    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_push_to_store_without_project_store_warns_and_returns(
        self,
        mock_cwd: Mock,
        mock_retrieve_manifest: Mock,
        mock_tf_handler_cls: Mock,
        mock_store_factory: Mock,
    ) -> None:
        mock_display = Mock()
        mock_cwd.return_value = Path("/mock/cwd")
        mock_retrieve_manifest.return_value = self.mock_manifest_no_store
        mock_tf_handler = Mock()
        mock_tf_handler.engine_dir_path = Path("/mock/cwd/engine")
        mock_tf_handler.apply.return_value = None
        mock_tf_handler_cls.return_value = mock_tf_handler

        handler = UpHandler(display_manager=mock_display)
        handler.push_to_store()

        mock_display.warning.assert_called_once()
        mock_store_factory.get_manager.assert_not_called()

    @patch("jupyter_deploy.handlers.project.up_handler.write_store_config")
    @patch("jupyter_deploy.handlers.project.up_handler.StoreManagerFactory")
    @patch("jupyter_deploy.handlers.project.up_handler.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_push_to_store_raises_when_find_store_fails(
        self,
        mock_cwd: Mock,
        mock_retrieve_manifest: Mock,
        mock_tf_handler_cls: Mock,
        mock_outputs_cls: Mock,
        mock_store_factory: Mock,
        mock_write_config: Mock,
    ) -> None:
        handler = self._setup_handler(mock_cwd, mock_retrieve_manifest, mock_tf_handler_cls)
        handler._store_access_manager = Mock()
        handler._store_access_manager.is_configured.return_value = True

        mock_store_manager = Mock()
        mock_store_manager.find_store.side_effect = ProjectStoreNotFoundError("No S3 bucket project store found")
        mock_store_factory.get_manager.return_value = mock_store_manager

        mock_output_def = StrTemplateOutputDefinition(output_name="deployment_id", value="dep-001")
        mock_outputs_cls.return_value.get_declared_output_def.return_value = mock_output_def

        with self.assertRaises(ProjectStoreNotFoundError):
            handler.push_to_store()

        mock_store_manager.push.assert_not_called()
        mock_write_config.assert_not_called()

    @patch("jupyter_deploy.handlers.project.up_handler.write_store_config")
    @patch("jupyter_deploy.handlers.project.up_handler.StoreManagerFactory")
    @patch("jupyter_deploy.handlers.project.up_handler.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_push_to_store_raises_when_write_store_config_fails(
        self,
        mock_cwd: Mock,
        mock_retrieve_manifest: Mock,
        mock_tf_handler_cls: Mock,
        mock_outputs_cls: Mock,
        mock_store_factory: Mock,
        mock_write_config: Mock,
    ) -> None:
        handler = self._setup_handler(mock_cwd, mock_retrieve_manifest, mock_tf_handler_cls)
        handler._store_access_manager = Mock()
        handler._store_access_manager.is_configured.return_value = True

        mock_store_manager = Mock()
        mock_store_info = StoreInfo(store_type=StoreType.S3_DDB, store_id="discovered-bucket", location="us-east-1")
        mock_store_manager.find_store.return_value = mock_store_info
        mock_store_factory.get_manager.return_value = mock_store_manager

        mock_output_def = StrTemplateOutputDefinition(output_name="deployment_id", value="dep-001")
        mock_outputs_cls.return_value.get_declared_output_def.return_value = mock_output_def

        mock_write_config.side_effect = PermissionError("Permission denied: .jd/store.yaml")

        with self.assertRaises(PermissionError):
            handler.push_to_store()

        # write_store_config runs before push, so push should NOT have been called
        mock_store_manager.push.assert_not_called()

    @patch("jupyter_deploy.handlers.project.up_handler.StoreManagerFactory")
    @patch("jupyter_deploy.handlers.project.up_handler.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_store_config")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_push_to_store_raises_when_retrieve_store_config_fails(
        self,
        mock_cwd: Mock,
        mock_retrieve_manifest: Mock,
        mock_retrieve_store_config: Mock,
        mock_tf_handler_cls: Mock,
        mock_outputs_cls: Mock,
        mock_store_factory: Mock,
    ) -> None:
        mock_cwd.return_value = Path("/mock/cwd")
        mock_retrieve_manifest.return_value = self.mock_manifest
        mock_tf_handler = Mock()
        mock_tf_handler.engine_dir_path = Path("/mock/cwd/engine")
        mock_tf_handler.apply.return_value = None
        mock_tf_handler_cls.return_value = mock_tf_handler

        # Simulate corrupt .jd/store.yaml
        mock_retrieve_store_config.side_effect = PermissionError("Permission denied: .jd/store.yaml")

        handler = UpHandler(display_manager=NullDisplay())

        with self.assertRaises(PermissionError):
            handler.push_to_store()

        mock_store_factory.get_manager.assert_not_called()

    @patch("jupyter_deploy.handlers.project.up_handler.write_store_config")
    @patch("jupyter_deploy.handlers.project.up_handler.StoreManagerFactory")
    @patch("jupyter_deploy.handlers.project.up_handler.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_push_to_store_raises_when_push_fails(
        self,
        mock_cwd: Mock,
        mock_retrieve_manifest: Mock,
        mock_tf_handler_cls: Mock,
        mock_outputs_cls: Mock,
        mock_store_factory: Mock,
        mock_write_config: Mock,
    ) -> None:
        handler = self._setup_handler(mock_cwd, mock_retrieve_manifest, mock_tf_handler_cls)
        handler._store_access_manager = Mock()
        handler._store_access_manager.is_configured.return_value = True

        mock_store_manager = Mock()
        mock_store_info = StoreInfo(store_type=StoreType.S3_DDB, store_id="discovered-bucket", location="us-east-1")
        mock_store_manager.find_store.return_value = mock_store_info
        mock_store_manager.push.side_effect = RuntimeError("S3 upload failed")
        mock_store_factory.get_manager.return_value = mock_store_manager

        mock_output_def = StrTemplateOutputDefinition(output_name="deployment_id", value="dep-001")
        mock_outputs_cls.return_value.get_declared_output_def.return_value = mock_output_def

        with self.assertRaises(RuntimeError) as ctx:
            handler.push_to_store()

        self.assertEqual(str(ctx.exception), "S3 upload failed")
        # write_store_config should have been called before push
        mock_write_config.assert_called_once()
