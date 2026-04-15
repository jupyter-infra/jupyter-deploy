"""E2E tests for jd show command."""

import pytest
from jupyter_deploy.enum import ValueSource
from pytest_jupyter_deploy.deployment import EndToEndDeployment


@pytest.mark.cli
def test_show_variables_list_matches_config(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --variables --list matches variables.yaml content.

    This test:
    1. Ensures deployment exists
    2. Reads variables.yaml to get expected variable names
    3. Runs jd show --variables --list --text
    4. Verifies all variables from yaml are present in output (order doesn't matter)
    """
    e2e_deployment.ensure_deployed()

    # Read variables config to get all variable names
    variables_config = e2e_deployment.get_variables_config()

    # Collect all variable names from all sections (required, required_sensitive, overrides, defaults)
    # jd show --variables --list shows ALL template variables
    expected_vars: set[str] = set()
    expected_vars.update(variables_config.required.keys())
    expected_vars.update(variables_config.required_sensitive.keys())
    expected_vars.update(variables_config.overrides.keys())
    expected_vars.update(variables_config.defaults.keys())

    # Run jd show --variables --list --text
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--variables", "--list", "--text"])

    # Parse comma-separated output (strip newlines that may be inserted by wrapping)
    output_vars = {var.strip().replace("\n", "") for var in result.stdout.strip().split(",") if var.strip()}

    # Verify size matches
    assert len(output_vars) == len(expected_vars), (
        f"Expected {len(expected_vars)} variables, got {len(output_vars)}. "
        f"Missing: {expected_vars - output_vars}, Extra: {output_vars - expected_vars}"
    )

    # Verify all names match (order doesn't matter)
    assert output_vars == expected_vars, (
        f"Variable names don't match. Missing: {expected_vars - output_vars}, Extra: {output_vars - expected_vars}"
    )


@pytest.mark.cli
def test_show_outputs_list_returns_expected_outputs(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --outputs --list returns expected terraform outputs.

    This test:
    1. Ensures deployment exists
    2. Reads manifest to get all values whose source is "output"
    3. Runs jd show --outputs --list --text
    4. Verifies all manifest output values are present in the command output
    """
    e2e_deployment.ensure_deployed()

    # Read manifest to get expected output names
    manifest = e2e_deployment.get_manifest()

    # Collect all value names where source is "output"
    expected_outputs: set[str] = set()
    if manifest.values:
        for value in manifest.values:
            if value.source == ValueSource.TEMPLATE_OUTPUT:
                expected_outputs.add(value.source_key)

    # Run jd show --outputs --list --text
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--outputs", "--list", "--text"])

    # Parse comma-separated output (strip newlines that may be inserted by wrapping)
    output_names = {name.strip().replace("\n", "") for name in result.stdout.strip().split(",") if name.strip()}

    # Verify all manifest output values are present
    assert expected_outputs.issubset(output_names), (
        f"Missing expected outputs: {expected_outputs - output_names}. Got outputs: {output_names}"
    )


@pytest.mark.cli
def test_show_variable_domain_matches_config(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --variable domain returns value from variables.yaml.

    This test:
    1. Ensures deployment exists
    2. Reads domain value from variables.yaml
    3. Queries domain via jd show --variable domain --text
    4. Verifies values match
    """
    e2e_deployment.ensure_deployed()

    # Read domain from variables config
    variables_config = e2e_deployment.get_variables_config()

    # Domain should be in required section
    expected_domain = variables_config.required["domain"]

    # Query domain via jd show
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--variable", "domain", "--text"])
    actual_domain = result.stdout.strip()

    assert actual_domain == expected_domain, f"Expected domain '{expected_domain}', got '{actual_domain}'"


@pytest.mark.cli
def test_show_output_jupyter_url_matches_variables(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --output jupyter_url returns URL matching variables.

    This test:
    1. Ensures deployment exists
    2. Reads domain and subdomain from variables.yaml
    3. Constructs expected URL as https://{subdomain}.{domain}
    4. Queries jupyter_url via jd show --output jupyter_url --text
    5. Verifies URLs match
    """
    e2e_deployment.ensure_deployed()

    # Read domain and subdomain from variables config
    variables_config = e2e_deployment.get_variables_config()
    domain = variables_config.required["domain"]
    subdomain = variables_config.required["subdomain"]

    # Construct expected URL
    expected_url = f"https://{subdomain}.{domain}"

    # Query jupyter_url via jd show
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--output", "jupyter_url", "--text"])
    actual_url = result.stdout.strip()

    assert actual_url == expected_url, f"Expected URL '{expected_url}', got '{actual_url}'"


@pytest.mark.cli
def test_show_default_does_not_error(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show (no flags) executes successfully.

    This test:
    1. Ensures deployment exists
    2. Runs jd show with no flags
    3. Verifies command succeeds
    4. Verifies output contains expected section headers
    """
    e2e_deployment.ensure_deployed()

    # Run jd show with no flags
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show"])

    # Verify command succeeded (returncode 0 is implicit in run_command)
    assert result.returncode == 0, f"jd show should succeed, got returncode {result.returncode}"

    # Verify output contains expected sections
    assert "Jupyter Deploy Project Information" in result.stdout, "Expected project info section"
    assert "Project Variables" in result.stdout, "Expected variables section"
    assert "Project Outputs" in result.stdout, "Expected outputs section"


@pytest.mark.cli
def test_show_template_name_matches_manifest(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --template-name returns value from manifest.yaml.

    This test:
    1. Ensures deployment exists
    2. Reads template name from manifest.yaml
    3. Queries template name via jd show --template-name --text
    4. Verifies values match
    """
    e2e_deployment.ensure_deployed()

    # Read template name from manifest
    manifest = e2e_deployment.get_manifest()

    expected_name = manifest.template.name

    # Query template name via jd show
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--template-name", "--text"])
    actual_name = result.stdout.strip()

    assert actual_name == expected_name, f"Expected template name '{expected_name}', got '{actual_name}'"


@pytest.mark.cli
def test_show_template_version_matches_manifest(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --template-version returns value from manifest.yaml.

    This test:
    1. Ensures deployment exists
    2. Reads template version from manifest.yaml
    3. Queries template version via jd show --template-version --text
    4. Verifies values match
    """
    e2e_deployment.ensure_deployed()

    # Read template version from manifest
    manifest = e2e_deployment.get_manifest()

    expected_version = manifest.template.version

    # Query template version via jd show
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--template-version", "--text"])
    actual_version = result.stdout.strip()

    assert actual_version == expected_version, f"Expected template version '{expected_version}', got '{actual_version}'"


@pytest.mark.cli
def test_show_project_id_returns_nonempty_value(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --project-id returns a non-empty project ID on a deployed project.

    This test:
    1. Ensures deployment exists
    2. Reads template name from manifest
    3. Queries project ID via jd show --project-id --text
    4. Verifies the project ID starts with the template name prefix
    """
    e2e_deployment.ensure_deployed()

    manifest = e2e_deployment.get_manifest()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--project-id", "--text"])
    actual_id = result.stdout.strip()

    assert actual_id, "Project ID should not be empty on a deployed project"
    assert actual_id.startswith(manifest.template.name), (
        f"Project ID '{actual_id}' should start with template name '{manifest.template.name}'"
    )


@pytest.mark.cli
def test_show_store_type_matches_manifest(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --store-type returns the store type from manifest.

    This test:
    1. Ensures deployment exists
    2. Reads project-store.store-type from manifest.yaml
    3. Queries store type via jd show --store-type --text
    4. Verifies values match
    """
    e2e_deployment.ensure_deployed()

    manifest = e2e_deployment.get_manifest()
    assert manifest.project_store is not None, "Manifest should have a project-store section"
    expected_store_type = manifest.project_store.store_type

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--store-type", "--text"])
    actual_store_type = result.stdout.strip()

    assert actual_store_type == expected_store_type, (
        f"Expected store type '{expected_store_type}', got '{actual_store_type}'"
    )


@pytest.mark.cli
def test_show_store_id_returns_nonempty_value(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --store-id returns a non-empty store ID on a deployed project.

    This test:
    1. Ensures deployment exists
    2. Queries store ID via jd show --store-id --text
    3. Verifies the store ID is not empty and not "N/A"
    """
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--store-id", "--text"])
    actual_store_id = result.stdout.strip()

    assert actual_store_id, "Store ID should not be empty on a deployed project"
    assert actual_store_id != "N/A", "Store ID should not be 'N/A' on a deployed project"


@pytest.mark.cli
def test_show_info_includes_store_and_project_id(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --info displays Store Type, Store ID, and Project ID rows.

    This test:
    1. Ensures deployment exists
    2. Runs jd show --info
    3. Verifies output contains Store Type, Store ID, and Project ID rows
    """
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--info"])

    assert result.returncode == 0, f"jd show --info should succeed, got returncode {result.returncode}"
    assert "Store Type" in result.stdout, "Info table should contain Store Type row"
    assert "Store ID" in result.stdout, "Info table should contain Store ID row"
    assert "Project ID" in result.stdout, "Info table should contain Project ID row"
    # On a deployed project, all store fields should have values
    assert "N/A" not in result.stdout, "Store Type, Store ID, and Project ID should not be N/A on a deployed project"


@pytest.mark.cli
def test_show_sensitive_variable_is_masked(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show -v <sensitive_var> --text returns masked value.

    This test:
    1. Ensures deployment exists
    2. Queries the sensitive variable oauth_app_client_secret via jd show --text
    3. Verifies the output is the masked placeholder ****
    """
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "show", "--variable", "oauth_app_client_secret", "--text"]
    )
    value = result.stdout.strip()

    assert value == "****", f"Expected masked value '****', got '{value}'"


@pytest.mark.cli
def test_show_reveal_sensitive_variable(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show -v <sensitive_var> --reveal --text returns the real secret.

    This test:
    1. Ensures deployment exists
    2. Queries the sensitive variable with --reveal --text
    3. Verifies the output is a non-empty value that is not the masked placeholder
    """
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "show", "--variable", "oauth_app_client_secret", "--reveal", "--text"]
    )
    value = result.stdout.strip()

    assert value, "Revealed secret should not be empty"
    assert value != "****", "Revealed secret should not be the masked placeholder"
