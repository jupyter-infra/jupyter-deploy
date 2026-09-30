from pathlib import Path

from jupyter_deploy import fs_utils
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import DisplayManager, NullDisplay
from jupyter_deploy.enum import StoreType
from jupyter_deploy.exceptions import StoreTypeNotSpecifiedError, TemplateNotFoundError
from jupyter_deploy.handlers.base_project_handler import write_store_config
from jupyter_deploy.handlers.docs_generator import DocsGenerator
from jupyter_deploy.handlers.preferences_handler import PreferencesHandler
from jupyter_deploy.infrastructure.enum import AWSInfrastructureType, InfrastructureType
from jupyter_deploy.provider.enum import ProviderType
from jupyter_deploy.provider.store.store_manager_factory import StoreManagerFactory
from jupyter_deploy.template_utils import TEMPLATES

# Abbreviation each engine uses in the distribution name of the templates it publishes.
ENGINE_PACKAGE_ABBREVIATIONS = {EngineType.TERRAFORM.value: "tf"}


def _suggest_template_package(engine: str, template_name: str) -> str | None:
    """Return the distribution that conventionally provides a template, or None when unsure.

    Official deployable templates are published as `jupyter-deploy-<engine>-<provider>-<infra>-<name>`,
    so the name follows from the coordinates. It is a suggestion rather than a fact: the CI template
    is published as `jupyter-infra-tf-aws-iam-ci`, and a third-party template may use any name at all.
    """
    abbreviation = ENGINE_PACKAGE_ABBREVIATIONS.get(engine)
    segments = template_name.split(":")
    if not abbreviation or len(segments) != 3 or not all(segments):
        return None

    return f"jupyter-deploy-{abbreviation}-{'-'.join(segments)}"


class InitHandler:
    """Base class to manage a project at the target disk location."""

    def __init__(
        self,
        project_dir: Path | None,
        engine: EngineType = EngineType.TERRAFORM,
        provider: ProviderType | None = None,
        infrastructure: InfrastructureType | None = None,
        template: str | None = None,
        display_manager: DisplayManager | None = None,
    ) -> None:
        """Create the project handler, resolving which template the project starts from.

        The template may be a full name of the form <provider>:<infrastructure>:<template>, in which
        case it is used as-is and the provider and infrastructure arguments are ignored; a base name
        such as `base` is composed with them. Passing None resolves the template from the user's
        preferences, then from the built-in default -- `template_source` records what settled it, so
        that a caller can report back a template the user never typed.

        The provider and infrastructure default here rather than in the signature, so that a caller
        can forward what its user did or did not pass without having to know the default itself.

        Raises:
            InvalidTemplateNameError: If an explicit or preferred full template name is malformed.
            ReadPreferencesError: If the preferences file cannot be read or parsed.
            TemplateNotFoundError: If no installed package provides the resolved template.
        """
        if not project_dir:
            self.project_path = fs_utils.get_default_project_path()
        else:
            self.project_path = project_dir

        self.abs_project_path = Path.resolve(self.project_path)
        self.engine = engine

        preferences_handler = PreferencesHandler(display_manager=display_manager or NullDisplay())
        self.template_name, self.template_source = preferences_handler.resolve_template(
            template=template,
            provider=provider or ProviderType.AWS,
            infrastructure=infrastructure or AWSInfrastructureType.EC2,
        )

        self.source_path = self._find_template_path(self.template_name)

    def _find_template_path(self, template_name: str | None) -> Path:
        """Return the path of the template name.

        The template should be of the form <provider>:<infrastructure>:<template>.

        Raises:
            ValueError: if the template name is empty, or the engine is not supported.
            TemplateNotFoundError: if no installed package provides the template.
        """
        if not template_name:
            raise ValueError("Template name cannot be empty")

        engine_name = self.engine.lower()

        if engine_name not in TEMPLATES:
            available_engines = list(TEMPLATES.keys()) if TEMPLATES else "none available"
            raise ValueError(f"Engine '{engine_name}' is not supported. Available engines: {available_engines}")

        engine_templates = TEMPLATES[engine_name]

        if template_name in engine_templates:
            return engine_templates[template_name]

        raise TemplateNotFoundError(
            template_name=template_name,
            engine=engine_name,
            installed=sorted(engine_templates.keys()),
            suggested_package=_suggest_template_package(engine_name, template_name),
        )

    def may_export_to_project_path(self) -> bool:
        """Verify that the project output path does not contain any file or sub-directory."""
        if not self.project_path.exists():
            return True
        return fs_utils.is_empty_dir(self.project_path)

    def clear_project_path(self) -> None:
        """Clear the project on disk.

        This method assumes that the user accepted to delete the existing files.
        """
        fs_utils.safe_clean_directory(self.project_path)

    def setup(self) -> None:
        """Copies the files from the source location to the target path of the project."""
        fs_utils.safe_copy_tree(self.source_path, self.project_path)

        # Generate documentation and configuration files
        docs_generator = DocsGenerator(
            project_path=self.project_path,
            engine=self.engine.value,
        )

        # Generate documentation files
        docs_generator.generate_gitignore()
        docs_generator.generate_agent_md()
        docs_generator.generate_troubleshoot_md()

    @staticmethod
    def restore(
        project_dir: Path,
        project_id: str,
        display_manager: DisplayManager,
        store_type: StoreType | None = None,
        store_id: str | None = None,
    ) -> Path:
        """Restore a project from the remote store into a local directory.

        Falls back to the preferred store type when none is passed, like every other command that
        reaches a store.

        Returns:
            The absolute path to the restored project.

        Raises:
            StoreTypeNotSpecifiedError: If no store type was passed and none is preferred.
            InvalidStoreTypeError: If the preferred store type is not recognized.
        """
        resolved_store_type = PreferencesHandler(display_manager=display_manager).resolve_store_type(store_type)
        if resolved_store_type is None:
            raise StoreTypeNotSpecifiedError([t.value for t in StoreType])

        dest_path = project_dir
        store_manager = StoreManagerFactory.get_manager(store_type=resolved_store_type, store_id=store_id)
        store_manager.pull(project_id, dest_path, display_manager)

        # Persist store origin to .jd/store.yaml so that subsequent commands
        # (jd show --info, jd config, jd up) can resolve the store without
        # rediscovery.  The store_id is resolved during pull().
        resolved_store_info = store_manager.resolve_store()
        write_store_config(
            dest_path,
            store_type=resolved_store_type.value,
            store_id=resolved_store_info.store_id,
            project_id=project_id,
        )

        return dest_path.resolve()
