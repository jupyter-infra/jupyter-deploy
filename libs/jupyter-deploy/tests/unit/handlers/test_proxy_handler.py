import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.exceptions import CommandNotImplementedError
from jupyter_deploy.handlers.payloads import ProxyConnectBundle, ProxyStatus
from jupyter_deploy.handlers.proxy_handler import ProxyHandler
from jupyter_deploy.manifest import JupyterDeployManifestV1
from jupyter_deploy.proxy.proxy_manager import ProxyManager


def _make_manifest(with_connect_info: bool = True) -> JupyterDeployManifestV1:
    commands = []
    if with_connect_info:
        commands.append(
            {
                "cmd": "proxy.connect-info",
                "sequence": [
                    {
                        "api-name": "aws.ec2.resolve-endpoint",
                        "arguments": [
                            {"api-attribute": "instance_id", "source": "output", "source-key": "iid"},
                            {"api-attribute": "port", "source": "literal", "value": "443"},
                        ],
                    },
                    {
                        "api-name": "aws.ssm.get-parameter",
                        "arguments": [{"api-attribute": "name", "source": "output", "source-key": "cert_pin"}],
                    },
                    {
                        "api-name": "aws.sts.mint-connect-token",
                        "arguments": [{"api-attribute": "binding_id", "source": "output", "source-key": "dep_id"}],
                    },
                ],
                "results": [
                    {"result-name": "proxy.connect-info.host", "source": "result", "source-key": "[0].PublicIpAddress"},
                    {"result-name": "proxy.connect-info.port", "source": "result", "source-key": "[0].Port"},
                    {"result-name": "proxy.connect-info.ca_cert", "source": "result", "source-key": "[1].Value"},
                    {"result-name": "proxy.connect-info.headers", "source": "result", "source-key": "[2].Headers"},
                    {"result-name": "proxy.connect-info.expires_at", "source": "result", "source-key": "[2].ExpiresAt"},
                ],
            }
        )
    return JupyterDeployManifestV1(
        **{  # type: ignore
            "schema_version": 1,
            "template": {"name": "aws-ec2-jupyterlab", "engine": "terraform", "version": "0.1.0"},
            "values": [],
            "commands": commands,
        }
    )


def _make_handler(manifest: JupyterDeployManifestV1 | None = None) -> ProxyHandler:
    with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve:
        mock_retrieve.return_value = manifest or _make_manifest()
        return ProxyHandler()


class TestProxyHandlerInit(unittest.TestCase):
    def test_init_wires_terraform_handlers_and_manager(self) -> None:
        handler = _make_handler()
        self.assertIsNotNone(handler._outputs_handler)
        self.assertIsNotNone(handler._variable_handler)
        self.assertIsNotNone(handler._manager)

    def test_init_raises_when_template_lacks_proxy_support(self) -> None:
        # No `proxy.connect-info` command -> the template does not support the proxy, so every
        # `jd proxy` command fails fast (uniformly) at handler construction.
        with self.assertRaises(CommandNotImplementedError):
            _make_handler(_make_manifest(with_connect_info=False))


class TestGetConnectBundle(unittest.TestCase):
    def test_runs_command_and_maps_results(self) -> None:
        handler = _make_handler()

        collected = {
            "host": "203.0.113.7",
            "port": 443,
            "ca_cert": "-----BEGIN CERTIFICATE-----\nPEM\n",
            "headers": {"Authorization": "Bearer k8s-aws-v1.xxx", "x-k8s-aws-id": "dep-abc"},
            "expires_at": "2026-06-10T18:01:00Z",
        }
        with (
            patch("jupyter_deploy.handlers.proxy_handler.cmd_runner.ManifestCommandRunner") as mock_runner_cls,
            patch("jupyter_deploy.handlers.proxy_handler.collect_results", return_value=collected),
        ):
            mock_runner = Mock()
            mock_runner_cls.return_value = mock_runner

            bundle = handler.get_connect_bundle()

            mock_runner.run_command_sequence.assert_called_once()
            self.assertEqual(
                bundle,
                ProxyConnectBundle(
                    host="203.0.113.7",
                    port=443,
                    ca_cert="-----BEGIN CERTIFICATE-----\nPEM\n",
                    headers={"Authorization": "Bearer k8s-aws-v1.xxx", "x-k8s-aws-id": "dep-abc"},
                    expires_at="2026-06-10T18:01:00Z",
                ),
            )

    def test_non_dict_headers_coerced_to_empty(self) -> None:
        handler = _make_handler()
        with (
            patch("jupyter_deploy.handlers.proxy_handler.cmd_runner.ManifestCommandRunner"),
            patch(
                "jupyter_deploy.handlers.proxy_handler.collect_results",
                return_value={"host": "h", "port": 443, "ca_cert": "c", "headers": "oops", "expires_at": "t"},
            ),
        ):
            bundle = handler.get_connect_bundle()
            self.assertEqual(bundle.headers, {})


class TestLifecycleDelegation(unittest.TestCase):
    """Lifecycle is delegated to a *private* ProxyManager — callers use the handler's own verbs."""

    def test_manager_is_private_not_public(self) -> None:
        handler = _make_handler()
        self.assertIsInstance(handler._manager, ProxyManager)
        # The manager is an implementation detail — not exposed on the handler's surface.
        self.assertFalse(hasattr(handler, "manager"))

    def test_delegates_all_lifecycle_verbs_to_manager(self) -> None:
        handler = _make_handler()
        manager = Mock()
        handler._manager = manager

        listening = ProxyStatus(state="running", pid=1, alive=True, port=51000, running=True)
        manager.start.return_value = listening
        manager.open.return_value = "http://127.0.0.1:51000/lab"
        manager.stop.return_value = [1]
        manager.status.return_value = "running"
        manager.show.return_value = listening

        self.assertIs(handler.start(detached=True), listening)
        manager.start.assert_called_once_with(detached=True)

        self.assertEqual(handler.open(path="/lab"), "http://127.0.0.1:51000/lab")
        manager.open.assert_called_once_with(path="/lab")

        self.assertEqual(handler.stop(), [1])
        manager.stop.assert_called_once_with()

        self.assertEqual(handler.status(), "running")
        manager.status.assert_called_once_with()

        self.assertIs(handler.show(), listening)
        manager.show.assert_called_once_with()

    def test_token_command_is_derived_for_the_project(self) -> None:
        # The manager's token command drives `jd proxy connect-info` for this project.
        handler = _make_handler()
        token_command = handler._manager._token_command
        self.assertIn("jupyter_deploy.cli.app", token_command)
        self.assertIn("proxy", token_command)
        self.assertIn("connect-info", token_command)
        self.assertIn("--path", token_command)
        # SG-door mode is a deploy-time template setting, not a runtime flag on the proxy.
        self.assertNotIn("--any-ip", token_command)
        self.assertNotIn("--cidr", token_command)
