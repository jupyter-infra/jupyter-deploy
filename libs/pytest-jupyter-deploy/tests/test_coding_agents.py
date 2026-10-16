"""Unit tests for the coding agent helpers: argument quoting and process detection."""

import re
import shlex
import subprocess
import unittest
from unittest.mock import Mock

from pytest_jupyter_deploy import coding_agents
from pytest_jupyter_deploy.cli import JDCliError


def _exec_failure(returncode: int) -> JDCliError:
    error = JDCliError(f"exit {returncode}")
    error.__cause__ = subprocess.CalledProcessError(returncode, ["jupyter-deploy"])
    return error


def _server_argv(deployment: Mock) -> list[str]:
    """The argv the server runs: `jd server exec` joins its trailing args with spaces, then shlex-splits."""
    cmd = deployment.cli.run_exec_with_retry.call_args.args[0]
    return shlex.split(" ".join(cmd[cmd.index("--") + 1 :]))


class TestAskPromptQuoting(unittest.TestCase):
    def test_claude_code_receives_the_prompt_as_one_argument(self) -> None:
        deployment = Mock()
        coding_agents.ask_claude_code(deployment, prompt="Reply with 'one' word", name="ws", scope="ns")
        self.assertEqual(_server_argv(deployment), ["claude", "-p", "Reply with 'one' word"])

    def test_codex_receives_the_prompt_as_one_argument(self) -> None:
        deployment = Mock()
        coding_agents.ask_codex(deployment, prompt="Reply with one word", name="ws", scope="ns")
        self.assertEqual(_server_argv(deployment), ["codex", "exec", "--skip-git-repo-check", "Reply with one word"])


class TestAgentTuiRunning(unittest.TestCase):
    def test_running_when_pgrep_matches(self) -> None:
        deployment = Mock()
        self.assertTrue(coding_agents.agent_tui_running(deployment, "codex", name="ws", scope="ns"))

    def test_not_running_when_pgrep_matches_nothing(self) -> None:
        deployment = Mock()
        deployment.cli.run_exec_with_retry.side_effect = _exec_failure(1)
        self.assertFalse(coding_agents.agent_tui_running(deployment, "codex", name="ws", scope="ns"))

    def test_raises_when_the_check_itself_fails(self) -> None:
        # e.g. 127: pgrep missing from the image must not read as "the agent exited".
        deployment = Mock()
        deployment.cli.run_exec_with_retry.side_effect = _exec_failure(127)
        with self.assertRaises(JDCliError):
            coding_agents.agent_tui_running(deployment, "codex", name="ws", scope="ns")


class TestAgentProcessPatterns(unittest.TestCase):
    def _matches(self, agent: str, cmdline: str) -> bool:
        # pgrep -f matches an extended regex anywhere in the command line.
        return re.search(coding_agents._AGENT_PROCESS_PATTERNS[agent], cmdline) is not None

    def test_matches_the_agent_processes(self) -> None:
        for agent, cmdline in [
            ("claude", "claude"),
            ("claude", "/usr/local/bin/claude --resume"),
            ("codex", "node /usr/local/bin/codex"),
            ("codex", "/opt/ai-clis/lib/node_modules/@openai/codex/vendor/bin/codex resume"),
        ]:
            with self.subTest(cmdline=cmdline):
                self.assertTrue(self._matches(agent, cmdline))

    def test_ignores_pgrep_and_lookalikes(self) -> None:
        for agent, cmdline in [
            ("claude", f"pgrep -f {coding_agents._AGENT_PROCESS_PATTERNS['claude']}"),
            ("codex", f"pkill -f {coding_agents._AGENT_PROCESS_PATTERNS['codex']}"),
            ("claude", "vim claude-notes.md"),
            ("codex", "/usr/bin/codex-code-mode-host"),
        ]:
            with self.subTest(cmdline=cmdline):
                self.assertFalse(self._matches(agent, cmdline))
