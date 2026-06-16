"""Constants for Terraform operations."""

from jupyter_deploy.engine.terraform.tf_enums import TerraformPlanMetadataSource, TerraformSequenceId

# Command constants
TF_INIT_CMD = ["terraform", "init"]
TF_PLAN_CMD = ["terraform", "plan"]
TF_APPLY_CMD = ["terraform", "apply"]
TF_DESTROY_CMD = ["terraform", "destroy"]
TF_OUTPUT_CMD = ["terraform", "output", "-json"]
TF_PARSE_PLAN_CMD = ["terraform", "show", "-json"]
TF_AUTO_APPROVE_CMD_OPTION = "-auto-approve"
TF_RM_FROM_STATE_CMD = ["terraform", "state", "rm"]
TF_INIT_RECONFIGURE_CMD_OPTION = "-reconfigure"
TF_INIT_MIGRATE_CMD_OPTIONS = ["-migrate-state", "-force-copy"]


# Directory constants
TF_ENGINE_DIR = "engine"
TF_PRESETS_DIR = "presets"

# File constants
TF_DEFAULT_PLAN_FILENAME = "jdout-tfplan"
TF_PLAN_METADATA_FILENAME = "jdout-tfplan.meta.json"
TF_RECORDED_VARS_FILENAME = "jdinputs.auto.tfvars"
TF_RECORDED_SECRETS_FILENAME = "jdinputs.secrets.auto.tfvars"
TF_STAGING_VARS_FILENAME = "jdinputs.staging.auto.tfvars"
TF_STAGING_SECRETS_FILENAME = "jdinputs.staging.secrets.auto.tfvars"
TF_CUSTOM_PRESET_FILENAME = "jdinputs.preset.override.tfvars"
TF_DESTROY_PRESET_FILENAME = "destroy.tfvars"
TF_VARIABLES_FILENAME = "variables.tf"
TF_OUTPUTS_FILENAME = "outputs.tf"
TF_BACKEND_FILENAME = "backend.tf"


def get_preset_filename(preset_name: str = "all") -> str:
    """Return the full preset filename."""
    return f"defaults-{preset_name}.tfvars"


# Re-export enums for backward compatibility
__all__ = [
    "TerraformSequenceId",
    "TerraformPlanMetadataSource",
    "TF_INIT_CMD",
    "TF_PLAN_CMD",
    "TF_APPLY_CMD",
    "TF_DESTROY_CMD",
    "TF_OUTPUT_CMD",
    "TF_PARSE_PLAN_CMD",
    "TF_AUTO_APPROVE_CMD_OPTION",
    "TF_RM_FROM_STATE_CMD",
    "TF_INIT_RECONFIGURE_CMD_OPTION",
    "TF_INIT_MIGRATE_CMD_OPTIONS",
    "TF_ENGINE_DIR",
    "TF_PRESETS_DIR",
    "TF_DEFAULT_PLAN_FILENAME",
    "TF_PLAN_METADATA_FILENAME",
    "TF_RECORDED_VARS_FILENAME",
    "TF_RECORDED_SECRETS_FILENAME",
    "TF_STAGING_VARS_FILENAME",
    "TF_STAGING_SECRETS_FILENAME",
    "TF_CUSTOM_PRESET_FILENAME",
    "TF_DESTROY_PRESET_FILENAME",
    "TF_VARIABLES_FILENAME",
    "TF_OUTPUTS_FILENAME",
    "TF_BACKEND_FILENAME",
    "get_preset_filename",
]
