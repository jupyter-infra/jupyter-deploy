"""E2E tests for configuration help and update without deployment."""

import ast

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set


@pytest.mark.cli
def test_config_help_show_variables(e2e_deployment: EndToEndDeployment) -> None:
    """Test that config help retrieves the list of variables."""
    e2e_deployment.ensure_deployed()

    # Run jd config --help to get the list of variables
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "config", "--help"])

    # Verify that the help output contains the "Template variables" section
    assert "Template variables" in result.stdout, "Expected 'Template variables' section in config help output"

    # Verify key variables are present in the help output
    expected_variables = [
        "--region",
        "--jupyter-package-manager",
        "--instance-type",
        "--oauth-allowed-usernames",
        "--additional-efs-mounts",
        "--additional-ebs-mounts",
    ]

    for var in expected_variables:
        assert var in result.stdout, f"Expected variable '{var}' in config help output"


@pytest.mark.cli
def test_config_set_string_variable(e2e_deployment: EndToEndDeployment) -> None:
    """Test that config can set a simple variable of type str."""
    e2e_deployment.ensure_deployed()

    # Get current package manager value
    current_value = e2e_deployment.read_override_value("jupyter_package_manager")

    # Determine the new value to switch to
    new_value = "pixi" if current_value == "uv" else "uv"

    # Set the new value by updating variables.yaml
    e2e_deployment.update_override_value("jupyter_package_manager", new_value)

    # Verify the change by reading from variables.yaml (no need to run jd config)
    updated_value = e2e_deployment.read_override_value("jupyter_package_manager")
    assert updated_value == new_value, (
        f"Expected jupyter_package_manager to be '{new_value}', but got '{updated_value}'"
    )

    # Also verify it appears in jd show output for the specific variable
    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "show", "--variable", "jupyter_package_manager", "--text"]
    )
    assert new_value in result.stdout, f"Expected to find '{new_value}' in variable value"

    # Switch back to the original value via file
    e2e_deployment.update_override_value("jupyter_package_manager", current_value)

    # Verify it was reverted by reading from variables.yaml (no need to run jd config)
    reverted_value = e2e_deployment.read_override_value("jupyter_package_manager")
    assert reverted_value == current_value, (
        f"Expected jupyter_package_manager to be reverted to '{current_value}', but got '{reverted_value}'"
    )


@pytest.mark.cli
@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_SAFE_USER"])
def test_config_set_list_string_variable(e2e_deployment: EndToEndDeployment, logged_user: str, safe_user: str) -> None:
    """Test that config can set a variable of type list[str]."""
    e2e_deployment.ensure_deployed()

    # Step 1: Use ensure_authorized to set only the logged user
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_authorized([logged_user], "", [])

    # Verify only logged user is set
    current_users = e2e_deployment.get_allowlisted_users()
    assert logged_user in current_users, f"Expected '{logged_user}' to be in allowlisted users"
    assert safe_user not in current_users, f"Expected '{safe_user}' to NOT be in allowlisted users initially"

    # Step 2: Use jd config to set both logged and safe user
    e2e_deployment.cli.run_command(
        [
            "jupyter-deploy",
            "config",
            "--oauth-allowed-usernames",
            logged_user,
            "--oauth-allowed-usernames",
            safe_user,
        ]
    )

    # Step 3: Verify with jd show for the specific variable
    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "show", "--variable", "oauth_allowed_usernames", "--text"]
    )
    # Check command succeeded
    assert result.returncode == 0, f"Command failed with: {result.stderr or result.stdout}"
    # Parse the list from the output
    users_list = ast.literal_eval(result.stdout.strip())
    assert isinstance(users_list, list), f"Expected list, got {type(users_list)}"
    assert logged_user in users_list, f"Expected '{logged_user}' in users list"
    assert safe_user in users_list, f"Expected '{safe_user}' in users list"
    assert set(users_list) == {logged_user, safe_user}, (
        f"Expected exactly [{logged_user}, {safe_user}], got {users_list}"
    )

    # Step 4: Use jd config to set only the safe user
    e2e_deployment.cli.run_command(
        [
            "jupyter-deploy",
            "config",
            "--oauth-allowed-usernames",
            safe_user,
        ]
    )

    # Step 5: Verify that logged user is removed and only safe user remains
    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "show", "--variable", "oauth_allowed_usernames", "--text"]
    )
    # Check command succeeded
    assert result.returncode == 0, f"Command failed with: {result.stderr or result.stdout}"
    # Parse the list from the output
    users_list = ast.literal_eval(result.stdout.strip())
    assert isinstance(users_list, list), f"Expected list, got {type(users_list)}"
    assert users_list == [safe_user], f"Expected only [{safe_user}], got {users_list}"

    # Step 6: Leave as is (no revert)


