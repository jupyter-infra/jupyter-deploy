from pathlib import Path

import yaml
from pydantic import TypeAdapter, ValidationError
from yaml.parser import ParserError
from yaml.scanner import ScannerError

from jupyter_deploy import constants, fs_utils, manifest, store_config, variables_config
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.enum import StoreType
from jupyter_deploy.exceptions import (
    InvalidManifestError,
    InvalidVariablesDotYamlError,
    ManifestNotADictError,
    ManifestNotFoundError,
    ReadManifestError,
)
from jupyter_deploy.handlers.command_history_handler import CommandHistoryHandler


class BaseProjectHandler:
    """Abstract class responsible for identifying the type of project.

    The current working directory MUST be a jupyter-deploy directory,
    otherwise this class will raise a typer.Exit().
    """

    def __init__(self, display_manager: DisplayManager) -> None:
        """Attempts to identify the engine associated with the project.

        Args:
            display_manager: Display manager for status updates

        Raises:
            ManifestNotFoundError: If project manifest not found
            ReadManifestError: If manifest cannot be read due to I/O error
            InvalidManifestError: If manifest cannot be parsed or validated
        """
        self.display_manager = display_manager
        self.project_path = Path.cwd()
        self.command_history_handler = CommandHistoryHandler(self.project_path)
        manifest_path = self.project_path / constants.MANIFEST_FILENAME

        project_manifest = retrieve_project_manifest(manifest_path)
        self.engine = project_manifest.get_engine()
        self.project_manifest = project_manifest

    def get_store_type_from_config_or_manifest(self) -> StoreType | None:
        """Resolve the store type from .jd/store.yaml > manifest.

        Returns None if no store is configured anywhere.

        Raises:
            InvalidStoreTypeError: If a resolved store type string is not recognized.
        """
        # Priority 1: .jd/store.yaml
        config = retrieve_store_config(self.project_path)
        if config is not None and config.store_type is not None:
            return config.get_store_type()

        # Priority 2: manifest project-store
        if self.project_manifest.project_store is not None:
            return self.project_manifest.project_store.get_store_type()

        return None

    def get_store_id_from_config(self) -> str | None:
        """Resolve the store ID from .jd/store.yaml.

        Returns None if no store ID is pinned (use tag-based discovery).
        """
        config = retrieve_store_config(self.project_path)
        if config is not None and config.store_id is not None:
            return config.store_id

        return None

    def get_project_id_from_config(self) -> str | None:
        """Resolve the project ID from .jd/store.yaml.

        Returns None if no project ID is stored.
        """
        config = retrieve_store_config(self.project_path)
        if config is not None and config.project_id is not None:
            return config.project_id

        return None


def retrieve_project_manifest(manifest_path: Path) -> manifest.JupyterDeployManifest:
    """Read the manifest file on disk, parse, validate and return it.

    Raises:
        ManifestNotFoundError: If manifest file not found
        ReadManifestError: If manifest file cannot be read due to I/O error
        InvalidManifestError: If manifest cannot be parsed or validated
    """
    if not fs_utils.file_exists(manifest_path):
        raise ManifestNotFoundError(f"Could not find manifest file at: {manifest_path.absolute()}")

    try:
        with open(manifest_path) as manifest_file:
            content = yaml.safe_load(manifest_file)
    except OSError as e:
        raise ReadManifestError(f"Cannot access manifest file at: {manifest_path.absolute()}. {e}") from e
    except (ParserError, ScannerError) as e:
        raise InvalidManifestError(f"Cannot parse manifest as YAML: {manifest_path.absolute()}. {e}") from e

    if not isinstance(content, dict):
        raise ManifestNotADictError(f"Manifest file must be a YAML dictionary: {manifest_path.absolute()}")

    try:
        return manifest.JupyterDeployManifest(**content)
    except ValidationError as e:
        error_details = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
        raise InvalidManifestError(
            f"Manifest validation failed: {manifest_path.absolute()}. Errors: {error_details}"
        ) from e


def retrieve_project_manifest_if_available(project_path: Path) -> manifest.JupyterDeployManifest | None:
    """Attempts to read the manifest file on disk, parse, and return.

    Return None if the file is not found, cannot be parsed or fails any of the validation.
    """

    manifest_path = project_path / constants.MANIFEST_FILENAME
    try:
        return retrieve_project_manifest(manifest_path)
    except ManifestNotFoundError:
        # Silently return None when manifest doesn't exist (expected in some contexts)
        return None
    except ReadManifestError as e:
        # Print errors for I/O issues (indicates actual problems)
        print(e)
        return None
    except InvalidManifestError as e:
        # Print errors for malformed manifests (indicates actual problems)
        print(e)
        return None


def retrieve_variables_config(variables_config_path: Path) -> variables_config.JupyterDeployVariablesConfig:
    """Read the variables confign file on disk, parse, validate and return it."""

    if not fs_utils.file_exists(variables_config_path):
        raise FileNotFoundError("Missing jupyter-deploy variables config file.")

    with open(variables_config_path) as variables_manifest_file:
        try:
            content = yaml.safe_load(variables_manifest_file)
        except yaml.YAMLError as e:
            raise InvalidVariablesDotYamlError(f"Invalid YAML syntax in variables.yaml: {e}") from None

    if not isinstance(content, dict):
        raise InvalidVariablesDotYamlError(
            "Invalid variables config file: jupyter-deploy variables config is not a dict."
        )

    # JupyterDeployVariablesConfig is a type alias (discriminated union), not a class —
    # TypeAdapter is required to validate data against it and route to V1 or V2.
    adapter: TypeAdapter[variables_config.JupyterDeployVariablesConfig] = TypeAdapter(
        variables_config.JupyterDeployVariablesConfig
    )
    try:
        return adapter.validate_python(content)  # type: ignore[return-value]
    except ValidationError as e:
        errors = "; ".join([f"{err['loc']}: {err['msg']}" for err in e.errors()])
        raise InvalidVariablesDotYamlError(f"Invalid variables.yaml: {errors}") from None


def retrieve_store_config(project_path: Path) -> store_config.JupyterDeployStoreConfig | None:
    """Read .jd/store.yaml and return a parsed config, or None if file does not exist."""
    store_config_path = project_path / constants.JD_DIR / constants.STORE_CONFIG_FILENAME
    if not fs_utils.file_exists(store_config_path):
        return None

    with open(store_config_path) as f:
        content = yaml.safe_load(f)

    if not isinstance(content, dict):
        return None

    return store_config.JupyterDeployStoreConfig(**content)


def write_store_config(
    project_path: Path,
    store_type: str | None = None,
    store_id: str | None = None,
    project_id: str | None = None,
) -> None:
    """Write .jd/store.yaml with the given values. Creates .jd/ dir if needed."""
    jd_dir = project_path / constants.JD_DIR
    jd_dir.mkdir(parents=True, exist_ok=True)

    config = store_config.JupyterDeployStoreConfigV1(store_type=store_type, store_id=store_id, project_id=project_id)
    content = config.model_dump(by_alias=True, exclude_none=True)

    fs_utils.write_yaml_file_with_comments(
        jd_dir / constants.STORE_CONFIG_FILENAME,
        content,
        key_order=store_config.STORE_CONFIG_V1_KEYS_ORDER,
    )
