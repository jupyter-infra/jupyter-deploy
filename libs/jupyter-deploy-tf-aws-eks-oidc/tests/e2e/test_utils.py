"""Shared utilities for the EKS OIDC template E2E suite."""

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
from pytest_jupyter_deploy.workspaces.kubectl import (
    kubectl_apply_workspace,
    kubectl_delete_workspace,
    kubectl_get_workspace_access_url,
)

from .conftest import WORKSPACE_NAMESPACE, WORKSPACES_DIR

NOTEBOOKS_DIR = Path(__file__).parent / "notebooks"

GPU_WORKSPACE = "e2e-gpu-workspace"
GPU_ROLE = "workspaces-gpu"
GPU_ROLE_SELECTOR = f"jupyter-deploy/role={GPU_ROLE}"
GPU_NODEPOOL = "workspace-gpu"
# The karpenter-nodepools chart names each pool's EC2NodeClass after the pool.
GPU_EC2NODECLASS = GPU_NODEPOOL


def kubectl_stdout(*args: str) -> str:
    result = subprocess.run(["kubectl", *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def poll(condition: Callable[[], bool], timeout_s: int, interval_s: int = 5, msg: str = "") -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if condition():
            return
        time.sleep(interval_s)
    raise TimeoutError(f"Condition not met within {timeout_s}s: {msg}")


def karpenter_resource_absent(resource: str, name: str) -> bool:
    """True once the named cluster resource no longer exists.

    Only a NotFound error counts as absent: treating any kubectl failure as
    absence would let a lost cluster connection pass a deletion assertion.
    """
    result = subprocess.run(["kubectl", "get", resource, name], capture_output=True, text=True, check=False)
    if result.returncode == 0:
        return False
    if "NotFound" in result.stderr:
        return True
    raise RuntimeError(f"kubectl get {resource} {name} failed: {result.stderr.strip()}")


def gpu_pool_deployed() -> bool:
    """True when the cluster currently has the workspace-gpu NodePool."""
    return not karpenter_resource_absent("nodepools.karpenter.sh", GPU_NODEPOOL)


def require_gpu_pool() -> None:
    """Skip the calling test unless the deployment currently has the GPU pool.

    JD_E2E_GPU_ENABLED alone does not imply the pool exists: CI runs set it
    against deployments with enable_default_gpu_pool off, and the pool
    lifecycle test enables the pool itself.
    """
    if not gpu_pool_deployed():
        pytest.skip("Deployment does not have the workspace-gpu NodePool (enable_default_gpu_pool off)")


def gpu_node_count() -> int:
    return len(get_node_names(GPU_ROLE_SELECTOR))


def verify_gpu_pool_listed(e2e_deployment: EndToEndDeployment) -> None:
    """jd pool list must surface the synthesized workspace-gpu NodePool."""
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "pool", "list"])
    assert GPU_NODEPOOL in result.stdout, f"Expected pool '{GPU_NODEPOOL}' in pool list output:\n{result.stdout}"


def verify_nvidia_device_plugin_daemonset() -> None:
    """The device-plugin DaemonSet must exist once a GPU pool is configured."""
    # check=False: with check=True an absent daemonset dies as CalledProcessError
    # before the assertion below can surface stdout/stderr in the test report.
    result = subprocess.run(
        ["kubectl", "get", "daemonset", "nvidia-device-plugin", "-n", "kube-system", "-o", "jsonpath={.metadata.name}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.strip() == "nvidia-device-plugin", (
        f"device plugin daemonset missing: {result.stdout} {result.stderr}"
    )


def verify_gpu_workspace_provisioning_and_scale_to_zero(e2e_deployment: EndToEndDeployment) -> None:
    """Run the GPU workspace lifecycle against a deployment with the GPU pool.

    Creates a jupyterlab-gpu workspace, verifies Karpenter provisions a fenced
    workspace-gpu node with a visible device (nvidia.com/gpu allocatable and
    nvidia-smi in the container), then deletes the workspace and waits for the
    pool to scale back to zero.
    """
    e2e_deployment.ensure_deployed()

    # Clean up any leftover workspace from a previous test run.
    try:
        kubectl_delete_workspace(GPU_WORKSPACE)
        poll(
            lambda: gpu_node_count() == 0,
            timeout_s=300,
            msg="pre-test cleanup: gpu node did not terminate",
        )
    except Exception:
        pass

    kubectl_apply_workspace(GPU_WORKSPACE, WORKSPACES_DIR)
    try:
        # First start provisions a node and pulls the image: minutes, not seconds.
        e2e_deployment.cli.poll_scoped_server_status(GPU_WORKSPACE, "Running", timeout_s=600)

        assert gpu_node_count() > 0, "Expected at least one gpu node after workspace creation"

        pod_node = kubectl_stdout(
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

        node_role = kubectl_stdout("get", "node", pod_node, "-o", "jsonpath={.metadata.labels.jupyter-deploy/role}")
        assert node_role == GPU_ROLE, f"GPU workspace pod landed on node with role '{node_role}', expected '{GPU_ROLE}'"

        nodepool = kubectl_stdout("get", "node", pod_node, "-o", r"jsonpath={.metadata.labels.karpenter\.sh/nodepool}")
        assert nodepool == GPU_NODEPOOL, f"GPU pod node has nodepool '{nodepool}', expected '{GPU_NODEPOOL}'"

        gpu_present = kubectl_stdout(
            "get", "node", pod_node, "-o", r"jsonpath={.metadata.labels.nvidia\.com/gpu\.present}"
        )
        assert gpu_present == "true", f"GPU node lacks the nvidia.com/gpu.present label (got '{gpu_present}')"

        taints = kubectl_stdout("get", "node", pod_node, "-o", "jsonpath={.spec.taints}")
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

    poll(
        lambda: gpu_node_count() == 0,
        timeout_s=600,
        msg="gpu NodePool did not scale to zero after workspace deletion",
    )


def verify_gpu_workspace_kernel_sees_cuda(
    e2e_deployment: EndToEndDeployment,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> None:
    """Run the gpu_check notebook through the JupyterLab UI on a GPU workspace.

    nvidia-smi, torch installed at test time via uv (the stock image ships no
    CUDA userland; the CUDA-enabled wheel comes from the torch package itself),
    then torch.cuda.is_available from the kernel. Deletes the workspace and
    waits for the GPU pool to scale back to zero.
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

    poll(
        lambda: gpu_node_count() == 0,
        timeout_s=600,
        msg="gpu NodePool did not scale to zero after workspace deletion",
    )
