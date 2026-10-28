"""E2E tests for the coding agents (Claude Code, Codex) shipped in the jupyter image.

Both must answer from the jupyter container with no setup, through Amazon Bedrock and the
credentials of a Bedrock-only app role: a sidecar assumes it from the instance role and publishes
the credentials to a file the container reads, so the container never holds the instance role and
cannot reach the instance metadata service at all. Requires the deployment's account to have the
Anthropic and OpenAI models enabled in Bedrock.

Non-ordered tests assume Bedrock is on (the default; ``bedrock_enabled_project`` handles an existing
project that turned it off). The ordered ones are the Bedrock half of the mutating pass: see
``constants.py`` for why each applies inline and the next test is its restore.
"""

import time
from datetime import UTC, datetime

import pytest
from pytest_jupyter_deploy.coding_agents import (
    BEDROCK_SIDECAR_SERVICE,
    CANARY,
    CANARY_PROMPT,
    agent_tui_running,
    app_role_access,
    ask_agent_expecting_failure,
    ask_claude_code,
    ask_codex,
    credentials_expiration,
    imds_reachable,
    read_app_credentials,
    restart_service,
    stop_agent_tui,
    wait_for_rotated_app_credentials,
)
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.files import build_server_exec_cmd
from pytest_jupyter_deploy.jupyterlab.terminal import (
    close_jupyterlab_terminal,
    open_jupyterlab_terminal,
    type_in_jupyterlab_terminal,
)
from pytest_jupyter_deploy.local_proxy import LocalProxyApplication
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set

from .constants import (
    ORDER_CODING_AGENTS_AFTER_GPU_PIXI,
    ORDER_MUTATING_BEDROCK_GEO,
    ORDER_MUTATING_BEDROCK_GLOBAL,
    ORDER_MUTATING_BEDROCK_OFF,
)

# A TUI missing a runtime dependency exits within seconds of starting; one still up after
# this long is waiting on its user.
TUI_SETTLE_S = 15


def _assert_both_agents_answer(e2e_deployment: EndToEndDeployment) -> None:
    assert CANARY in ask_claude_code(e2e_deployment)
    assert CANARY in ask_codex(e2e_deployment)


def _region_prefix(e2e_deployment: EndToEndDeployment) -> str:
    result = e2e_deployment.cli.run_command(build_server_exec_cmd(["printenv", "ANTHROPIC_BEDROCK_REGION_PREFIX"]))
    return result.stdout.split()[-1]


# --------------------------------------------------------------------------- Bedrock on (default)


def test_claude_code_answers_through_bedrock(e2e_deployment: EndToEndDeployment, bedrock_enabled_project: None) -> None:
    assert CANARY in ask_claude_code(e2e_deployment)


def test_codex_answers_through_bedrock(e2e_deployment: EndToEndDeployment, bedrock_enabled_project: None) -> None:
    assert CANARY in ask_codex(e2e_deployment)


@pytest.mark.parametrize("agent", ["claude", "codex"])
def test_agent_tui_starts_in_jupyterlab_terminal(
    e2e_deployment: EndToEndDeployment,
    client_proxy_app: LocalProxyApplication,
    bedrock_enabled_project: None,
    agent: str,
) -> None:
    """The agent's TUI starts from a JupyterLab terminal and stays up."""
    e2e_deployment.ensure_server_running()
    client_proxy_app.verify_jupyterlab_accessible()
    stop_agent_tui(e2e_deployment, agent)
    terminal = open_jupyterlab_terminal(client_proxy_app.page)
    try:
        type_in_jupyterlab_terminal(client_proxy_app.page, terminal, agent)
        time.sleep(TUI_SETTLE_S)
        assert agent_tui_running(e2e_deployment, agent), (
            f"{agent} exited within {TUI_SETTLE_S}s of starting in the JupyterLab terminal"
        )
    finally:
        stop_agent_tui(e2e_deployment, agent)
        close_jupyterlab_terminal(client_proxy_app.page, terminal)


def test_jupyter_cannot_reach_imds(e2e_deployment: EndToEndDeployment, bedrock_enabled_project: None) -> None:
    """The container must never see the instance role: IMDS is dropped at the docker network edge."""
    assert not imds_reachable(e2e_deployment)


