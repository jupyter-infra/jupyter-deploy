from pathlib import Path

from jupyter_deploy import fs_utils
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.presets.path import PRESET_ROOT_PATH


class ProjectHandler:
    """Base class to manage a project at the target disk location."""

    def __init__(
        self,
        project_dir: str | None,
        engine: EngineType = EngineType.TERRAFORM,
        template_name: str = "",
    ) -> None:
        """Create the project handler."""
        if not project_dir:
            self.project_path = fs_utils.get_default_project_path()
        else:
            self.project_path = Path(project_dir)

        self.engine = engine
        self.source_path = self._find_template_path(template_name)

    def _find_template_path(self, template_name: str) -> Path:
        """Return the path of the template name.

        The template should be of the form <provider>:<infra-type>:<template_name>.
        """
        template_path_parts = template_name.split(":")
        tf_template_path = Path(PRESET_ROOT_PATH / self.engine.lower())

        for template_path_part in template_path_parts:
            tf_template_path /= template_path_part

        return tf_template_path

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
