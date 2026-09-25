"""Unit tests for jupyter_deploy.exceptions module."""

import unittest

from jupyter_deploy.exceptions import (
    ConfigurationError,
    DownAutoApproveRequiredError,
    HostCommandInstructionError,
    ImageNotFoundError,
    ImageTagNotFoundError,
    IncompatibleHostStateError,
    InstructionError,
    InstructionNotFoundError,
    InteractiveSessionError,
    InteractiveSessionTimeoutError,
    InvalidInstructionArgumentError,
    InvalidInstructionResultError,
    InvalidManifestError,
    InvalidPresetError,
    InvalidServiceError,
    InvalidVariablesDotYamlError,
    JupyterDeployError,
    LogCleanupError,
    LogNotFoundError,
    ManifestNotADictError,
    ManifestNotFoundError,
    ManifestValueNotDeclaredError,
    NoProxyFoundError,
    OutputNotFoundError,
    ProjectIdNotAvailableError,
    ProjectOutputsNotAvailableError,
    ProjectStoreAccessConfigurationError,
    ProjectStoreNotFoundError,
    ProxyNotInstalledError,
    ProxyStartError,
    ReadConfigurationError,
    ReadManifestError,
    RequiredOutputNotFoundError,
    RequiredOutputTypeError,
    ResourcePollTimeoutError,
    SupervisedExecutionError,
    ToolRequiredError,
    UnreachableHostError,
    UnsupportedProviderRegionError,
    VariableNotFoundError,
    VolumeNotBackupableError,
    VolumeNotFoundError,
    WriteConfigurationError,
)


class TestJupyterDeployError(unittest.TestCase):
    """Test cases for the base JupyterDeployError exception."""

    def test_base_exception_with_message(self) -> None:
        """Test creating exception with a message."""
        error = JupyterDeployError("Test error message")
        self.assertEqual(str(error), "Test error message")
        self.assertIsInstance(error, Exception)

    def test_inheritance_chain(self) -> None:
        """Test that JupyterDeployError inherits from Exception."""
        error = JupyterDeployError("test")
        self.assertIsInstance(error, Exception)


class TestManifestErrors(unittest.TestCase):
    """Test cases for manifest-related exceptions."""

    def test_project_not_found_error(self) -> None:
        """Test ManifestNotFoundError creation and inheritance."""
        error = ManifestNotFoundError("Project not found")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, FileNotFoundError)
        self.assertEqual(str(error), "Project not found")

    def test_read_manifest_error(self) -> None:
        """Test ReadManifestError creation and inheritance."""
        error = ReadManifestError("Cannot read manifest")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, OSError)
        self.assertEqual(str(error), "Cannot read manifest")

    def test_invalid_manifest_error(self) -> None:
        """Test InvalidManifestError creation and inheritance."""
        error = InvalidManifestError("Invalid manifest")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, ValueError)

    def test_not_a_dict_error(self) -> None:
        """Test ManifestNotADictError is a subclass of InvalidManifestError."""
        error = ManifestNotADictError("Not a dict")
        self.assertIsInstance(error, InvalidManifestError)
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, ValueError)


