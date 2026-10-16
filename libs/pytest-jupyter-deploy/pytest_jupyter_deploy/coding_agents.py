"""Prompt the coding agents (Claude Code, Codex) installed on a server, through `jd server exec`.

Both run headless (``claude -p``, ``codex exec``), which skips their first-run dialogs (theme,
trust, onboarding). Callers should assert on a token they ask the model for, never on CLI text,
so that CLI releases cannot break them. ``agent_tui_running`` checks the interactive TUI started
elsewhere (e.g. in a JupyterLab terminal) is still up, again without reading what it renders.
"""

import contextlib
import shlex
import subprocess

from pytest_jupyter_deploy.cli import JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.files import build_server_exec_cmd

CANARY = "JDPONG"
CANARY_PROMPT = f"Reply with the single word {CANARY} and nothing else."
AGENT_TIMEOUT_S = 300

# Matches the agent's own processes by argv[0] (the codex launcher runs under node, so its
# argv[0] is node and the native binary's is a path), and never pgrep's own pattern argument.
_AGENT_PROCESS_PATTERNS = {"claude": "(^|/)claude( |$)", "codex": "(^|/)codex( |$)"}


def _ask(
    e2e_deployment: EndToEndDeployment, argv: list[str], name: str | None, scope: str | None, timeout_s: int
) -> subprocess.CompletedProcess[str]:
    return e2e_deployment.cli.run_exec_with_retry(
        build_server_exec_cmd([shlex.join(argv)], name=name, scope=scope), timeout_seconds=timeout_s
    )


def ask_claude_code(
    e2e_deployment: EndToEndDeployment,
    prompt: str = CANARY_PROMPT,
    name: str | None = None,
    scope: str | None = None,
    timeout_s: int = AGENT_TIMEOUT_S,
) -> str:
    """Return Claude Code's answer to ``prompt``.

    Raises:
        JDCliError: If Claude Code exits non-zero (e.g. it cannot reach its model).
    """
    return _ask(e2e_deployment, ["claude", "-p", prompt], name, scope, timeout_s).stdout


def ask_codex(
    e2e_deployment: EndToEndDeployment,
    prompt: str = CANARY_PROMPT,
    name: str | None = None,
    scope: str | None = None,
    timeout_s: int = AGENT_TIMEOUT_S,
) -> str:
    """Return Codex's answer to ``prompt``; runs outside a git repository.

    Raises:
        JDCliError: If Codex exits non-zero (e.g. it cannot reach its model).
    """
    return _ask(e2e_deployment, ["codex", "exec", "--skip-git-repo-check", prompt], name, scope, timeout_s).stdout


def agent_tui_running(
    e2e_deployment: EndToEndDeployment, agent: str, name: str | None = None, scope: str | None = None
) -> bool:
    """Return whether a process of ``agent`` ("claude" or "codex") runs on the server.

    Raises:
        JDCliError: If the check itself fails (e.g. the image lacks pgrep), rather than
            reporting the agent as stopped.
    """
    cmd = build_server_exec_cmd([shlex.join(["pgrep", "-f", _AGENT_PROCESS_PATTERNS[agent]])], name=name, scope=scope)
    try:
        e2e_deployment.cli.run_exec_with_retry(cmd)
    except JDCliError as e:
        # pgrep exits 1 when nothing matches.
        if isinstance(e.__cause__, subprocess.CalledProcessError) and e.__cause__.returncode == 1:
            return False
        raise
    return True


def stop_agent_tui(
    e2e_deployment: EndToEndDeployment, agent: str, name: str | None = None, scope: str | None = None
) -> None:
    """Kill every process of ``agent`` on the server; a no-op when none runs."""
    cmd = build_server_exec_cmd([shlex.join(["pkill", "-f", _AGENT_PROCESS_PATTERNS[agent]])], name=name, scope=scope)
    with contextlib.suppress(JDCliError):
        e2e_deployment.cli.run_exec_with_retry(cmd)
