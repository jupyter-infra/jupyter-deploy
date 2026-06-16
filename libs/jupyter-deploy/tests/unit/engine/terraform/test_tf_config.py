import subprocess
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import Mock, patch

from pydantic import ValidationError

from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.engine.terraform.tf_config import TerraformConfigHandler
from jupyter_deploy.engine.terraform.tf_constants import (
    TF_DEFAULT_PLAN_FILENAME,
    TF_ENGINE_DIR,
    TF_PRESETS_DIR,
)
from jupyter_deploy.engine.terraform.tf_enums import TerraformSequenceId
from jupyter_deploy.engine.vardefs import (
    BoolTemplateVariableDefinition,
    DictStrTemplateVariableDefinition,
    FloatTemplateVariableDefinition,
    ListStrTemplateVariableDefinition,
    StrTemplateVariableDefinition,
    TemplateVariableDefinition,
)
from jupyter_deploy.exceptions import ReadConfigurationError, SupervisedExecutionError
from jupyter_deploy.handlers.command_history_handler import LogCleanupError


class TestTerraformConfigHandler(unittest.TestCase):
    MOCK_OVERRIDE_PRESET_PATH = Path("/mock/path/engine/jdinputs.preset.override.tfvars")
    MOCK_RECORD_VARS_PATH = Path("/mock/path/engine/jdinputs.auto.tfvars")
    MOCK_RECORD_SECRETS_PATH = Path("/mock/path/engine/jdinputs.secrets.auto.tfvars")

    def get_mock_command_history(self) -> Mock:
        """Return a mock CommandHistoryHandler."""
        mock_history = Mock()
        mock_history.create_log_file.return_value = Path("/mock/path/.jd-history/config/20260129-143022.log")
        mock_history.clear_logs.return_value = Mock()  # Returns cleanup result
        return mock_history

    def get_mock_variable_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        mock_handler = Mock()
        mock_get_recorded_variables_filepath = Mock()
        mock_get_recorded_secrets_filepath = Mock()
        mock_get_staging_variables_filepath = Mock()
        mock_get_staging_secrets_filepath = Mock()
        mock_reset_recorded_variables = Mock()
        mock_reset_recorded_secrets = Mock()
        mock_sync_engine_varfiles_to_staging = Mock()
        mock_discard_staging = Mock()
        mock_sync_variables_config = Mock()
        mock_get_template_variables = Mock()
        mock_update_variable_records = Mock()
        mock_create_filtered_preset_file = Mock()
        mock_nullify_failed_variables = Mock(return_value=[])

        mock_handler.get_recorded_variables_filepath = mock_get_recorded_variables_filepath
        mock_handler.get_recorded_secrets_filepath = mock_get_recorded_secrets_filepath
        mock_handler.get_staging_variables_filepath = mock_get_staging_variables_filepath
        mock_handler.get_staging_secrets_filepath = mock_get_staging_secrets_filepath
        mock_handler.reset_recorded_variables = mock_reset_recorded_variables
        mock_handler.reset_recorded_secrets = mock_reset_recorded_secrets
        mock_handler.sync_engine_varfiles_to_staging = mock_sync_engine_varfiles_to_staging
        mock_handler.discard_staging = mock_discard_staging
        mock_handler.sync_project_variables_config = mock_sync_variables_config
        mock_handler.get_template_variables = mock_get_template_variables
        mock_handler.update_variable_records = mock_update_variable_records
        mock_handler.create_filtered_preset_file = mock_create_filtered_preset_file
        mock_handler.nullify_failed_variables = mock_nullify_failed_variables

        mock_get_recorded_variables_filepath.return_value = TestTerraformConfigHandler.MOCK_RECORD_VARS_PATH
        mock_get_recorded_secrets_filepath.return_value = TestTerraformConfigHandler.MOCK_RECORD_SECRETS_PATH
        # Staging paths return non-existent paths by default (no staging file to add as -var-file)
        mock_get_staging_variables_filepath.return_value = Path("/tmp/nonexistent-staging-vars.tfvars")
        mock_get_staging_secrets_filepath.return_value = Path("/tmp/nonexistent-staging-secrets.tfvars")
        mock_create_filtered_preset_file.return_value = TestTerraformConfigHandler.MOCK_OVERRIDE_PRESET_PATH

        return mock_handler, {
            "get_recorded_variables_filepath": mock_get_recorded_variables_filepath,
            "get_recorded_secrets_filepath": mock_get_recorded_secrets_filepath,
            "get_staging_variables_filepath": mock_get_staging_variables_filepath,
            "get_staging_secrets_filepath": mock_get_staging_secrets_filepath,
            "reset_recorded_variables": mock_reset_recorded_variables,
            "reset_recorded_secrets": mock_reset_recorded_secrets,
            "sync_engine_varfiles_to_staging": mock_sync_engine_varfiles_to_staging,
            "discard_staging": mock_discard_staging,
            "sync_project_variables_config": mock_sync_variables_config,
            "get_template_variables": mock_get_template_variables,
            "update_variables_record": mock_update_variable_records,
            "create_filtered_preset_file": mock_create_filtered_preset_file,
            "nullify_failed_variables": mock_nullify_failed_variables,
        }

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_class_can_instantiate(self, mock_variable_handler_cls: Mock) -> None:
        # Arrange
        path = Path("/fake/path")
        manifest = Mock()
        mock_history = self.get_mock_command_history()

        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler
        handler = TerraformConfigHandler(path, manifest, mock_history, NullDisplay())

        # Assert
        self.assertIsNotNone(handler)
        self.assertEqual(handler.plan_out_path, path / TF_ENGINE_DIR / TF_DEFAULT_PLAN_FILENAME)
        self.assertEqual(handler.project_manifest, manifest)
        self.assertEqual(handler.tf_variables_handler, mock_vars_handler)

        # expensive methods of EngineVariablesHandler are not called
        mock_vars_fns["get_template_variables"].assert_not_called()
        mock_vars_fns["update_variables_record"].assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_class_uses_custom_output_file_when_provided(self, mock_variable_handler_cls: Mock) -> None:
        # Arrange
        path = Path("/fake/path")
        manifest = Mock()
        custom_output = "custom-output-file"
        mock_vars_handler, _ = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler
        handler = TerraformConfigHandler(
            path, manifest, self.get_mock_command_history(), NullDisplay(), output_filename=custom_output
        )

        # Assert
        self.assertIsNotNone(handler)
        self.assertEqual(handler.plan_out_path, path / TF_ENGINE_DIR / custom_output)
        self.assertEqual(handler.tf_variables_handler, mock_vars_handler)

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_verify_preset_exists_calls_fs_util(self, mock_variable_handler_cls: Mock, mock_file_exists: Mock) -> None:
        # Arrange
        path = Path("/fake/path")
        mock_vars_handler, _ = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler
        handler = TerraformConfigHandler(
            path, Mock(), command_history_handler=self.get_mock_command_history(), display_manager=NullDisplay()
        )

        # Act
        handler.verify_preset_exists("all")

        # Assert
        mock_file_exists.assert_called_once_with(
            file_path=path / TF_ENGINE_DIR / TF_PRESETS_DIR / "defaults-all.tfvars"
        )

    @patch("jupyter_deploy.fs_utils.find_matching_filenames")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_list_presets_calls_fs_util(self, mock_variable_handler_cls: Mock, mock_find: Mock) -> None:
        mock_find.return_value = [
            "defaults-all.tfvars",
            "defaults-base.tfvars",
            "defaults-all-except-instance.tfvars",
        ]

        # Arrange
        path = Path("/fake/path")
        mock_vars_handler, _ = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler
        handler = TerraformConfigHandler(
            path, Mock(), command_history_handler=self.get_mock_command_history(), display_manager=NullDisplay()
        )

        # Act
        presets = handler.list_presets()

        # Assert
        self.assertEqual(sorted(["all", "all-except-instance", "base", "none"]), sorted(presets))
        mock_find.assert_called_once_with(
            dir_path=handler.engine_dir_path / TF_PRESETS_DIR,
            file_pattern="defaults-*.tfvars",
        )

    @patch("jupyter_deploy.fs_utils.find_matching_filenames")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_list_presets_always_returns_none(self, mock_variable_handler_cls: Mock, mock_find: Mock) -> None:
        mock_find.return_value = []

        # Arrange
        path = Path("/fake/path")
        mock_vars_handler, _ = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler
        handler = TerraformConfigHandler(
            path, Mock(), command_history_handler=self.get_mock_command_history(), display_manager=NullDisplay()
        )

        # Act
        presets = handler.list_presets()

        # Assert
        self.assertEqual(["none"], presets)

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_reset_recorded_variables_calls_vars_handler(self, mock_variable_handler_cls: Mock) -> None:
        # Arrange
        path = Path("/fake/path")
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler
        handler = TerraformConfigHandler(
            path, Mock(), command_history_handler=self.get_mock_command_history(), display_manager=NullDisplay()
        )

        # Act
        handler.reset_recorded_variables()

        # Assert
        mock_vars_fns["reset_recorded_variables"].assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_reset_recorded_secrets_calls_vars_handler(self, mock_variable_handler_cls: Mock) -> None:
        # Arrange
        path = Path("/fake/path")
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler
        handler = TerraformConfigHandler(
            path, Mock(), command_history_handler=self.get_mock_command_history(), display_manager=NullDisplay()
        )

        # Act
        handler.reset_recorded_secrets()

        # Assert
        mock_vars_fns["reset_recorded_secrets"].assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_calls_tf_init(self, mock_variable_handler_cls: Mock, mock_create_executor: Mock) -> None:
        # Arrange
        mock_vars_handler, _ = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor for both init and plan
        mock_executor = Mock()
        mock_executor.execute.return_value = 0  # Return code 0 (success)
        mock_create_executor.return_value = mock_executor

        handler = TerraformConfigHandler(Path("/fake/path"), Mock(), self.get_mock_command_history(), NullDisplay())

        # Act
        handler.configure()

        # Assert - both init and plan executors should be created
        self.assertEqual(mock_create_executor.call_count, 2)
        init_call = mock_create_executor.mock_calls[0]
        self.assertEqual(init_call[2]["exec_dir"], Path("/fake/path/engine"))

        # Verify execute was called on the executor
        self.assertEqual(mock_executor.execute.call_count, 2)

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_passes_reconfigure_when_backend_tf_exists(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        # Arrange
        mock_vars_handler, _ = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        mock_executor = Mock()
        mock_executor.execute.return_value = 0
        mock_create_executor.return_value = mock_executor

        path = Path("/fake/path")
        handler = TerraformConfigHandler(path, Mock(), self.get_mock_command_history(), NullDisplay())

        # Simulate backend.tf existing
        with patch.object(Path, "exists", return_value=True):
            handler.configure()

        # Assert - init command should include -reconfigure
        init_execute_call = mock_executor.execute.call_args_list[0]
        init_cmd = init_execute_call[0][0]
        self.assertEqual(init_cmd, ["terraform", "init", "-reconfigure"])

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_does_not_pass_reconfigure_without_backend_tf(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        # Arrange
        mock_vars_handler, _ = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        mock_executor = Mock()
        mock_executor.execute.return_value = 0
        mock_create_executor.return_value = mock_executor

        path = Path("/fake/path")
        handler = TerraformConfigHandler(path, Mock(), self.get_mock_command_history(), NullDisplay())

        # Simulate backend.tf NOT existing
        with patch.object(Path, "exists", return_value=False):
            handler.configure()

        # Assert - init command should NOT include -reconfigure
        init_execute_call = mock_executor.execute.call_args_list[0]
        init_cmd = init_execute_call[0][0]
        self.assertEqual(init_cmd, ["terraform", "init"])

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_calls_tf_plan_with_a_named_plan(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        # Arrange
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor for both init and plan - both succeed
        mock_executor = Mock()
        mock_executor.execute.return_value = 0  # Return code 0 (success)
        mock_create_executor.return_value = mock_executor

        handler = TerraformConfigHandler(Path("/fake/path"), Mock(), self.get_mock_command_history(), NullDisplay())

        # Act
        handler.configure()

        # Assert - configure completed successfully (no exception raised)
        self.assertEqual(mock_create_executor.call_count, 2)  # Init and plan
        self.assertEqual(mock_executor.execute.call_count, 2)
        mock_vars_fns["sync_engine_varfiles_to_staging"].assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_calls_tf_plan_passes_preset(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        # Arrange
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor for both init and plan - both succeed
        mock_executor = Mock()
        mock_executor.execute.return_value = 0  # Return code 0 (success)
        mock_create_executor.return_value = mock_executor

        path = Path("/fake/path")
        handler = TerraformConfigHandler(
            path, Mock(), command_history_handler=self.get_mock_command_history(), display_manager=NullDisplay()
        )

        # Act
        handler.configure(preset_name="all")

        # Assert - configure completed successfully (no exception raised)
        self.assertEqual(mock_create_executor.call_count, 2)  # Init and plan

        # Verify preset file was created
        expect_called_path = path / TF_ENGINE_DIR / TF_PRESETS_DIR / "defaults-all.tfvars"
        mock_vars_fns["sync_engine_varfiles_to_staging"].assert_called_once()
        mock_vars_fns["create_filtered_preset_file"].assert_called_once_with(expect_called_path)

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_calls_tf_plan_with_variable_override(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        # Arrange
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor for both init and plan - both succeed
        mock_executor = Mock()
        mock_executor.execute.return_value = 0  # Return code 0 (success)
        mock_create_executor.return_value = mock_executor

        path = Path("/fake/path")
        handler = TerraformConfigHandler(
            path, Mock(), command_history_handler=self.get_mock_command_history(), display_manager=NullDisplay()
        )

        mock_var1 = Mock(spec=StrTemplateVariableDefinition)
        mock_var2 = Mock(spec=FloatTemplateVariableDefinition)
        mock_var3 = Mock(spec=BoolTemplateVariableDefinition)
        mock_var4 = Mock(spec=ListStrTemplateVariableDefinition)
        mock_var5 = Mock(spec=DictStrTemplateVariableDefinition)
        mock_variables: dict[str, TemplateVariableDefinition] = OrderedDict(
            {"var1": mock_var1, "var2": mock_var2, "var3": mock_var3, "var4": mock_var4, "var5": mock_var5}
        )
        for idx, key in enumerate(mock_variables.keys()):
            mock_variables[key].variable_name = f"var{idx + 1}"

        mock_var1.assigned_value = "some-value"
        mock_var2.assigned_value = 3.1459
        mock_var3.assigned_value = True
        mock_var4.assigned_value = ["email1@example.com", "email2@example.com"]
        mock_var5.assigned_value = {"Key1": "Val1", "Key2": "Val2"}

        # Act
        handler.configure(preset_name="all", variable_overrides=mock_variables)

        # Assert - configure completed successfully (no exception raised)
        self.assertEqual(mock_create_executor.call_count, 2)  # Init and plan
        mock_vars_fns["sync_engine_varfiles_to_staging"].assert_called_once()
        mock_vars_fns["create_filtered_preset_file"].assert_called_once()

        # Verify the executor was called with the plan commands
        plan_executor_call = mock_executor.execute.mock_calls[1]  # Second call is for plan
        plan_cmds = plan_executor_call[1][0]
        plan_cmds_len = len(plan_cmds)

        # Verify variable overrides were passed to terraform plan
        self.assertEqual("-var", plan_cmds[plan_cmds_len - 10])
        self.assertEqual("var1=some-value", plan_cmds[plan_cmds_len - 9])

        self.assertEqual("-var", plan_cmds[plan_cmds_len - 8])
        self.assertEqual("var2=3.1459", plan_cmds[plan_cmds_len - 7])

        self.assertEqual("-var", plan_cmds[plan_cmds_len - 6])
        self.assertEqual("var3=true", plan_cmds[plan_cmds_len - 5])

        self.assertEqual("-var", plan_cmds[plan_cmds_len - 4])
        self.assertEqual('var4=["email1@example.com", "email2@example.com"]', plan_cmds[plan_cmds_len - 3])

        self.assertEqual("-var", plan_cmds[plan_cmds_len - 2])
        self.assertEqual('var5={"Key1": "Val1", "Key2": "Val2"}', plan_cmds[plan_cmds_len - 1])

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_does_not_call_plan_if_tf_init_fails(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        # Arrange
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor for init - fails with non-zero return code
        mock_executor = Mock()
        mock_executor.execute.return_value = 1  # Return code 1 (failure)
        mock_create_executor.return_value = mock_executor

        handler = TerraformConfigHandler(Path("/fake/path"), Mock(), self.get_mock_command_history(), NullDisplay())

        # Act & Assert - should raise ExecutionError
        with self.assertRaises(SupervisedExecutionError) as context:
            handler.configure()

        self.assertEqual(context.exception.retcode, 1)
        self.assertEqual(context.exception.command, "config")
        self.assertEqual(mock_create_executor.call_count, 1)  # Only init should be called
        self.assertEqual(mock_executor.execute.call_count, 1)
        mock_vars_fns["sync_engine_varfiles_to_staging"].assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_does_not_call_plan_if_tf_init_timesout(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        # Arrange
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor for init - simulate timeout by raising TimeoutError
        mock_executor = Mock()
        mock_executor.execute.side_effect = TimeoutError("Command timed out")
        mock_create_executor.return_value = mock_executor

        handler = TerraformConfigHandler(Path("/fake/path"), Mock(), self.get_mock_command_history(), NullDisplay())

        # Act & Assert - should raise TimeoutError
        with self.assertRaises(TimeoutError):
            handler.configure()

        self.assertEqual(mock_create_executor.call_count, 1)  # Only init should be called
        self.assertEqual(mock_executor.execute.call_count, 1)
        mock_vars_fns["sync_engine_varfiles_to_staging"].assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_print_to_console_if_plan_fails(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        # Arrange
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor: init succeeds, plan fails
        mock_executor = Mock()
        mock_executor.execute.side_effect = [0, 1]  # init=0 (success), plan=1 (failure)
        mock_create_executor.return_value = mock_executor

        handler = TerraformConfigHandler(Path("/fake/path"), Mock(), self.get_mock_command_history(), NullDisplay())

        # Act & Assert - should raise ExecutionError
        with self.assertRaises(SupervisedExecutionError) as context:
            handler.configure()

        self.assertEqual(context.exception.retcode, 1)
        self.assertEqual(context.exception.command, "config")
        self.assertEqual(mock_create_executor.call_count, 2)  # Both init and plan
        self.assertEqual(mock_executor.execute.call_count, 2)
        mock_vars_fns["sync_engine_varfiles_to_staging"].assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_print_to_console_if_plan_timesout(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        # Arrange
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor: init succeeds, plan times out
        mock_executor = Mock()
        mock_executor.execute.side_effect = [0, TimeoutError("Command timed out")]  # init=0 (success), plan=timeout
        mock_create_executor.return_value = mock_executor

        handler = TerraformConfigHandler(Path("/fake/path"), Mock(), self.get_mock_command_history(), NullDisplay())

        # Act & Assert - should raise TimeoutError
        with self.assertRaises(TimeoutError):
            handler.configure()

        self.assertEqual(mock_create_executor.call_count, 2)  # Both init and plan
        self.assertEqual(mock_executor.execute.call_count, 2)
        mock_vars_fns["sync_engine_varfiles_to_staging"].assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_persists_variable_overrides_to_yaml_before_plan(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        """CLI --variable values are written to variables.yaml before plan runs,
        so they survive even if terraform plan fails."""
        # Arrange
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor: init succeeds, plan fails
        mock_executor = Mock()
        mock_executor.execute.side_effect = [0, 1]
        mock_create_executor.return_value = mock_executor

        # Create variable overrides (simulating --region us-east-1 --instance-type t3.large)
        region_override = Mock()
        region_override.assigned_value = "us-east-1"
        instance_override = Mock()
        instance_override.assigned_value = "t3.large"

        # to_tf_var_option returns the CLI args for terraform
        with patch("jupyter_deploy.engine.terraform.tf_vardefs.to_tf_var_option", return_value=["-var=x"]):
            handler = TerraformConfigHandler(Path("/fake/path"), Mock(), self.get_mock_command_history(), NullDisplay())

            # Act — plan fails, but overrides should still be persisted
            with self.assertRaises(SupervisedExecutionError):
                handler.configure(variable_overrides={"region": region_override, "instance_type": instance_override})

        # Assert — sync_project_variables_config was called with the CLI values
        # BEFORE the plan ran (so they survive the failure)
        mock_vars_fns["sync_project_variables_config"].assert_called_once_with(
            {"region": "us-east-1", "instance_type": "t3.large"}
        )
        # Staging was discarded after the failed plan
        mock_vars_fns["discard_staging"].assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_plan_metadata.save_plan_metadata")
    @patch("jupyter_deploy.engine.terraform.tf_plan.extract_resource_counts_from_plan")
    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.engine.terraform.tf_plan.format_plan_variables")
    @patch("jupyter_deploy.engine.terraform.tf_plan.extract_variables_from_plan")
    @patch("jupyter_deploy.engine.terraform.tf_plan.extract_plan")
    @patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_record_saves_vars_and_secrets_and_syncs_vars_only(
        self,
        mock_variable_handler_cls: Mock,
        mock_capture: Mock,
        mock_parse: Mock,
        mock_extract: Mock,
        mock_format: Mock,
        mock_write: Mock,
        mock_extract_counts: Mock,
        mock_save_metadata: Mock,
    ) -> None:
        # Arrange
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        mock_capture.return_value = "i-am-a-serialized-plan"
        mock_plan = Mock()
        mock_plan.resource_changes = []
        mock_parse.return_value = mock_plan
        mock_extract_counts.return_value = (5, 3, 2)
        mock_var1 = Mock()
        mock_var2 = Mock()
        mock_secret = Mock()
        mock_var1.value = 1
        mock_var2.value = "two"
        mock_secret.value = "nuclear-codes"
        mock_extract.return_value = ({"var1": mock_var1, "var2": mock_var2}, {"secret1": mock_secret})
        mock_format.side_effect = [["var1 = 1\n", 'var2 = "two"\n'], ['secret1 = "nuclear-codes"\n']]

        path = Path("/fake/path")
        handler = TerraformConfigHandler(
            path, Mock(), command_history_handler=self.get_mock_command_history(), display_manager=NullDisplay()
        )

        # Act
        handler.record()

        # Assert — plan parsed once, metadata saved
        mock_capture.assert_called_once()
        mock_parse.assert_called_once_with("i-am-a-serialized-plan")
        mock_extract_counts.assert_called_once_with(mock_plan)
        mock_save_metadata.assert_called_once()
        mock_extract.assert_called_once_with(mock_plan)

        # Both vars and secrets files are written
        self.assertEqual(mock_format.call_count, 2)
        self.assertEqual(mock_write.call_count, 2)

        mock_write_vars_call = mock_write.mock_calls[0]
        self.assertEqual(mock_write_vars_call[1][0], TestTerraformConfigHandler.MOCK_RECORD_VARS_PATH)
        self.assertIn("var1 = 1\n", mock_write_vars_call[1][1])
        self.assertIn('var2 = "two"\n', mock_write_vars_call[1][1])

        mock_write_secrets_call = mock_write.mock_calls[1]
        self.assertEqual(mock_write_secrets_call[1][0], TestTerraformConfigHandler.MOCK_RECORD_SECRETS_PATH)
        self.assertIn('secret1 = "nuclear-codes"\n', mock_write_secrets_call[1][1])

        # Only vars (not secrets) are synced back to variables.yaml
        mock_vars_fns["sync_project_variables_config"].assert_called_once_with({"var1": 1, "var2": "two"})

    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_catches_plan_retrieve_errors_and_print(
        self,
        mock_variable_handler_cls: Mock,
        mock_capture: Mock,
        mock_write: Mock,
    ) -> None:
        # Arrange
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler
        mock_capture.side_effect = subprocess.CalledProcessError(
            1, ["terraform", "show", "-json"], "something went wrong", None
        )
        handler = TerraformConfigHandler(Path("/fake/path"), Mock(), self.get_mock_command_history(), NullDisplay())

        # Act & Assert
        with self.assertRaises(ReadConfigurationError):
            handler.record()

        mock_write.assert_not_called()
        mock_vars_fns["sync_project_variables_config"].assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_plan_metadata.save_plan_metadata")
    @patch("jupyter_deploy.engine.terraform.tf_plan.extract_resource_counts_from_plan")
    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.engine.terraform.tf_plan.extract_variables_from_plan")
    @patch("jupyter_deploy.engine.terraform.tf_plan.extract_plan")
    @patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_catches_plan_validation_errors(
        self,
        mock_variable_handler_cls: Mock,
        mock_capture: Mock,
        mock_parse: Mock,
        mock_extract: Mock,
        mock_write: Mock,
        mock_extract_counts: Mock,
        mock_save_metadata: Mock,
    ) -> None:
        # Arrange
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler
        mock_capture.return_value = '{"resource_changes": []}'  # Valid JSON for metadata extraction
        mock_plan = Mock()
        mock_parse.return_value = mock_plan
        mock_extract_counts.return_value = (5, 3, 2)
        mock_extract.side_effect = ValidationError("some error", [])
        handler = TerraformConfigHandler(Path("/fake/path"), Mock(), self.get_mock_command_history(), NullDisplay())

        # Act & Assert
        with self.assertRaises(ReadConfigurationError):
            handler.record()

        mock_capture.assert_called_once()
        mock_parse.assert_called_once()
        mock_extract_counts.assert_called_once()
        mock_save_metadata.assert_called_once()
        mock_extract.assert_called_once()
        mock_write.assert_not_called()
        mock_vars_fns["sync_project_variables_config"].assert_not_called()

    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.engine.terraform.tf_plan.extract_plan")
    @patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_catches_plan_json_parse_errors(
        self,
        mock_variable_handler_cls: Mock,
        mock_capture: Mock,
        mock_parse: Mock,
        mock_write: Mock,
    ) -> None:
        # Arrange
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler
        mock_capture.return_value = "i-am-a-serialized-plan"
        mock_parse.side_effect = ValueError("Invalid JSON")
        handler = TerraformConfigHandler(Path("/fake/path"), Mock(), self.get_mock_command_history(), NullDisplay())

        # Act & Assert
        with self.assertRaises(ReadConfigurationError):
            handler.record()

        mock_capture.assert_called_once()
        mock_parse.assert_called_once()
        mock_write.assert_not_called()
        mock_vars_fns["sync_project_variables_config"].assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformSupervisedExecutionCallback")
    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_with_display_manager_uses_supervised_callback(
        self,
        mock_variable_handler_cls: Mock,
        mock_create_executor: Mock,
        mock_callback_cls: Mock,
    ) -> None:
        """Test that configure with display_manager uses TerraformSupervisedExecutionCallback."""
        # Arrange
        mock_vars_handler, _ = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor for both init and plan - both succeed
        mock_executor = Mock()
        mock_executor.execute.return_value = 0
        mock_create_executor.return_value = mock_executor

        # Mock callback
        mock_callback = Mock()
        mock_callback_cls.return_value = mock_callback

        # Create handler WITH display_manager
        mock_display_manager = Mock()
        mock_display_manager.is_pass_through.return_value = False  # Use supervised callbacks
        handler = TerraformConfigHandler(
            Path("/fake/path"),
            Mock(),
            self.get_mock_command_history(),
            display_manager=mock_display_manager,  # type: ignore[arg-type]
        )

        # Act
        handler.configure()

        # Assert - configure completed successfully (no exception raised)

        # Verify TerraformSupervisedExecutionCallback was created twice (init and plan)
        self.assertEqual(mock_callback_cls.call_count, 2)

        # Verify init callback
        init_callback_call = mock_callback_cls.call_args_list[0]
        self.assertEqual(init_callback_call.kwargs["display_manager"], mock_display_manager)
        self.assertEqual(init_callback_call.kwargs["sequence_id"], TerraformSequenceId.config_init)

        # Verify plan callback
        plan_callback_call = mock_callback_cls.call_args_list[1]
        self.assertEqual(plan_callback_call.kwargs["display_manager"], mock_display_manager)
        self.assertEqual(plan_callback_call.kwargs["sequence_id"], TerraformSequenceId.config_plan)

        # Verify executor was created with the supervised callback
        self.assertEqual(mock_create_executor.call_count, 2)
        init_executor_call = mock_create_executor.call_args_list[0]
        self.assertEqual(init_executor_call.kwargs["execution_callback"], mock_callback)

        plan_executor_call = mock_create_executor.call_args_list[1]
        self.assertEqual(plan_executor_call.kwargs["execution_callback"], mock_callback)

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformNoopExecutionCallback")
    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_without_display_manager_uses_noop_callback(
        self,
        mock_variable_handler_cls: Mock,
        mock_create_executor: Mock,
        mock_noop_callback_cls: Mock,
    ) -> None:
        """Test that configure without display_manager uses TerraformNoopExecutionCallback."""
        # Arrange
        mock_vars_handler, _ = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor for both init and plan - both succeed
        mock_executor = Mock()
        mock_executor.execute.return_value = 0
        mock_create_executor.return_value = mock_executor

        # Mock noop callback
        mock_noop = Mock()
        mock_noop_callback_cls.return_value = mock_noop

        # Create handler with pass-through display_manager (verbose mode)
        mock_display_manager = Mock()
        mock_display_manager.is_pass_through.return_value = True  # Use noop callbacks
        handler = TerraformConfigHandler(
            Path("/fake/path"),
            Mock(),
            self.get_mock_command_history(),
            display_manager=mock_display_manager,  # type: ignore[arg-type]
        )

        # Act
        handler.configure()

        # Assert - configure completed successfully (no exception raised)

        # Verify TerraformNoopExecutionCallback was created twice (init and plan)
        self.assertEqual(mock_noop_callback_cls.call_count, 2)

        # Verify executor was created with the noop callback
        self.assertEqual(mock_create_executor.call_count, 2)
        init_executor_call = mock_create_executor.call_args_list[0]
        self.assertEqual(init_executor_call.kwargs["execution_callback"], mock_noop)

        plan_executor_call = mock_create_executor.call_args_list[1]
        self.assertEqual(plan_executor_call.kwargs["execution_callback"], mock_noop)

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_clears_old_logs_on_success(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        """Test that configure calls clear_logs on successful execution."""
        # Arrange
        mock_vars_handler, _ = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor for both init and plan - both succeed
        mock_executor = Mock()
        mock_executor.execute.return_value = 0
        mock_create_executor.return_value = mock_executor

        mock_history = self.get_mock_command_history()
        handler = TerraformConfigHandler(Path("/fake/path"), Mock(), mock_history, NullDisplay())

        # Act
        handler.configure()

        # Assert - clear_logs should be called after successful execution
        mock_history.clear_logs.assert_called_once_with("config")

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_does_not_clear_logs_on_failure(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        """Test that configure does NOT call clear_logs when plan fails."""
        # Arrange
        mock_vars_handler, _ = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor: init succeeds, plan fails
        mock_executor = Mock()
        mock_executor.execute.side_effect = [0, 1]
        mock_create_executor.return_value = mock_executor

        mock_history = self.get_mock_command_history()
        handler = TerraformConfigHandler(Path("/fake/path"), Mock(), mock_history, NullDisplay())

        # Act & Assert - should raise ExecutionError
        with self.assertRaises(SupervisedExecutionError):
            handler.configure()

        # Assert - clear_logs should NOT be called on failure
        mock_history.clear_logs.assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_bubbles_up_clear_logs_exception(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        """Test that configure bubbles up LogCleanupError from clear_logs."""
        # Arrange
        mock_vars_handler, _ = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor for both init and plan - both succeed
        mock_executor = Mock()
        mock_executor.execute.return_value = 0
        mock_create_executor.return_value = mock_executor

        mock_history = self.get_mock_command_history()
        mock_history.clear_logs.side_effect = LogCleanupError("Failed to delete 2 log file(s)")
        handler = TerraformConfigHandler(Path("/fake/path"), Mock(), mock_history, NullDisplay())

        # Act & Assert - should raise LogCleanupError from clear_logs
        with self.assertRaises(LogCleanupError) as context:
            handler.configure()

        self.assertEqual(str(context.exception), "Failed to delete 2 log file(s)")
        mock_history.clear_logs.assert_called_once_with("config")

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_nullifies_failed_variables_on_plan_failure(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        """On plan failure, variables that failed validation are nullified."""
        # Arrange
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler
        mock_vars_fns["nullify_failed_variables"].return_value = ["subdomain"]

        # Capture the plan callback so we can inject error lines into its buffer
        captured_callbacks: list[object] = []

        def factory_side_effect(**kwargs: object) -> Mock:
            captured_callbacks.append(kwargs.get("execution_callback"))
            mock_executor = Mock()
            # init=0 on first call, plan=1 on second
            if len(captured_callbacks) == 1:
                mock_executor.execute.return_value = 0
            else:
                # Inject validation error lines before returning failure
                callback = kwargs["execution_callback"]
                callback._line_buffer.extend(  # type: ignore[attr-defined]
                    [
                        "│ Error: Invalid value for variable",
                        '│   on variables.tf line 230, in variable "subdomain":',
                        "│ The subdomain must only contain letters.",
                    ]
                )
                mock_executor.execute.return_value = 1
            return mock_executor

        mock_create_executor.side_effect = factory_side_effect

        handler = TerraformConfigHandler(Path("/fake/path"), Mock(), self.get_mock_command_history(), NullDisplay())

        # Act
        with self.assertRaises(SupervisedExecutionError):
            handler.configure()

        # Assert — nullify_failed_variables was called with the extracted var name
        mock_vars_fns["nullify_failed_variables"].assert_called_once_with(["subdomain"])

    @patch("jupyter_deploy.engine.terraform.tf_supervised_executor_factory.create_terraform_executor")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_configure_does_not_nullify_on_plan_success(
        self, mock_variable_handler_cls: Mock, mock_create_executor: Mock
    ) -> None:
        """On plan success, nullify_failed_variables is NOT called."""
        # Arrange
        mock_vars_handler, mock_vars_fns = self.get_mock_variable_handler_and_fns()
        mock_variable_handler_cls.return_value = mock_vars_handler

        # Mock executor: init succeeds, plan succeeds
        mock_executor = Mock()
        mock_executor.execute.return_value = 0
        mock_create_executor.return_value = mock_executor

        handler = TerraformConfigHandler(Path("/fake/path"), Mock(), self.get_mock_command_history(), NullDisplay())

        # Act
        handler.configure()

        # Assert — nullify_failed_variables was NOT called
        mock_vars_fns["nullify_failed_variables"].assert_not_called()
