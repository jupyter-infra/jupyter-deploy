import json
from typing import Any

from pydantic import BaseModel, ConfigDict


class TerraformPlanRootModuleVariable(BaseModel):
    model_config = ConfigDict(extra="allow")
    description: str | None = None
    sensitive: bool | None = False


class TerraformPlanRootModule(BaseModel):
    model_config = ConfigDict(extra="allow")
    variables: dict[str, TerraformPlanRootModuleVariable]


class TerraformPlanConfiguration(BaseModel):
    model_config = ConfigDict(extra="allow")
    root_module: TerraformPlanRootModule


class TerraformPlanVariableContent(BaseModel):
    model_config = ConfigDict(extra="allow")
    value: Any | None


class TerraformPlan(BaseModel):
    model_config = ConfigDict(extra="allow")
    variables: dict[str, TerraformPlanVariableContent]
    configuration: TerraformPlanConfiguration


def format_terraform_value(value: Any) -> str:
    """Format a value for a .tfvars file."""
    if value is None:
        return "null"
    elif isinstance(value, str):
        # Escape quotes in strings
        escaped_value = value.replace('"', '\\"')
        return f'"{escaped_value}"'
    elif isinstance(value, bool):
        return str(value).lower()
    elif isinstance(value, list):
        if not len(value):
            return "[]"
        out = ["["] + [f"{format_terraform_value(v)}," for v in value] + ["]"]
        return "\n".join(out)
    elif isinstance(value, dict):
        if not len(value):
            return "{}"

        out = ["{"]
        for key, val in value.items():
            out.append(f"{key} = {format_terraform_value(val)}")
        out.append("}")
        return "\n".join(out)
    else:
        return str(value)


def extract_variables_from_json_plan(
    plan_content: str,
) -> tuple[dict[str, TerraformPlanVariableContent], dict[str, TerraformPlanVariableContent]]:
    """Parse the content of a terraform plan as json, return tuple of variables, secrets.

    Raise:
        ValueError if the plan_content is not a valid JSON
        ValueError if the plan_content is not a dict
        ValidationError if the plan_content.variables does not conform to the schema
    """
    try:
        parsed_plan = json.loads(plan_content)
    except json.JSONDecodeError as e:
        raise ValueError("Terraform plan cannot be parsed as JSON.") from e

    if type(parsed_plan) is not dict:
        raise ValueError("Terraform plan is not valid: excepted a dict.")

    plan = TerraformPlan(**parsed_plan)

    sensitive_varnames = set(
        [var_name for var_name, var_config in plan.configuration.root_module.variables.items() if var_config.sensitive]
    )

    variables = {
        var_name: var_value for var_name, var_value in plan.variables.items() if var_name not in sensitive_varnames
    }
    secrets = {var_name: var_value for var_name, var_value in plan.variables.items() if var_name in sensitive_varnames}

    return variables, secrets


def format_plan_variables(vars: dict[str, TerraformPlanVariableContent]) -> list[str]:
    """Return a dict of terraform plan variable entries to a list to save to a .tfvars file."""
    return [f"{name} = {format_terraform_value(var.value)}\n" for name, var in vars.items()]
