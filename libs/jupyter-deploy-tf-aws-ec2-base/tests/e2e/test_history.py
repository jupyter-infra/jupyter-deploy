"""E2E tests for jd history commands."""

from pytest_jupyter_deploy.deployment import EndToEndDeployment


def test_history_list_config_shows_existing_logs(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd history list config shows existing logs with expected format.

    This test:
    1. Ensures deployment exists with some history
    2. Runs jd history list config (table format)
    3. Verifies output is non-empty
    4. Verifies table contains expected columns
    5. Runs jd history list config --text
    6. Verifies plain text output shows file paths
    """
    e2e_deployment.ensure_deployed()

    # Run jd history list config (table format)
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "history", "list", "config"])

    # Verify output is non-empty
    assert result.stdout.strip(), "Expected non-empty output from jd history list config"

    # Verify table headers are present
    assert "Log Type" in result.stdout, "Expected 'Log Type' column in table output"
    assert "Timestamp" in result.stdout, "Expected 'Timestamp' column in table output"
    assert "Location" in result.stdout, "Expected 'Location' column in table output"

    # Verify at least one log entry exists (should contain "file" as storage type)
    assert "file" in result.stdout, "Expected at least one file-based log entry"

    # Run jd history list config --text (plain text format)
    result_text = e2e_deployment.cli.run_command(["jupyter-deploy", "history", "list", "config", "--text"])

    # Verify plain text output shows file paths
    assert result_text.stdout.strip(), "Expected non-empty output from jd history list config --text"
    # Should contain .log file paths
    assert ".log" in result_text.stdout, "Expected .log file paths in plain text output"


def test_history_list_up_shows_existing_logs(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd history list up shows existing logs with expected format.

    This test:
    1. Ensures deployment exists with up history (runs no-op jd up if needed)
    2. Runs jd history list up (table format)
    3. Verifies output is non-empty
    4. Verifies table contains expected columns
    5. Runs jd history list up --text
    6. Verifies plain text output shows file paths
    """
    e2e_deployment.ensure_up_history()

    # Run jd history list up (table format)
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "history", "list", "up"])

    # Verify output is non-empty
    assert result.stdout.strip(), "Expected non-empty output from jd history list up"

    # Verify table headers are present
    assert "Log Type" in result.stdout, "Expected 'Log Type' column in table output"
    assert "Timestamp" in result.stdout, "Expected 'Timestamp' column in table output"
    assert "Location" in result.stdout, "Expected 'Location' column in table output"

    # Verify at least one log entry exists (should contain "file" as storage type)
    assert "file" in result.stdout, "Expected at least one file-based log entry"

    # Run jd history list up --text (plain text format)
    result_text = e2e_deployment.cli.run_command(["jupyter-deploy", "history", "list", "up", "--text"])

    # Verify plain text output shows file paths
    assert result_text.stdout.strip(), "Expected non-empty output from jd history list up --text"
    # Should contain .log file paths
    assert ".log" in result_text.stdout, "Expected .log file paths in plain text output"


def test_history_show_latest_without_command(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd history show displays most recent log across all commands.

    This test:
    1. Ensures deployment exists with execution history
    2. Runs jd history show (no command argument)
    3. Verifies command succeeds
    4. Verifies output contains log content
    """
    e2e_deployment.ensure_deployed()

    # Run jd history show (no command argument)
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "history", "show"])

    # Verify command succeeded
    assert result.returncode == 0, f"Expected jd history show to succeed, got returncode {result.returncode}"

    # Verify output contains content (should be non-empty)
    assert result.stdout.strip(), "Expected non-empty log content from jd history show"

    # Should contain terraform-related content since last command was likely config or up
    # At minimum, logs should contain some recognizable content
    assert len(result.stdout) > 100, "Expected substantial log content (>100 chars)"


def test_history_show_config_command(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd history show config displays latest config log.

    This test:
    1. Ensures deployment exists with config history
    2. Runs jd history show config
    3. Verifies output displays log content
    4. Verifies content contains terraform-related keywords
    """
    e2e_deployment.ensure_deployed()

    # Run jd history show config
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "history", "show", "config"])

    # Verify command succeeded
    assert result.returncode == 0, f"Expected jd history show config to succeed, got returncode {result.returncode}"

    # Verify output contains content
    assert result.stdout.strip(), "Expected non-empty log content from jd history show config"

    # Verify content contains terraform-related keywords
    # Config logs should contain terraform plan output
    stdout_lower = result.stdout.lower()
    assert "terraform" in stdout_lower, "Expected 'terraform' keyword in config log"


def test_history_show_up_command(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd history show up displays latest up log.

    This test:
    1. Ensures deployment exists with up history (runs no-op jd up if needed)
    2. Runs jd history show up
    3. Verifies output displays log content
    4. Verifies content contains terraform-related keywords
    """
    e2e_deployment.ensure_up_history()

    # Run jd history show up
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "history", "show", "up"])

    # Verify command succeeded
    assert result.returncode == 0, f"Expected jd history show up to succeed, got returncode {result.returncode}"

    # Verify output contains content
    assert result.stdout.strip(), "Expected non-empty log content from jd history show up"

    # Verify content contains terraform-related keywords
    # Up logs should contain terraform apply output
    stdout_lower = result.stdout.lower()
    assert "terraform" in stdout_lower or "apply complete" in stdout_lower, (
        "Expected 'terraform' or 'Apply complete' keyword in up log"
    )


def test_history_show_up_command_slice(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd history show up with -l and -s flags correctly slices log output.

    This test:
    1. Ensures deployment exists with up history (runs no-op jd up if needed)
    2. Runs jd history show up -l 20 -s 10
    3. Verifies output displays sliced log content
    4. Verifies output has expected line count (at most 20 lines)
    """
    e2e_deployment.ensure_up_history()

    # Run jd history show up -l 20 -s 10
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "history", "show", "up", "-l", "20", "-s", "10"])

    # Verify command succeeded
    assert result.returncode == 0, (
        f"Expected jd history show up -l 20 -s 10 to succeed, got returncode {result.returncode}"
    )

    # Verify output contains content
    assert result.stdout.strip(), "Expected non-empty log content from jd history show up -l 20 -s 10"

    # Count lines in output
    lines = result.stdout.splitlines()
    assert len(lines) <= 20, f"Expected at most 20 lines, got {len(lines)}"

    # Should have some content (assuming logs are long enough)
    assert len(lines) > 0, "Expected at least some lines in sliced output"


def test_history_clear_with_high_keep_value(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd history clear -k 100 succeeds without errors.

    This test:
    1. Ensures deployment exists with config history
    2. Runs jd history clear config -k 100
    3. Verifies command succeeds (exit code 0)
    4. Verifies appropriate message is displayed

    Note: Using -k 100 makes this effectively non-mutating since most
    deployments won't have 100 logs to clean up.
    """
    e2e_deployment.ensure_deployed()

    # Run jd history clear config -k 100
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "history", "clear", "config", "-k", "100"])

    # Verify command succeeded
    assert result.returncode == 0, (
        f"Expected jd history clear config -k 100 to succeed, got returncode {result.returncode}"
    )

    # Verify output contains an appropriate message
    # Either "No stale log files to clear" or success message about cleared files
    assert result.stdout.strip(), "Expected non-empty output from jd history clear"

    # Should contain one of these patterns
    stdout_lower = result.stdout.lower()
    has_expected_message = (
        "no stale log files to clear" in stdout_lower or "cleared" in stdout_lower or "kept" in stdout_lower
    )
    assert has_expected_message, f"Expected appropriate clear message, got: {result.stdout}"
