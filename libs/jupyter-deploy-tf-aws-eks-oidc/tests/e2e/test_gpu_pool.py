"""E2E test for the enable_default_gpu_pool on/off lifecycle on the EKS OIDC template.

Unlike test_workspace_gpu.py, this does not need a GPU-enabled deployment: it
turns the flag on itself (jd config + jd up), runs the GPU verifications while
the pool exists, turns the flag off, and verifies the pool tears down cleanly.
Restores the flag to its original value on any failure.
"""

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.oauth2_proxy.dex import DexGitHubOAuth2ProxyApplication
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set

from .test_utils import (
    GPU_EC2NODECLASS,
    GPU_NODEPOOL,
    gpu_node_count,
    gpu_pool_deployed,
    karpenter_resource_absent,
    poll,
    verify_gpu_pool_listed,
    verify_gpu_workspace_kernel_sees_cuda,
    verify_gpu_workspace_provisioning_and_scale_to_zero,
    verify_nvidia_device_plugin_daemonset,
)

GPU_POOL_FLAG = "enable_default_gpu_pool"

# Bound for the Karpenter termination finalizers to clear after the flag-off
# apply; #349's stuck finalizer never clears, so a timeout is the regression.
POOL_REMOVAL_TIMEOUT_S = 600


def _gpu_pool_flag(e2e_deployment: EndToEndDeployment) -> bool:
    return bool(e2e_deployment.read_override_value(GPU_POOL_FLAG))


def _apply_gpu_pool_flag(e2e_deployment: EndToEndDeployment, enabled: bool) -> None:
    """Record the flag in variables.yaml, then apply with jd config + jd up.

    jd config exposes the variable only as a set-true flag (typer generates no
    --no- form for explicitly named bool options), so both directions go
    through the variables.yaml override.
    """
    e2e_deployment.update_override_value(GPU_POOL_FLAG, enabled)
    e2e_deployment.ensure_deployed_with([])


@skip_if_testvars_not_set(["JD_E2E_GPU_ENABLED", "JD_E2E_USER"])
@pytest.mark.mutating
@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_gpu_pool_enable_disable_drains_and_deletes_cleanly(
    e2e_deployment: EndToEndDeployment,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> None:
    """Flag on → GPU surface, workspace lifecycle, kernel CUDA → flag off → pool fully deleted.

    While the pool exists, runs the GPU verifications that otherwise require a
    GPU-enabled deployment: pool listed, device-plugin DaemonSet, the workspace
    lifecycle, and the torch/CUDA notebook. The flag-off half is the #349
    regression check: the workspace-gpu NodePool and EC2NodeClass deletions
    must complete instead of hanging on the Karpenter termination finalizers.
    """
    e2e_deployment.ensure_deployed()
    original = _gpu_pool_flag(e2e_deployment)

    try:
        _apply_gpu_pool_flag(e2e_deployment, True)
        assert gpu_pool_deployed(), "workspace-gpu NodePool missing after enabling enable_default_gpu_pool"
        verify_gpu_pool_listed(e2e_deployment)
        verify_nvidia_device_plugin_daemonset()

        verify_gpu_workspace_provisioning_and_scale_to_zero(e2e_deployment)
        verify_gpu_workspace_kernel_sees_cuda(e2e_deployment, dex_oauth_app)

        _apply_gpu_pool_flag(e2e_deployment, False)
        poll(
            lambda: gpu_node_count() == 0,
            timeout_s=300,
            msg="gpu nodes did not drain after disabling the pool",
        )
        poll(
            lambda: karpenter_resource_absent("nodepools.karpenter.sh", GPU_NODEPOOL),
            timeout_s=POOL_REMOVAL_TIMEOUT_S,
            msg="workspace-gpu NodePool was not deleted after disabling the pool",
        )
        poll(
            lambda: karpenter_resource_absent("ec2nodeclasses.karpenter.k8s.aws", GPU_EC2NODECLASS),
            timeout_s=POOL_REMOVAL_TIMEOUT_S,
            msg="workspace-gpu EC2NodeClass was not deleted (stuck termination finalizer, #349)",
        )
    finally:
        if _gpu_pool_flag(e2e_deployment) != original:
            _apply_gpu_pool_flag(e2e_deployment, original)
