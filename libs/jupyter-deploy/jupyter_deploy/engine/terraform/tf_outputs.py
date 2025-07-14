from pathlib import Path

from jupyter_deploy import cmd_utils, fs_utils
from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.outdefs import TemplateOutputDefinition
from jupyter_deploy.engine.terraform import tf_outdefs, tf_outfiles
from jupyter_deploy.engine.terraform.tf_constants import TF_ENGINE_DIR, TF_OUTPUT_CMD, TF_OUTPUTS_FILENAME
from jupyter_deploy.manifest import JupyterDeployManifest


class TerraformOutputsHandler(EngineOutputsHandler):
    """Terraform-specific implementation of the OutputsHandler."""

    def __init__(self, project_path: Path, project_manifest: JupyterDeployManifest) -> None:
        self.project_path = project_path
        self.project_manifest = project_manifest
        self._full_template_outputs: dict[str, TemplateOutputDefinition] | None = None
        self.engine_dir_path = project_path / TF_ENGINE_DIR

    def get_full_project_outputs(self) -> dict[str, TemplateOutputDefinition]:
        # cache handling to avoid the expensive fs operation necessary
        # to retrieve the output definitions.
        if self._full_template_outputs:
            return self._full_template_outputs

        # execute the terraform output command
        output_cmd = TF_OUTPUT_CMD.copy()
        output_content = cmd_utils.run_cmd_and_capture_output(output_cmd, exec_dir=self.engine_dir_path)
        output_defs_from_cmd = tf_outdefs.parse_output_cmd_result(output_content)

        # read the outputs.tf, retrieve the description
        outputs_dot_tf_path = self.engine_dir_path / TF_OUTPUTS_FILENAME
        output_dot_tf_content = fs_utils.read_short_file(outputs_dot_tf_path)
        description_from_outputs_dot_tf = tf_outfiles.extract_description_from_dot_tf_content(output_dot_tf_content)

        combined_output_defs = tf_outfiles.combine_cmd_and_outputs_dot_tf_results(
            output_defs_from_cmd=output_defs_from_cmd,
            descriptions_from_file=description_from_outputs_dot_tf,
        )

        template_output_defs = {
            output_name: output_def.to_template_definition() for output_name, output_def in combined_output_defs.items()
        }
        self._full_template_outputs = template_output_defs
        return template_output_defs

    def get_output_definition(self, output_name: str) -> TemplateOutputDefinition:
        full_template_outputs = self.get_full_project_outputs()
        output_def = full_template_outputs.get(output_name)

        if not output_def:
            raise ValueError(f"Output name not found: {output_name}")
        return output_def
