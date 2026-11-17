"""E2E tests for remote access (VS Code, Cursor or Kiro over SSH) on the EKS OIDC template.

The cases run in order as one enable_remote_access off->on->off window, each flip a jd config
plus jd up; remote_access_flag_guard restores the flag if a case leaves it flipped.
"""

import base64
import contextlib
import http.client
import json
import os
import secrets
from collections.abc import Generator
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.kubernetes.kubectl import resource_absent, run_kubectl
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.polling import poll
from pytest_jupyter_deploy.workspaces.kubectl import (
    kubectl_apply_workspace,
    kubectl_delete_workspace,
    kubectl_poll_workspace_status,
    kubectl_request_workspace_connection,
)
from pytest_jupyter_deploy.workspaces.network_probe import probe_service, probe_service_allowed, workspace_service_host
from pytest_jupyter_deploy.workspaces.template import list_template_names

from .constants import (
    GPU_POOL_FLAG,
    IMPERSONATED_USER,
    OPERATOR_NAMESPACE,
    ORDER_REMOTE_ACCESS,
    REMOTE_ACCESS_FLAG,
    SIDECAR_CONTAINER,
    SIDECAR_PORT,
    VSCODE_GPU_TEMPLATE_NAME,
    VSCODE_TEMPLATE_NAME,
    VSCODE_WORKSPACE,
    WEBSOCKET_STRATEGY,
    WORKSPACE_APP_PORT,
    WORKSPACE_NAMESPACE,
    WORKSPACES_DIR,
)

pytestmark = [
    pytest.mark.mutating,
    pytest.mark.usefixtures("kubernetes_cluster_login", "remote_access_flag_guard"),
]

# Bound for the operator to finalize a removed template or strategy.
REMOVAL_TIMEOUT_S = 120
# The tools the VS Code image promises: the coding agents, and what an editor's remote server
# install needs (applications/vscode/Dockerfile).
IMAGE_TOOLS = ("claude", "codex", "git", "curl")


def _apply_remote_access_flag(e2e_deployment: EndToEndDeployment, enabled: bool) -> None:
    """Record the flag in variables.yaml, then apply with jd config + jd up.

    Both directions go through the variables.yaml override: jd config exposes a bool
    only as a set-true flag.
    """
    e2e_deployment.update_override_value(REMOTE_ACCESS_FLAG, enabled)
    e2e_deployment.ensure_deployed_with([])


def _workspace_template(name: str, namespace: str) -> dict[str, Any] | None:
    result = run_kubectl("get", "workspacetemplate", name, "-n", namespace, "-o", "json")
    return json.loads(result.stdout) if result.returncode == 0 else None


def _ingress_policy_rule_ports(namespace: str) -> list[set[int]]:
    """The ports each ingress rule of the namespace's workspace-ingress NetworkPolicy admits."""
    result = run_kubectl("get", "networkpolicy", "workspace-ingress", "-n", namespace, "-o", "json", check=True)
    return [{port["port"] for port in rule["ports"]} for rule in json.loads(result.stdout)["spec"]["ingress"]]


def _workspace_pod_containers(name: str, namespace: str) -> dict[str, bool]:
    """Container name to readiness, for the workspace's pod."""
    result = run_kubectl(
        "get", "pods", "-n", namespace, "-l", f"workspace.jupyter.org/workspace-name={name}", "-o", "json", check=True
    )
    pod = json.loads(result.stdout)["items"][0]
    return {status["name"]: status["ready"] for status in pod["status"].get("containerStatuses", [])}


def _vscode_image_uri(e2e_deployment: EndToEndDeployment) -> str:
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--output", "vscode_image_uri", "--text"])
    return result.stdout.strip()


