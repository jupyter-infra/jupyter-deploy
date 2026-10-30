"""E2E tests for scheduled workspace volume snapshots on the EKS OIDC template.

These tests verify that each workspace volume carries a tag an enabled Data Lifecycle
Manager (DLM) policy targets: the condition for DLM to snapshot it. They deliberately
leave the rest of the feature untested:

1. Effective snapshotting: DLM has no on-demand run, its shortest interval is one hour,
   and a run only starts within an hour of its scheduled time. Waiting for the first
   snapshot would take one to two hours after deploy, and timing against the suite's
   own duration would make the test brittle.
2. Reaping on `jd down`: the destroy-time reaper only runs on teardown, and this suite
   has no `jd down` test.
3. Retention count: observing DLM delete the oldest snapshot takes retain_count + 1
   runs, so hours at best, and it exercises DLM's own behavior rather than this
   template's.
"""

import json
import subprocess

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.kubernetes.kubectl import run_kubectl

WORKSPACE_STORAGE_CLASS = "ebs-sc"


def _kubectl_json(*args: str) -> dict:
    result: dict = json.loads(run_kubectl(*args, "-o", "json", check=True).stdout)
    return result


def _aws_json(region: str, *args: str) -> dict:
    cmd = ["aws", *args, "--region", region, "--output", "json"]
    result: dict = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    return result


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_workspace_volumes_are_targeted_by_snapshot_policy(
    e2e_deployment: EndToEndDeployment, e2e_workspace: str, default_workspace_namespace: str
) -> None:
    """Every bound ebs-sc volume in the default workspace namespace has an enabled snapshot policy."""
    region = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "-v", "region", "--text"]).stdout.strip()
    deployment_id = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "show", "-o", "deployment_id", "--text"]
    ).stdout.strip()

    pvcs = _kubectl_json("get", "pvc", "-n", default_workspace_namespace)["items"]
    pv_names = [
        pvc["spec"]["volumeName"]
        for pvc in pvcs
        if pvc["spec"].get("storageClassName") == WORKSPACE_STORAGE_CLASS and pvc["status"].get("phase") == "Bound"
    ]
    assert pv_names, (
        f"No bound {WORKSPACE_STORAGE_CLASS} PVC in {default_workspace_namespace} (expected {e2e_workspace}'s)"
    )

    for pv_name in pv_names:
        volume_id = _kubectl_json("get", "pv", pv_name)["spec"]["csi"]["volumeHandle"]
        volume = _aws_json(region, "ec2", "describe-volumes", "--volume-ids", volume_id)["Volumes"][0]
        tags = {t["Key"]: t["Value"] for t in volume.get("Tags", [])}
        # Snapshots copy their volume's tags, and the `jd down` reaper finds them by DeploymentId.
        assert tags.get("DeploymentId") == deployment_id, (
            f"Volume {volume_id} ({pv_name}) has DeploymentId {tags.get('DeploymentId')!r}, expected {deployment_id!r}"
        )
        targeted = [
            f"{key}={value}"
            for key, value in tags.items()
            if _aws_json(
                region, "dlm", "get-lifecycle-policies", "--state", "ENABLED", "--target-tags", f"{key}={value}"
            )["Policies"]
        ]
        assert targeted, f"Volume {volume_id} ({pv_name}) carries no tag an enabled snapshot policy targets: {tags}"
