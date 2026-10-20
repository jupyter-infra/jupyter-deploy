"""E2E tests for the coding agents (Claude Code, Codex) shipped in the jupyter image.

Both must answer from the jupyter container with no setup, through Amazon Bedrock and the instance
role credentials. Requires the deployment's account to have the Anthropic and OpenAI models enabled
in Bedrock; the bedrock_enabled_project fixture enables Bedrock on the project if it is off.
"""

from collections.abc import Generator

import pytest
from pytest_jupyter_deploy.coding_agents import CANARY, ask_claude_code, ask_codex
from pytest_jupyter_deploy.deployment import EndToEndDeployment


@pytest.fixture(scope="module")
def bedrock_enabled_project(e2e_deployment: EndToEndDeployment, request: pytest.FixtureRequest) -> Generator[None]:
    """A project with bedrock_enabled set to true.

    Bedrock is off by default, so turning it on changes the project: that only happens where
    mutating cases may run, and the module restores the previous value afterwards. Elsewhere the
    module is skipped.
    """
    e2e_deployment.ensure_deployed()
    if e2e_deployment.get_bool_variable_value("bedrock_enabled"):
        yield
        return

    existing_project = request.config.getoption("--e2e-existing-project")
    if existing_project and not request.config.getoption("--with-mutating-cases"):
        pytest.skip(
            "bedrock_enabled is false on this project: pass --with-mutating-cases to turn it on for this module"
        )

    previous = e2e_deployment.read_override_value("bedrock_enabled")
    e2e_deployment.ensure_deployed_with_overrides({"bedrock_enabled": True})
    try:
        yield
    finally:
        if previous is None:
            e2e_deployment.ensure_deployed_with(["--reset-variable", "bedrock_enabled"])
        else:
            e2e_deployment.ensure_deployed_with_overrides({"bedrock_enabled": previous})


def test_claude_code_answers_through_bedrock(e2e_deployment: EndToEndDeployment, bedrock_enabled_project: None) -> None:
    """Claude Code answers a prompt with no setup."""
    assert CANARY in ask_claude_code(e2e_deployment)


def test_codex_answers_through_bedrock(e2e_deployment: EndToEndDeployment, bedrock_enabled_project: None) -> None:
    """Codex answers a prompt with no setup."""
    assert CANARY in ask_codex(e2e_deployment)
