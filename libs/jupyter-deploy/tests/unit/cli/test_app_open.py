import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.app import runner as app_runner
from jupyter_deploy.exceptions import OpenWebBrowserError, UrlNotAvailableError, UrlNotSecureError


class TestOpenCommand(unittest.TestCase):
    """Test cases for the open command."""

    def get_mock_open_handler(
        self, multi_server: bool = False, multi_host: bool = False
    ) -> tuple[Mock, dict[str, Mock]]:
        """Return a mocked open handler with manifest commands.

        Defaults to a single-tenant manifest (multi_server/multi_host False). Pass
        multi_server=True to exercise the multi-tenant troubleshooting branch.
        """
        mock_open_handler = Mock()
        mock_open = Mock(return_value="https://example.com/jupyter")
        mock_manifest = Mock()

        # Default manifest with all commands available
        mock_manifest.has_command = Mock(return_value=True)
        mock_manifest.multi_server = multi_server
        mock_manifest.multi_host = multi_host
        # Multi-tenant hints gate the health suggestion on a declared health block.
        mock_manifest.health = object() if (multi_server or multi_host) else None

        mock_open_handler.open = mock_open
        mock_open_handler.project_manifest = mock_manifest

        return mock_open_handler, {
            "open": mock_open,
            "project_manifest": mock_manifest,
        }

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_runs_open(self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock) -> None:
        """Test that open command successfully opens the URL."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_open_fns["open"].assert_called_once_with(name=None, scope=None)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_with_custom_path(self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock) -> None:
        """Test that open command accepts a custom path."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open", "--path", "/custom/path"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(Path("/custom/path"))
        mock_open_fns["open"].assert_called_once_with(name=None, scope=None)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_returns_nonzero_on_browser_error(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that open command returns non-zero exit code when browser fails to open."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()
        mock_open_fns["open"].side_effect = OpenWebBrowserError(
            "Failed to open URL in browser.", "https://example.com/jupyter"
        )
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        self.assertEqual(result.exit_code, 1)
        mock_open_fns["open"].assert_called_once_with(name=None, scope=None)
        self.assertIn("Failed to open URL in browser", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_displays_hint_on_success(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that open command displays troubleshooting hint on success."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        self.assertEqual(result.exit_code, 0)
        # Check that success message is displayed
        self.assertIn("Opening app at:", result.output)
        self.assertIn("https://example.com/jupyter", result.output)
        # Check that hint is displayed
        self.assertIn("Having trouble?", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_displays_hint_on_browser_error(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that open command displays troubleshooting hint when browser fails."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()
        mock_open_fns["open"].side_effect = OpenWebBrowserError(
            "Failed to open URL in browser.", "https://example.com/jupyter"
        )
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        self.assertEqual(result.exit_code, 1)
        # Check that error message is displayed
        self.assertIn("Failed to open URL in browser", result.output)
        # Check that hint is displayed even on error
        self.assertIn("Having trouble?", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_hint_respects_manifest_host_commands(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that troubleshooting hint displays commands based on manifest."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()

        # Configure manifest to only have host.status and host.restart
        def has_command(cmd: str) -> bool:
            return cmd in ["host.status", "host.restart"]

        mock_open_fns["project_manifest"].has_command = Mock(side_effect=has_command)
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        self.assertEqual(result.exit_code, 0)
        # Check host commands are shown
        self.assertIn("jd host status", result.output)
        self.assertIn("jd host restart", result.output)
        # Check server commands are NOT shown
        self.assertNotIn("jd server status", result.output)
        self.assertNotIn("jd server restart", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_hint_respects_manifest_server_commands(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that troubleshooting hint displays server commands when available."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()

        # Configure manifest to only have server.status and server.restart
        def has_command(cmd: str) -> bool:
            return cmd in ["server.status", "server.restart"]

        mock_open_fns["project_manifest"].has_command = Mock(side_effect=has_command)
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        self.assertEqual(result.exit_code, 0)
        # Check server commands are shown
        self.assertIn("jd server status", result.output)
        self.assertIn("jd server restart", result.output)
        # Check host commands are NOT shown
        self.assertNotIn("jd host status", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_hint_shows_host_start_when_no_restart(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that hint shows host.start when host.restart is not available."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()

        # Configure manifest with host.status and host.start (no restart)
        def has_command(cmd: str) -> bool:
            return cmd in ["host.status", "host.start"]

        mock_open_fns["project_manifest"].has_command = Mock(side_effect=has_command)
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("jd host status", result.output)
        self.assertIn("jd host start", result.output)
        self.assertNotIn("jd host restart", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_hint_shows_server_start_when_no_restart(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that hint shows server.start when server.restart is not available."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()

        # Configure manifest with server.status and server.start (no restart)
        def has_command(cmd: str) -> bool:
            return cmd in ["server.status", "server.start"]

        mock_open_fns["project_manifest"].has_command = Mock(side_effect=has_command)
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("jd server status", result.output)
        self.assertIn("jd server start", result.output)
        self.assertNotIn("jd server restart", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_hint_shows_host_connect(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that hint shows host.connect when available."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()

        # Configure manifest with host.connect
        def has_command(cmd: str) -> bool:
            return cmd == "host.connect"

        mock_open_fns["project_manifest"].has_command = Mock(side_effect=has_command)
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("jd host connect", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_no_hint_when_no_commands_available(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that no hint is displayed when manifest has no troubleshooting commands."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()

        # Configure manifest with no relevant commands
        mock_open_fns["project_manifest"].has_command = Mock(return_value=False)
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Opening app at:", result.output)
        # Check that hint is NOT displayed
        self.assertNotIn("Having trouble?", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_raises_on_other_exceptions(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that open command raises and returns non-zero for unexpected exceptions."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()
        mock_open_fns["open"].side_effect = RuntimeError("Unexpected error")
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        self.assertNotEqual(result.exit_code, 0)
        mock_open_fns["open"].assert_called_once_with(name=None, scope=None)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_url_not_available_returns_zero(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that UrlNotAvailableError returns exit code 0 with helpful message."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()
        mock_open_fns["open"].side_effect = UrlNotAvailableError(
            "URL not available. Run 'jd config' then 'jd up'.", "https://example.com"
        )
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        # Should return 0 for graceful degradation
        self.assertEqual(result.exit_code, 0)
        # Should display the error message
        self.assertIn("URL not available", result.output)
        # Should show helpful suggestions
        self.assertIn("jd config", result.output)
        self.assertIn("jd up", result.output)
        # Should NOT display "Having trouble?" hint
        self.assertNotIn("Having trouble?", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_url_not_secure_returns_nonzero(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that UrlNotSecureError returns non-zero exit code (security error)."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()
        mock_open_fns["open"].side_effect = UrlNotSecureError(
            "Insecure URL detected. Only HTTPS URLs are allowed for security reasons.",
            "http://example.com/jupyter",
        )
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        # Should return non-zero for security errors (handled by error decorator)
        self.assertNotEqual(result.exit_code, 0)
        # Should display the error message
        self.assertIn("Insecure URL detected", result.output)
        self.assertIn("HTTPS", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_url_not_line_wrapped(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that long URLs are printed on a single line without wrapping."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()
        long_url = "https://another-long-subsub-domain.some-very-long-subdomain.example.com/workspaces/default/some-long-workspace-name/lab"
        mock_open_fns["open"].return_value = long_url
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        self.assertEqual(result.exit_code, 0)
        # The full URL must appear on a single line (soft_wrap=True prevents Rich from breaking it)
        output_lines = result.output.splitlines()
        url_lines = [line for line in output_lines if long_url in line]
        self.assertEqual(len(url_lines), 1, f"URL should appear intact on one line, got output:\n{result.output}")

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_with_server_name(self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock) -> None:
        """Test that open command passes server name to handler."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()
        mock_open_fns["open"].return_value = "https://example.com/workspaces/default/my-ws/"
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open", "--server-name", "my-ws"])

        self.assertEqual(result.exit_code, 0)
        mock_open_fns["open"].assert_called_once_with(name="my-ws", scope=None)
        self.assertIn("Opening app at:", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_with_server_name_and_scope(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that open command passes server name and scope to handler."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()
        mock_open_fns["open"].return_value = "https://example.com/workspaces/team-a/my-ws/"
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open", "--server-name", "my-ws", "--scope", "team-a"])

        self.assertEqual(result.exit_code, 0)
        mock_open_fns["open"].assert_called_once_with(name="my-ws", scope="team-a")

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_scope_without_server_name(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Test that open command with only --scope still opens the default URL."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open", "--scope", "team-a"])

        self.assertEqual(result.exit_code, 0)
        mock_open_fns["open"].assert_called_once_with(name=None, scope="team-a")

    # --- Multi-tenant troubleshooting hints ---

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_multi_tenant_default_shows_health(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Plain `jd open` on a multi-tenant template points at the health check, not host/server."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler(multi_server=True)
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Having trouble?", result.output)
        self.assertIn("jd health", result.output)
        # No single-tenant "your host"/"your server" hints on a shared cluster.
        self.assertNotIn("jd host status", result.output)
        self.assertNotIn("jd server status", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_multi_tenant_server_name_shows_server_hints(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """`jd open --server-name` on a multi-tenant template targets that server, then broadens out."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler(multi_server=True)
        mock_open_fns["open"].return_value = "https://example.com/workspaces/default/my-ws/"
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open", "--server-name", "my-ws"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Having trouble?", result.output)
        self.assertIn("jd server status --name my-ws", result.output)
        self.assertIn("jd server list", result.output)
        self.assertIn("jd health", result.output)
        # No --scope in the hint when the user did not pass one.
        self.assertNotIn("--scope", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_multi_tenant_server_name_threads_scope(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """A user-supplied --scope is threaded into the server hints."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler(multi_server=True)
        mock_open_fns["open"].return_value = "https://example.com/workspaces/team-a/my-ws/"
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open", "--server-name", "my-ws", "--scope", "team-a"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("jd server status --name my-ws --scope team-a", result.output)
        self.assertIn("jd server list --scope team-a", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_multi_tenant_gates_hints_on_declared_commands(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """Multi-tenant server hints are gated on the manifest declaring the underlying commands."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler(multi_server=True)
        mock_open_fns["open"].return_value = "https://example.com/workspaces/default/my-ws/"

        # Only server.status is declared; no server.list and no health block.
        def has_command(cmd: str) -> bool:
            return cmd == "server.status"

        mock_open_fns["project_manifest"].has_command = Mock(side_effect=has_command)
        mock_open_fns["project_manifest"].health = None
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open", "--server-name", "my-ws"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("jd server status --name my-ws", result.output)
        self.assertNotIn("jd server list", result.output)
        self.assertNotIn("jd health", result.output)

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_multi_tenant_no_hint_when_nothing_declared(
        self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock
    ) -> None:
        """No hint block on a multi-tenant template that declares no relevant commands or health."""
        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler(multi_server=True)
        mock_open_fns["project_manifest"].has_command = Mock(return_value=False)
        mock_open_fns["project_manifest"].health = None
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("Having trouble?", result.output)
