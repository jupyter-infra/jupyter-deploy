"""Unit tests for the local client-proxy helpers (LocalProxyApplication + JDCli proxy methods)."""

import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pytest_jupyter_deploy.cli import JDCli, JDCliError
from pytest_jupyter_deploy.local_proxy import LocalProxyApplication


def _completed(stdout: str) -> subprocess.CompletedProcess[str]:
    """Build a CompletedProcess with the given stdout (as JDCli.run_command returns)."""
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


class TestJDCliProxyMethods(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = JDCli(Path("/tmp/project"))

    def test_get_proxy_port_parses_json(self) -> None:
        with patch.object(self.cli, "run_command", return_value=_completed('{"state": "running", "port": 54321}\n')):
            assert self.cli.get_proxy_port() == 54321

    def test_get_proxy_port_raises_when_no_port(self) -> None:
        with (
            patch.object(self.cli, "run_command", return_value=_completed('{"state": "running", "port": null}')),
            self.assertRaises(JDCliError),
        ):
            self.cli.get_proxy_port()

    def test_get_proxy_url_appends_path(self) -> None:
        with patch.object(self.cli, "get_proxy_port", return_value=8080):
            assert self.cli.get_proxy_url("/lab") == "http://127.0.0.1:8080/lab"

    def test_get_proxy_url_no_path(self) -> None:
        with patch.object(self.cli, "get_proxy_port", return_value=8080):
            assert self.cli.get_proxy_url() == "http://127.0.0.1:8080"

    def test_start_proxy_starts_then_reads_url(self) -> None:
        with (
            patch.object(self.cli, "run_command") as mock_run,
            patch.object(self.cli, "get_proxy_port", return_value=9000),
        ):
            url = self.cli.start_proxy("/lab")

        assert url == "http://127.0.0.1:9000/lab"
        mock_run.assert_called_once_with(["jupyter-deploy", "proxy", "start"])

    def test_start_proxy_passes_idle_timeout_when_given(self) -> None:
        with (
            patch.object(self.cli, "run_command") as mock_run,
            patch.object(self.cli, "get_proxy_port", return_value=9000),
        ):
            self.cli.start_proxy(idle_timeout_seconds=45)

        mock_run.assert_called_once_with(
            ["jupyter-deploy", "proxy", "start", "--idle-timeout-seconds", "45"],
        )

    def test_start_proxy_passes_idle_timeout_zero(self) -> None:
        # 0 means "never auto-shut down" — a real value, not an absent one, so it must be sent.
        with (
            patch.object(self.cli, "run_command") as mock_run,
            patch.object(self.cli, "get_proxy_port", return_value=9000),
        ):
            self.cli.start_proxy(idle_timeout_seconds=0)

        assert "--idle-timeout-seconds" in mock_run.call_args.args[0]

    def test_stop_proxy_invokes_cli(self) -> None:
        with patch.object(self.cli, "run_command") as mock_run:
            self.cli.stop_proxy()
        mock_run.assert_called_once_with(["jupyter-deploy", "proxy", "stop"])

    def test_is_proxy_running_true_when_details_readable(self) -> None:
        with patch.object(self.cli, "get_proxy_details", return_value={"state": "running", "port": 1}):
            assert self.cli.is_proxy_running() is True

    def test_is_proxy_running_false_when_no_proxy(self) -> None:
        with patch.object(self.cli, "get_proxy_details", side_effect=JDCliError("no proxy")):
            assert self.cli.is_proxy_running() is False

    def test_wait_until_proxy_stopped_returns_true_once_gone(self) -> None:
        # Running, running, then gone: the poll has to keep looking rather than judge on first read.
        with (
            patch.object(self.cli, "is_proxy_running", side_effect=[True, True, False]),
            patch("pytest_jupyter_deploy.cli.time.sleep"),
        ):
            assert self.cli.wait_until_proxy_stopped(timeout_seconds=30) is True

    def test_wait_until_proxy_stopped_returns_false_on_timeout(self) -> None:
        with (
            patch.object(self.cli, "is_proxy_running", return_value=True),
            patch("pytest_jupyter_deploy.cli.time.sleep"),
            patch("pytest_jupyter_deploy.cli.time.monotonic", side_effect=[0.0, 0.0, 99.0, 99.0]),
        ):
            assert self.cli.wait_until_proxy_stopped(timeout_seconds=30) is False

    def test_get_proxy_status_parses_line(self) -> None:
        with patch.object(self.cli, "run_command", return_value=_completed("Proxy status: \x1b[36mrunning\x1b[0m")):
            assert self.cli.get_proxy_status() == "running"

    def test_get_proxy_status_raises_when_unparsable(self) -> None:
        with (
            patch.object(self.cli, "run_command", return_value=_completed("no status here")),
            self.assertRaises(ValueError),
        ):
            self.cli.get_proxy_status()


def _make_app(app_path: str = "/lab") -> tuple[LocalProxyApplication, Mock, Mock]:
    """Create a LocalProxyApplication with a mocked Page and deployment."""
    page = Mock()
    deployment = Mock()
    deployment.get_manifest.return_value.get_open.return_value.path = app_path
    deployment.cli.start_proxy.return_value = f"http://127.0.0.1:5000{app_path}"
    app = LocalProxyApplication(page=page, deployment=deployment)
    return app, page, deployment


class TestLocalProxyApplication(unittest.TestCase):
    def test_start_reads_manifest_path_and_starts_proxy(self) -> None:
        app, _, deployment = _make_app("/lab")
        url = app.start()

        assert url == "http://127.0.0.1:5000/lab"
        assert app.jupyterlab_url == "http://127.0.0.1:5000/lab"
        deployment.cli.start_proxy.assert_called_once_with(path="/lab", replace=False, idle_timeout_seconds=None)

    def test_start_forwards_replace_and_idle_timeout(self) -> None:
        # A test asserting idle auto-shutdown needs a window it can wait out; the shipped default is
        # two hours. `replace` goes with it, since such a test restarts the fixture's own proxy.
        app, _, deployment = _make_app("/lab")
        app.start(replace=True, idle_timeout_seconds=45)

        deployment.cli.start_proxy.assert_called_once_with(path="/lab", replace=True, idle_timeout_seconds=45)

    def test_stop_delegates_to_cli(self) -> None:
        app, _, deployment = _make_app()
        app.stop()
        deployment.cli.stop_proxy.assert_called_once_with()

    def test_verify_raises_if_not_started(self) -> None:
        app, _, _ = _make_app()
        with self.assertRaises(RuntimeError):
            app.verify_jupyterlab_accessible()

    def test_verify_succeeds_first_try(self) -> None:
        app, page, _ = _make_app()
        app.start()

        with patch("pytest_jupyter_deploy.local_proxy.application.expect") as mock_expect:
            app.verify_jupyterlab_accessible()

        page.goto.assert_called_once()
        mock_expect.assert_called_once()

    def test_verify_retries_then_succeeds(self) -> None:
        app, page, _ = _make_app()
        app.start()
        # First goto raises (upstream not ready), second succeeds.
        page.goto.side_effect = [Exception("502"), None]

        with (
            patch("pytest_jupyter_deploy.local_proxy.application.expect"),
            patch("pytest_jupyter_deploy.local_proxy.application.time.sleep"),
        ):
            app.verify_jupyterlab_accessible(max_retries=3)

        assert page.goto.call_count == 2

    def test_verify_raises_after_exhausting_retries(self) -> None:
        app, page, _ = _make_app()
        app.start()
        page.goto.side_effect = Exception("connection refused")

        with (
            patch("pytest_jupyter_deploy.local_proxy.application.time.sleep"),
            self.assertRaises(AssertionError),
        ):
            app.verify_jupyterlab_accessible(max_retries=2)

        assert page.goto.call_count == 2