class TestVariableErrors(unittest.TestCase):
    """Test cases for variable and configuration exceptions."""

    def test_invalid_variables_error(self) -> None:
        """Test InvalidVariablesDotYamlError creation and inheritance."""
        error = InvalidVariablesDotYamlError("Invalid variables.yaml file")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, ValueError)

    def test_variable_not_found_error(self) -> None:
        """Test VariableNotFoundError with variable name."""
        error = VariableNotFoundError("my_variable")
        self.assertEqual(error.variable_name, "my_variable")
        self.assertIn("my_variable", str(error))
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, KeyError)

    def test_output_not_found_error(self) -> None:
        """Test OutputNotFoundError with output name."""
        error = OutputNotFoundError("my_output")
        self.assertEqual(error.output_name, "my_output")
        self.assertIn("my_output", str(error))
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, KeyError)

    def test_key_error_subclasses_render_message_without_quotes(self) -> None:
        """KeyError.__str__ returns repr(args[0]); the CLI must print the plain message."""
        self.assertEqual(str(OutputNotFoundError("my_output")), "Output 'my_output' not found.")
        self.assertEqual(str(VariableNotFoundError("my_variable")), "Variable 'my_variable' not found.")

    def test_project_outputs_not_available_error(self) -> None:
        """Test ProjectOutputsNotAvailableError with output name."""
        error = ProjectOutputsNotAvailableError("deployment_id")
        self.assertEqual(error.output_name, "deployment_id")
        self.assertIn("deployment_id", str(error))
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, KeyError)
        # the two cases carry different next steps, so neither may catch the other
        self.assertNotIsInstance(error, RequiredOutputNotFoundError)

    def test_required_output_not_found_error(self) -> None:
        """Test RequiredOutputNotFoundError with output name."""
        error = RequiredOutputNotFoundError("deployment_id")
        self.assertEqual(error.output_name, "deployment_id")
        self.assertIn("deployment_id", str(error))
        self.assertNotIn('"', str(error))
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, KeyError)

    def test_required_output_type_error(self) -> None:
        """Test RequiredOutputTypeError with the expected and actual type names."""
        error = RequiredOutputTypeError(
            output_name="deployment_id",
            expected_type="StrTemplateOutputDefinition",
            actual_type="ListStrTemplateOutputDefinition",
        )
        self.assertEqual(error.output_name, "deployment_id")
        self.assertEqual(error.expected_type, "StrTemplateOutputDefinition")
        self.assertEqual(error.actual_type, "ListStrTemplateOutputDefinition")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, TypeError)

    def test_manifest_value_not_declared_error(self) -> None:
        """Test ManifestValueNotDeclaredError with value name."""
        error = ManifestValueNotDeclaredError("open_url")
        self.assertEqual(error.value_name, "open_url")
        self.assertIn("open_url", str(error))
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, NotImplementedError)

    def test_invalid_preset_error(self) -> None:
        """Test InvalidPresetError with preset name and valid presets."""
        valid_presets = ["prod", "dev", "staging"]
        error = InvalidPresetError("invalid", valid_presets)
        self.assertEqual(error.preset_name, "invalid")
        self.assertEqual(error.valid_presets, valid_presets)
        self.assertIn("invalid", str(error))
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, ValueError)

    def test_invalid_service_error(self) -> None:
        """Test InvalidServiceError with service name and valid services."""
        valid_services = ["jupyter", "jupyterlab", "vscode"]
        error = InvalidServiceError("invalid-service", valid_services)
        self.assertEqual(error.service_name, "invalid-service")
        self.assertEqual(error.valid_services, valid_services)
        self.assertIn("invalid-service", str(error))
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, ValueError)


class TestConfigurationErrors(unittest.TestCase):
    """Test cases for configuration-related exceptions."""

    def test_configuration_error_base(self) -> None:
        """Test ConfigurationError base class and inheritance."""
        error = ConfigurationError("Config error")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)

    def test_read_configuration_error(self) -> None:
        """Test ReadConfigurationError with file path."""
        error = ReadConfigurationError("/path/to/plan.json")
        self.assertEqual(error.file_path, "/path/to/plan.json")
        self.assertIn("/path/to/plan.json", str(error))
        self.assertIsInstance(error, ConfigurationError)
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)

    def test_write_configuration_error(self) -> None:
        """Test WriteConfigurationError with file path."""
        error = WriteConfigurationError("/path/to/config.yaml")
        self.assertEqual(error.file_path, "/path/to/config.yaml")
        self.assertIn("/path/to/config.yaml", str(error))
        self.assertIsInstance(error, ConfigurationError)
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)


