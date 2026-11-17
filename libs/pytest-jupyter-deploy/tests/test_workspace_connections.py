"""Unit tests for the workspaces.kubectl connection request."""

import json
import subprocess
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from pytest_jupyter_deploy.workspaces.kubectl import kubectl_request_workspace_connection

_RESPONSE = {"status": {"workspaceConnectionUrl": "wss://example.test/workspaces/team-a/ws1/ssh-ws?token=t"}}


class TestKubectlRequestWorkspaceConnection(unittest.TestCase):
    @patch("pytest_jupyter_deploy.workspaces.kubectl.run_kubectl")
    def test_posts_the_request_to_the_extension_api_and_returns_the_answer(self, mock_run_kubectl: Mock) -> None:
        bodies: list[dict[str, Any]] = []

        def capture(*args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            # The body file lives only for the call.
            bodies.append(json.loads(Path(args[args.index("-f") + 1]).read_text()))
            return subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps(_RESPONSE), stderr="")

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
