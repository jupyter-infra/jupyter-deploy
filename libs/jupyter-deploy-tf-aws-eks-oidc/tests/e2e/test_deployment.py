"""E2E test for full EKS deployment lifecycle from scratch.

These tests only run during fresh deploy (marked full_deployment).
After `jd config` + `jd up` complete, they verify the full health stack
passes and the getting-started page is accessible.
"""

import json

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.oauth2_proxy.dex import DexGitHubOAuth2ProxyApplication
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set

ORDER_DEPLOYMENT = 1

EXPECTED_CRONJOBS = [
    "jwt-rotator",
]


@pytest.mark.order(ORDER_DEPLOYMENT)
@pytest.mark.full_deployment
def test_cluster_active_after_deployment(e2e_deployment: EndToEndDeployment) -> None:
    """Cluster status is ACTIVE after deploy."""
    e2e_deployment.ensure_deployed()
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "cluster", "status"])
    assert "Active" in result.stdout, f"Expected Active cluster status, got:\n{result.stdout}"


@pytest.mark.order(ORDER_DEPLOYMENT + 2)
@pytest.mark.full_deployment
def test_health_all_pass_after_deployment(e2e_deployment: EndToEndDeployment) -> None:
    """All health layers pass after a fresh deploy."""
    e2e_deployment.ensure_deployed()
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health", "--json"])
    data = json.loads(result.stdout)

    assert "connection" in data, f"Expected 'connection' key, got: {list(data.keys())}"
    conn = data["connection"]
    assert conn["status_category"] == "healthy", (
        f"Connection not healthy: status_category={conn['status_category']}, detail={conn['detail']}"
    )

    layers = data["layers"]
    assert len(layers) >= 3, f"Expected at least 3 health rows, got {len(layers)}"

    layer_names = {entry["layer"] for entry in layers}
    assert "cluster" in layer_names, f"Expected 'cluster' layer, got: {layer_names}"
    assert "load-balancer" in layer_names, f"Expected 'load-balancer' layer, got: {layer_names}"
    assert "components" in layer_names, f"Expected 'components' layer, got: {layer_names}"

    manifest = e2e_deployment.get_manifest()
    manifest_components = manifest.get_components()
    component_entries = [e for e in layers if e["layer"] == "components"]
    component_names = {e["name"] for e in component_entries}
    for name in manifest_components:
        assert name in component_names, f"Expected component '{name}' in health output"

    for entry in layers:
        if entry["name"] in EXPECTED_CRONJOBS:
            assert entry["status_category"] in ("healthy", "in-progress"), (
                f"CronJob '{entry['name']}' unexpected status: "
                f"status_category={entry['status_category']}, detail={entry['detail']}"
            )
        else:
            assert entry["status_category"] == "healthy", (
                f"Layer '{entry['layer']}' ({entry['name']}) not healthy: "
                f"status_category={entry['status_category']}, status={entry['status']}, detail={entry['detail']}"
            )
        assert entry["status"], f"Layer '{entry['layer']}' ({entry['name']}) has empty status"


@pytest.mark.order(ORDER_DEPLOYMENT + 3)
@pytest.mark.full_deployment
@skip_if_testvars_not_set(["JD_E2E_USER"])
def test_web_app_accessible_after_deployment(
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
    getting_started_url: str,
) -> None:
    """Web UI is accessible via OAuth after deploy."""
    dex_oauth_app.ensure_authenticated()
    dex_oauth_app.page.goto(getting_started_url, wait_until="load", timeout=60000)
    content = dex_oauth_app.page.content()
    assert "workspaces" in content.lower(), f"Expected web UI content, got:\n{content[:500]}"


@pytest.mark.order(ORDER_DEPLOYMENT + 4)
@pytest.mark.full_deployment
def test_deployment_history_captured(e2e_deployment: EndToEndDeployment) -> None:
    """Config and up logs are captured in jd history after deployment."""
    e2e_deployment.ensure_deployed()
    config_list_result = e2e_deployment.cli.run_command(["jupyter-deploy", "history", "list", "config", "--text"])
    config_logs = [line for line in config_list_result.stdout.strip().split("\n") if line.strip()]
    assert len(config_logs) >= 1, f"Expected at least 1 config log, found {len(config_logs)}"

    up_list_result = e2e_deployment.cli.run_command(["jupyter-deploy", "history", "list", "up", "--text"])
    up_logs = [line for line in up_list_result.stdout.strip().split("\n") if line.strip()]
    assert len(up_logs) >= 1, f"Expected at least 1 up log, found {len(up_logs)}"

    config_show_result = e2e_deployment.cli.run_command(["jupyter-deploy", "history", "show", "config"])
    assert "Terraform has been successfully initialized!" in config_show_result.stdout, (
        "Expected 'Terraform has been successfully initialized!' in config log"
    )

    up_show_result = e2e_deployment.cli.run_command(["jupyter-deploy", "history", "show", "up"])
    assert "Apply complete!" in up_show_result.stdout, "Expected 'Apply complete!' in up log"
    assert "Outputs:" in up_show_result.stdout, "Expected 'Outputs:' section in up log"
