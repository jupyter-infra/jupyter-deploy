import subprocess

from jupyter_deploy import cmd_utils
from jupyter_deploy.exceptions import InstructionError, InvalidKubernetesClusterTargetError


def verify_kubeconfig_context(expected_cluster_config: str | None, kubeconfig_path: str | None = None) -> None:
    """Guard against acting on the wrong cluster before shelling out to kubectl/helm.

    The in-memory Kubernetes client is auth-pinned to a specific cluster, but `kubectl`
    and `helm` subprocesses trust whatever the kubeconfig's current-context points at.
    When a command declares an `expected_cluster_config` argument (e.g. the cluster ARN,
    which `aws eks update-kubeconfig` uses as the context name), this asserts the active
    context matches it exactly before the subprocess runs.

    When `expected_cluster_config` is empty/None the check is skipped — commands that do
    not declare it keep their previous behavior (backward compatible).

    Raises:
        InvalidKubernetesClusterTargetError: If the active context does not match the expected cluster.
        InstructionError: If the current context cannot be read.
    """
    if not expected_cluster_config:
        return

    cmds = ["kubectl", "config", "current-context"]
    if kubeconfig_path:
        cmds += ["--kubeconfig", kubeconfig_path]

    try:
        current_context = cmd_utils.run_cmd_and_capture_output(cmds).strip()
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else ""
        raise InstructionError(
            f"Could not read the current kubectl context to verify the target cluster: {stderr}"
        ) from None

    if current_context != expected_cluster_config:
        raise InvalidKubernetesClusterTargetError(
            current_context=current_context, expected_cluster_config=expected_cluster_config
        )