class TestExecutionErrors(unittest.TestCase):
    """Test cases for execution-related exceptions."""

    def test_execution_error(self) -> None:
        """Test ExecutionError with command, retcode, and message."""
        error = SupervisedExecutionError(
            command="terraform apply",
            retcode=1,
            message="Apply failed",
        )
        self.assertEqual(error.command, "terraform apply")
        self.assertEqual(error.retcode, 1)
        self.assertEqual(str(error), "Apply failed")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, Exception)


class TestToolErrors(unittest.TestCase):
    """Test cases for tool requirement exceptions."""

    def test_tool_required_error_minimal(self) -> None:
        """Test ToolRequiredError with just tool name."""
        error = ToolRequiredError("terraform")
        self.assertEqual(error.tool_name, "terraform")
        self.assertIsNone(error.installation_url)
        self.assertIsNone(error.error_msg)
        self.assertIn("terraform", str(error))
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)

    def test_tool_required_error_full(self) -> None:
        """Test ToolRequiredError with all attributes."""
        error = ToolRequiredError(
            tool_name="aws",
            installation_url="https://aws.amazon.com/cli/",
            error_msg="Command not found: aws",
        )
        self.assertEqual(error.tool_name, "aws")
        self.assertEqual(error.installation_url, "https://aws.amazon.com/cli/")
        self.assertEqual(error.error_msg, "Command not found: aws")
        self.assertIn("aws", str(error))
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)

    def test_proxy_not_installed_error(self) -> None:
        """Test ProxyNotInstalledError carries the console script name."""
        error = ProxyNotInstalledError("jupyter-deploy-client-proxy")
        self.assertEqual(error.console_script, "jupyter-deploy-client-proxy")
        self.assertIn("jupyter-deploy-client-proxy", str(error))
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)

    def test_no_proxy_found_error(self) -> None:
        """Test NoProxyFoundError default + custom message."""
        error = NoProxyFoundError()
        self.assertIn("No running proxy", str(error))
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(str(NoProxyFoundError("custom")), "custom")

    def test_proxy_start_error(self) -> None:
        """Test ProxyStartError carries an optional log dir."""
        error = ProxyStartError("proxy exited early", log_dir="/tmp/.jd-proxy/server/default/ts")
        self.assertIn("proxy exited early", str(error))
        self.assertEqual(error.log_dir, "/tmp/.jd-proxy/server/default/ts")
        self.assertIsNone(ProxyStartError("x").log_dir)
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)


class TestResourceErrors(unittest.TestCase):
    """Test cases for resource management exceptions."""

    def test_down_auto_approve_required_error(self) -> None:
        """Test DownAutoApproveRequiredError with persisting resources."""
        resources = ["aws_instance.main", "aws_s3_bucket.data"]
        error = DownAutoApproveRequiredError(resources)
        self.assertEqual(error.persisting_resources, resources)
        self.assertIn("auto-approve", str(error).lower())
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, ValueError)


