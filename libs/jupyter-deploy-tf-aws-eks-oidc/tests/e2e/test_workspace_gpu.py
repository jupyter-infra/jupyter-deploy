"""E2E test for the GPU workspace journey on the EKS OIDC template.

Requires a deployment with enable_default_gpu_pool: true (and G/VT on-demand quota in
the account); gated on JD_E2E_GPU_ENABLED so every other run skips.
"""

import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.kubernetes.nodes import (
    get_node_allocatable_gpu_count,
    get_node_names,
)
from pytest_jupyter_deploy.notebook import delete_notebook, run_notebook_in_jupyterlab, upload_notebook
from pytest_jupyter_deploy.oauth2_proxy.dex import DexGitHubOAuth2ProxyApplication
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.workspaces.kubectl import (
    kubectl_apply_workspace,
    kubectl_delete_workspace,
    kubectl_get_workspace_access_url,
)

from .conftest import WORKSPACES_DIR

NOTEBOOKS_DIR = Path(__file__).parent / "notebooks"

WORKSPACE_NAMESPACE = "default"
GPU_WORKSPACE = "e2e-gpu-workspace"
GPU_ROLE = "workspaces-gpu"
GPU_ROLE_SELECTOR = f"jupyter-deploy/role={GPU_ROLE}"
GPU_NODEPOOL = "workspace-gpu"