def test_app_role_is_bedrock_only(e2e_deployment: EndToEndDeployment, bedrock_enabled_project: None) -> None:
    """Credentials in the container belong to the app role, which reaches Bedrock and nothing else."""
    bucket = e2e_deployment.cli.get_str_output("deployment_scripts_bucket_name")
    access = app_role_access(e2e_deployment, bucket)
    assert "bedrock-app" in access["arn"], access
    assert access["bedrock_ok"], access
    assert access["s3_denied"], access


def test_app_credentials_rotate(e2e_deployment: EndToEndDeployment, bedrock_enabled_project: None) -> None:
    """A sidecar restart publishes a new key the agents pick up without their own restart."""
    before = read_app_credentials(e2e_deployment)
    assert credentials_expiration(before) > datetime.now(UTC), before["Expiration"]

    restart_service(e2e_deployment, BEDROCK_SIDECAR_SERVICE)
    after = wait_for_rotated_app_credentials(e2e_deployment, before["AccessKeyId"])
    assert credentials_expiration(after) > datetime.now(UTC), after["Expiration"]
    assert CANARY in ask_claude_code(e2e_deployment)


# --------------------------------------------------------------------------- mutating pass


@pytest.mark.order(ORDER_CODING_AGENTS_AFTER_GPU_PIXI)
@pytest.mark.mutating
@pytest.mark.gpu
@skip_if_testvars_not_set(["JD_E2E_GPU_INSTANCE", "JD_E2E_LARGER_LOG_RETENTION_DAYS"])
def test_agents_answer_on_pixi_after_instance_swap(e2e_deployment: EndToEndDeployment) -> None:
    """Right after apply #1: the pixi image ships the agents too, and the new instance got credentials."""
    assert e2e_deployment.get_str_variable_value("jupyter_package_manager") == "pixi", "run after apply #1"
    if not e2e_deployment.get_bool_variable_value("bedrock_enabled"):
        pytest.skip("bedrock_enabled is false on this project")
    e2e_deployment.ensure_server_running()
    _assert_both_agents_answer(e2e_deployment)


@pytest.mark.order(ORDER_MUTATING_BEDROCK_OFF)
@pytest.mark.mutating
def test_bedrock_off_removes_the_sidecar_and_the_agents_fail_clearly(e2e_deployment: EndToEndDeployment) -> None:
    """Apply: Bedrock off. No sidecar, no credentials, both agents fail on the missing model, app stays up."""
    e2e_deployment.ensure_deployed_with_overrides({"bedrock_enabled": False})
    e2e_deployment.ensure_server_running()

    claude_failure = ask_agent_expecting_failure(e2e_deployment, ["claude", "-p", CANARY_PROMPT])
    assert "credentials" in claude_failure.lower(), claude_failure
    codex_failure = ask_agent_expecting_failure(
        e2e_deployment, ["codex", "exec", "--skip-git-repo-check", CANARY_PROMPT]
    )
    assert "unset: bedrock_enabled is false" in codex_failure, codex_failure

    assert e2e_deployment.cli.get_server_status() == "IN_SERVICE"
    e2e_deployment.cli.run_command_expecting_failure(
        ["jupyter-deploy", "server", "logs", "--service", BEDROCK_SIDECAR_SERVICE]
    )


@pytest.mark.order(ORDER_MUTATING_BEDROCK_GLOBAL)
@pytest.mark.mutating
def test_bedrock_global_scope_answers(e2e_deployment: EndToEndDeployment) -> None:
    """Apply: Bedrock back on with global inference profiles; restores the sidecar after the off apply."""
    e2e_deployment.ensure_deployed_with_overrides({"bedrock_enabled": True, "bedrock_inference_scope": "global"})
    e2e_deployment.ensure_server_running()
    assert _region_prefix(e2e_deployment) == "global"
    _assert_both_agents_answer(e2e_deployment)


@pytest.mark.order(ORDER_MUTATING_BEDROCK_GEO)
@pytest.mark.mutating
def test_bedrock_defaults_restored(e2e_deployment: EndToEndDeployment) -> None:
    """Apply: back to the defaults (geo scope); ends the on -> off -> on round trip."""
    e2e_deployment.ensure_deployed_with(
        ["--reset-variable", "bedrock_inference_scope", "--reset-variable", "bedrock_enabled"]
    )
    e2e_deployment.ensure_server_running()
    assert _region_prefix(e2e_deployment) != "global"
    _assert_both_agents_answer(e2e_deployment)
