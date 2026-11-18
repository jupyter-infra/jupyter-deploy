"""E2E tests for remote access (VS Code, Cursor or Kiro over SSH) on the EKS OIDC template.

The cases run in order as one enable_remote_access off->on->off window, each flip a jd config
plus jd up. The window also offers a pool-bound VS Code config; remote_access_window restores
the flag and the configs if a case leaves them changed. On a deployment that already has the
flag on, the refusal and the disable cases skip and the window leaves the flag on.
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
    kubectl_get_workspace_pod,
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
    ROUTER_NAMESPACE,
    SIDECAR_CONTAINER,
    SIDECAR_PORT,
    VSCODE_GPU_TEMPLATE_NAME,
    VSCODE_SMALL_TEMPLATE,
    VSCODE_SMALL_TEMPLATE_CONFIG,
    VSCODE_TEMPLATE_NAME,
    VSCODE_WORKSPACE,
    WEBSOCKET_STRATEGY,
    WORKSPACE_APP_PORT,
    WORKSPACE_NAMESPACE,
    WORKSPACES_DIR,
)
from .overrides import pools_offering, restore_overrides, snapshot_overrides

pytestmark = [
    pytest.mark.mutating,
    pytest.mark.usefixtures("kubernetes_cluster_login", "remote_access_window"),
]

# The variables the window rewrites: the flag, and the mapping that offers the pool-bound config.
WINDOW_VARIABLES = [REMOTE_ACCESS_FLAG, "workspace_templates", "workspace_nodepools", "workspace_namespaces"]
VSCODE_TEMPLATES = (VSCODE_TEMPLATE_NAME, VSCODE_SMALL_TEMPLATE)
# Bound for the operator to finalize a removed template or strategy.
REMOVAL_TIMEOUT_S = 120
# The tools the VS Code image promises: the coding agents, and what an editor's remote server
# install needs (applications/vscode/Dockerfile).
IMAGE_TOOLS = ("claude", "codex", "git", "curl")


def _workspace_template(name: str, namespace: str) -> dict[str, Any]:
    result = run_kubectl("get", "workspacetemplate", name, "-n", namespace, "-o", "json")
    assert result.returncode == 0, f"{name} WorkspaceTemplate missing in {namespace}: {result.stderr}"
    template: dict[str, Any] = json.loads(result.stdout)
    return template


def _ingress_policy_ports(namespace: str) -> dict[str, set[int]]:
    """The ports the namespace's workspace-ingress NetworkPolicy admits, by source namespace."""
    result = run_kubectl("get", "networkpolicy", "workspace-ingress", "-n", namespace, "-o", "json", check=True)
    policy = json.loads(result.stdout)
    return {
        rule["from"][0]["namespaceSelector"]["matchLabels"]["kubernetes.io/metadata.name"]: {
            port["port"] for port in rule["ports"]
        }
        for rule in policy["spec"]["ingress"]
    }


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


def _delete_workspaces_of(templates: tuple[str, ...]) -> None:
    """Delete the workspaces of the given cards, which pin the templates the restoring apply removes."""
    with contextlib.suppress(Exception):
        run_kubectl(
            "delete",
            "workspaces",
            "-n",
            WORKSPACE_NAMESPACE,
            "-l",
            f"workspace.jupyter.org/template-name in ({','.join(templates)})",
            check=True,
        )


def _window_open(e2e_deployment: EndToEndDeployment, window: dict[str, Any]) -> bool:
    """Whether the flag differs from its state before the module or the pool-bound config is still configured."""
    configs = e2e_deployment.get_list_of_maps_variable_value("workspace_templates")
    return e2e_deployment.get_bool_variable_value(REMOTE_ACCESS_FLAG) != window["flag_was_on"] or any(
        config["name"] == VSCODE_SMALL_TEMPLATE for config in configs
    )


@pytest.fixture(scope="module")
def remote_access_window(e2e_deployment: EndToEndDeployment) -> Generator[dict[str, Any], None, None]:
    """The flag's state and the overrides before the module, restored if a case left the window open.

    On a deployment that had the flag on, only the pool-bound config's workspaces are the window's
    to delete before the restoring apply.
    """
    e2e_deployment.ensure_deployed()
    window: dict[str, Any] = {
        "flag_was_on": e2e_deployment.get_bool_variable_value(REMOTE_ACCESS_FLAG),
        "overrides": snapshot_overrides(e2e_deployment, WINDOW_VARIABLES),
    }
    yield window
    if _window_open(e2e_deployment, window):
        _delete_workspaces_of((VSCODE_SMALL_TEMPLATE,) if window["flag_was_on"] else VSCODE_TEMPLATES)
        restore_overrides(e2e_deployment, window["overrides"])