class TestInstructionErrors(unittest.TestCase):
    """Test cases for instruction execution exceptions."""

    def test_instruction_error_base(self) -> None:
        """Test InstructionError base class and inheritance."""
        error = InstructionError("Instruction failed")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)

    def test_interactive_session_error(self) -> None:
        """Test InteractiveSessionError creation and inheritance."""
        error = InteractiveSessionError("Session failed")
        self.assertIsInstance(error, InstructionError)
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)

    def test_interactive_session_timeout_error(self) -> None:
        """Test InteractiveSessionTimeoutError creation and inheritance."""
        error = InteractiveSessionTimeoutError("Session timed out")
        self.assertIsInstance(error, InteractiveSessionError)
        self.assertIsInstance(error, InstructionError)
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, TimeoutError)

    def test_unreachable_host_error(self) -> None:
        """Test UnreachableHostError creation and inheritance."""
        error = UnreachableHostError("Host unreachable")
        self.assertIsInstance(error, InstructionError)
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, ConnectionError)
        self.assertIsNone(error.hint)

    def test_unreachable_host_error_with_hint(self) -> None:
        """Test UnreachableHostError with hint."""
        error = UnreachableHostError("Host unreachable", hint="Check network connection")
        self.assertEqual(error.hint, "Check network connection")
        self.assertEqual(str(error), "Host unreachable")

    def test_incompatible_host_state_error(self) -> None:
        """Test IncompatibleHostStateError creation and inheritance."""
        error = IncompatibleHostStateError("Host in wrong state")
        self.assertIsInstance(error, InstructionError)
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)
        self.assertIsNone(error.hint)

    def test_incompatible_host_state_error_with_hint(self) -> None:
        """Test IncompatibleHostStateError with hint."""
        error = IncompatibleHostStateError("Host in wrong state", hint="Wait for ready state")
        self.assertEqual(error.hint, "Wait for ready state")
        self.assertEqual(str(error), "Host in wrong state")

    def test_host_command_instruction_error(self) -> None:
        """Test HostCommandInstructionError creation and attributes."""
        error = HostCommandInstructionError(
            message="Command failed",
            retcode=127,
            stdout="some output",
            stderr="error message",
        )
        self.assertIsInstance(error, InstructionError)
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(error.retcode, 127)
        self.assertEqual(error.stdout, "some output")
        self.assertEqual(error.stderr, "error message")
        self.assertEqual(str(error), "Command failed")

    def test_instruction_not_found_error(self) -> None:
        """Test InstructionNotFoundError creation and inheritance."""
        error = InstructionNotFoundError("Instruction not found")
        self.assertIsInstance(error, InstructionError)
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)

    def test_invalid_instruction_argument_error(self) -> None:
        """Test InvalidInstructionArgumentError creation and inheritance."""
        error = InvalidInstructionArgumentError("Invalid argument")
        self.assertIsInstance(error, InstructionError)
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, ValueError)

    def test_invalid_instruction_result_error(self) -> None:
        """Test InvalidInstructionResultError creation and inheritance."""
        error = InvalidInstructionResultError("Invalid result")
        self.assertIsInstance(error, InstructionError)
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, ValueError)


class TestHistoryErrors(unittest.TestCase):
    """Test cases for history and logging exceptions."""

    def test_log_not_found(self) -> None:
        """Test LogNotFoundError creation and inheritance."""
        error = LogNotFoundError("Log file not found")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, ValueError)

    def test_log_cleanup_error(self) -> None:
        """Test LogCleanupError creation and inheritance."""
        error = LogCleanupError("Cleanup failed")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, Exception)


class TestProjectStoreErrors(unittest.TestCase):
    """Test cases for project store exceptions."""

    def test_store_not_found_error(self) -> None:
        error = ProjectStoreNotFoundError("Store not configured")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)

    def test_store_access_configuration_error(self) -> None:
        error = ProjectStoreAccessConfigurationError("migration failed")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)

    def test_project_id_not_available_error(self) -> None:
        error = ProjectIdNotAvailableError("deployment_id not available")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, RuntimeError)

    def test_unsupported_provider_region_error(self) -> None:
        error = UnsupportedProviderRegionError("aws-iso")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, NotImplementedError)
        self.assertEqual(error.region_or_location, "aws-iso")
        self.assertIn("aws-iso", str(error))


class TestImageErrors(unittest.TestCase):
    """Test cases for image-related exceptions."""

    def test_image_not_found_error(self) -> None:
        error = ImageNotFoundError("myimage", ["jupyterlab", "worker"])
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, ValueError)
        self.assertEqual(error.image_name, "myimage")
        self.assertEqual(error.valid_images, ["jupyterlab", "worker"])
        self.assertIn("myimage", str(error))

    def test_image_tag_not_found_error(self) -> None:
        error = ImageTagNotFoundError("jupyterlab", "v99")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, ValueError)
        self.assertEqual(error.image_name, "jupyterlab")
        self.assertEqual(error.tag, "v99")
        self.assertIn("v99", str(error))
        self.assertIn("jupyterlab", str(error))


