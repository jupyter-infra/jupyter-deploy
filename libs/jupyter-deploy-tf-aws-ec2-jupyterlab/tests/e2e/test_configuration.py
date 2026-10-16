"""E2E configuration tests for the aws-ec2-jupyterlab template.

The whole point of this template is a zero-required-argument flow: `jd config` (terraform
plan) must succeed with no domain / OAuth / email variables. These tests therefore carry NO
``@skip_if_testvars_not_set`` decorators — they need AWS credentials, but no test env vars.

Omitted: covered by the base template suite (`test_configuration.py`, `test_config_set.py`,
`test_config_interactive.py`, `test_backward_compatibility.py` — ~30 tests)
  Every `jd config` error-recovery and value-plumbing path: invalid type, malformed YAML, stale
  store-id, list-dict non-nullification, `--verbose`, interactive error recovery, variable
  reset, `--set` for each variable type, and v1 -> v2 `variables.yaml` migration. All of it is
  CLI-layer behavior that does not vary by template, and each case costs a `jd init` plus a
  `terraform init` + `plan`. (The v1 migration is doubly moot here: a v1 `variables.yaml` for
  this template is an empty file.)

Kept: the zero-variable flow, the injected-flag surface (which IS template-specific — the flags
are generated from this template's variables), and the generated-file assertions.

Most tests share a module-scoped ``initialized_project`` / ``configured_project`` so the
expensive part happens a few times rather than once per test. Only the tests that themselves
run or drive `jd config` take their own throwaway project.
"""

import re
import subprocess
from pathlib import Path

import pytest
import yaml
from pytest_jupyter_deploy.cli import JDCli
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.undeployed_project import undeployed_project

# Flags `jd config` must inject for THIS template, derived from its variables.tf at runtime.
_EXPECTED_CONFIG_FLAGS = [
    "--instance-type",
    "--jupyter-package-manager",
    "--additional-ebs-mounts",
    "--additional-efs-mounts",
    "--log-files-retention-days",
]


@pytest.mark.no_deploy
def test_project_is_configurable(e2e_deployment: EndToEndDeployment) -> None:
    """A project configures (terraform plan succeeds) with no required variables.

    1. Create a temporary project directory (in /tmp)
    2. Run `jd init` to initialize the project
    3. Copy the (empty) test configuration variables
    4. Run `jd config` to configure the project
    5. Verify configuration completes without errors and the engine dir was created
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.configure_project(cli=cli)

        engine_dir = project_path / "engine"
        assert engine_dir.exists(), f"Engine directory should exist after config: {engine_dir}"


@pytest.mark.no_deploy
def test_config_requires_no_variables(e2e_deployment: EndToEndDeployment) -> None:
    """`jd config` with no arguments and no variables.yaml edits succeeds (uber-simple flow)."""
    with undeployed_project(e2e_deployment.suite_config) as (_, cli):
        # Do NOT prepare any configuration — the freshly initialized project must be complete.
        result = cli.run_command(["jupyter-deploy", "config"])
        assert "Your project is ready" in result.stdout


@pytest.mark.no_deploy
def test_availability_zone_is_settable_and_clearable_from_the_cli(e2e_deployment: EndToEndDeployment) -> None:
    """`jd config --availability-zone <zone>` pins placement, and `any` gives up the pin again.

    Both directions matter and only the second is subtle. The zone decides where the instance AND
    its EBS volumes land, and EBS cannot cross zones, so this is a deploy-time-only choice — which
    makes "how do I undo it" a real question.

    The sentinel is the word `any` rather than an empty value because the CLI cannot express
    emptiness: `--availability-zone ""` is stored in variables.yaml as '""' and rendered into
    tfvars as a two-character zone name, so it pins garbage instead of clearing the pin. `any` is
    something a caller can actually type.

    Each `jd config` runs a real plan, so this covers the placement lookup end to end — and only a
    real plan does: `terraform validate` cannot catch the unknown-value and empty-list errors this
    path went through, because it never resolves the default VPC's subnets.
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):

        def configured_zone() -> str | None:
            """The zone as terraform receives it, not as variables.yaml spells it.

            `jd config --availability-zone ""` records the cleared override in variables.yaml as
            the two-character string '""', so asserting on the YAML would be asserting on a
            serialization quirk. The generated tfvars is what the template actually consumes.
            """
            tfvars = (project_path / "engine" / "jdinputs.auto.tfvars").read_text()
            match = re.search(r'^availability_zone\s*=\s*"(.*)"$', tfvars, re.MULTILINE)
            return match.group(1) if match else None

        # us-west-2b rather than the zone the suite deploys into: a value that differs from both the
        # preset and the suite's own pin, so a no-op would be visible.
        result = cli.run_command(["jupyter-deploy", "config", "--availability-zone", "us-west-2b"])
        assert "Your project is ready" in result.stdout, f"`jd config` did not complete: {result.stdout[-500:]}"
        assert configured_zone() == "us-west-2b", f"Expected the zone to be pinned, got: {configured_zone()!r}"

        result = cli.run_command(["jupyter-deploy", "config", "--availability-zone", "any"])
        assert "Your project is ready" in result.stdout, (
            f"Giving up the pin broke `jd config`; the sentinel is not usable: {result.stdout[-500:]}"
        )
        assert configured_zone() == "any", f"Expected the zone to be back to any, got: {configured_zone()!r}"


