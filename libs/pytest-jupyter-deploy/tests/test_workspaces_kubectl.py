"""Unit tests for the workspaces.kubectl pod lookup, connection request and template-wide deletion."""

import json
import subprocess
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from pytest_jupyter_deploy.workspaces.kubectl import (
    kubectl_delete_workspaces_of_templates,
    kubectl_get_workspace_pod,
    kubectl_request_workspace_connection,
)

_RESPONSE = {"status": {"workspaceConnectionUrl": "wss://example.test/workspaces/team-a/ws1/ssh-ws?token=t"}}


def _kubectl_json(payload: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps(payload), stderr="")


class TestKubectlGetWorkspacePod(unittest.TestCase):
    @patch("pytest_jupyter_deploy.workspaces.kubectl.run_kubectl")
    def test_returns_the_pod_carrying_the_workspace_label(self, mock_run_kubectl: Mock) -> None:
        pod = {"metadata": {"name": "workspace-ws1-abc"}, "status": {"containerStatuses": []}}
        mock_run_kubectl.return_value = _kubectl_json({"items": [pod]})

        self.assertEqual(kubectl_get_workspace_pod("ws1", "team-a"), pod)
        self.assertEqual(
            mock_run_kubectl.call_args.args,
            ("get", "pods", "-n", "team-a", "-l", "workspace.jupyter.org/workspace-name=ws1", "-o", "json"),
        )
        self.assertTrue(mock_run_kubectl.call_args.kwargs["check"])

    @patch("pytest_jupyter_deploy.workspaces.kubectl.run_kubectl")
    def test_skips_the_pod_being_replaced(self, mock_run_kubectl: Mock) -> None:
        terminating = {"metadata": {"name": "workspace-ws1-old", "deletionTimestamp": "2026-11-17T00:00:00Z"}}
        live = {"metadata": {"name": "workspace-ws1-new"}}
        mock_run_kubectl.return_value = _kubectl_json({"items": [terminating, live]})

        self.assertEqual(kubectl_get_workspace_pod("ws1"), live)

    @patch("pytest_jupyter_deploy.workspaces.kubectl.run_kubectl")
    def test_raises_when_no_live_pod_carries_the_label(self, mock_run_kubectl: Mock) -> None:
        terminating = {"metadata": {"name": "workspace-ws1-old", "deletionTimestamp": "2026-11-17T00:00:00Z"}}
        mock_run_kubectl.return_value = _kubectl_json({"items": [terminating]})

        with self.assertRaises(LookupError):
            kubectl_get_workspace_pod("ws1")


class TestKubectlRequestWorkspaceConnection(unittest.TestCase):
    @patch("pytest_jupyter_deploy.workspaces.kubectl.run_kubectl")
    def test_posts_the_request_to_the_extension_api_and_returns_the_answer(self, mock_run_kubectl: Mock) -> None:
        bodies: list[dict[str, Any]] = []

        def capture(*args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            # The body file lives only for the call.
            bodies.append(json.loads(Path(args[args.index("-f") + 1]).read_text()))
            return _kubectl_json(_RESPONSE)

        mock_run_kubectl.side_effect = capture
        out = kubectl_request_workspace_connection(
            "ws1", "team-a", as_user="github:alice", as_groups=["github:org:team-a"]
        )

        self.assertEqual(out, _RESPONSE)
        self.assertEqual(
            mock_run_kubectl.call_args.args[:3],
            (
                "create",
                "--raw",
                "/apis/connection.workspace.jupyter.org/v1alpha1/namespaces/team-a/workspaceconnections",
            ),
        )
        self.assertEqual(
            bodies,
            [
                {
                    "apiVersion": "connection.workspace.jupyter.org/v1alpha1",
                    "kind": "WorkspaceConnection",
                    "metadata": {"namespace": "team-a"},
                    "spec": {"workspaceName": "ws1", "workspaceConnectionType": "ssh-over-websocket"},
                }
            ],
        )
        self.assertEqual(mock_run_kubectl.call_args.kwargs["as_user"], "github:alice")
        self.assertEqual(mock_run_kubectl.call_args.kwargs["as_groups"], ["github:org:team-a"])
        self.assertTrue(mock_run_kubectl.call_args.kwargs["check"])


class TestKubectlDeleteWorkspacesOfTemplates(unittest.TestCase):
    @patch("pytest_jupyter_deploy.workspaces.kubectl.run_kubectl")
    def test_selects_the_workspaces_by_their_template_label(self, mock_run_kubectl: Mock) -> None:
        kubectl_delete_workspaces_of_templates(["vscode", "e2e-vscode-small"], "team-a")

        self.assertEqual(
            mock_run_kubectl.call_args.args,
            (
                "delete",
                "workspaces",
                "-n",
                "team-a",
                "-l",
                "workspace.jupyter.org/template-name in (vscode,e2e-vscode-small)",
            ),
        )
        self.assertTrue(mock_run_kubectl.call_args.kwargs["check"])

    @patch("pytest_jupyter_deploy.workspaces.kubectl.run_kubectl")
    def test_deletes_nothing_for_no_templates(self, mock_run_kubectl: Mock) -> None:
        kubectl_delete_workspaces_of_templates([], "team-a")

        mock_run_kubectl.assert_not_called()
