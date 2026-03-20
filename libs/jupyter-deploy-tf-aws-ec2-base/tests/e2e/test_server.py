import subprocess

import pexpect
import pytest
from pytest_jupyter_deploy.cli import JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.oauth2_proxy.github import GitHubOAuth2ProxyApplication


def test_server_running(
    e2e_deployment: EndToEndDeployment, github_oauth_app: GitHubOAuth2ProxyApplication, logged_user: str
) -> None:
    """Test that the Jupyter server is available."""
    # Prerequisites
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_authorized([logged_user], "", [])

    # Get server status
    server_status = e2e_deployment.cli.get_server_status()
    assert server_status == "IN_SERVICE", f"Expected server status 'IN_SERVICE', got '{server_status}'"

    # Verify application is accessible
    github_oauth_app.ensure_authenticated()
    github_oauth_app.verify_jupyterlab_accessible()


def test_stop_server(
    e2e_deployment: EndToEndDeployment, github_oauth_app: GitHubOAuth2ProxyApplication, logged_user: str
) -> None:
    """Test that the Jupyter server can be stopped from command line."""
    # Prerequisites
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_authorized([logged_user], "", [])

    # Stop server and assert status
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "stop"])
    server_status = e2e_deployment.cli.get_server_status()
    assert server_status == "STOPPED", f"Expected server status 'STOPPED', got '{server_status}'"

    # Verify application is not accessible after stop
    github_oauth_app.verify_server_unaccessible()


def test_start_server(
    e2e_deployment: EndToEndDeployment, github_oauth_app: GitHubOAuth2ProxyApplication, logged_user: str
) -> None:
    """Test that the Jupyter server can be started from command line."""
    # Prerequisites
    e2e_deployment.ensure_server_stopped_and_host_is_running()
    e2e_deployment.ensure_authorized([logged_user], "", [])

    # Start server and assert status
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "start"])
    server_status = e2e_deployment.cli.get_server_status()
    assert server_status == "IN_SERVICE", f"Expected server status 'IN_SERVICE', got '{server_status}'"

    # Verify application is accessible after start
    github_oauth_app.ensure_authenticated()
    github_oauth_app.verify_jupyterlab_accessible()


def test_server_logs(e2e_deployment: EndToEndDeployment) -> None:
    """Test that server logs can be retrieved."""
    # Prerequisites
    e2e_deployment.ensure_server_running()

    # Get server logs
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "logs"])

    # Verify we got some output
    assert result.stdout, "Expected non-empty logs output"
    # Logs should contain some indication that this is log output
    # The output contains "stdout" or similar markers
    assert "stdout" in result.stdout or "stderr" in result.stdout, "Expected log output markers"


def test_all_service_logs(
    e2e_deployment: EndToEndDeployment, github_oauth_app: GitHubOAuth2ProxyApplication, logged_user: str
) -> None:
    """Test that logs can be retrieved for each individual service."""
    # Prerequisites
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_authorized([logged_user], "", [])

    # Visit the application to ensure there are logs for all of the services
    # otherwise, depending on the order of tests, traefik may not have any logs
    # e.g., if the previous ran restarted the host
    github_oauth_app.ensure_authenticated()
    github_oauth_app.verify_jupyterlab_accessible()

    # Test logs for jupyter service
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "logs", "-s", "jupyter"])
    assert result.stdout, "Expected non-empty logs output for jupyter service"
    assert "stdout" in result.stdout or "stderr" in result.stdout, "Expected log output markers for jupyter"

    # Test logs for traefik service
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "logs", "-s", "traefik"])
    assert result.stdout, "Expected non-empty logs output for traefik service"
    assert "stdout" in result.stdout or "stderr" in result.stdout, "Expected log output markers for traefik"

    # Test logs for oauth service
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "logs", "-s", "oauth"])
    assert result.stdout, "Expected non-empty logs output for oauth service"
    assert "stdout" in result.stdout or "stderr" in result.stdout, "Expected log output markers for oauth"


def test_server_logs_piped_command(e2e_deployment: EndToEndDeployment) -> None:
    """Test that piped commands work with server logs."""
    # Prerequisites
    e2e_deployment.ensure_server_running()

    # Test: --tail 5 returns exactly 5 log entries
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "logs", "--", "--tail", "5"])

    # Verify we got some output
    assert result.stdout, "Expected non-empty logs output with --tail 5"

    # Parse log entries using the utility function
    log_entries = e2e_deployment.cli.parse_log_entries_from_output(result.stdout)

    # Assert we got exactly 5 log entries
    assert len(log_entries) == 5, f"Expected exactly 5 log entries with --tail 5, got {len(log_entries)}"


