"""E2E test for full EKS deployment lifecycle from scratch.

These tests only run during fresh deploy (marked full_deployment).
After `jd config` + `jd up` complete, they verify the cluster and platform
components are healthy and the getting-started page is accessible.
"""

import json

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.oauth2_proxy.dex import DexGitHubOAuth2ProxyApplication
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set

ORDER_DEPLOYMENT = 1

EXPECTED_DEPLOYMENTS = [
    "traefik",
    "dex",
    "oauth2-proxy",
    "authmiddleware",
    "console",
    "workspace-operator",
]

EXPECTED_CRONJOBS = [
    "jwt-rotator",
]


@pytest.mark.order(ORDER_DEPLOYMENT)
@pytest.mark.full_deployment
def test_cluster_active_after_deployment(e2e_deployment: EndToEndDeployment) -> None:
    """Cluster status is ACTIVE after deploy."""
    e2e_deployment.ensure_deployed()
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "cluster", "status"])
    assert "ACTIVE" in result.stdout, f"Expected ACTIVE cluster status, got:\n{result.stdout}"


@pytest.mark.order(ORDER_DEPLOYMENT + 1)
@pytest.mark.full_deployment
def test_components_healthy_after_deployment(e2e_deployment: EndToEndDeployment) -> None:
    """All platform components reach healthy state after deploy."""
    e2e_deployment.ensure_deployed()
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "health", "--json"])
    data = json.loads(result.stdout)
    components = {c["name"]: c for c in data["components"]}

    for name in EXPECTED_DEPLOYMENTS:
        assert name in components, f"Expected Deployment component '{name}' in health output"
        c = components[name]
        assert c["type"] == "Deployment", f"{name}: expected type Deployment, got {c['type']}"
        assert c["status"] == "Ready", f"{name}: expected status Ready, got {c['status']}"
        assert c["status_category"] == "healthy", f"{name}: expected healthy, got {c['status_category']}"

    for name in EXPECTED_CRONJOBS:
        assert name in components, f"Expected CronJob component '{name}' in health output"
        c = components[name]
        assert c["type"] == "CronJob", f"{name}: expected type CronJob, got {c['type']}"
        assert c["status_category"] == "healthy", f"{name}: expected healthy, got {c['status_category']}"


@pytest.mark.order(ORDER_DEPLOYMENT + 2)
@pytest.mark.full_deployment
@skip_if_testvars_not_set(["JD_E2E_USER"])
def test_getting_started_accessible_after_deployment(
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
    getting_started_url: str,
) -> None:
    """Getting-started page is accessible via OAuth after deploy."""
    dex_oauth_app.ensure_authenticated()
    dex_oauth_app.page.goto(getting_started_url, wait_until="load", timeout=60000)
    content = dex_oauth_app.page.content()
    assert "kubeconfig" in content.lower() or "get-started" in content.lower(), (
        f"Expected getting-started content, got:\n{content[:500]}"
    )


@pytest.mark.order(ORDER_DEPLOYMENT + 3)
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
