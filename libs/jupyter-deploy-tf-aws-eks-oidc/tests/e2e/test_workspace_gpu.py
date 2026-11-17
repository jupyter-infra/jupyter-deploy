"""E2E tests for the GPU feature on the EKS OIDC template.

One enable_default_gpu_pool on->off window: the first case turns the flag on
(jd config + jd up); the ordered cases run the kubectl critical path (torch/CUDA
notebook), stop that workspace and start it again on a fresh node with its home
volume, run the UI critical path, and check scale-to-zero after deletion; the
last case turns the flag off and verifies the pool tears down fully (#349).
gpu_pool_flag_guard restores the flag if any case leaves the window open.
The kubectl and restart cases each write a start-phase record to
test-results/start-phases/, which the e2e job uploads.
Gated on JD_E2E_GPU_ENABLED (needs G/VT on-demand quota in the account).
"""

import contextlib
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.kubernetes.kubectl import resource_absent, run_kubectl
from pytest_jupyter_deploy.kubernetes.nodes import get_node_allocatable_gpu_count, get_node_names
from pytest_jupyter_deploy.notebook import delete_notebook, run_notebook_in_jupyterlab, upload_notebook
from pytest_jupyter_deploy.oauth2_proxy.dex import DexGitHubOAuth2ProxyApplication
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.polling import poll
from pytest_jupyter_deploy.workspaces.kubectl import (
    kubectl_apply_workspace,
    kubectl_delete_workspace,
    kubectl_get_workspace_access_url,
    kubectl_list_workspace_pods,
)
from pytest_jupyter_deploy.workspaces.web_app import WebAppNavigator

from .constants import (
    GPU_EC2NODECLASS,
    GPU_NODEPOOL,
    GPU_POOL_FLAG,
    GPU_ROLE,
    GPU_ROLE_SELECTOR,
    GPU_TEMPLATE_DISPLAY_NAME,
    GPU_TEMPLATE_NAME,
    GPU_WORKSPACE,
    ORDER_GPU,
    WORKSPACE_NAMESPACE,
    WORKSPACES_DIR,
)
from .test_utils import (
    get_workspace_pod,
    record_workspace_start,
    utc_now,
    write_start_phase_record,
)

NOTEBOOKS_DIR = Path(__file__).parent / "notebooks"

# Bound for the Karpenter termination finalizers to clear after the flag-off
# apply; #349's stuck finalizer never clears, so a timeout is the regression.
POOL_REMOVAL_TIMEOUT_S = 600

# Written to the home volume before the stop, read back on the fresh node.
RESTART_MARKER = "/home/jovyan/e2e-gpu-restart-marker.txt"

pytestmark = [
    pytest.mark.gpu,
    pytest.mark.mutating,
    pytest.mark.usefixtures("kubernetes_cluster_login", "gpu_pool_flag_guard"),
]


def _kubectl_stdout(*args: str) -> str:
    return run_kubectl(*args, check=True).stdout.strip()


def _node_instance(node_name: str) -> str:
    instance = _kubectl_stdout("get", "node", node_name, "-o", "jsonpath={.spec.providerID}")
    assert instance, f"node {node_name} has no providerID"
    return instance


def _gpu_node_count() -> int:
    return len(get_node_names(GPU_ROLE_SELECTOR))


def _apply_gpu_pool_flag(e2e_deployment: EndToEndDeployment, enabled: bool) -> None:
    """Record the flag in variables.yaml, then apply with jd config + jd up.

    jd config exposes the variable only as a set-true flag (typer generates no
    --no- form for explicitly named bool options), so both directions go
    through the variables.yaml override.
    """
    e2e_deployment.update_override_value(GPU_POOL_FLAG, enabled)
    e2e_deployment.ensure_deployed_with([])


@pytest.fixture(scope="module")
def gpu_pool_flag_guard(e2e_deployment: EndToEndDeployment) -> Generator[None, None, None]:
    """Restore enable_default_gpu_pool to its pre-module value if a case left it flipped."""
    e2e_deployment.ensure_deployed()
    original = bool(e2e_deployment.read_override_value(GPU_POOL_FLAG))
    yield
    # The kubectl case leaves GPU_WORKSPACE running for the restart case; a filtered run can end
    # the module with it alive, and a live GPU pod keeps a GPU node up.
    with contextlib.suppress(Exception):
        kubectl_delete_workspace(GPU_WORKSPACE)
    if bool(e2e_deployment.read_override_value(GPU_POOL_FLAG)) != original:
        # A live GPU pod pins the pool; drop leftovers before the restoring apply.
        # The UI case's workspace name is generated at create time, so select by the
        # template label instead: the operator's defaulting webhook stamps it on every
        # workspace and admission is failurePolicy=Fail, so it cannot be absent.
        with contextlib.suppress(Exception):
            run_kubectl(
                "delete",
                "workspaces",
                "-n",
                WORKSPACE_NAMESPACE,
                "-l",
                f"workspace.jupyter.org/template-name={GPU_TEMPLATE_NAME}",
                check=True,
            )
        _apply_gpu_pool_flag(e2e_deployment, original)