@pytest.mark.order(ORDER_REMOTE_ACCESS)
def test_vscode_config_is_refused_without_the_flag(
    e2e_deployment: EndToEndDeployment, remote_access_window: dict[str, Any]
) -> None:
    """`jd config` refuses a workspace_templates config with app vscode while the flag is off, naming it."""
    e2e_deployment.ensure_deployed()
    if remote_access_window["flag_was_on"]:
        pytest.skip(f"the deployment already has {REMOTE_ACCESS_FLAG} on")

    previous = e2e_deployment.read_override_value("workspace_templates")
    configs = e2e_deployment.get_list_of_maps_variable_value("workspace_templates")
    try:
        e2e_deployment.update_override_value(
            "workspace_templates", [*configs, {"name": VSCODE_SMALL_TEMPLATE, "app": "vscode"}]
        )
        error = e2e_deployment.cli.run_command_expecting_failure(["jupyter-deploy", "config"])
        assert f'app = "vscode" need {REMOTE_ACCESS_FLAG} = true: {VSCODE_SMALL_TEMPLATE}' in error, error
    finally:
        if previous is None:
            e2e_deployment.delete_override_value("workspace_templates")
        else:
            e2e_deployment.update_override_value("workspace_templates", previous)


@pytest.mark.order(ORDER_REMOTE_ACCESS + 1)
def test_enable_remote_access_offers_the_vscode_cards(
    e2e_deployment: EndToEndDeployment, shared_namespace: str
) -> None:
    """Enabling the flag builds the image and offers the VS Code card and a pool-bound VS Code config on the strategy.

    With a workspace_namespaces mapping, a namespace offers only the configs its entry lists, so
    the default namespace's entry gets the pool-bound config, and the GPU card when the pool is on;
    listing the built-in vscode card there is a no-op.
    """
    e2e_deployment.ensure_deployed()
    gpu_pool = e2e_deployment.get_bool_variable_value(GPU_POOL_FLAG)
    configs = e2e_deployment.get_list_of_maps_variable_value("workspace_templates")
    pools = e2e_deployment.get_list_of_maps_variable_value("workspace_nodepools")
    namespaces = e2e_deployment.get_list_of_maps_variable_value("workspace_namespaces")
    if namespaces and not any(entry["name"] == WORKSPACE_NAMESPACE for entry in namespaces):
        pytest.skip(f"the workspace_namespaces mapping has no {WORKSPACE_NAMESPACE} entry to offer the cards in")
    overrides: dict[str, Any] = {
        REMOTE_ACCESS_FLAG: True,
        "workspace_templates": [*configs, VSCODE_SMALL_TEMPLATE_CONFIG],
        "workspace_nodepools": pools_offering(pools, VSCODE_SMALL_TEMPLATE),
    }
    if namespaces:
        offered = [VSCODE_TEMPLATE_NAME, VSCODE_SMALL_TEMPLATE, *([VSCODE_GPU_TEMPLATE_NAME] if gpu_pool else [])]
        overrides["workspace_namespaces"] = [
            {
                **entry,
                "templates": ",".join(
                    dict.fromkeys([*[t for t in entry.get("templates", "").split(",") if t], *offered])
                ),
            }
            if entry["name"] == WORKSPACE_NAMESPACE
            else entry
            for entry in namespaces
        ]
    e2e_deployment.ensure_deployed_with_overrides(overrides)

    image_uri = _vscode_image_uri(e2e_deployment)
    assert ".dkr.ecr." in image_uri, f"vscode_image_uri is not an ECR image: {image_uri!r}"
    templates = {name: _workspace_template(name, WORKSPACE_NAMESPACE) for name in VSCODE_TEMPLATES}
    for template in templates.values():
        assert template["metadata"]["labels"]["workspace.jupyter.org/default-template"] == "false"
        assert template["spec"]["defaultImage"] == image_uri
        assert template["spec"]["defaultAccessStrategy"] == {"name": WEBSOCKET_STRATEGY, "namespace": shared_namespace}
        assert "defaultIdleShutdown" not in template["spec"], "VS Code workspaces have no idle shutdown yet"
    small = templates[VSCODE_SMALL_TEMPLATE]["spec"]
    assert small["displayName"] == VSCODE_SMALL_TEMPLATE_CONFIG["display_name"]
    assert small["resourceBounds"]["resources"]["cpu"] == {"min": "1", "max": "1"}
    assert small["resourceBounds"]["resources"]["memory"] == {"min": "2Gi", "max": "2Gi"}

    assert not resource_absent("workspaceaccessstrategies", WEBSOCKET_STRATEGY, shared_namespace), (
        f"{WEBSOCKET_STRATEGY} missing from {shared_namespace}"
    )
    assert (VSCODE_GPU_TEMPLATE_NAME in list_template_names(WORKSPACE_NAMESPACE)) is gpu_pool, (
        f"{VSCODE_GPU_TEMPLATE_NAME} must be offered exactly when {GPU_POOL_FLAG} is on (it is {gpu_pool})"
    )
    assert _ingress_policy_ports(WORKSPACE_NAMESPACE) == {
        ROUTER_NAMESPACE: {WORKSPACE_APP_PORT, SIDECAR_PORT},
        OPERATOR_NAMESPACE: {WORKSPACE_APP_PORT},
    }


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
        pod = kubectl_get_workspace_pod(VSCODE_WORKSPACE, WORKSPACE_NAMESPACE)
        ready = {status["name"]: status["ready"] for status in pod["status"].get("containerStatuses", [])}
        assert ready.get(SIDECAR_CONTAINER) is True, f"{SIDECAR_CONTAINER} missing or not ready: {ready}"

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
        token = parse_qs(url.query).get("token", [""])[0]
        assert token, f"connection URL carries no token: {url.geturl()}"

        route = url._replace(query="").geturl()
        assert _websocket_upgrade_status(route, token) == 101
        without_token = _websocket_upgrade_status(route, None)
        assert 400 <= without_token < 500, f"the route answered {without_token} to an upgrade without a token"

        host = workspace_service_host(VSCODE_WORKSPACE, WORKSPACE_NAMESPACE)
        assert probe_service_allowed(host, SIDECAR_PORT, from_namespace=ROUTER_NAMESPACE), (
            f"the router namespace should reach the sidecar port {SIDECAR_PORT}"
        )
        for denied in (OPERATOR_NAMESPACE, WORKSPACE_NAMESPACE):
            assert not probe_service(host, SIDECAR_PORT, from_namespace=denied), (
                f"namespace {denied} should be denied the sidecar port {SIDECAR_PORT}"
            )
    finally:
        kubectl_delete_workspace(VSCODE_WORKSPACE, namespace=WORKSPACE_NAMESPACE)


