"""Centralized exception definitions for jupyter-deploy.

All custom exceptions inherit from JupyterDeployError for consistent error handling
across interfaces (CLI, API, etc.), while also preserving their original exception
types (ValueError, RuntimeError, etc.) for backwards compatibility.
"""

from jupyter_deploy.enum import ProviderType


class JupyterDeployError(Exception):
    """Base exception for all jupyter-deploy errors."""

    pass


# ============================================================================
# Manifest and project errors
# ============================================================================


class ManifestNotFoundError(JupyterDeployError, FileNotFoundError):
    """Raised when manifest file is missing or project cannot be found."""

    pass


class CommandNotImplementedError(JupyterDeployError, NotImplementedError):
    """Raised when a command is not found in the project manifest.

    Attributes:
        command_name: The name of the command that was not found
    """

    def __init__(self, command_name: str) -> None:
        self.command_name = command_name
        super().__init__(f"Command '{command_name}' is not implemented in this template.")


class ReadManifestError(JupyterDeployError, OSError):
    """Raised when manifest file cannot be read due to I/O error."""

    pass


class InvalidManifestError(JupyterDeployError, ValueError):
    """Raised when manifest parse or validation fails."""

    pass


class ManifestNotADictError(InvalidManifestError, ValueError):
    """Raised when manifest file doesn't parse as a dictionary."""

    pass


class InvalidVariablesDotYamlError(JupyterDeployError, ValueError):
    """Raised when variables.yaml file is invalid or malformed."""

    pass


# ============================================================================
# Variable and configuration errors
# ============================================================================


class VariableNotFoundError(JupyterDeployError, KeyError):
    """Raised when a variable name is not found in the project.

    Attributes:
        variable_name: The name of the variable that was not found
    """

    def __init__(self, variable_name: str) -> None:
        self.variable_name = variable_name
        super().__init__(f"Variable '{variable_name}' not found.")


class OutputNotFoundError(JupyterDeployError, KeyError):
    """Raised when an output name is not found in the project.

    Attributes:
        output_name: The name of the output that was not found
    """

    def __init__(self, output_name: str) -> None:
        self.output_name = output_name
        super().__init__(f"Output '{output_name}' not found.")


class SecretNotFoundError(JupyterDeployError, RuntimeError):
    """Raised when a secret cannot be restored from the cloud provider.

    Attributes:
        variable_name: The sensitive variable whose secret could not be restored
    """

    def __init__(self, variable_name: str, reason: str) -> None:
        self.variable_name = variable_name
        super().__init__(f"Cannot restore secret for '{variable_name}': {reason}")


class InvalidPresetError(JupyterDeployError, ValueError):
    """Raised when an invalid preset name is provided.

    Attributes:
        preset_name: The invalid preset name provided
        valid_presets: List of valid preset names for this template
    """

    def __init__(self, preset_name: str, valid_presets: list[str]) -> None:
        self.preset_name = preset_name
        self.valid_presets = valid_presets
        super().__init__(f"Invalid preset: '{preset_name}'")


class InvalidServiceError(JupyterDeployError, ValueError):
    """Raised when an invalid service name is provided.

    Attributes:
        service_name: The invalid service name provided
        valid_services: List of valid service names
    """

    def __init__(self, service_name: str, valid_services: list[str]) -> None:
        self.service_name = service_name
        self.valid_services = valid_services
        super().__init__(f"Invalid service: '{service_name}'")


class InvalidProjectPathError(JupyterDeployError, ValueError):
    """Raised when an invalid project path is provided."""

    pass


class UrlNotAvailableError(JupyterDeployError, ValueError):
    """Raised when URL is not available or empty."""

    pass


class UrlNotSecureError(JupyterDeployError, ValueError):
    """Raised when URL is not HTTPS."""

    def __init__(self, message: str, url: str) -> None:
        self.url = url
        super().__init__(message)


class OpenWebBrowserError(JupyterDeployError, RuntimeError):
    """Raised when opening URL in web browser fails."""

    def __init__(self, message: str, url: str) -> None:
        self.url = url
        super().__init__(message)


class ConfigurationError(JupyterDeployError, RuntimeError):
    """Base exception for configuration errors."""

    pass


