import hcl2
from pydantic import ValidationError

from jupyter_deploy.engine.terraform import tf_vardefs


def parse_variables_dot_tf_content(content: str) -> dict[str, tf_vardefs.TerraformVariableDefinition]:
    """Parse the content of a variables.tf file, return variables as dict name->var_def."""
    if not content:
        return {}

    parsed_variables_dot_tf = hcl2.loads(content)
    parsed_vars = tf_vardefs.ParsedVariablesDotTf(**parsed_variables_dot_tf)

    parsed_vars_definitions = parsed_vars.variable

    result: dict[str, tf_vardefs.TerraformVariableDefinition] = {}

    for idx, parsed_var in enumerate(parsed_vars_definitions):
        if not isinstance(parsed_var, dict):
            print(f"Warning: parsed variable was not a dict at idx: {idx}")
            continue

        var_name = next(iter(parsed_var), None)

        if not var_name or len(parsed_var.keys()) != 1:
            print(f"Warning: parsed variable at idx '{idx}' is not a dict of size 1.")
            continue

        var_config = parsed_var[var_name]

        if not isinstance(var_name, str):
            print(f"Warning: parsed variable key is not a string: {idx}")
            continue
        if not isinstance(var_config, dict):
            print(f"Warning: parsed variable '{var_name}' config is not a dict")
            continue

        tf_type = var_config.pop("type")
        var_config["tf_type"] = tf_type
        var_config["variable_name"] = var_name

        # TODO: handle simple nested type
        if tf_type in [tf_vardefs.TerraformType.LIST_STR, tf_vardefs.TerraformType.MAP_STR]:
            print(f"Skippping nested variables of type: {tf_type}")
            continue

        try:
            var_def = tf_vardefs.create_tf_variable_definition(var_config)
            result.update({var_name: var_def})
        except ValidationError as e:
            print(f"Error parsing variable definition for '{var_name}': {e.errors()}")
            continue
        except RuntimeError as e:
            print(f"Skipping unhandled variable type. {e}")
            continue

    return result


def parse_dot_tfvars_content_and_add_defaults(
    content: str,
    variable_defs: dict[str, tf_vardefs.TerraformVariableDefinition],
) -> None:
    """Parse the content of a .tfvars, add as default to the previously parsed variables definition.

    Modify the 'variable_defs' entries in place.

    This method skips the value of all sensitive variables, as defined in the 'variable_defs'
    parameter.
    """
    parsed_vars_name_default_value_map = hcl2.loads(content)

    for var_name, var_default in parsed_vars_name_default_value_map.items():
        varname = var_name if isinstance(var_name, str) else None

        if not varname:
            print(f"Warning: variable name '{varname}' in .tfvars should be a string; skippin.")
            continue

        if varname not in variable_defs:
            print(f"Warning: variable '{var_name}' in .tfvars file not found in 'variables.tf'; skipping.")
            continue

        var_def = variable_defs[varname]

        if var_def.sensitive:
            print(f"Warning: found value in .tfvars file for sensitive variable '{varname}'; ignoring.")
            continue

        try:
            updated_var_def = tf_vardefs.create_tf_variable_definition({**var_def.model_dump(), "default": var_default})
            variable_defs[varname] = updated_var_def
        except ValidationError as e:
            print(f"Warning: invalid default in .tfvars file for '{varname}', ignoring: {e.errors()}")
            continue
