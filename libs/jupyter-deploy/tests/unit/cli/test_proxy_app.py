import json
import re
import unittest
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.proxy_app import proxy_app
from jupyter_deploy.exceptions import (
    NoProxyFoundError,
    ProxyAlreadyRunningError,
    ProxyIdentityUnconfirmedError,
    ProxyNotInstalledError,
    ProxySessionNotFoundError,
)
from jupyter_deploy.handlers.payloads import ProxyConnectBundle, ProxySession, ProxyStatus

_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def _plain(text: str) -> str:
    """Normalize CLI output for substring checks.

    CI forces color, so Rich wraps + styles help/messages: it splits option names across
    style spans (``--path`` → ``-\x1b[0m\x1b[1;36m-path``) and line-wraps long hints. Strip
    ANSI escapes and collapse whitespace so a plain substring assertion is deterministic.
    """
    return re.sub(r"\s+", " ", _ANSI.sub("", text))


class TestProxyApp(unittest.TestCase):
    def test_help_lists_subcommands(self) -> None:
        runner = CliRunner()
        result = runner.invoke(proxy_app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        for cmd in ["connect-info", "start", "open", "stop", "status", "show", "sessions", "logs"]:
            self.assertIn(cmd, _plain(result.stdout))

    def test_no_arg_defaults_to_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(proxy_app, [])
        self.assertIn(result.exit_code, (0, 2))


class TestStartCommand(unittest.TestCase):
    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_always_starts_detached(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.start.return_value = ProxyStatus(state="running", pid=1, alive=True, port=51000, running=True)
        mock_handler_cls.return_value = handler

        result = CliRunner().invoke(proxy_app, ["start"])

        self.assertEqual(result.exit_code, 0)
        handler.start.assert_called_once_with(detached=True)
        self.assertIn("51000", _plain(result.stdout))
        # No flag given → the handler takes the default idle timeout, it is not pinned here.
        self.assertIsNone(mock_handler_cls.call_args.kwargs["idle_timeout_seconds"])

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_idle_timeout_to_handler(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.start.return_value = ProxyStatus(state="running", pid=1, alive=True, port=51000, running=True)
        mock_handler_cls.return_value = handler

        result = CliRunner().invoke(proxy_app, ["start", "--idle-timeout-seconds", "0"])

        self.assertEqual(result.exit_code, 0)
        # 0 opts out of auto-shutdown entirely, so it has to survive as 0 rather than being
        # treated as "unset" and replaced by the default.
        self.assertEqual(mock_handler_cls.call_args.kwargs["idle_timeout_seconds"], 0)

    def test_no_detached_flag(self) -> None:
        # `jd proxy start` is always detached; there is no --detached/-d flag to accept.
        result = CliRunner().invoke(proxy_app, ["start", "-d"])
        self.assertNotEqual(result.exit_code, 0)

    def test_exposes_only_path_flag(self) -> None:
        result = CliRunner().invoke(proxy_app, ["start", "--help"])
        for knob in ["--listen-port", "--log-dir", "--log-level", "--refresh-margin-seconds", "--cidr", "--any-ip"]:
            self.assertNotIn(knob, _plain(result.stdout))
        self.assertIn("--path", _plain(result.stdout))

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_proxy_not_installed_emits_hint(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.start.side_effect = ProxyNotInstalledError("jupyter-deploy-client-proxy")
        mock_handler_cls.return_value = handler

        result = CliRunner().invoke(proxy_app, ["start"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("jupyter-deploy[proxy]", _plain(result.stdout))

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_exits_nonzero_when_already_running(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.start.side_effect = ProxyAlreadyRunningError(pid=999, port=51000)
        mock_handler_cls.return_value = handler

        result = CliRunner().invoke(proxy_app, ["start"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("already running", _plain(result.stdout))
        # points the user at the alternatives instead of clobbering
        self.assertIn("jd proxy stop", _plain(result.stdout))
        self.assertIn("jd proxy open", _plain(result.stdout))

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_start_raises(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.start.side_effect = Exception("Test error")
        mock_handler_cls.return_value = handler

        result = CliRunner().invoke(proxy_app, ["start"])
        self.assertNotEqual(result.exit_code, 0)


class TestOpenCommand(unittest.TestCase):
    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_opens_running_proxy_at_manifest_path(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.project_manifest.get_open.return_value = Mock(path="/lab")
        mock_handler_cls.return_value = handler

        result = CliRunner().invoke(proxy_app, ["open"])

        self.assertEqual(result.exit_code, 0)
        # Pure open — never starts anything; the handler raises if no proxy is running.
        handler.open.assert_called_once_with(path="/lab")
        handler.start.assert_not_called()

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_errors_when_no_proxy_running(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.project_manifest.get_open.return_value = Mock(path="/lab")
        handler.open.side_effect = NoProxyFoundError()
        mock_handler_cls.return_value = handler

        result = CliRunner().invoke(proxy_app, ["open"])

        self.assertNotEqual(result.exit_code, 0)

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_open_raises(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.open.side_effect = Exception("Test error")
        mock_handler_cls.return_value = handler

        result = CliRunner().invoke(proxy_app, ["open"])
        self.assertNotEqual(result.exit_code, 0)


class TestConnectInfoCommand(unittest.TestCase):
    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_emits_bundle_json_on_stdout(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.get_connect_bundle.return_value = ProxyConnectBundle(
            host="203.0.113.7",
            port=443,
            ca_cert="PEM",
            headers={"Authorization": "Bearer k8s-aws-v1.xxx", "x-k8s-aws-id": "dep-abc"},
            expires_at="2026-06-10T18:01:00Z",
        )
        mock_handler_cls.return_value = handler

        runner = CliRunner()
        result = runner.invoke(proxy_app, ["connect-info"])

        self.assertEqual(result.exit_code, 0)
        parsed = json.loads(result.stdout)
        self.assertEqual(
            parsed,
            {
                "host": "203.0.113.7",
                "port": 443,
                "ca_cert": "PEM",
                "headers": {"Authorization": "Bearer k8s-aws-v1.xxx", "x-k8s-aws-id": "dep-abc"},
                "expires_at": "2026-06-10T18:01:00Z",
            },
        )
        handler.get_connect_bundle.assert_called_once_with()

    def test_connect_info_exposes_only_path(self) -> None:
        # SG-door mode is a deploy-time template setting (restrict_origin_ip); no runtime knobs.
        runner = CliRunner()
        result = runner.invoke(proxy_app, ["connect-info", "--help"])
        self.assertNotIn("--any-ip", _plain(result.stdout))
        self.assertNotIn("--cidr", _plain(result.stdout))

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_get_connect_bundle_raises(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.get_connect_bundle.side_effect = Exception("Test error")
        mock_handler_cls.return_value = handler

        result = CliRunner().invoke(proxy_app, ["connect-info"])
        self.assertNotEqual(result.exit_code, 0)


class TestStopCommand(unittest.TestCase):
    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_reports_stopped_pids(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.stop.return_value = [4321]
        mock_handler_cls.return_value = handler

        runner = CliRunner()
        result = runner.invoke(proxy_app, ["stop"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("4321", _plain(result.stdout))

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_exits_nonzero_when_nothing_running(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.stop.side_effect = NoProxyFoundError()
        mock_handler_cls.return_value = handler

        result = CliRunner().invoke(proxy_app, ["stop"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("No running proxy", _plain(result.stdout))

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_exits_nonzero_when_identity_unconfirmed(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.stop.side_effect = ProxyIdentityUnconfirmedError(["/proj/.jd-proxy/server/default/20260610"])
        mock_handler_cls.return_value = handler

        result = CliRunner().invoke(proxy_app, ["stop"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("could not confirm", _plain(result.stdout))
        # points the user at the stale directory for manual cleanup
        self.assertIn("20260610", _plain(result.stdout))

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_stop_raises(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.stop.side_effect = Exception("Test error")
        mock_handler_cls.return_value = handler

        result = CliRunner().invoke(proxy_app, ["stop"])
        self.assertNotEqual(result.exit_code, 0)


class TestStatusCommand(unittest.TestCase):
    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_prints_single_status_string(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.status.return_value = "running"
        mock_handler_cls.return_value = handler

        runner = CliRunner()
        result = runner.invoke(proxy_app, ["status"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Proxy status", _plain(result.stdout))
        self.assertIn("running", _plain(result.stdout))

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_no_proxy_found_exits_one_with_hint(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        # No confirmed running proxy -> a clear error, not a silent "not-running".
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.status.side_effect = NoProxyFoundError()
        mock_handler_cls.return_value = handler

        runner = CliRunner()
        result = runner.invoke(proxy_app, ["status"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("jd proxy start", _plain(result.stdout))

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_status_raises(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.status.side_effect = Exception("Test error")
        mock_handler_cls.return_value = handler

        result = CliRunner().invoke(proxy_app, ["status"])
        self.assertNotEqual(result.exit_code, 0)


class TestShowCommand(unittest.TestCase):
    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_show_prints_detail_json(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.show.return_value = ProxyStatus(
            state="running", pid=4321, alive=True, port=8443, expires_at="2026-06-10T18:01:00Z", running=True
        )
        mock_handler_cls.return_value = handler

        runner = CliRunner()
        result = runner.invoke(proxy_app, ["show", "--json"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["state"], "running")
        self.assertEqual(payload["pid"], 4321)
        self.assertEqual(payload["port"], 8443)
        self.assertEqual(payload["expires_at"], "2026-06-10T18:01:00Z")
        self.assertTrue(payload["alive"])
        self.assertTrue(payload["running"])

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_show_missing_status_file_exits_one(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.show.side_effect = NoProxyFoundError()
        mock_handler_cls.return_value = handler

        runner = CliRunner()
        result = runner.invoke(proxy_app, ["show"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("jd proxy start", _plain(result.stdout))

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_show_raises(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = Mock()
        handler.show.side_effect = Exception("Test error")
        mock_handler_cls.return_value = handler

        result = CliRunner().invoke(proxy_app, ["show"])
        self.assertNotEqual(result.exit_code, 0)


_SESSIONS = [
    ProxySession(
        session_id="20260610-180100.000",
        state="running",
        pid=222,
        port=8002,
        started_at="2026-06-10T18:01:00.000",
        log_dir="/proj/.jd-proxy/server/default/20260610-180100.000",
    ),
    ProxySession(session_id="20260610-180000.000", state="dead", pid=111, started_at="2026-06-10T18:00:00.000"),
]


class TestSessionsCommand(unittest.TestCase):
    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_lists_sessions_as_a_table(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        mock_handler_cls.return_value.sessions.return_value = _SESSIONS

        result = CliRunner().invoke(proxy_app, ["sessions"])

        self.assertEqual(result.exit_code, 0, result.output)
        mock_handler_cls.return_value.sessions.assert_called_once_with(limit=None)
        out = _plain(result.stdout)
        for value in ("20260610-180100.000", "running", "222", "8002", "20260610-180000.000", "dead", "111"):
            self.assertIn(value, out)
        self.assertLess(out.index("20260610-180100.000"), out.index("20260610-180000.000"))

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_json_output_and_limit(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        mock_handler_cls.return_value.sessions.return_value = _SESSIONS[:1]

        result = CliRunner().invoke(proxy_app, ["sessions", "-n", "1", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        mock_handler_cls.return_value.sessions.assert_called_once_with(limit=1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["sessions"][0]["session_id"], "20260610-180100.000")
        self.assertEqual(payload["sessions"][0]["port"], 8002)

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_no_sessions_says_so_and_succeeds(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        mock_handler_cls.return_value.sessions.return_value = []

        result = CliRunner().invoke(proxy_app, ["sessions"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("No proxy session", _plain(result.stdout))
        self.assertIn("jd proxy start", _plain(result.stdout))

    def test_rejects_a_zero_limit(self) -> None:
        result = CliRunner().invoke(proxy_app, ["sessions", "-n", "0"])
        self.assertNotEqual(result.exit_code, 0)


class TestLogsCommand(unittest.TestCase):
    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_prints_the_whole_log_by_default(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = mock_handler_cls.return_value
        handler.session_log_lines.return_value = ("20260610-180100.000", iter(["first\n", "second\n"]))

        result = CliRunner().invoke(proxy_app, ["logs"])

        self.assertEqual(result.exit_code, 0, result.output)
        handler.session_log_lines.assert_called_once_with(session_id=None)
        handler.session_log_tail.assert_not_called()
        self.assertEqual(result.stdout, "first\nsecond\n")

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_lines_and_skip_select_a_tail_window(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = mock_handler_cls.return_value
        handler.session_log_tail.return_value = ("20260610-180000.000", ["[x] not markup\n"])

        result = CliRunner().invoke(proxy_app, ["logs", "--session-id", "20260610-180000.000", "-l", "5", "-s", "2"])

        self.assertEqual(result.exit_code, 0, result.output)
        handler.session_log_tail.assert_called_once_with(session_id="20260610-180000.000", max_lines=5, skip=2)
        self.assertEqual(result.stdout, "[x] not markup\n")

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_skip_alone_uses_the_default_window(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        handler = mock_handler_cls.return_value
        handler.session_log_tail.return_value = ("20260610-180000.000", [])

        result = CliRunner().invoke(proxy_app, ["logs", "-s", "10"])

        self.assertEqual(result.exit_code, 0, result.output)
        handler.session_log_tail.assert_called_once_with(session_id=None, max_lines=1000, skip=10)

    @patch("jupyter_deploy.cli.proxy_app.ProxyHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_unknown_session_exits_one_with_hint(self, mock_project_dir: Mock, mock_handler_cls: Mock) -> None:
        mock_project_dir.return_value.__enter__.return_value = None
        mock_handler_cls.return_value.session_log_lines.side_effect = ProxySessionNotFoundError("nope")

        result = CliRunner().invoke(proxy_app, ["logs", "--session-id", "nope"])

        self.assertEqual(result.exit_code, 1)
        out = _plain(result.stdout)
        self.assertIn("nope", out)
        self.assertIn("jd proxy sessions", out)