class ReadConfigurationError(ConfigurationError, RuntimeError):
    """Raised when reading or parsing the file that captured the results of a config command fails.

    Attributes:
        file_path: Path to the configuration file that failed to read
    """

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        super().__init__(f"Failed to read or parse file at: {file_path}")


class WriteConfigurationError(ConfigurationError, RuntimeError):
    """Raised when writing the results of a config command to disk fails.

    Attributes:
        file_path: Path to the configuration file that failed to write
    """

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        super().__init__(f"Failed to write configuration to: {file_path}")


# ============================================================================
# Supervised execution errors
# ============================================================================


class SupervisedExecutionError(JupyterDeployError, Exception):
    """Raised when a supervised command execution fails.

    These errors generate history logs that can be viewed with 'jd history show'.

    Attributes:
        command: The command that failed (e.g., "config", "up", "down")
        retcode: The non-zero return code from the failed command
    """

    def __init__(self, command: str, retcode: int, message: str) -> None:
        self.command = command
        self.retcode = retcode
        super().__init__(message)


# ============================================================================
# Instruction execution errors
# ============================================================================


class InstructionError(JupyterDeployError, RuntimeError):
    """Base exception for instruction execution errors."""

    pass


class InvalidProviderCredentialsError(InstructionError, RuntimeError):
    """Raised when provider credentials are missing or invalid.

    Attributes:
        provider_name: Cloud provider type
        original_message: Original error message from the provider SDK
    """

    def __init__(self, provider_name: ProviderType, original_message: str) -> None:
        self.provider_name = provider_name
        self.original_message = original_message
        super().__init__(f"Invalid or missing {provider_name.value} credentials")


class ProviderPermissionError(InstructionError, RuntimeError):
    """Raised when operation is denied due to insufficient permissions.

    Attributes:
        provider_name: Cloud provider type
        operation: The operation that was attempted (e.g., 'ec2:StartInstance')
        original_message: Original error message from the provider SDK
    """

    def __init__(self, provider_name: ProviderType, operation: str | None, original_message: str) -> None:
        self.provider_name = provider_name
        self.operation = operation
        self.original_message = original_message
        if operation:
            super().__init__(f"Permission error for {provider_name.value} operation: {operation}")
        else:
            super().__init__(f"Permission error for {provider_name.value} operation")


class UnsupportedProviderRegionError(JupyterDeployError, NotImplementedError):
    """Raised when the provider region or partition is not supported.

    Attributes:
        region_or_location: The unsupported region or partition identifier
        hint: Optional hint for resolving the error
    """

    def __init__(self, region_or_location: str, hint: str | None = None) -> None:
        self.region_or_location = region_or_location
        self.hint = hint
        super().__init__(f"Unsupported provider region or location: {region_or_location}")


class InteractiveSessionError(InstructionError, RuntimeError):
    """Raised when an interactive session fails."""

    pass


class InteractiveSessionTimeoutError(InteractiveSessionError, TimeoutError):
    """Raised when an interactive session times out."""

    pass


class UnreachableHostError(InstructionError, ConnectionError):
    """Raised when host cannot be reached (e.g., SSM agent offline).

    Attributes:
        hint: Optional helpful hint for resolving the error
    """

    def __init__(self, message: str, hint: str | None = None) -> None:
        self.hint = hint
        super().__init__(message)


class IncompatibleHostStateError(InstructionError, RuntimeError):
    """Raised when host is in wrong state for the requested operation.

    Attributes:
        hint: Optional helpful hint for resolving the error
    """

    def __init__(self, message: str, hint: str | None = None) -> None:
        self.hint = hint
        super().__init__(message)


class HostCommandInstructionError(InstructionError, RuntimeError):
    """Raised when a command execution fails on a host.

    Attributes:
        retcode: The exit code from the command
        stdout: Standard output content from the command
        stderr: Standard error content from the command
    """

    def __init__(self, message: str, retcode: int, stdout: str, stderr: str) -> None:
        self.retcode = retcode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(message)


class InstructionNotFoundError(InstructionError, RuntimeError):
    """Raised when an instruction cannot be found or is not implemented."""

    pass


