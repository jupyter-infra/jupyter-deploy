"""Suite configuration models using Pydantic."""

import os
from functools import cached_property
from pathlib import Path

import yaml
from jupyter_deploy import constants as jd_constants
from jupyter_deploy import fs_utils as jd_fs_utils
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.base_project_handler import retrieve_project_manifest, retrieve_variables_config
from jupyter_deploy.manifest import JupyterDeployManifest
from jupyter_deploy.variables_config import (
    VARIABLES_CONFIG_V1_COMMENTS,
    VARIABLES_CONFIG_V1_KEYS_ORDER,
    VARIABLES_CONFIG_V2_COMMENTS,
    VARIABLES_CONFIG_V2_KEYS_ORDER,
    JupyterDeployVariablesConfig,
    JupyterDeployVariablesConfigV2,
)
from pydantic import TypeAdapter

from pytest_jupyter_deploy import constants


class SuiteConfig:
    """E2E test suite configuration."""

    manifest: JupyterDeployManifest
    variables_config: JupyterDeployVariablesConfig

    def __init__(self, suite_dir: Path, existing_project_dir: Path | None = None) -> None:
        """Instantiate the suite config.

        Args:
            suite_dir (Path): base directory of the e2e test suite
            existing_project_dir (Path): directory where the jupyter-deploy is deployed.
        """

        self.suite_dir = suite_dir
        self._existing_project_dir = existing_project_dir
        self._loaded = False

    def references_existing_project(self) -> bool:
        """Return True if the config points to an existing project, False if it owns the resources."""
        return self._existing_project_dir is not None

    def load(self) -> None:
        """Locate, read and parse manifest, variable and env vars.

        Raises:
            FileNotFoundError: If manifest.yaml does not exist
        """
        if self._loaded:
            return

        if self._existing_project_dir:
            # Load from existing project directory
            self.project_dir = self._existing_project_dir
            self.manifest = retrieve_project_manifest(self.project_dir / jd_constants.MANIFEST_FILENAME)
            self.variables_config = retrieve_variables_config(self.project_dir / jd_constants.VARIABLES_FILENAME)
        else:
            # Load from template directory
            template_dir_path = self.find_template_dir_path()
            self.manifest = retrieve_project_manifest(template_dir_path / jd_constants.MANIFEST_FILENAME)
            self.variables_config = retrieve_variables_config(template_dir_path / jd_constants.VARIABLES_FILENAME)

            # Use a fixed sandbox directory (mounted in container)
            self.project_dir = Path(os.getcwd()) / constants.SANDBOX_E2E_DIR
        self._loaded = True

    def find_template_dir_path(self) -> Path:
        """Return the path to the directory of the template.

        A template project is structured as follows:
        project-name
        |_project_name
        |__template
        |___manifest.yaml
        |___variables.yaml
        |_tests
        |__e2e
        |__unit
        """
        # suite_dir is tests/e2e, go up 2 levels to get to project root
        project_root = self.suite_dir.parent.parent

        # Find the package directory (project-name -> project_name)
        project_name = project_root.name.replace("-", "_")
        package_dir = project_root / project_name

        if not package_dir.exists():
            raise FileNotFoundError(
                f"Package directory not found: {package_dir}. "
                f"Expected directory structure: {project_root.name}/{project_name}/{constants.TEMPLATE_DIR}"
            )

        template_dir = package_dir / constants.TEMPLATE_DIR
        if not template_dir.exists():
            raise FileNotFoundError(
                f"Template directory not found: {template_dir}. "
                f"Expected directory structure: {project_root.name}/{project_name}/{constants.TEMPLATE_DIR}"
            )

        return template_dir

    @cached_property
    def template_engine(self) -> EngineType:
        """Template engine as listed in the manifest."""
        return self.manifest.get_engine()

    @cached_property
    def template_provider(self) -> str:
        """Template cloud provider derived from the template name"""
        template_name = self.manifest.template.name
        parts = template_name.split("-")
        if len(parts) < 4:
            raise ValueError(
                f"Invalid manifest template name: {template_name}. "
                f"Expected format: {{engine}}-{{provider}}-{{infrastructure}}-{{name}}"
            )
        provider = parts[1]
        return provider

    @cached_property
    def template_infrastructure(self) -> str:
        """Template infrastructure derived from the template name."""
        template_name = self.manifest.template.name
        parts = template_name.split("-")
        if len(parts) < 4:
            raise ValueError(
                f"Invalid manifest template name: {template_name}. "
                f"Expected format: {{engine}}-{{provider}}-{{infrastructure}}-{{name}}"
            )
        infrastructure = parts[2]
        return infrastructure

    @cached_property
    def template_base_name(self) -> str:
        """Template base name derived from the template name."""
        template_name = self.manifest.template.name
        parts = template_name.split("-")
        if len(parts) < 4:
            raise ValueError(
                f"Invalid manifest template name: {template_name}. "
                f"Expected format: {{engine}}-{{provider}}-{{infrastructure}}-{{name}}"
            )
        base_name = parts[3:]
        return "-".join(base_name)

    def prepare_configuration(self, config_name: str = "base", target_dir: Path | None = None) -> None:
        """Load variables yaml of specific configuration, applies substitution, copies to project dir.

        Args:
            config_name: Name of the configuration to load (default: "base")
            target_dir: Optional target directory to write variables.yaml to.
                        If not provided, uses self.project_dir.
        """
        # Load the configuration file with environment variable expansion
        resolved_variables = self._load_configuration(config_name)

        # Determine target directory
        write_dir = target_dir if target_dir is not None else self.project_dir

        # Write resolved configuration using the correct format for the schema version
        variables_config_path = write_dir / jd_constants.VARIABLES_FILENAME
        if isinstance(resolved_variables, JupyterDeployVariablesConfigV2):
            jd_fs_utils.write_yaml_file_with_comments(
                variables_config_path,
                resolved_variables.model_dump(),
                key_order=VARIABLES_CONFIG_V2_KEYS_ORDER,
                comments=VARIABLES_CONFIG_V2_COMMENTS,
            )
        else:
            jd_fs_utils.write_yaml_file_with_comments(
                variables_config_path,
                resolved_variables.model_dump(),
                key_order=VARIABLES_CONFIG_V1_KEYS_ORDER,
                comments=VARIABLES_CONFIG_V1_COMMENTS,
            )

    def _load_configuration(self, config_name: str) -> JupyterDeployVariablesConfig:
        """Load a deployment configuration to the target directory.

        This function:
        1. Loads configurations/{config_name}.yaml
        2. Expands environment variables in the configuration
        3. Validates the result using the CLI's JupyterDeployVariablesConfig model
        4. Returns the validated config

        Environment variables must be set in the environment (passed through
        docker-compose in containerized environments).

        Args:
            config_name: Configuration name (e.g., "base")

        Returns:
            Validated variables configuration

        Raises:
            FileNotFoundError: If configuration file does not exist
            ValidationError: If configuration is invalid
        """
        # Load configuration file
        config_file = self.suite_dir / constants.CONFIGURATIONS_DIR / f"{config_name}.yaml"
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration not found at path: {config_file.absolute()}")

        with open(config_file) as f:
            resolved_content = os.path.expandvars(f.read())
            data = yaml.safe_load(resolved_content)

        if not isinstance(data, dict):
            raise ValueError("Invalid variables config file: jupyter-deploy variables config is not a dict.")

        adapter: TypeAdapter[JupyterDeployVariablesConfig] = TypeAdapter(JupyterDeployVariablesConfig)
        return adapter.validate_python(data)  # type: ignore[return-value]
