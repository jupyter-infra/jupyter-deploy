"""Constants for Terraform operations."""

# Command constants
TF_INIT_CMD = ["terraform", "init"]
TF_PLAN_CMD = ["terraform", "plan"]
TF_APPLY_CMD = ["terraform", "apply"]
TF_DESTROY_CMD = ["terraform", "destroy"]
TF_OUTPUT_CMD = ["terraform", "output", "-json"]
TF_PARSE_PLAN_CMD = ["terraform", "show", "-json"]
TF_AUTO_APPROVE_CMD_OPTION = "-auto-approve"
TF_RM_FROM_STATE_CMD = ["terraform", "state", "rm"]

# Directory constants
TF_ENGINE_DIR = "engine"
TF_PRESETS_DIR = "presets"

# File constants
TF_DEFAULT_PLAN_FILENAME = "jdout-tfplan"
TF_RECORDED_VARS_FILENAME = "jdinputs.auto.tfvars"
TF_RECORDED_SECRETS_FILENAME = "jdinputs.secrets.auto.tfvars"
TF_CUSTOM_PRESET_FILENAME = "jdinputs.preset.override.tfvars"
TF_DESTROY_PRESET_FILENAME = "destroy.tfvars"
TF_VARIABLES_FILENAME = "variables.tf"
TF_OUTPUTS_FILENAME = "outputs.tf"


def get_preset_filename(preset_name: str = "all") -> str:
    """Return the full preset filename."""
    return f"defaults-{preset_name}.tfvars"
