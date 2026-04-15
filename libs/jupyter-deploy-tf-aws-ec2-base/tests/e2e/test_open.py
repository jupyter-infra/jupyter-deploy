"""E2E tests for jd open command."""

import re

from pytest_jupyter_deploy.deployment import EndToEndDeployment


# Not marked @pytest.mark.cli — requires a running host and browser, not available in headless CLI containers
def test_open_show_correct_url(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd open displays the correct URL and the URL is accessible.

    This test:
    1. Ensures deployment and authorization are set up
    2. Runs `jd open` and captures output
    3. Extracts the URL from the output
    4. Verifies the URL format (HTTPS)
    """
    # Prerequisite: ensure deployment and authorization
    e2e_deployment.ensure_deployed()
    e2e_deployment.ensure_server_running()

    # Run jd open and capture output
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "open"])

    # Verify the output contains expected text
    assert "Opening Jupyter app at:" in result.stdout, "Expected 'Opening Jupyter app at:' in jd open output"

    # Extract the URL from the output using regex
    # Expected format: "Opening Jupyter app at: https://subdomain.domain.com"
    url_pattern = r"Opening Jupyter app at:\s+(https://[^\s]+)"
    match = re.search(url_pattern, result.stdout)
    assert match is not None, "Could not extract URL from jd open output"

    url = match.group(1)

    # Verify URL format
    assert url.startswith("https://"), f"Expected HTTPS URL, got: {url}"

    # Verify URL matches the expected domain from variables.yaml
    subdomain = e2e_deployment.get_str_variable_value("subdomain")
    domain = e2e_deployment.get_str_variable_value("domain")
    expected_url = f"https://{subdomain}.{domain}"
    assert url == expected_url, f"Expected URL '{expected_url}', but got '{url}'"