def _kubectl(*args: str) -> str:
    result = subprocess.run(["kubectl", *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _poll(condition: "Callable[[], bool]", timeout_s: int, interval_s: int = 5, msg: str = "") -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if condition():
            return
        time.sleep(interval_s)
    raise TimeoutError(f"Condition not met within {timeout_s}s: {msg}")


def _gpu_node_count() -> int:
    return len(get_node_names(GPU_ROLE_SELECTOR))


@skip_if_testvars_not_set(["JD_E2E_GPU_ENABLED"])
@pytest.mark.mutating
@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_gpu_workspace_provisioning_nvidia_smi_and_scale_to_zero(e2e_deployment: EndToEndDeployment) -> None:
    """Full GPU workspace lifecycle: fenced provisioning, a visible device, scale-to-zero.

    1. Create a workspace from the jupyterlab-gpu template
    2. Karpenter provisions a workspace-gpu node (role label + taint + gpu.present)
    3. The device plugin advertises nvidia.com/gpu and nvidia-smi sees the device
    4. Delete → the GPU pool scales back to zero
    """
    e2e_deployment.ensure_deployed()

    # Clean up any leftover workspace from a previous test run.
    try:
        kubectl_delete_workspace(GPU_WORKSPACE)
        _poll(
            lambda: _gpu_node_count() == 0,
            timeout_s=300,
            msg="pre-test cleanup: gpu node did not terminate",
        )
    except Exception:
        pass

    kubectl_apply_workspace(GPU_WORKSPACE, WORKSPACES_DIR)
    try:
        # First start provisions a node and pulls the image: minutes, not seconds.
        e2e_deployment.cli.poll_scoped_server_status(GPU_WORKSPACE, "Running", timeout_s=600)

        assert _gpu_node_count() > 0, "Expected at least one gpu node after workspace creation"

        pod_node = _kubectl(
            "get",
            "pods",
            "-n",
            WORKSPACE_NAMESPACE,
            "-l",
            f"workspace.jupyter.org/workspace-name={GPU_WORKSPACE}",
            "-o",
            "jsonpath={.items[0].spec.nodeName}",
        )
        assert pod_node, f"Could not find pod node for workspace {GPU_WORKSPACE}"

        node_role = _kubectl("get", "node", pod_node, "-o", "jsonpath={.metadata.labels.jupyter-deploy/role}")
        assert node_role == GPU_ROLE, f"GPU workspace pod landed on node with role '{node_role}', expected '{GPU_ROLE}'"

        nodepool = _kubectl("get", "node", pod_node, "-o", r"jsonpath={.metadata.labels.karpenter\.sh/nodepool}")
        assert nodepool == GPU_NODEPOOL, f"GPU pod node has nodepool '{nodepool}', expected '{GPU_NODEPOOL}'"

        gpu_present = _kubectl("get", "node", pod_node, "-o", r"jsonpath={.metadata.labels.nvidia\.com/gpu\.present}")
        assert gpu_present == "true", f"GPU node lacks the nvidia.com/gpu.present label (got '{gpu_present}')"

        taints = _kubectl("get", "node", pod_node, "-o", "jsonpath={.spec.taints}")
        assert GPU_ROLE in taints, f"GPU node is not tainted with the {GPU_ROLE} role (taints: {taints})"

        assert get_node_allocatable_gpu_count(pod_node) >= 1, (
            "Device plugin did not register nvidia.com/gpu on the node"
        )

        e2e_deployment.cli.wait_for_workspace_pod_exec_ready(GPU_WORKSPACE)
        result = e2e_deployment.cli.run_exec_with_retry(
            ["jupyter-deploy", "server", "exec", "--name", GPU_WORKSPACE, "--", "nvidia-smi"]
        )
        assert "NVIDIA-SMI" in result.stdout, f"nvidia-smi did not see a device:\n{result.stdout}"
    finally:
        kubectl_delete_workspace(GPU_WORKSPACE)

    _poll(
        lambda: _gpu_node_count() == 0,
        timeout_s=600,
        msg="gpu NodePool did not scale to zero after workspace deletion",
    )


@skip_if_testvars_not_set(["JD_E2E_GPU_ENABLED", "JD_E2E_USER"])
@pytest.mark.mutating
@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_gpu_workspace_kernel_sees_cuda(
    e2e_deployment: EndToEndDeployment,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> None:
    """The notebook kernel can install torch and use CUDA on a GPU workspace.

    Runs the gpu_check notebook through the JupyterLab UI, mirroring the
    ec2-base precedent: nvidia-smi, torch installed at test time via uv (the
    stock image ships no CUDA userland; the CUDA-enabled wheel comes from the
    torch package itself), then torch.cuda.is_available from the kernel.
    Targets the built-in g-family pool. No torch cleanup is needed: the
    workspace and its volume are deleted at the end of the test.
    """
    e2e_deployment.ensure_deployed()

    kubectl_apply_workspace(GPU_WORKSPACE, WORKSPACES_DIR)
    try:
        # First start provisions a node and pulls the image: minutes, not seconds.
        e2e_deployment.cli.poll_scoped_server_status(GPU_WORKSPACE, "Running", timeout_s=600)
        e2e_deployment.cli.wait_for_workspace_pod_exec_ready(GPU_WORKSPACE)

        access_url = kubectl_get_workspace_access_url(GPU_WORKSPACE, WORKSPACE_NAMESPACE)
        dex_oauth_app.verify_workspace_accessible(access_url)

        notebook_path = NOTEBOOKS_DIR / "gpu_check.ipynb"
        server_path = upload_notebook(
            e2e_deployment,
            notebook_path,
            "e2e-test/gpu_check.ipynb",
            name=GPU_WORKSPACE,
            scope=WORKSPACE_NAMESPACE,
        )

        # torch pulls ~2.5 GiB of CUDA wheels; long timeout, slow poll.
        run_notebook_in_jupyterlab(dex_oauth_app.page, server_path, timeout_ms=300000, poll_interval_ms=5000)

        delete_notebook(e2e_deployment, server_path, name=GPU_WORKSPACE, scope=WORKSPACE_NAMESPACE)
    finally:
        kubectl_delete_workspace(GPU_WORKSPACE)

    _poll(
        lambda: _gpu_node_count() == 0,
        timeout_s=600,
        msg="gpu NodePool did not scale to zero after workspace deletion",
    )
