"""Unit tests for the coding agent helpers: argument quoting, process detection, app-role probes."""

import base64
import json
import re
import shlex
import subprocess
import unittest
from unittest.mock import Mock, patch

from pytest_jupyter_deploy import coding_agents
from pytest_jupyter_deploy.cli import JDCliError


def _exec_failure(returncode: int) -> JDCliError:
    error = JDCliError(f"exit {returncode}")
    error.__cause__ = subprocess.CalledProcessError(returncode, ["jupyter-deploy"])
    return error


def _server_argv(deployment: Mock, method: str = "run_exec_with_retry") -> list[str]:
    """The argv the server runs: `jd server exec` joins its trailing args with spaces, then shlex-splits."""
    cmd = getattr(deployment.cli, method).call_args.args[0]
    return shlex.split(" ".join(cmd[cmd.index("--") + 1 :]))


def _exec_output(payload: str) -> str:
    """What `jd server exec` prints: rich rules around the container's stdout."""
    return f"──── stdout ────\n{payload}\n────────────────\n"


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


class TestAppRoleProbe(unittest.TestCase):
    def test_script_probes_every_boundary_of_the_app_role(self) -> None:
        for call in ("get_caller_identity", "list_foundation_models", "list_objects_v2", "get_secret_value"):
            with self.subTest(call=call):
                self.assertIn(call, coding_agents.APP_ROLE_PROBE_SCRIPT)
        compile(coding_agents.APP_ROLE_PROBE_SCRIPT, "<probe>", "exec")

    def test_runs_in_jupyter_with_boto3_and_returns_the_report(self) -> None:
        deployment = Mock()
        report = {"arn": "arn:aws:sts::1:assumed-role/x-bedrock-app/jupyter", "bedrock_ok": True, "s3_denied": True}
        deployment.cli.run_command.return_value.stdout = _exec_output(json.dumps(report))

        self.assertEqual(coding_agents.app_role_access(deployment, "bucket", "arn:secret"), report)

        argv = _server_argv(deployment, "run_command")
        self.assertEqual(argv[:6], ["uv", "run", "--with", "boto3", "python", "-c"])
        self.assertEqual(argv[7:], ["bucket", "arn:secret"])
        encoded = re.search(r"b64decode\('([^']+)'\)", argv[6])
        assert encoded is not None
        self.assertEqual(base64.b64decode(encoded.group(1)).decode(), coding_agents.APP_ROLE_PROBE_SCRIPT)

    def test_omits_the_secret_when_none(self) -> None:
        deployment = Mock()
        deployment.cli.run_command.return_value.stdout = _exec_output("{}")
        coding_agents.app_role_access(deployment, "bucket")
        self.assertEqual(_server_argv(deployment, "run_command")[7:], ["bucket"])


class TestReadAppCredentials(unittest.TestCase):
    def test_parses_the_json_line_and_widens_the_terminal(self) -> None:
        deployment = Mock()
        creds = {"Version": 1, "AccessKeyId": "ASIA1", "Expiration": "2026-10-27T12:00:00Z"}
        deployment.cli.run_command.return_value.stdout = _exec_output(json.dumps(creds))

        self.assertEqual(coding_agents.read_app_credentials(deployment), creds)
        self.assertEqual(_server_argv(deployment, "run_command"), ["cat", coding_agents.APP_CREDENTIALS_PATH])
        # Without a wide COLUMNS rich folds the session token across lines.
        self.assertIn("COLUMNS", deployment.cli.run_command.call_args.kwargs["env"])

    def test_expiration_parses_the_cli_zulu_format(self) -> None:
        expiration = coding_agents.credentials_expiration({"Expiration": "2026-10-27T12:00:00Z"})
        self.assertEqual(expiration.utcoffset().total_seconds(), 0)  # type: ignore[union-attr]

    def test_raises_without_a_json_line(self) -> None:
        deployment = Mock()
        deployment.cli.run_command.return_value.stdout = _exec_output("cat: No such file")
        with self.assertRaises(AssertionError):
            coding_agents.read_app_credentials(deployment)


class TestWaitForRotatedAppCredentials(unittest.TestCase):
    @patch("pytest_jupyter_deploy.coding_agents.time.sleep")
    def test_returns_once_the_key_changes(self, sleep: Mock) -> None:
        deployment = Mock()
        deployment.cli.run_command.return_value.stdout = _exec_output('{"AccessKeyId": "ASIA2"}')
        creds = coding_agents.wait_for_rotated_app_credentials(deployment, "ASIA1")
        self.assertEqual(creds["AccessKeyId"], "ASIA2")
        sleep.assert_not_called()

    @patch("pytest_jupyter_deploy.coding_agents.time.sleep")
    def test_fails_when_the_key_never_changes(self, sleep: Mock) -> None:
        deployment = Mock()
        deployment.cli.run_command.return_value.stdout = _exec_output('{"AccessKeyId": "ASIA1"}')
        with self.assertRaises(AssertionError):
            coding_agents.wait_for_rotated_app_credentials(deployment, "ASIA1", timeout_s=0)


class TestImdsReachable(unittest.TestCase):
    def test_reachable_when_curl_exits_zero(self) -> None:
        deployment = Mock()
        self.assertTrue(coding_agents.imds_reachable(deployment))
        argv = _server_argv(deployment, "run_command")
        self.assertEqual(argv[0], "curl")
        self.assertIn("http://169.254.169.254/latest/api/token", argv)
        self.assertIn("X-aws-ec2-metadata-token-ttl-seconds: 60", argv)

    def test_unreachable_when_curl_fails(self) -> None:
        deployment = Mock()
        deployment.cli.run_command.side_effect = _exec_failure(28)
        self.assertFalse(coding_agents.imds_reachable(deployment))


class TestAskAgentExpectingFailure(unittest.TestCase):
    def test_forwards_the_quoted_argv_and_returns_the_text(self) -> None:
        deployment = Mock()
        deployment.cli.run_command_expecting_failure.return_value = "No credentials found"
        text = coding_agents.ask_agent_expecting_failure(deployment, ["claude", "-p", "two words"])
        self.assertEqual(text, "No credentials found")
        self.assertEqual(_server_argv(deployment, "run_command_expecting_failure"), ["claude", "-p", "two words"])


class TestRestartService(unittest.TestCase):
    def test_restarts_the_named_service(self) -> None:
        deployment = Mock()
        coding_agents.restart_service(deployment, "bedrock-sidecar")
        deployment.cli.run_command.assert_called_once_with(
            ["jupyter-deploy", "server", "restart", "--service", "bedrock-sidecar"]
        )
