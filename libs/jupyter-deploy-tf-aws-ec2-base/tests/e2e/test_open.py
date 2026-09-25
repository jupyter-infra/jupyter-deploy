"""E2E tests for jd open command."""

import re

import pytest
from pytest_jupyter_deploy.cli import JDCliError
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
    assert "Opening app at:" in result.stdout, "Expected 'Opening app at:' in jd open output"

    # Extract the URL from the output using regex
    # Expected format: "Opening app at: https://subdomain.domain.com"
    url_pattern = r"Opening app at:\s+(https://[^\s]+)"
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


# The two rejections below run without a host: `jd open` validates the flag against the manifest
# and exits before it resolves an output or calls AWS. Marked `cli` for that reason -- they are the
# cheapest place to catch a template and the core guard drifting apart, which unit tests cannot do
# because they mock the manifest.
#
# Both assert only that the rejected flag is named, not the sentence around it.


@pytest.mark.cli
def test_open_rejects_server_name_on_a_single_app_template(e2e_deployment: EndToEndDeployment) -> None:
    """`jd open --server-name` is rejected, and the failure names the flag.

    Selecting a server needs the `open.server` manifest command, which this template does not
    declare. Naming the flag is the contract: reporting `jd open` as unsupported would be wrong,
    since plain `jd open` is this template's primary flow (test_open_show_correct_url above).
    """
    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(["jupyter-deploy", "open", "--server-name", "default"])

    assert "--server-name" in str(exc_info.value), f"Expected the flag to be named, got: {exc_info.value}"


@pytest.mark.cli
def test_open_rejects_detached_on_a_url_template(e2e_deployment: EndToEndDeployment) -> None:
    """`jd open -d` is rejected here rather than silently ignored.

    --detached backgrounds the local client proxy, which only exists for proxy-mode templates
    (see the jupyterlab suite). This template opens a public URL, so there is no process to
    background and the flag is meaningless.
    """
    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(["jupyter-deploy", "open", "-d"])

    assert "--detached" in str(exc_info.value), f"Expected the flag to be named, got: {exc_info.value}"