def _websocket_upgrade_status(url: str, token: str | None) -> int:
    """HTTP status of the WebSocket upgrade on the connection URL, the request the plugin makes.

    The token travels in the Authorization header as the plugin sends it. The response is not read
    past its status line; after a 101 the client closes the session without using it.
    """
    parsed = urlparse(url)
    headers = {
        "Connection": "Upgrade",
        "Upgrade": "websocket",
        "Sec-WebSocket-Version": "13",
        "Sec-WebSocket-Key": base64.b64encode(secrets.token_bytes(16)).decode(),
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    connection = http.client.HTTPSConnection(parsed.netloc, timeout=30)
    try:
        connection.request("GET", parsed.path, headers=headers)
        return connection.getresponse().status
    finally:
        connection.close()


@pytest.fixture(scope="module")
def remote_access_flag_guard(e2e_deployment: EndToEndDeployment) -> Generator[None, None, None]:
    """Restore enable_remote_access to its pre-module value if a case left it flipped."""
    e2e_deployment.ensure_deployed()
    original = bool(e2e_deployment.read_override_value(REMOTE_ACCESS_FLAG))
    yield
    if bool(e2e_deployment.read_override_value(REMOTE_ACCESS_FLAG)) != original:
        # A live VS Code workspace pins its template, which the flag-off apply removes.
        with contextlib.suppress(Exception):
            run_kubectl(
                "delete",
                "workspaces",
                "-n",
                WORKSPACE_NAMESPACE,
                "-l",
                f"workspace.jupyter.org/template-name={VSCODE_TEMPLATE_NAME}",
                check=True,
            )
        _apply_remote_access_flag(e2e_deployment, original)


@pytest.mark.order(ORDER_REMOTE_ACCESS)
def test_vscode_config_is_refused_without_the_flag(e2e_deployment: EndToEndDeployment) -> None:
    """`jd config` refuses a workspace_templates config with app vscode while the flag is off, naming it."""
    e2e_deployment.ensure_deployed()
    if e2e_deployment.get_bool_variable_value(REMOTE_ACCESS_FLAG):
        pytest.skip(f"the deployment already has {REMOTE_ACCESS_FLAG} on")

    configs = e2e_deployment.get_list_of_maps_variable_value("workspace_templates")
    try:
        e2e_deployment.update_override_value(
            "workspace_templates", [*configs, {"name": "e2e-vscode-cpu", "app": "vscode"}]
        )
        error = e2e_deployment.cli.run_command_expecting_failure(["jupyter-deploy", "config"])
        assert f'app = "vscode" need {REMOTE_ACCESS_FLAG} = true: e2e-vscode-cpu' in error, error
    finally:
        e2e_deployment.update_override_value("workspace_templates", configs)


@pytest.mark.order(ORDER_REMOTE_ACCESS + 1)
def test_enable_remote_access_offers_the_vscode_card(e2e_deployment: EndToEndDeployment, shared_namespace: str) -> None:
    """Enabling the flag builds the image, offers the VS Code card on the WebSocket strategy, opens the sidecar port."""
    e2e_deployment.ensure_deployed()
    _apply_remote_access_flag(e2e_deployment, True)

    image_uri = _vscode_image_uri(e2e_deployment)
    assert ".dkr.ecr." in image_uri and "/vscode-v" in image_uri, f"vscode_image_uri is not an ECR image: {image_uri!r}"

    template = _workspace_template(VSCODE_TEMPLATE_NAME, WORKSPACE_NAMESPACE)
    assert template is not None, f"{VSCODE_TEMPLATE_NAME} WorkspaceTemplate missing after enabling {REMOTE_ACCESS_FLAG}"
    assert template["spec"]["defaultImage"] == image_uri
    assert template["spec"]["defaultAccessStrategy"] == {"name": WEBSOCKET_STRATEGY, "namespace": shared_namespace}
    assert "defaultIdleShutdown" not in template["spec"], "VS Code workspaces have no idle shutdown yet"
    assert not resource_absent("workspaceaccessstrategies", WEBSOCKET_STRATEGY, shared_namespace), (
        f"{WEBSOCKET_STRATEGY} missing from {shared_namespace}"
    )

    gpu_pool = e2e_deployment.get_bool_variable_value(GPU_POOL_FLAG)
    assert (VSCODE_GPU_TEMPLATE_NAME in list_template_names(WORKSPACE_NAMESPACE)) is gpu_pool, (
        f"{VSCODE_GPU_TEMPLATE_NAME} must be offered exactly when {GPU_POOL_FLAG} is on (it is {gpu_pool})"
    )

    for ports in _ingress_policy_rule_ports(WORKSPACE_NAMESPACE):
        assert ports == {WORKSPACE_APP_PORT, SIDECAR_PORT}, f"workspace-ingress admits {ports}"


@pytest.mark.order(ORDER_REMOTE_ACCESS + 2)
@skip_if_testvars_not_set(["JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_vscode_workspace_runs_with_the_sidecar_and_hands_out_an_ssh_connection(
    e2e_deployment: EndToEndDeployment, eks_domain: str
) -> None:
    """A workspace from the VS Code card runs with the sidecar, and a team member gets a wss URL to it.

    The jd server commands reach the workspace container of the two-container pod. The connection
    request runs as a member of the workspace RBAC team, the identity the plugin uses.
    """
    e2e_deployment.ensure_deployed()
    with contextlib.suppress(Exception):
        kubectl_delete_workspace(VSCODE_WORKSPACE, namespace=WORKSPACE_NAMESPACE)

    kubectl_apply_workspace(VSCODE_WORKSPACE, WORKSPACES_DIR)
    try:
        # First start pulls the new image; allow minutes.
        kubectl_poll_workspace_status(VSCODE_WORKSPACE, "Running", namespace=WORKSPACE_NAMESPACE, timeout_s=600)
        containers = _workspace_pod_containers(VSCODE_WORKSPACE, WORKSPACE_NAMESPACE)
        assert containers.get(SIDECAR_CONTAINER) is True, f"{SIDECAR_CONTAINER} missing or not ready: {containers}"

        e2e_deployment.cli.wait_for_workspace_pod_exec_ready(VSCODE_WORKSPACE, scope=WORKSPACE_NAMESPACE, timeout_s=60)
        for tool in IMAGE_TOOLS:
            e2e_deployment.cli.run_exec_with_retry(
                ["jupyter-deploy", "server", "exec", "--name", VSCODE_WORKSPACE, "--scope", WORKSPACE_NAMESPACE]
                + ["--", tool, "--version"]
            )
        e2e_deployment.cli.run_command(
            ["jupyter-deploy", "server", "logs", "--name", VSCODE_WORKSPACE, "--scope", WORKSPACE_NAMESPACE]
        )

        group = f"github:{os.environ['JD_E2E_ORG']}:{os.environ['JD_E2E_RBAC_TEAM']}"
        connection = kubectl_request_workspace_connection(
            VSCODE_WORKSPACE, WORKSPACE_NAMESPACE, as_user=IMPERSONATED_USER, as_groups=[group]
        )
        url = urlparse(connection["status"]["workspaceConnectionUrl"])
        assert url.scheme == "wss", f"connection URL is not wss: {url.geturl()}"
        assert url.netloc == eks_domain, f"connection URL does not point at the deployment: {url.geturl()}"
        assert url.path == f"/workspaces/{WORKSPACE_NAMESPACE}/{VSCODE_WORKSPACE}/ssh-ws"
        token = parse_qs(url.query).get("token", [""])[0]
        assert token, f"connection URL carries no token: {url.geturl()}"

        route = url._replace(query="").geturl()
        assert _websocket_upgrade_status(route, token) == 101
        without_token = _websocket_upgrade_status(route, None)
        assert 400 <= without_token < 500, f"the route answered {without_token} to an upgrade without a token"

        host = workspace_service_host(VSCODE_WORKSPACE, WORKSPACE_NAMESPACE)
        assert probe_service_allowed(host, SIDECAR_PORT, from_namespace=OPERATOR_NAMESPACE), (
            f"the operator namespace should reach the sidecar port {SIDECAR_PORT}"
        )
        assert not probe_service(host, SIDECAR_PORT, from_namespace=WORKSPACE_NAMESPACE), (
            f"a co-tenant pod should be denied the sidecar port {SIDECAR_PORT}"
        )
    finally:
        kubectl_delete_workspace(VSCODE_WORKSPACE, namespace=WORKSPACE_NAMESPACE)


@pytest.mark.order(ORDER_REMOTE_ACCESS + 3)
def test_deleted_websocket_strategy_is_repaired_on_apply(
    e2e_deployment: EndToEndDeployment, shared_namespace: str
) -> None:
    """An apply re-creates the WebSocket strategy after a CRD wipe orphaned it (#270 for the OAuth one)."""
    e2e_deployment.ensure_deployed()
    run_kubectl("delete", "workspaceaccessstrategy", WEBSOCKET_STRATEGY, "-n", shared_namespace, check=True)
    poll(
        lambda: resource_absent("workspaceaccessstrategies", WEBSOCKET_STRATEGY, shared_namespace),
        timeout_s=REMOVAL_TIMEOUT_S,
        msg=f"{WEBSOCKET_STRATEGY} still present after its deletion",
    )

    e2e_deployment.ensure_deployed_with([])

    assert not resource_absent("workspaceaccessstrategies", WEBSOCKET_STRATEGY, shared_namespace), (
        f"{WEBSOCKET_STRATEGY} was not re-created by the apply"
    )


@pytest.mark.order(ORDER_REMOTE_ACCESS + 4)
def test_disable_remote_access_removes_the_vscode_card(
    e2e_deployment: EndToEndDeployment, shared_namespace: str
) -> None:
    """Disabling the flag removes the VS Code card, the strategy and the image output, and closes the sidecar port."""
    e2e_deployment.ensure_deployed()
    _apply_remote_access_flag(e2e_deployment, False)

    poll(
        lambda: resource_absent("workspacetemplates", VSCODE_TEMPLATE_NAME, WORKSPACE_NAMESPACE),
        timeout_s=REMOVAL_TIMEOUT_S,
        msg=f"{VSCODE_TEMPLATE_NAME} WorkspaceTemplate still present after disabling {REMOTE_ACCESS_FLAG}",
    )
    poll(
        lambda: resource_absent("workspaceaccessstrategies", WEBSOCKET_STRATEGY, shared_namespace),
        timeout_s=REMOVAL_TIMEOUT_S,
        msg=f"{WEBSOCKET_STRATEGY} still present after disabling {REMOTE_ACCESS_FLAG}",
    )
    assert _vscode_image_uri(e2e_deployment) == ""
    for ports in _ingress_policy_rule_ports(WORKSPACE_NAMESPACE):
        assert ports == {WORKSPACE_APP_PORT}, f"workspace-ingress still admits {ports}"
