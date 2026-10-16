"""E2E tests for the coding agents (Claude Code, Codex) shipped in the JupyterLab workspace image.

Both must answer from a workspace with no setup, through Amazon Bedrock, and their interactive
TUIs must start in JupyterLab's embedded terminal. Requires the deployment's account to have the
Anthropic and OpenAI models enabled in Bedrock; the coding_agents_workspace fixture enables
Bedrock on the deployment if it is off.
"""

import time

import pytest
from pytest_jupyter_deploy.coding_agents import CANARY, agent_tui_running, ask_claude_code, ask_codex, stop_agent_tui
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.jupyterlab.terminal import (
    close_jupyterlab_terminal,
    open_jupyterlab_terminal,
    type_in_jupyterlab_terminal,
)
from pytest_jupyter_deploy.oauth2_proxy.dex import DexGitHubOAuth2ProxyApplication
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.workspaces.kubectl import kubectl_get_workspace_access_url

from .constants import WORKSPACE_NAMESPACE

# A TUI missing a runtime dependency exits within seconds of starting; one still up after
# this long is waiting on its user.
TUI_SETTLE_S = 15


def test_claude_code_answers_through_bedrock(e2e_deployment: EndToEndDeployment, coding_agents_workspace: str) -> None:
    """Claude Code answers a prompt with no setup."""
    assert CANARY in ask_claude_code(e2e_deployment, name=coding_agents_workspace, scope=WORKSPACE_NAMESPACE)


def test_codex_answers_through_bedrock(e2e_deployment: EndToEndDeployment, coding_agents_workspace: str) -> None:
    """Codex answers a prompt with no setup."""
    assert CANARY in ask_codex(e2e_deployment, name=coding_agents_workspace, scope=WORKSPACE_NAMESPACE)


@pytest.mark.parametrize("agent", ["claude", "codex"])
@skip_if_testvars_not_set(["JD_E2E_USER"])
def test_agent_tui_starts_in_jupyterlab_terminal(
    e2e_deployment: EndToEndDeployment,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
    coding_agents_workspace: str,
    agent: str,
) -> None:
    """The agent's TUI starts from a JupyterLab terminal and stays up."""
    dex_oauth_app.verify_workspace_accessible(
        kubectl_get_workspace_access_url(coding_agents_workspace, WORKSPACE_NAMESPACE)
    )
    stop_agent_tui(e2e_deployment, agent, name=coding_agents_workspace, scope=WORKSPACE_NAMESPACE)
    terminal = open_jupyterlab_terminal(dex_oauth_app.page)
    try:
        type_in_jupyterlab_terminal(dex_oauth_app.page, terminal, agent)
        time.sleep(TUI_SETTLE_S)
        assert agent_tui_running(e2e_deployment, agent, name=coding_agents_workspace, scope=WORKSPACE_NAMESPACE), (
            f"{agent} exited within {TUI_SETTLE_S}s of starting in the JupyterLab terminal"
        )
    finally:
        stop_agent_tui(e2e_deployment, agent, name=coding_agents_workspace, scope=WORKSPACE_NAMESPACE)
        close_jupyterlab_terminal(dex_oauth_app.page, terminal)
