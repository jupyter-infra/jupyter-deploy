"""E2E tests for `jd show` — restricted to what THIS template declares.

Omitted: covered by the base template suite (`test_show.py`, 16 tests)
  Everything about how `jd show` *renders*: the variables/outputs list mechanics, single-line
  and multi-line descriptions, `--info` composition, `--reveal`, project-id / store-id /
  store-type plumbing, template-name and template-version lookup, and bare `jd show`. All of
  it is CLI-layer behavior, identical for every template, and additionally covered by
  `tests/unit/test_manifest_yaml.py` / `test_version.py`. Re-testing it here would buy nothing
  and cost a `jd init` + `jd config` (terraform init + plan) per test — the most expensive
  thing in this suite.

What is left is the four assertions that are about this template's declared surface: its
outputs set, its no-secrets invariant, and the two outputs the access path depends on.
"""

from jupyter_deploy.engine.terraform.tf_varfiles import parse_variables_dot_tf_content
from jupyter_deploy.enum import ValueSource
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.terraform.utils import get_variables_dot_tf_path


def test_show_outputs_list_matches_template(e2e_deployment: EndToEndDeployment) -> None:
    """`jd show --outputs --list` exposes every output this template's manifest declares.

    The manifest resolves command arguments by output name, so a renamed or dropped output does
    not fail at plan time — it fails at `jd server logs` time, with a resolution error.

    Derived from the manifest rather than checked against a hand-listed set: a literal list has to
    be maintained by hand and goes stale silently. The outputs named only in command *arguments*
    (the SSM document names) are covered where they are used — `test_server.py` for the `server_*`
    documents, `test_teams.py`/`test_users.py` for `auth_*_update_document`, `test_auth.py` for
    `auth_check_document` — so a dropped one fails there with a real symptom.
    """
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--outputs", "--list", "--text"])
    output_names = {name.strip().replace("\n", "") for name in result.stdout.strip().split(",") if name.strip()}

    manifest = e2e_deployment.get_manifest()
    declared = {value.source_key for value in (manifest.values or []) if value.source == ValueSource.TEMPLATE_OUTPUT}
    assert declared.issubset(output_names), (
        f"Manifest declares outputs the template does not emit: {declared - output_names}"
    )


def test_show_declares_no_sensitive_variables(e2e_deployment: EndToEndDeployment) -> None:
    """This template declares no sensitive variable — there is nothing to mask or `--reveal`.

    The no-secrets invariant, and the reason the template needs no `--restore-secrets` on
    restore and no Secrets Manager entry: access is proven by the caller's own AWS credentials,
    which never enter the project. A `sensitive = true` variable appearing here would mean a
    long-lived secret had been reintroduced into the deployment's state.
    """
    e2e_deployment.ensure_deployed()

    variables_tf = get_variables_dot_tf_path(e2e_deployment.suite_config.project_dir)
    declared = parse_variables_dot_tf_content(variables_tf.read_text())

    # Guard the guard: a parse that silently yields nothing would make the assertion below pass
    # vacuously, which is how the previous regex-based version of this test went blind.
    assert declared, f"Parsed no variable definitions out of {variables_tf}"

    sensitive = sorted(name for name, var_def in declared.items() if var_def.sensitive)
    assert not sensitive, f"Expected no sensitive variables, found: {sensitive}"

    variables_config = e2e_deployment.get_variables_config()
    assert not variables_config.required_sensitive, (
        f"Expected no required_sensitive variables, got: {variables_config.required_sensitive}"
    )