def test_server_exec_default_to_jupyter(e2e_deployment: EndToEndDeployment) -> None:
    """Test that server exec defaults to jupyter service when no service is specified."""
    # Prerequisites
    e2e_deployment.ensure_server_running()

    # Execute whoami command without specifying service (should default to jupyter)
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", "whoami"])

    # Verify we got output and we're in the jupyter container (jovyan user)
    assert result.stdout, "Expected non-empty stdout"
    assert "jovyan" in result.stdout, f"Expected 'jovyan' user (jupyter service), got: {result.stdout}"


def test_server_exec_all_services(e2e_deployment: EndToEndDeployment) -> None:
    """Test that exec works for all services (jupyter, traefik, oauth)."""
    # Prerequisites
    e2e_deployment.ensure_server_running()

    # Test jupyter service with whoami (available in jupyter container)
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "-s", "jupyter", "--", "whoami"])
    assert result.stdout, "Expected non-empty stdout for jupyter service"
    assert "jovyan" in result.stdout, f"Expected 'jovyan' user in jupyter, got: {result.stdout}"

    # Test traefik service with ps | grep traefik
    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "server", "exec", "-s", "traefik", "--", "ps", "|", "grep", "traefik"]
    )
    assert result.stdout, "Expected non-empty stdout for traefik service"
    assert "traefik" in result.stdout, f"Expected 'traefik' process in output, got: {result.stdout}"

    # Test oauth service with oauth2-proxy --version (distroless container with no shell)
    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "server", "exec", "-s", "oauth", "--", "oauth2-proxy", "--version"]
    )
    assert result.stdout, "Expected non-empty stdout for oauth service"
    assert "oauth2-proxy" in result.stdout, f"Expected 'oauth2-proxy' version in output, got: {result.stdout}"


def test_server_exec_failed_command(e2e_deployment: EndToEndDeployment) -> None:
    """Test server exec with a command that fails."""
    # Prerequisites
    e2e_deployment.ensure_server_running()

    # Execute non-existent command in jupyter service - should raise JDCliError with non-zero exit code
    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(
            ["jupyter-deploy", "server", "exec", "-s", "jupyter", "--", "command_that_does_not_exist"]
        )

    # Verify the exception wraps a CalledProcessError with exit code 126 (OCI runtime exec failure)
    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, subprocess.CalledProcessError)
    assert exc_info.value.__cause__.returncode == 126


def test_server_connect_default_service(e2e_deployment: EndToEndDeployment) -> None:
    """Test that we can connect to the default service (jupyter) via SSM and run a simple command."""
    # Prerequisites
    e2e_deployment.ensure_server_running()
    e2e_deployment.wait_for_connection_agent()

    # Start an interactive jd server connect session (no -s flag, should default to jupyter)
    with e2e_deployment.cli.spawn_interactive_session("jupyter-deploy server connect") as session:
        # Wait for the session to start (AWS SSM output)
        session.expect("Starting session with SessionId:", timeout=10)

        # Send whoami command
        session.sendline("whoami")

        # Expect jovyan in the output (jupyter container user)
        session.expect("jovyan", timeout=5)

        # Exit the session
        session.sendline("exit")

        # Wait for the session to close
        session.expect(pexpect.EOF, timeout=5)


def test_server_connect_jupyter(e2e_deployment: EndToEndDeployment) -> None:
    """Test that we can connect to the jupyter service via SSM and run a simple command."""
    # Prerequisites
    e2e_deployment.ensure_server_running()
    e2e_deployment.wait_for_connection_agent()

    # Start an interactive jd server connect session with explicit -s jupyter
    with e2e_deployment.cli.spawn_interactive_session("jupyter-deploy server connect -s jupyter") as session:
        # Wait for the session to start (AWS SSM output)
        session.expect("Starting session with SessionId:", timeout=10)

        # Send whoami command
        session.sendline("whoami")

        # Expect jovyan in the output (jupyter container user)
        session.expect("jovyan", timeout=5)

        # Exit the session
        session.sendline("exit")

        # Wait for the session to close
        session.expect(pexpect.EOF, timeout=5)


def test_server_connect_traefik(e2e_deployment: EndToEndDeployment) -> None:
    """Test that we can connect to the traefik service via SSM and run a simple command."""
    # Prerequisites
    e2e_deployment.ensure_server_running()
    e2e_deployment.wait_for_connection_agent()

    # Start an interactive jd server connect session with explicit -s traefik
    with e2e_deployment.cli.spawn_interactive_session("jupyter-deploy server connect -s traefik") as session:
        # Wait for the session to start (AWS SSM output)
        session.expect("Starting session with SessionId:", timeout=10)

        # Send ps command
        session.sendline("ps")

        # Expect traefik in the output (traefik process)
        session.expect("traefik", timeout=5)

        # Exit the session
        session.sendline("exit")

        # Wait for the session to close
        session.expect(pexpect.EOF, timeout=5)
