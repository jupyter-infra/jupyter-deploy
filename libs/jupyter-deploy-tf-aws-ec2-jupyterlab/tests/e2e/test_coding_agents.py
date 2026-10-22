"""E2E tests for the coding agents (Claude Code, Codex) shipped in the jupyter image.

Both must answer from the jupyter container with no setup, through Amazon Bedrock and the instance
role credentials. Requires the deployment's account to have the Anthropic and OpenAI models enabled
in Bedrock; the bedrock_enabled_project fixture enables Bedrock on the project if it is off.
"""

from pytest_jupyter_deploy.coding_agents import CANARY, ask_claude_code, ask_codex
from pytest_jupyter_deploy.deployment import EndToEndDeployment


def test_claude_code_answers_through_bedrock(e2e_deployment: EndToEndDeployment, bedrock_enabled_project: None) -> None:
    assert CANARY in ask_claude_code(e2e_deployment)


def test_codex_answers_through_bedrock(e2e_deployment: EndToEndDeployment, bedrock_enabled_project: None) -> None:
    assert CANARY in ask_codex(e2e_deployment)
