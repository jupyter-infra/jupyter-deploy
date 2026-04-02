from pathlib import Path

from jupyter_deploy.engine.engine_store_access import EngineStoreAccessManager
from jupyter_deploy.engine.engine_up import EngineUpHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.engine.supervised_execution import CompletionContext, DisplayManager
from jupyter_deploy.engine.terraform import tf_up
from jupyter_deploy.engine.terraform.tf_constants import TF_ENGINE_DIR
from jupyter_deploy.engine.terraform.tf_outputs import TerraformOutputsHandler
from jupyter_deploy.engine.terraform.tf_store_access import TerraformStoreAccessManager
from jupyter_deploy.exceptions import ProjectIdNotAvailableError
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler, write_store_config
from jupyter_deploy.provider.store.store_manager_factory import StoreManagerFactory


class UpHandler(BaseProjectHandler):
    _handler: EngineUpHandler
    _store_access_manager: EngineStoreAccessManager

    def __init__(self, display_manager: DisplayManager) -> None:
        """Base class to manage the up command of a jupyter-deploy project."""
        super().__init__(display_manager=display_manager)

        if self.engine == EngineType.TERRAFORM:
            self._handler = tf_up.TerraformUpHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
                command_history_handler=self.command_history_handler,
                display_manager=display_manager,
            )
            self._store_access_manager = TerraformStoreAccessManager(
                engine_dir_path=self.project_path / TF_ENGINE_DIR,
            )
            self._outputs_handler = TerraformOutputsHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
            )
        else:
            raise NotImplementedError(f"UpHandler implementation not found for engine: {self.engine}")

    def get_default_config_filename(self) -> str:
        """Get the default config file name for the current engine."""
        return self._handler.get_default_config_filename()

    def get_config_file_path(self, config_filename: str | None = None) -> Path:
        """Return the full path to the config file.

        Raises:
            FileNotFoundError: If the config file does not exist.
        """
        if config_filename is None:
            config_filename = self.get_default_config_filename()

        config_file_path = self._handler.engine_dir_path / config_filename

        if not config_file_path.exists():
            raise FileNotFoundError(
                f"Config file '{config_filename}' not found in {self.project_path}. "
                f"If you have not yet generated a config file for your current project, "
                f'please run "jd config" from the project directory first.'
            )

        return config_file_path

    def apply(self, config_file_path: Path, auto_approve: bool = False) -> CompletionContext | None:
        """Apply the infrastructure changes defined in the config file.

        Args:
            config_file_path: The path to the config file.
            auto_approve: Whether to auto-approve the changes without prompting.

        Returns:
            CompletionContext with completion summary, or None if not available.
        """
        return self._handler.apply(config_file_path, auto_approve)

    def push_to_store(self) -> None:
        """Push the project to the remote store.

        Resolves store type and ID from .jd/store.yaml > manifest.
        After successful find_store, persists discovered store-id to .jd/store.yaml.

        No-op if no store type is configured anywhere.

        Raises:
            ProjectIdNotAvailableError: If deployment_id is not declared or not available.
            ProjectStoreNotFoundError: If no project store is found in the account.
        """
        store_type = self.get_store_type_from_config_or_manifest()
        if not store_type:
            self.display_manager.warning("No project store type configured. Skipping store push.")
            return

        store_id = self.get_store_id_from_config()

        try:
            deployment_id_value = self.project_manifest.get_declared_value("deployment_id")
        except NotImplementedError:
            raise ProjectIdNotAvailableError(
                "Template must declare a 'deployment_id' value required for project store."
            ) from None

        deployment_id_def = self._outputs_handler.get_declared_output_def("deployment_id", StrTemplateOutputDefinition)
        if not deployment_id_def.value:
            raise ProjectIdNotAvailableError(f"Output '{deployment_id_value.source_key}' is not available.")

        project_id = self.project_manifest.compute_project_id(deployment_id_def.value)
        store_manager = StoreManagerFactory.get_manager(store_type=store_type, store_id=store_id)
        store_info = store_manager.find_store()

        if not self._store_access_manager.is_configured():
            self._store_access_manager.configure(store_info, project_id, self.display_manager)

        # Persist store-id and project-id to .jd/store.yaml BEFORE push,
        # so the S3 snapshot includes it and restored projects get a complete
        # store config without needing a second jd up.
        write_store_config(
            self.project_path,
            store_type=store_type.value,
            store_id=store_info.store_id,
            project_id=project_id,
        )

        store_manager.push(self.project_path, project_id, self.display_manager)