@pytest.mark.order(ORDER_GPU)
@skip_if_testvars_not_set(["JD_E2E_GPU_ENABLED"])
def test_enable_gpu_pool(e2e_deployment: EndToEndDeployment) -> None:
    """Enabling the flag creates the workspace-gpu pool and installs the device plugin."""
    e2e_deployment.ensure_deployed()
    _apply_gpu_pool_flag(e2e_deployment, True)

    assert not resource_absent("nodepools.karpenter.sh", GPU_NODEPOOL), (
        "workspace-gpu NodePool missing after enabling enable_default_gpu_pool"
    )

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "list"])
    assert GPU_NODEPOOL in result.stdout, f"Expected pool '{GPU_NODEPOOL}' in pool list output:\n{result.stdout}"

    daemonset = run_kubectl(
        "get", "daemonset", "nvidia-device-plugin", "-n", "kube-system", "-o", "jsonpath={.metadata.name}"
    )
    assert daemonset.stdout.strip() == "nvidia-device-plugin", (
        f"device plugin daemonset missing: {daemonset.stdout} {daemonset.stderr}"
    )


@pytest.mark.order(ORDER_GPU + 1)
@skip_if_testvars_not_set(["JD_E2E_GPU_ENABLED", "JD_E2E_USER"])
@pytest.mark.usefixtures("gpu_pool_required")
def test_kubectl_gpu_workspace_runs_cuda_notebook(
    e2e_deployment: EndToEndDeployment,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
    request: pytest.FixtureRequest,
) -> None:
    """kubectl critical path: create from the GPU template, await, open, torch sees CUDA.

    Also pins the fenced provisioning contract: the pod lands on a workspace-gpu
    node (role label + taint + nvidia.com/gpu.present) with a registered device.
    On success the workspace stays up for the restart case, which deletes it.
    """
    e2e_deployment.ensure_deployed()

    # Clean up any leftover workspace from a previous test run.
    with contextlib.suppress(Exception):
        kubectl_delete_workspace(GPU_WORKSPACE)
        poll(lambda: _gpu_node_count() == 0, timeout_s=300, msg="pre-test cleanup: gpu node did not terminate")

    requested = utc_now()
    kubectl_apply_workspace(GPU_WORKSPACE, WORKSPACES_DIR)
    handed_off = False
    try:
        # First start provisions a node and pulls the image; allow minutes.
        e2e_deployment.cli.poll_scoped_server_status(GPU_WORKSPACE, "Running", timeout_s=600)

        assert _gpu_node_count() > 0, "Expected at least one gpu node after workspace creation"

        pod = get_workspace_pod(GPU_WORKSPACE, WORKSPACE_NAMESPACE)
        pod_node = pod["spec"].get("nodeName", "")
        assert pod_node, f"Could not find pod node for workspace {GPU_WORKSPACE}"
        record = record_workspace_start(
            request.node.originalname, e2e_deployment, GPU_WORKSPACE, WORKSPACE_NAMESPACE, requested, pod
        )

        node_role = _kubectl_stdout("get", "node", pod_node, "-o", "jsonpath={.metadata.labels.jupyter-deploy/role}")
        assert node_role == GPU_ROLE, f"GPU workspace pod landed on node with role '{node_role}', expected '{GPU_ROLE}'"

        nodepool = _kubectl_stdout("get", "node", pod_node, "-o", r"jsonpath={.metadata.labels.karpenter\.sh/nodepool}")
        assert nodepool == GPU_NODEPOOL, f"GPU pod node has nodepool '{nodepool}', expected '{GPU_NODEPOOL}'"

        gpu_present = _kubectl_stdout(
            "get", "node", pod_node, "-o", r"jsonpath={.metadata.labels.nvidia\.com/gpu\.present}"
        )
        assert gpu_present == "true", f"GPU node lacks the nvidia.com/gpu.present label (got '{gpu_present}')"

        taints = _kubectl_stdout("get", "node", pod_node, "-o", "jsonpath={.spec.taints}")
        assert GPU_ROLE in taints, f"GPU node is not tainted with the {GPU_ROLE} role (taints: {taints})"

        assert get_node_allocatable_gpu_count(pod_node) >= 1, "Device plugin did not register nvidia.com/gpu"

        e2e_deployment.cli.wait_for_workspace_pod_exec_ready(GPU_WORKSPACE)
        result = e2e_deployment.cli.run_exec_with_retry(
            ["jupyter-deploy", "server", "exec", "--name", GPU_WORKSPACE, "--", "nvidia-smi"]
        )
        assert "NVIDIA-SMI" in result.stdout, f"nvidia-smi did not see a device:\n{result.stdout}"

        access_url = kubectl_get_workspace_access_url(GPU_WORKSPACE, WORKSPACE_NAMESPACE)
        dex_oauth_app.verify_workspace_accessible(access_url)

        server_path = upload_notebook(
            e2e_deployment,
            NOTEBOOKS_DIR / "gpu_check.ipynb",
            "e2e-test/gpu_check.ipynb",
            name=GPU_WORKSPACE,
            scope=WORKSPACE_NAMESPACE,
        )
        # torch pulls ~2.5 GiB of CUDA wheels; long timeout, slow poll.
        notebook_started = time.monotonic()
        run_notebook_in_jupyterlab(dex_oauth_app.page, server_path, timeout_ms=300000, poll_interval_ms=5000)
        record["durations_s"]["notebook_gpu_check"] = round(time.monotonic() - notebook_started, 1)
        write_start_phase_record(record)
        delete_notebook(e2e_deployment, server_path, name=GPU_WORKSPACE, scope=WORKSPACE_NAMESPACE)
        handed_off = True
    finally:
        if not handed_off:
            kubectl_delete_workspace(GPU_WORKSPACE)