class InvalidInstructionArgumentError(InstructionError, ValueError):
    """Raised when an instruction argument is invalid or missing."""

    pass


class InvalidInstructionResultError(InstructionError, ValueError):
    """Raised when an instruction result is invalid or cannot be resolved."""

    pass


# ============================================================================
# Tool and requirement errors
# ============================================================================


class ToolRequiredError(JupyterDeployError, RuntimeError):
    """Raised when a required tool is not installed or has an incorrect version.

    Attributes:
        tool_name: Name of the required tool
        installation_url: Optional URL with installation instructions
        error_msg: Optional detailed error message from the check
    """

    def __init__(
        self,
        tool_name: str,
        installation_url: str | None = None,
        error_msg: str | None = None,
    ) -> None:
        self.tool_name = tool_name
        self.installation_url = installation_url
        self.error_msg = error_msg
        super().__init__(f"This operation requires {tool_name} to be installed in your system.")


# ============================================================================
# Resource management errors
# ============================================================================


class DownAutoApproveRequiredError(JupyterDeployError, ValueError):
    """Raised when auto-approve is required but not provided.

    Attributes:
        persisting_resources: List of resources that would persist after down
    """

    def __init__(self, persisting_resources: list[str]) -> None:
        self.persisting_resources = persisting_resources
        super().__init__(
            "Auto-approve is required when there are persisting resources. Pass --answer-yes or -y to proceed."
        )


# ============================================================================
# History and logging errors
# ============================================================================


class LogNotFoundError(JupyterDeployError, ValueError):
    """Raised when a command execution log cannot be found."""

    pass


class LogCleanupError(JupyterDeployError, Exception):
    """Raised when log cleanup fails."""

    pass


# ============================================================================
# Project store errors
# ============================================================================


class InvalidStoreTypeError(JupyterDeployError, ValueError):
    """Raised when a manifest declares an unrecognized project store type.

    Attributes:
        store_type: The invalid store type string
        valid_store_types: List of valid store type values
    """

    def __init__(self, store_type: str, valid_store_types: list[str]) -> None:
        self.store_type = store_type
        self.valid_store_types = valid_store_types
        super().__init__(f"Invalid store type: '{store_type}'")


class ProjectStoreNotFoundError(JupyterDeployError, RuntimeError):
    """Raised when no project store is found.

    Attributes:
        hint: Optional hint for resolving the error
    """

    def __init__(self, message: str = "", hint: str | None = None) -> None:
        self.hint = hint
        super().__init__(message)


class ProjectStoreAccessConfigurationError(JupyterDeployError, RuntimeError):
    """Raised when configuring engine access to the project store fails.

    For example, in the case of terraform, when either writing backend.tf
    or running terraform init -migrate-state fails.
    """

    pass


class ProjectStoreReadError(JupyterDeployError, RuntimeError):
    """Raised when reading from the project store fails (e.g., AccessDenied on remote state).

    Attributes:
        hint: Actionable hint for the user
        store_type: The store type (if available)
        store_id: The store ID (if available)
    """

    def __init__(
        self, message: str, hint: str | None = None, store_type: str | None = None, store_id: str | None = None
    ) -> None:
        self.hint = hint
        self.store_type = store_type
        self.store_id = store_id
        super().__init__(message)


class ProjectNotFoundInStoreError(JupyterDeployError, RuntimeError):
    """Raised when a project is not found in the remote store.

    Attributes:
        project_id: The project ID that was not found
        store_type: The store type that was queried (if available)
        store_id: The store ID that was queried (if available)
    """

    def __init__(self, project_id: str, store_type: str | None = None, store_id: str | None = None) -> None:
        self.project_id = project_id
        self.store_type = store_type
        self.store_id = store_id
        super().__init__(f"Project '{project_id}' not found in the store.")


class ProjectIdNotAvailableError(JupyterDeployError, RuntimeError):
    """Raised when the project ID cannot be resolved from deployment outputs.

    Attributes:
        hint: Optional hint for resolving the error
    """

    def __init__(self, message: str, hint: str | None = None) -> None:
        self.hint = hint
        super().__init__(message)
