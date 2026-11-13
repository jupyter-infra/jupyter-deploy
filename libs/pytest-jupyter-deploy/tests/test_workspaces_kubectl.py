"""Unit tests for the Workspace pod lookup."""

import json
import subprocess
from unittest.mock import MagicMock, patch

from pytest_jupyter_deploy.workspaces.kubectl import kubectl_list_workspace_pods

LIVE_POD = {"metadata": {"name": "ws1-7d9f"}, "spec": {"nodeName": "node-a"}}
TERMINATING_POD = {"metadata": {"name": "ws1-2c4e", "deletionTimestamp": "2026-10-12T15:00:00Z"}, "spec": {}}


def _completed(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


@patch("pytest_jupyter_deploy.kubernetes.kubectl.subprocess.run")
def test_list_workspace_pods_returns_live_pods_only(mock_run: MagicMock) -> None:
    mock_run.return_value = _completed(json.dumps({"items": [TERMINATING_POD, LIVE_POD]}))

    pods = kubectl_list_workspace_pods("ws1", "team-a")

    assert pods == [LIVE_POD]
    assert mock_run.call_args.args[0] == [
        "kubectl",
        "get",
        "pods",
        "-n",
        "team-a",
        "-l",
        "workspace.jupyter.org/workspace-name=ws1",
        "-o",
        "json",
    ]


@patch("pytest_jupyter_deploy.kubernetes.kubectl.subprocess.run")
def test_list_workspace_pods_is_empty_without_pods(mock_run: MagicMock) -> None:
    mock_run.return_value = _completed(json.dumps({"items": []}))

    assert kubectl_list_workspace_pods("ws1") == []