@pytest.mark.order(ORDER_REMOTE_ACCESS + 3)
def test_deleted_websocket_strategy_is_repaired_on_apply(
    e2e_deployment: EndToEndDeployment, shared_namespace: str
) -> None:
    """An apply re-creates the WebSocket strategy after a CRD wipe orphaned it (#270 for the OAuth one).

    The operator holds the strategy with a finalizer for the templates that reference it; a CRD
    wipe takes the finalizer with the object, so the test clears it the same way.
    """
    e2e_deployment.ensure_deployed()
    run_kubectl(
        "delete", "workspaceaccessstrategy", WEBSOCKET_STRATEGY, "-n", shared_namespace, "--wait=false", check=True
    )
    patched = run_kubectl(
        "patch",
        "workspaceaccessstrategy",
        WEBSOCKET_STRATEGY,
        "-n",
        shared_namespace,
        "--type=merge",
        "-p",
        '{"metadata":{"finalizers":null}}',
    )
    assert patched.returncode == 0 or "not found" in patched.stderr.lower(), patched.stderr
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
def test_disable_remote_access_removes_the_vscode_cards(
    e2e_deployment: EndToEndDeployment, shared_namespace: str, remote_access_window: dict[str, Any]
) -> None:
    """Disabling the flag removes the VS Code cards, the strategy and the image output, and closes the sidecar port."""
    e2e_deployment.ensure_deployed()
    if remote_access_window["flag_was_on"]:
        pytest.skip(f"the deployment had {REMOTE_ACCESS_FLAG} on before the module; the window keeps it")
    restore_overrides(e2e_deployment, remote_access_window["overrides"])

    for name in VSCODE_TEMPLATES:
        poll(
            lambda name=name: resource_absent("workspacetemplates", name, WORKSPACE_NAMESPACE),
            timeout_s=REMOVAL_TIMEOUT_S,
            msg=f"{name} WorkspaceTemplate still present after disabling {REMOTE_ACCESS_FLAG}",
        )
    poll(
        lambda: resource_absent("workspaceaccessstrategies", WEBSOCKET_STRATEGY, shared_namespace),
        timeout_s=REMOVAL_TIMEOUT_S,
        msg=f"{WEBSOCKET_STRATEGY} still present after disabling {REMOTE_ACCESS_FLAG}",
    )
    assert _vscode_image_uri(e2e_deployment) == ""
    assert _ingress_policy_ports(WORKSPACE_NAMESPACE) == {
        ROUTER_NAMESPACE: {WORKSPACE_APP_PORT},
        OPERATOR_NAMESPACE: {WORKSPACE_APP_PORT},
    }
