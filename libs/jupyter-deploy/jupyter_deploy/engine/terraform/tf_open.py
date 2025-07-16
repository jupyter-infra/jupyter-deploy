from pathlib import Path

from jupyter_deploy.engine.engine_open import EngineOpenHandler
from jupyter_deploy.engine.terraform import tf_outputs
from jupyter_deploy.manifest import JupyterDeployManifest


class TerraformOpenHandler(EngineOpenHandler):
    """Terraform implementation of the EngineOpenHandler."""

    def __init__(
        self,
        project_path: Path,
        project_manifest: JupyterDeployManifest,
    ) -> None:
        """Instantiate the terraform open handler."""
        outputs_handler = tf_outputs.TerraformOutputsHandler(
            project_path=project_path,
            project_manifest=project_manifest,
        )

        super().__init__(
            project_path=project_path,
            project_manifest=project_manifest,
            output_handler=outputs_handler,
        )
