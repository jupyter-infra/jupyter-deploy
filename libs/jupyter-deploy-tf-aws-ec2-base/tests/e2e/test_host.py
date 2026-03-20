"""E2E tests for deployment."""

import subprocess

import pexpect
import pytest
from pytest_jupyter_deploy.cli import JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment


def test_host_running(e2e_deployment: EndToEndDeployment) -> None:
    """Test that the host is running."""
    # Prerequisites
    e2e_deployment.ensure_host_running()

    # Get host status
    host_status = e2e_deployment.cli.get_host_status()
    assert host_status == "running", f"Expected host status 'running', got '{host_status}'"


def test_host_stop(e2e_deployment: EndToEndDeployment) -> None:
    """Test that the host can be stopped from command line."""
    # Prerequisites
    e2e_deployment.ensure_host_running()

    # Stop host and assert status
    e2e_deployment.cli.run_command(["jupyter-deploy", "host", "stop"])
    host_status = e2e_deployment.cli.get_host_status()
    assert host_status == "stopped", f"Expected host status 'stopped', got '{host_status}'"

    # Verify connection agent reports not connected
    connection_status = e2e_deployment.cli.get_connection_status()
    assert connection_status == "notconnected", f"Expected 'notconnected', got '{connection_status}'"


def test_host_start(e2e_deployment: EndToEndDeployment) -> None:
    """Test that the host can be started from command line."""
    # Prerequisites
    e2e_deployment.ensure_host_stopped()

    # Start host (this is what we're testing)
    e2e_deployment.cli.run_command(["jupyter-deploy", "host", "start"])

    # Assert status
    host_status = e2e_deployment.cli.get_host_status()
    assert host_status == "running", f"Expected host status 'running', got '{host_status}'"

    # Check connection status
    e2e_deployment.wait_for_connection_agent()
    status = e2e_deployment.cli.get_connection_status()
    assert status == "connected", f"Expected 'connected', got '{status}'"


def test_host_connect_whoami(e2e_deployment: EndToEndDeployment) -> None:
    """Test that we can connect to the host via SSM and run a simple command."""
    # Prerequisites
    e2e_deployment.ensure_host_running()
    e2e_deployment.wait_for_connection_agent()

    # Start an interactive jd host connect session
    with e2e_deployment.cli.spawn_interactive_session("jupyter-deploy host connect") as session:
        # Wait for the session to start (AWS SSM output)
        session.expect("Starting session with SessionId:", timeout=10)

        # Send whoami command
        session.sendline("whoami")

        # Expect ssm-user in the output
        session.expect("ssm-user", timeout=5)

        # Exit the session
        session.sendline("exit")

        # Wait for the session to close
        session.expect(pexpect.EOF, timeout=5)


def test_host_exec_simple_command(e2e_deployment: EndToEndDeployment) -> None:
    """Test that we can execute a simple command on the host."""
    # Prerequisites
    e2e_deployment.ensure_host_running()
    e2e_deployment.wait_for_host_agent()

    # Execute whoami command
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "host", "exec", "--", "whoami"])

    # Verify we got output
    assert result.stdout, "Expected non-empty stdout"
    assert "root" in result.stdout, f"Expected 'root' in output, got: {result.stdout}"


def test_host_exec_disk_usage(e2e_deployment: EndToEndDeployment) -> None:
    """Test host exec with disk usage command."""
    # Prerequisites
    e2e_deployment.ensure_host_running()
    e2e_deployment.wait_for_host_agent()

    # Execute df command
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "host", "exec", "--", "df", "-h"])

    # Verify output contains filesystem information
    assert result.stdout, "Expected non-empty stdout"
    assert "Filesystem" in result.stdout or "/" in result.stdout, f"Expected filesystem info, got: {result.stdout}"


def test_host_exec_failed_command(e2e_deployment: EndToEndDeployment) -> None:
    """Test host exec with a command that fails."""
    # Prerequisites
    e2e_deployment.ensure_host_running()
    e2e_deployment.wait_for_host_agent()

    # Execute non-existent command - should raise JDCliError with non-zero exit code
    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(["jupyter-deploy", "host", "exec", "--", "command_that_does_not_exist"])

    # Verify the exception wraps a CalledProcessError with exit code 127 (command not found)
    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, subprocess.CalledProcessError)
    assert exc_info.value.__cause__.returncode == 127