@pytest.mark.no_deploy
def test_config_interactive_accepts_all_defaults(e2e_deployment: EndToEndDeployment) -> None:
    """Interactive `jd config` completes with no prompt at all — the headline flow.

    The base template's interactive test is a script of eight answers (domain, email, OAuth
    id/secret, …). Here the assertion is the inverse and is the template's entire promise: an
    interactive run must never stop to ask. A single `var.` prompt appearing would mean a
    variable had lost its default and the zero-argument flow was quietly broken — which the
    non-interactive test above cannot catch, because a non-tty run fails rather than prompting.
    """
    with undeployed_project(e2e_deployment.suite_config) as (_, cli):
        with cli.spawn_interactive_session("jupyter-deploy config", timeout=300) as session:
            session.expect("Your project is ready")
            transcript = session.before or ""

        assert "var." not in transcript, (
            f"`jd config` prompted for a variable; the zero-argument flow is broken:\n{transcript[-2000:]}"
        )


@pytest.mark.no_deploy
def test_config_help_shows_template_flags(initialized_project: tuple[Path, JDCli]) -> None:
    """`jd config --help` injects this template's variables as flags.

    The flags are generated at runtime from the project's own `variables.tf`, which is why they
    appear on `jd config --help` only from inside a project, so their presence is what proves the
    injection ran against this project rather than a bundled variable set.
    """
    _, cli = initialized_project

    # A wide terminal so rich cannot wrap a long flag name across two lines mid-token.
    result = cli.run_command(["jupyter-deploy", "config", "--help"], env={"COLUMNS": "200"})
    help_text = result.stdout

    missing = [flag for flag in _EXPECTED_CONFIG_FLAGS if flag not in help_text]
    assert not missing, f"`jd config --help` is missing this template's flags: {missing}"


@pytest.mark.no_deploy
def test_variables_yaml_has_no_required_variables(initialized_project: tuple[Path, JDCli]) -> None:
    """The generated project's variables.yaml must have empty required / required_sensitive."""
    project_path, _ = initialized_project

    with open(project_path / "variables.yaml") as f:
        config = yaml.safe_load(f)
    assert not config.get("required"), f"Expected no required variables, got: {config.get('required')}"
    assert not config.get("required_sensitive"), (
        f"Expected no required_sensitive variables, got: {config.get('required_sensitive')}"
    )


@pytest.mark.no_deploy
def test_gitignore_generated_after_init(initialized_project: tuple[Path, JDCli]) -> None:
    """`.gitignore` is generated after `jd init` with the JD + terraform patterns."""
    project_path, _ = initialized_project

    gitignore_path = project_path / ".gitignore"
    assert gitignore_path.exists(), f".gitignore should exist after init: {gitignore_path}"

    content = gitignore_path.read_text()
    assert ".jd-history/" in content
    # #348: without this, `jd up` backs up proxy runtime dirs (logs included) to S3.
    assert ".jd-proxy/" in content
    assert "jdout-" in content
    assert "jdinputs." in content
    assert ".terraform/" in content
    assert ".tfstate" in content
    assert ".terraform.lock.hcl" in content
    assert "{{ engine_ignore_patterns }}" not in content


@pytest.mark.no_deploy
def test_agent_md_generated_after_init(initialized_project: tuple[Path, JDCli]) -> None:
    """AGENT.md is generated (and its .template removed) with all snippets substituted."""
    project_path, _ = initialized_project

    agent_path = project_path / "AGENT.md"
    assert agent_path.exists(), f"AGENT.md should exist after init: {agent_path}"
    assert not (project_path / "AGENT.md.template").exists(), "AGENT.md.template should be removed after init"

    content = agent_path.read_text()
    assert "{{" not in content, "Should not contain template placeholders"
    assert "}}" not in content, "Should not contain template placeholders"


@pytest.mark.no_deploy
def test_troubleshoot_md_generated_after_init(initialized_project: tuple[Path, JDCli]) -> None:
    """TROUBLESHOOT.md is generated (and its .template removed) with all snippets substituted."""
    project_path, _ = initialized_project

    troubleshoot_path = project_path / "TROUBLESHOOT.md"
    assert troubleshoot_path.exists(), f"TROUBLESHOOT.md should exist after init: {troubleshoot_path}"
    assert not (project_path / "TROUBLESHOOT.md.template").exists(), (
        "TROUBLESHOOT.md.template should be removed after init"
    )

    content = troubleshoot_path.read_text()
    assert "{{" not in content, "Should not contain template placeholders"
    assert "}}" not in content, "Should not contain template placeholders"


@pytest.mark.no_deploy
def test_store_config_written_after_config(configured_project: tuple[Path, JDCli]) -> None:
    """`.jd/store.yaml` is created after `jd config` with the s3-only store type."""
    project_path, _ = configured_project

    store_config_path = project_path / ".jd" / "store.yaml"
    assert store_config_path.exists(), f".jd/store.yaml should exist after config: {store_config_path}"

    with open(store_config_path) as f:
        store_config = yaml.safe_load(f)

    assert store_config.get("store-type") == "s3-only", (
        f"Expected store-type 's3-only', got '{store_config.get('store-type')}'"
    )
    assert store_config.get("store-id"), "store-id should not be empty"


@pytest.mark.no_deploy
def test_show_project_id_fails_on_unconfigured_project(configured_project: tuple[Path, JDCli]) -> None:
    """`jd show --project-id` fails gracefully (no stack trace) on an undeployed project."""
    project_path, _ = configured_project

    result = subprocess.run(
        ["jupyter-deploy", "show", "--project-id"],
        capture_output=True,
        text=True,
        cwd=project_path,
    )
    assert result.returncode != 0, "jd show --project-id should fail on an undeployed project"
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr
