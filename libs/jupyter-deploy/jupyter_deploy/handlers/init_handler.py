from pathlib import Path

from jupyter_deploy import fs_utils
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.infrastructure.enum import AWSInfrastructureType, InfrastructureType
from jupyter_deploy.provider.enum import ProviderType
from jupyter_deploy.template_utils import TEMPLATES


class InitHandler:
    """Base class to manage a project at the target disk location."""

    def __init__(
        self,
        project_dir: str | None,
        engine: EngineType = EngineType.TERRAFORM,
        provider: ProviderType = ProviderType.AWS,
        infrastructure: InfrastructureType = AWSInfrastructureType.EC2,
        template: str = "tls-via-ngrok",
    ) -> None:
        """Create the project handler."""
        if not project_dir:
            self.project_path = fs_utils.get_default_project_path()
        else:
            self.project_path = Path(project_dir)

        self.abs_project_path = Path.resolve(self.project_path)
        self.engine = engine

        full_template_name: str | None = None
        if provider and infrastructure and template:
            full_template_name = f"{provider.lower()}:{infrastructure.lower()}:{template.lower()}"

        self.source_path = self._find_template_path(full_template_name)

    def _find_template_path(self, template_name: str | None) -> Path:
        """Return the path of the template name.

        The template should be of the form <provider>:<infrastructure>:<template>.

        Raises:
            ValueError: if the template is not found.
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

        raise ValueError(
            f"Template '{template_name}' not found for engine '{engine_name}'. "
            f"Available templates: {list(engine_templates.keys()) if engine_templates else 'none'}"
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