@pytest.mark.order(ORDER_GPU + 2)
@skip_if_testvars_not_set(["JD_E2E_GPU_ENABLED", "JD_E2E_USER"])
@pytest.mark.usefixtures("gpu_pool_required")
def test_stopped_gpu_workspace_restarts_on_fresh_node_with_its_home_volume(
    e2e_deployment: EndToEndDeployment,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
    request: pytest.FixtureRequest,
) -> None:
    """Stopping the only GPU workspace scales the pool to zero; starting it brings up a new
    node and the home volume follows: a marker file and the torch install from the
    kubectl case are both there without any reinstall.
    """
    e2e_deployment.ensure_deployed()
    if not kubectl_list_workspace_pods(GPU_WORKSPACE, WORKSPACE_NAMESPACE):
        pytest.fail(
            f"{GPU_WORKSPACE} is not running; this case continues from test_kubectl_gpu_workspace_runs_cuda_notebook"
        )
    try:
        first_pod = get_workspace_pod(GPU_WORKSPACE, WORKSPACE_NAMESPACE)
        # The instance id, not the node name: a replacement node in the same subnet can get the
        # released IP back, and EKS names nodes after it.
        first_instance = _node_instance(first_pod["spec"]["nodeName"])
        e2e_deployment.cli.run_exec_with_retry(
            [
                "jupyter-deploy",
                "server",
                "exec",
                "--name",
                GPU_WORKSPACE,
                "--",
                f"sh -c 'echo restart-ok > {RESTART_MARKER}'",
            ]
        )

        e2e_deployment.cli.run_command(["jupyter-deploy", "server", "stop", "--name", GPU_WORKSPACE])
        e2e_deployment.cli.poll_scoped_server_status(GPU_WORKSPACE, "Stopped", timeout_s=180)
        # The pool consolidates an empty node after 60s; the rest is EC2 termination.
        poll(
            lambda: _gpu_node_count() == 0,
            timeout_s=600,
            msg="gpu NodePool did not scale to zero after stopping the workspace",
        )

        requested = utc_now()
        e2e_deployment.cli.run_command(["jupyter-deploy", "server", "start", "--name", GPU_WORKSPACE])
        # Start from zero provisions a node in the volume's zone and pulls the image; allow minutes.
        e2e_deployment.cli.poll_scoped_server_status(GPU_WORKSPACE, "Running", timeout_s=600)

        pod = get_workspace_pod(GPU_WORKSPACE, WORKSPACE_NAMESPACE)
        record = record_workspace_start(
            request.node.originalname, e2e_deployment, GPU_WORKSPACE, WORKSPACE_NAMESPACE, requested, pod
        )
        new_instance = _node_instance(pod["spec"]["nodeName"])
        assert new_instance != first_instance, (
            f"Restarted pod is on instance {first_instance} again; expected a fresh node after the pool scaled to zero"
        )

        e2e_deployment.cli.wait_for_workspace_pod_exec_ready(GPU_WORKSPACE)
        marker = e2e_deployment.cli.run_exec_with_retry(
            ["jupyter-deploy", "server", "exec", "--name", GPU_WORKSPACE, "--", "cat", RESTART_MARKER]
        )
        assert "restart-ok" in marker.stdout, f"Marker file did not survive the restart:\n{marker.stdout}"

        access_url = kubectl_get_workspace_access_url(GPU_WORKSPACE, WORKSPACE_NAMESPACE)
        dex_oauth_app.verify_workspace_accessible(access_url)

        server_path = upload_notebook(
            e2e_deployment,
            NOTEBOOKS_DIR / "gpu_cuda_available.ipynb",
            "e2e-test/gpu_cuda_available.ipynb",
            name=GPU_WORKSPACE,
            scope=WORKSPACE_NAMESPACE,
        )
        # No install cell: torch has to come from the venv on the volume.
        notebook_started = time.monotonic()
        run_notebook_in_jupyterlab(dex_oauth_app.page, server_path, timeout_ms=180000)
        record["durations_s"]["notebook_gpu_cuda_available"] = round(time.monotonic() - notebook_started, 1)
        write_start_phase_record(record)
        delete_notebook(e2e_deployment, server_path, name=GPU_WORKSPACE, scope=WORKSPACE_NAMESPACE)
    finally:
        # Free the single GPU promptly so the UI case can reuse a warm node;
        # scale-to-zero after deletion is asserted once, after the UI case.
        kubectl_delete_workspace(GPU_WORKSPACE)