class TestResourcePollTimeoutError(unittest.TestCase):
    """ "Stopped watching", never "failed" -- the provider carries on after this is raised."""

    def test_carries_the_state_and_hint(self) -> None:
        error = ResourcePollTimeoutError("volume backup", "snap-1", "pending (42% done)", hint="Run 'jd volume show'.")
        self.assertEqual(error.resource_kind, "volume backup")
        self.assertEqual(error.resource_name, "snap-1")
        self.assertEqual(error.state, "pending (42% done)")
        self.assertIn("snap-1", str(error))
        self.assertIn("pending", str(error))

    def test_says_it_stopped_waiting_rather_than_failed(self) -> None:
        """Wording matters: a timeout on a backup reads as data loss unless it says otherwise.

        The generic message stops at "stopped waiting"; the reassurance that the operation continues is
        the raise site's, since only it knows what carries on and what the user can check.
        """
        message = str(ResourcePollTimeoutError("volume backup", "snap-1", "pending"))
        self.assertIn("Stopped waiting", message)
        self.assertNotIn("failed", message)

    def test_is_catchable_as_both_jupyter_deploy_and_timeout(self) -> None:
        """JupyterDeployError so the CLI renders it; TimeoutError so existing callers still catch it."""
        error = ResourcePollTimeoutError("volume backup", "snap-1", "pending")
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, TimeoutError)


class TestVolumeErrors(unittest.TestCase):
    """Test cases for volume-related exceptions."""

    def test_volume_not_found_error(self) -> None:
        error = VolumeNotFoundError("scratch", ["home", "home/external-ebs1"])
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, ValueError)
        self.assertEqual(error.volume_name, "scratch")
        self.assertEqual(error.valid_volumes, ["home", "home/external-ebs1"])
        self.assertIn("scratch", str(error))

    def test_volume_not_found_is_not_an_instruction_error(self) -> None:
        """A handler-layer error, so the CLI can list the valid names.

        `ResourceNotFoundError` is the provider-layer sibling: it means an API could not find a
        resource and carries no list of alternatives, so the two must not be interchangeable.
        """
        self.assertNotIsInstance(VolumeNotFoundError("scratch", []), InstructionError)

    def test_volume_not_backupable_error(self) -> None:
        error = VolumeNotBackupableError(
            "home/shared",
            "the template declares no backup mechanism for 'efs' storage",
            volume_class="efs",
            hint="Run 'jd volume backup --all'.",
        )
        self.assertIsInstance(error, JupyterDeployError)
        self.assertIsInstance(error, ValueError)
        self.assertEqual(error.volume_name, "home/shared")
        self.assertEqual(error.volume_class, "efs")
        self.assertEqual(error.reason, "the template declares no backup mechanism for 'efs' storage")
        self.assertEqual(error.hint, "Run 'jd volume backup --all'.")
        self.assertIn("home/shared", str(error))
        self.assertIn("no backup mechanism", str(error))

    def test_volume_not_backupable_error_is_not_a_host_state_error(self) -> None:
        """Deliberately NOT IncompatibleHostStateError: nothing about the host is wrong.

        No retry, permission grant, or state change makes the answer different, so a caller that
        caught the host-state error to offer "stop the host and try again" must not catch this.
        """
        error = VolumeNotBackupableError("vol-ref", "this deployment only references it")
        self.assertNotIsInstance(error, IncompatibleHostStateError)

    def test_volume_not_backupable_error_optional_fields_default(self) -> None:
        error = VolumeNotBackupableError("vol-ref", "this deployment only references it")
        self.assertEqual(error.volume_class, "")
        self.assertIsNone(error.hint)

    def test_volume_not_backupable_error_message_ends_with_a_period(self) -> None:
        """The reason is a clause, not a sentence; the exception composes the sentence."""
        error = VolumeNotBackupableError("home", "some reason")
        self.assertEqual(str(error), "Volume 'home' cannot be backed up: some reason.")
