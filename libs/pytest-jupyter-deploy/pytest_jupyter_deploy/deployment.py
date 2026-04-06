"""Deployment lifecycle management for E2E tests."""

import ast
import time
from pathlib import Path
from typing import Any

import yaml
from jupyter_deploy import constants as jd_constants
from jupyter_deploy import fs_utils as jd_fs_utils
from jupyter_deploy.handlers.base_project_handler import retrieve_project_manifest, retrieve_variables_config
from jupyter_deploy.manifest import JupyterDeployManifest
from jupyter_deploy.variables_config import (
    VARIABLES_CONFIG_V1_COMMENTS,
    VARIABLES_CONFIG_V1_KEYS_ORDER,
    JupyterDeployVariablesConfig,
)

from pytest_jupyter_deploy.cli import JDCli, JDCliError
from pytest_jupyter_deploy.constants import (
    CONFIGURATION_DEFAULT_NAME,
    DEPLOY_TIMEOUT_SECONDS,
    DESTROY_TIMEOUT_SECONDS,
    SSM_NOT_REPORTING_SENTINEL,
)
from pytest_jupyter_deploy.suite_config import SuiteConfig


class EndToEndDeployment:
    """Represents a Jupyter-Deploy project for end to end testing."""

    def __init__(
        self,
        suite_config: SuiteConfig,
        config_name: str = CONFIGURATION_DEFAULT_NAME,
        deploy_timeout_seconds: int = DEPLOY_TIMEOUT_SECONDS,
        destroy_timeout_seconds: int = DESTROY_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize the deployment manager.

        Args:
            suite_config: Suite configuration
            config_name: Configuration name to use (default: "base")
            deploy_timeout_seconds: Timeout in seconds for deployment (default: 1800)
            destroy_timeout_seconds: Timeout in seconds for destroy (default: 600)
        """
        self.suite_config = suite_config
        self.config_name = config_name
        self.deploy_timeout_seconds = deploy_timeout_seconds
        self.destroy_timeout_seconds = destroy_timeout_seconds
        self._cli: JDCli | None = None
        self._is_deployed = False
        self._has_up_history = False
        self._owns_project_resources = False

    @property
    def cli(self) -> JDCli:
        """Get the CLI instance, initializing it if needed.

        The CLI is initialized with the project directory after suite_config is loaded.
        """
        if self._cli is None:
            # Ensure suite_config is loaded so project_dir is available
            self.suite_config.load()
            self._cli = JDCli(self.suite_config.project_dir)
        return self._cli

    def ensure_deployed(self) -> None:
        """Ensure that the project is deployed.

        Raise:
            RuntimeError if the target container is not available.
        """
        # First, abort early if already flagged as deployed
        if self._is_deployed:
            return

        # Second, load the config, which will identity if the user requested to test against
        # an existing project or desires a deployment from scratch
        self.suite_config.load()

        # CASE 1: Test against an Existing Project
        if self.suite_config.references_existing_project():
            # The dir MUST already exist, and be mounted on the container at the path.
            if not self.suite_config.project_dir.exists():
                raise RuntimeError(
                    "Cannot run integration tests; referenced project does not exist "
                    f"at path: {self.suite_config.project_dir.absolute()}"
                )
            # Run jd config to ensure the engine is initialized in this
            # environment. The host and the test container may run different
            # terraform versions, and with a remote backend (e.g. backend.tf
            # for S3), terraform requires re-initialization to connect.
            # With a local backend this is a no-op since terraform can read
            # the state file directly regardless of version.
            self.cli.run_command(["jupyter-deploy", "config"])
            self._is_deployed = True
        # CASE 2: Deploy from Scratch, then Test against it
        else:
            # In this case also, the directory MUST already exist
            # 1/ the tests run in a container
            # 2/ the project directory lives in the developer's workspace
            # 3/ therefore, the project directory mounts on the test container
            # which is why it must exist!
            if not self.suite_config.project_dir.exists():
                raise RuntimeError(
                    "Project directory does not exist: "
                    f"{self.suite_config.project_dir.absolute()}\n"
                    f"Create this directory first, and ensure it is empty."
                )
            # And this directory MUST be empty to avoid overwriting another deployment
            elif any(self.suite_config.project_dir.iterdir()):
                raise RuntimeError(
                    f"Cannot deploy: project directory already exists and is not empty: "
                    f"{self.suite_config.project_dir.absolute()}\n"
                    f"This safety check prevents accidentally destroying terraform.state.\n"
                    f"To redeploy, manually remove the directory first."
                )
            # If both conditions are satisfied, then the project directory is mounted
            # (since the file system inside the container sees it), and it is clean (empty)
            # we can proceed
            self._deploy_e2e_project()

    def ensure_up_history(self) -> None:
        """Ensure that `jd history list up` has at least one entry.

        Restored projects have config history (from the restore's `jd config`)
        but no up history. This runs a no-op `jd up -y` to create an up log
        entry. The result is cached so the cost is paid at most once per run.
        """
        if self._has_up_history:
            return

        self.ensure_deployed()
        self.cli.run_command(["jupyter-deploy", "up", "-y"], timeout_seconds=self.deploy_timeout_seconds)
        self._has_up_history = True

    def ensure_host_running(self) -> None:
        """Call host status, attempts to call host start if not running."""

        self.ensure_deployed()

        if not self._is_host_running():
            self.cli.run_command(["jupyter-deploy", "host", "start"])

            if not self._is_host_running():
                raise RuntimeError("Host failed to start")

    def ensure_host_stopped(self) -> None:
        """Call host status, attempts to call host stop if running"""

        self.ensure_deployed()

        if not self._is_host_stopped():
            self.cli.run_command(["jupyter-deploy", "host", "stop"])

            if not self._is_host_stopped():
                raise RuntimeError("Host is not stopped")

    def ensure_server_running(self, wait_after_restart: bool = False) -> None:
        """Ensure the Jupyter server is running.

        This method attempts to get the server into a running state by:
        1. Checking if server is already available (fast path)
        2. If server check fails (host not running), start the host first
        3. If server is not available but host is running, restart the server

        Args:
            wait_after_restart: If True, poll for IN_SERVICE after a restart
                instead of checking once. Useful in CI where containers may
                need extra time to initialize after a cold start.

        Raises:
            RuntimeError: If the server cannot be made available
        """
        self.ensure_deployed()

        # Step 1: Try to check if server is already available (fast path)
        try:
            if self._is_server_available():
                return
        except JDCliError:
            # Step 2: Check if host is running and start it if needed
            if not self._is_host_running():
                self.cli.run_command(["jupyter-deploy", "host", "start"])

                if not self._is_host_running():
                    raise RuntimeError("Host failed to start") from None

            # Wait for host to be reachable after the start
            self.wait_for_host_agent()

        # Step 3: Attempt to restart the server
        self.cli.run_command(["jupyter-deploy", "server", "restart"])

        if wait_after_restart:
            self._wait_for_server_in_service()
        elif not self._is_server_available():
            raise RuntimeError("Jupyter Server failed to start after restart")

    def ensure_server_stopped_and_host_is_running(self) -> None:
        """Ensure the host is running and the Jupyter server is stopped.

        This method attempts to ensure the server is stopped by:
        1. Checking if server is already stopped (fast path)
        2. If server check fails (host not running), ensure host is running and retry
        3. If server is not stopped, stop it

        Raises:
            RuntimeError: If the host cannot be started or server cannot be stopped
        """
        self.ensure_deployed()

        # Step 1: Try to check if server is already stopped (fast path)
        try:
            if self._is_server_stopped():
                return
        except JDCliError:
            # Server status check failed - likely host is not running
            # Ensure host is running
            self.ensure_host_running()

            # Retry server status check
            if self._is_server_stopped():
                return

        # Step 2: Server is not stopped - attempt to stop it
        self.cli.run_command(["jupyter-deploy", "server", "stop"])

        # Step 3: Verify server stopped successfully
        if not self._is_server_stopped():
            raise RuntimeError("Jupyter Server failed to stop")

    def configure_project(self, cli: JDCli | None = None) -> None:
        """Configure the E2E project by running jd config.

        Args:
            cli: Optional CLI instance to use. If provided, uses cli.project_dir as the project directory.
                 If not provided, uses self.cli and self.suite_config.project_dir.

        Raises:
            JDCliError: If configuration or deployment fails
        """
        # Ensure suite config is loaded
        self.suite_config.load()

        # Determine which CLI and project directory to use
        if cli is not None:
            # Use provided CLI and its project directory
            use_cli = cli
            project_dir = cli.project_dir
            # Prepare configuration to the custom project directory
            self.suite_config.prepare_configuration(self.config_name, target_dir=project_dir)
        else:
            # Use self.cli and suite_config.project_dir
            use_cli = self.cli
            project_dir = self.suite_config.project_dir
            # Prepare configuration (copies variables.yaml to default project dir)
            self.suite_config.prepare_configuration(self.config_name)

        # Run jd config
        use_cli.run_command(["jupyter-deploy", "config"])

    def _deploy_e2e_project(self) -> None:
        """Calls jd init, jd config, jd up."""
        # Initialize project
        engine = self.suite_config.template_engine.value
        provider = self.suite_config.template_provider
        infrastructure = self.suite_config.template_infrastructure
        base_name = self.suite_config.template_base_name

        # Run jd init from parent directory, not from inside the target directory
        # We use the absolute path and don't switch into the directory because
        # the CLI module import evaluates decorators that call Path.cwd(), which
        # can fail when run from an empty directory in a subprocess
        init_cmd = [
            "jupyter-deploy",
            "init",
            "--engine",
            engine,
            "--provider",
            provider,
            "--infrastructure",
            infrastructure,
            "--template",
            base_name,
            ".",  # cli.run_command() switch dirs to the project file already
        ]
        self.cli.run_command(init_cmd)

        # Call config
        self.configure_project()

        # Run deployment
        self.cli.run_command(["jupyter-deploy", "up", "-y"], timeout_seconds=self.deploy_timeout_seconds)

        self._is_deployed = True
        self._has_up_history = True

    def ensure_destroyed(self) -> None:
        """Ensure the deployment is torn down."""
        if not self._is_deployed:
            return

        try:
            # Run teardown
            self.cli.run_command(["jupyter-deploy", "down", "-y"], timeout_seconds=self.destroy_timeout_seconds)
        finally:
            self._is_deployed = False

    def _is_host_running(self) -> bool:
        """Return True if the host is running, False otherwise."""
        status = self.cli.get_host_status()
        return status == "running"

    def _is_host_stopped(self) -> bool:
        """Return True if the host is stopped, False otherwise."""
        status = self.cli.get_host_status()
        return status == "stopped"

    def _is_server_available(self) -> bool:
        """Return True if the server is available (IN_SERVICE), False otherwise."""
        status = self.cli.get_server_status()
        return status == "IN_SERVICE"

    def _wait_for_server_in_service(self, timeout_seconds: int = 180, interval_seconds: int = 10) -> None:
        """Poll server status until IN_SERVICE or timeout.

        Args:
            timeout: Maximum wait time in seconds (default: 5 minutes)
            interval: Seconds between polls (default: 10)

        Raises:
            RuntimeError: If the server does not reach IN_SERVICE within timeout
        """
        elapsed = 0
        while elapsed < timeout_seconds:
            if self._is_server_available():
                return
            time.sleep(interval_seconds)
            elapsed += interval_seconds
        status = self.cli.get_server_status()
        raise RuntimeError(f"Server did not reach IN_SERVICE within {timeout_seconds}s (last status: {status})")

    def _is_server_stopped(self) -> bool:
        """Return True if the server is stopped (STOPPED), False otherwise."""
        status = self.cli.get_server_status()
        return status == "STOPPED"

    def wait_for_host_agent(self, max_retries: int = 6) -> None:
        """Wait for agent responsible for communication to be ready on the host.

        SSM agent needs time to register with AWS Systems Manager after
        the EC2 instance starts or restarts. This method polls until SSM
        is ready or max retries is reached.

        Args:
            max_retries: Maximum number of retry attempts (default: 6)

        Raises:
            JDCliError: If SSM doesn't become ready within max_retries
        """
        for attempt in range(max_retries):
            try:
                # Try a simple server status check to verify SSM is ready
                self.cli.get_server_status()
                return
            except JDCliError as e:
                if SSM_NOT_REPORTING_SENTINEL in str(e):
                    if attempt < max_retries - 1:
                        # Exponential backoff with cap: 2, 4, 8, 16, 30, 30... (max ~90s total)
                        delay = min(2 ** (attempt + 1), 30)
                        time.sleep(delay)
                    else:
                        # Max retries exceeded
                        raise
                else:
                    # Different error - don't retry
                    raise

    def wait_for_connection_agent(self, max_retries: int = 10) -> None:
        """Wait for Session Manager connection to be ready on the host.

        The ssmmessages WebSocket channel (used by StartSession) can lag behind
        the ec2messages channel (used by SendCommand). This method polls
        SSM:GetConnectionStatus until the session channel is ready.

        Args:
            max_retries: Maximum number of retry attempts (default: 10)

        Raises:
            JDCliError: If connection doesn't become ready within max_retries
        """
        for attempt in range(max_retries):
            status = self.cli.get_connection_status()
            if status == "connected":
                return
            if attempt < max_retries - 1:
                delay = min(2 ** (attempt + 1), 30)
                time.sleep(delay)

        raise JDCliError(f"Session Manager connection not ready after {max_retries} attempts (last status: {status})")

    def ensure_no_org_nor_teams_allowlisted(self) -> None:
        """Unset the organization, list then remove any allowlisted team."""
        self.ensure_deployed()

        # Unset organization
        self.cli.run_command(["jupyter-deploy", "organization", "unset"])

        # Clear teams by removing all existing teams
        teams = self.cli.get_allowlisted_teams()
        if teams:
            self.cli.run_command(["jupyter-deploy", "teams", "remove"] + teams)

    def ensure_no_teams_allowlisted(self) -> None:
        """List then remove any allowlisted team."""
        self.ensure_deployed()

        # Clear teams by removing all existing teams
        teams = self.cli.get_allowlisted_teams()
        if teams:
            self.cli.run_command(["jupyter-deploy", "teams", "remove"] + teams)

    def ensure_org_allowlisted(self, org: str) -> None:
        """Set the specified organization."""
        self.ensure_deployed()

        # Set organization
        self.cli.run_command(["jupyter-deploy", "organization", "set", org])

    def get_allowlisted_users(self) -> list[str]:
        """Return the list of allowlisted users, or empty list if none"""
        return self.cli.get_allowlisted_users()

    def get_allowlisted_teams(self) -> list[str]:
        """Return the list of allowlisted teams, or empty list if none"""
        return self.cli.get_allowlisted_teams()

    def get_allowlisted_org(self) -> str | None:
        """Return the allowlisted organization, or None if none set"""
        return self.cli.get_allowlisted_org()

    def ensure_no_users_allowlisted(self) -> None:
        """Remove all allowlisted users."""
        self.ensure_deployed()

        users = self.cli.get_allowlisted_users()
        if users:
            self.cli.run_command(["jupyter-deploy", "users", "remove"] + users)

    def ensure_authorized(self, users: list[str], org: str, teams: list[str]) -> None:
        """Ensure authorization is set up with the specified users, organization, and teams.

        Args:
            users: List of GitHub usernames to allowlist (noop if empty list)
            org: GitHub organization to allowlist (noop if empty string)
            teams: List of GitHub teams to allowlist (noop if empty list or None)
        """
        self.ensure_deployed()

        # Set users if provided
        if users:
            self.cli.run_command(["jupyter-deploy", "users", "set"] + users)

        # Set organization if provided
        if org:
            self.cli.run_command(["jupyter-deploy", "organization", "set", org])

        # Set teams if provided
        if teams:
            # First ensure organization is set (teams require org)
            if not org:
                current_org = self.get_allowlisted_org()
                if not current_org:
                    raise ValueError("Cannot set teams without an organization")
            self.cli.run_command(["jupyter-deploy", "teams", "set"] + teams)

    def get_variables_yaml_path(self) -> Path:
        """Get the path to the variables.yaml file."""
        return self.suite_config.project_dir / jd_constants.VARIABLES_FILENAME

    def get_variables_config(self) -> JupyterDeployVariablesConfig:
        """Parse and return the variables config.

        Raises:
            FileNotFoundError: If variables.yaml doesn't exist
            ValidationError: If variables.yaml is invalid
        """
        variables_yaml_path = self.get_variables_yaml_path()
        return retrieve_variables_config(variables_yaml_path)

    def get_manifest(self) -> JupyterDeployManifest:
        """Parsed and return the project manifest.

        Raises:
            FileNotFoundError: If manifest.yaml doesn't exist
            ValidationError: If manifest.yaml is invalid
        """
        manifest_path = self.suite_config.project_dir / jd_constants.MANIFEST_FILENAME
        return retrieve_project_manifest(manifest_path)

    def read_override_value(self, key: str) -> Any:
        """Read a value from the overrides section of variables.yaml.

        Args:
            key: The key to read from overrides

        Returns:
            The value from overrides, or None if not set
        """
        variables_yaml = self.get_variables_yaml_path()
        with open(variables_yaml) as f:
            config = yaml.safe_load(f)

        overrides = config.get("overrides", {})
        return overrides.get(key)

    def update_override_value(self, key: str, value: Any) -> None:
        """Update a single override value in variables.yaml.

        Args:
            key: The override key to update (e.g., "instance_type")
            value: The new value to set (any type - preserves int, str, bool, etc.)

        Note:
            Keep value typed as Any instead of str to preserve proper YAML types.
            For example, passing int 50 writes as `50`, not `'50'` in YAML.
        """
        variables_yaml = self.get_variables_yaml_path()

        # Read current config
        with open(variables_yaml) as f:
            config = yaml.safe_load(f)

        # Ensure overrides section exists
        if "overrides" not in config:
            config["overrides"] = {}

        # Update the specific key
        config["overrides"][key] = value

        # Write back with comments preserved
        jd_fs_utils.write_yaml_file_with_comments(
            variables_yaml,
            config,
            key_order=VARIABLES_CONFIG_V1_KEYS_ORDER,
            comments=VARIABLES_CONFIG_V1_COMMENTS,
        )

    def ensure_deployed_with(self, config_args: list[str], timeout_seconds: int | None = None) -> None:
        """Ensure the deployment is updated with new configuration.

        This method reconfigures and redeploys an existing project with new settings.

        Args:
            config_args: Additional arguments to pass to `jd config` command
            timeout_seconds: Override deploy timeout for this call

        Raises:
            JDCliError: If configuration or deployment fails
        """
        # Ensure project exists
        self.ensure_deployed()

        # Run jd config with provided arguments
        config_cmd = ["jupyter-deploy", "config"] + config_args
        self.cli.run_command(config_cmd)

        # Run jd up to apply changes
        timeout = timeout_seconds if timeout_seconds is not None else self.deploy_timeout_seconds
        self.cli.run_command(["jupyter-deploy", "up", "-y"], timeout_seconds=timeout)
        self._has_up_history = True

    def get_str_variable_value(self, variable_name: str) -> str:
        """Call jupyter-deploy show CLI, return the parsed response as str."""
        result = self.cli.run_command(["jupyter-deploy", "show", "--variable", variable_name, "--text"])
        output = result.stdout.strip()
        # Try to parse as Python literal first
        try:
            value = ast.literal_eval(output)
        except (ValueError, SyntaxError):
            # If it fails, treat the output as a plain string (unquoted identifier)
            value = output
        assert isinstance(value, str), f"Expected str, got {type(value)}"
        return value

    def get_list_str_variable_value(self, variable_name: str) -> list[str]:
        """Call jupyter-deploy show CLI, return the parsed response as list[str]."""
        result = self.cli.run_command(["jupyter-deploy", "show", "--variable", variable_name, "--text"])
        output = result.stdout.strip()
        # Parse as Python literal
        value = ast.literal_eval(output)
        assert isinstance(value, list), f"Expected list, got {type(value)}"
        return value