@pytest.mark.order(ORDER_GPU + 3)
@skip_if_testvars_not_set(["JD_E2E_GPU_ENABLED", "JD_E2E_USER"])
@pytest.mark.usefixtures("gpu_pool_required")
def test_ui_created_gpu_workspace_runs_cuda_notebook(
    e2e_deployment: EndToEndDeployment,
    dex_oauth_web_app: WebAppNavigator,
) -> None:
    """UI critical path: create from the GPU template card, await, open, torch sees CUDA."""
    e2e_deployment.ensure_deployed()

    name = dex_oauth_web_app.create_workspace_from_template(GPU_TEMPLATE_DISPLAY_NAME)
    try:
        # First start provisions a node and pulls the image; allow minutes.
        dex_oauth_web_app.wait_for_running(timeout=600000)

        dex_oauth_web_app.goto_workspace_list()
        dex_oauth_web_app.open_workspace_from_card(name)
        dex_oauth_web_app.verify_jupyterlab_loaded()

        e2e_deployment.cli.wait_for_workspace_pod_exec_ready(name)
        server_path = upload_notebook(
            e2e_deployment,
            NOTEBOOKS_DIR / "gpu_check.ipynb",
            "e2e-test/gpu_check.ipynb",
            name=name,
            scope=WORKSPACE_NAMESPACE,
        )
        # torch pulls ~2.5 GiB of CUDA wheels; long timeout, slow poll.
        run_notebook_in_jupyterlab(dex_oauth_web_app.page, server_path, timeout_ms=300000, poll_interval_ms=5000)
        delete_notebook(e2e_deployment, server_path, name=name, scope=WORKSPACE_NAMESPACE)
    finally:
        # UI deletion is covered in test_web_app; deleting via kubectl avoids the duplicate.
        kubectl_delete_workspace(name)


@pytest.mark.order(ORDER_GPU + 4)
@skip_if_testvars_not_set(["JD_E2E_GPU_ENABLED"])
@pytest.mark.usefixtures("gpu_pool_required")
def test_gpu_pool_scales_to_zero_after_workspace_deletion(e2e_deployment: EndToEndDeployment) -> None:
    """With every GPU workspace deleted, the pool releases its nodes back to zero."""
    e2e_deployment.ensure_deployed()

    poll(
        lambda: _gpu_node_count() == 0,
        timeout_s=600,
        msg="gpu NodePool did not scale to zero after workspace deletion",
    )


@pytest.mark.order(ORDER_GPU + 5)
@skip_if_testvars_not_set(["JD_E2E_GPU_ENABLED"])
@pytest.mark.usefixtures("gpu_pool_required")
def test_disable_gpu_pool_deletes_nodepool_and_ec2nodeclass(e2e_deployment: EndToEndDeployment) -> None:
    """Disabling the flag drains the nodes and fully deletes the pool (#349).

    The workspace-gpu NodePool and EC2NodeClass deletions must complete instead
    of hanging on the Karpenter termination finalizers.
    """
    e2e_deployment.ensure_deployed()

    _apply_gpu_pool_flag(e2e_deployment, False)
    poll(
        lambda: _gpu_node_count() == 0,
        timeout_s=300,
        msg="gpu nodes did not drain after disabling the pool",
    )
    poll(
        lambda: resource_absent("nodepools.karpenter.sh", GPU_NODEPOOL),
        timeout_s=POOL_REMOVAL_TIMEOUT_S,
        msg="workspace-gpu NodePool was not deleted after disabling the pool",
    )
    poll(
        lambda: resource_absent("ec2nodeclasses.karpenter.k8s.aws", GPU_EC2NODECLASS),
        timeout_s=POOL_REMOVAL_TIMEOUT_S,
        msg="workspace-gpu EC2NodeClass was not deleted (stuck termination finalizer, #349)",
    )
