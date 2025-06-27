import hcl2

from jupyter_deploy.engine.terraform import tf_outdefs


def extract_description_from_dot_tf_content(content: str) -> dict[str, str]:
    """Parse the content of a outputs.tf file, return outputs as dict name->description."""
    if not content:
        return {}

    parsed_outputs_dot_tf = hcl2.loads(content)
    parsed_outputs = tf_outdefs.ParsedOutputsDotTf(**parsed_outputs_dot_tf)
    parsed_outputs_definitions = parsed_outputs.output

    result: dict[str, str] = {}

    for idx, parsed_out in enumerate(parsed_outputs_definitions):
        if not isinstance(parsed_out, dict):
            print(f"Warning: parsed output was not a dict at idx: {idx}")
            continue

        out_name = next(iter(parsed_out), None)

        if not out_name or len(parsed_out.keys()) != 1:
            print(f"Warning: parsed output at idx '{idx}' is not a dict of size 1.")
            continue

        out_config = parsed_out[out_name]

        if not isinstance(out_name, str):
            print(f"Warning: parsed output key is not a string: {idx}")
            continue
        if not isinstance(out_config, dict):
            print(f"Warning: parsed output '{out_name}' config is not a dict")
            continue

        description = out_config.get("description", "")
        if not isinstance(description, str):
            print(f"Warning: parsed output '{out_name}' description is not a str")
            description = ""

        result.update({out_name: description})

    return result


def combine_cmd_and_outputs_dot_tf_results(
    output_defs_from_cmd: dict[str, tf_outdefs.TerraformOutputDefinition],
    descriptions_from_file: dict[str, str],
) -> dict[str, tf_outdefs.TerraformOutputDefinition]:
    """Adds to description to the output_defs from cmd, return updated dict."""

    for output_name, output_def_from_cmd in output_defs_from_cmd.items():
        description = descriptions_from_file.get(output_name)

        if description is None:
            print(f"Warning: output '{output_name}' not found in outputs.tf file.")
            output_def_from_cmd.description = ""
            continue

        output_def_from_cmd.description = description

    return output_defs_from_cmd