@pytest.mark.cli
def test_config_set_list_of_dict_variable(e2e_deployment: EndToEndDeployment) -> None:
    """Test that config can set variable of type list of dict[str, str]."""
    e2e_deployment.ensure_deployed()

    # Get current additional_ebs_mounts value
    current_mounts = e2e_deployment.read_override_value("additional_ebs_mounts") or []

    # Set additional EBS mounts with two entries by updating variables.yaml
    # Entry 1: name=data, mount_point=external-data, size_gb="50"
    # Entry 2: name=work, mount_point=external-work
    # Note: All values must be strings since the type is list(map(string))
    new_mounts = [
        {"name": "data", "mount_point": "external-data", "size_gb": "50"},
        {"name": "work", "mount_point": "external-work"},
    ]
    e2e_deployment.update_override_value("additional_ebs_mounts", new_mounts)

    # Verify the change by reading from variables.yaml (no need to run jd config)
    updated_mounts = e2e_deployment.read_override_value("additional_ebs_mounts") or []

    # Check that we have exactly 2 mounts
    assert len(updated_mounts) == 2, f"Expected 2 EBS mounts, but got {len(updated_mounts)}"

    # Verify the first mount (data)
    data_mount = next((m for m in updated_mounts if m.get("name") == "data"), None)
    assert data_mount is not None, "Expected to find mount with name 'data'"
    assert data_mount.get("mount_point") == "external-data", (
        f"Expected mount_point 'external-data', got '{data_mount.get('mount_point')}'"
    )
    assert data_mount.get("size_gb") == "50", f"Expected size_gb '50', got {data_mount.get('size_gb')}"

    # Verify the second mount (work)
    work_mount = next((m for m in updated_mounts if m.get("name") == "work"), None)
    assert work_mount is not None, "Expected to find mount with name 'work'"
    assert work_mount.get("mount_point") == "external-work", (
        f"Expected mount_point 'external-work', got '{work_mount.get('mount_point')}'"
    )

    # Also verify they appear in jd show output for the specific variable
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--variable", "additional_ebs_mounts", "--text"])

    # Parse the list of dicts from the output
    mounts_list = ast.literal_eval(result.stdout.strip())
    assert isinstance(mounts_list, list), f"Expected list, got {type(mounts_list)}"
    assert len(mounts_list) == 2, f"Expected 2 mounts, got {len(mounts_list)}"

    # Verify the data mount
    data_mount = next((m for m in mounts_list if m.get("name") == "data"), None)
    assert data_mount is not None, "Expected to find mount with name 'data'"
    assert data_mount == {"name": "data", "mount_point": "external-data", "size_gb": "50"}, (
        f"Expected data mount to match exactly, got {data_mount}"
    )

    # Verify the work mount
    work_mount = next((m for m in mounts_list if m.get("name") == "work"), None)
    assert work_mount is not None, "Expected to find mount with name 'work'"
    assert work_mount == {"name": "work", "mount_point": "external-work"}, (
        f"Expected work mount to match exactly, got {work_mount}"
    )

    # Revert to the original value via the file experience
    e2e_deployment.update_override_value("additional_ebs_mounts", current_mounts)

    # Verify it was reverted (no need to run jd config)
    reverted_mounts = e2e_deployment.read_override_value("additional_ebs_mounts") or []

    assert reverted_mounts == current_mounts, (
        f"Expected additional_ebs_mounts to be reverted to {current_mounts}, but got {reverted_mounts}"
    )


@pytest.mark.cli
def test_config_set_string_variable_with_verbose(e2e_deployment: EndToEndDeployment) -> None:
    """Test that config --verbose shows full terraform output without progress bar artifacts."""
    e2e_deployment.ensure_deployed()

    # Run jd config --verbose to verify it shows full terraform output
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "config", "--verbose"])

    # Verify command succeeded
    assert result.returncode == 0, f"Expected config --verbose to succeed, got returncode {result.returncode}"

    # Check for terraform init success message
    assert "Terraform has been successfully initialized!" in result.stdout, (
        "Expected 'Terraform has been successfully initialized!' in verbose output"
    )

    # Verify no progress bar artifacts (spinners, live box remnants)
    # Progress bar typically uses ANSI escape codes or special characters
    # Check that output doesn't contain common progress indicators
    assert "⠋" not in result.stdout, "Found spinner character in verbose output (should not have progress bar)"
    assert "⠙" not in result.stdout, "Found spinner character in verbose output (should not have progress bar)"
