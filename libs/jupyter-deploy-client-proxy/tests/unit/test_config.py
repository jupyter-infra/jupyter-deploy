import unittest

from pydantic import ValidationError

from jupyter_deploy_client_proxy.constants import DEFAULT_REFRESH_MARGIN_SECONDS
from jupyter_deploy_client_proxy.server.config import JupyterDeployClientProxyConfig


class TestJupyterDeployClientProxyConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        config = JupyterDeployClientProxyConfig(token_argv=["jd", "proxy", "connect-info"])
        self.assertEqual(config.listen_host, "127.0.0.1")
        self.assertEqual(config.listen_port, 0)
        self.assertEqual(config.refresh_margin_seconds, DEFAULT_REFRESH_MARGIN_SECONDS)
        self.assertIsNone(config.ca_cert_override)

    def test_overrides(self) -> None:
        config = JupyterDeployClientProxyConfig(
            token_argv=["cat", "b.json"], listen_port=8080, refresh_margin_seconds=30, ca_cert_override="PEM"
        )
        self.assertEqual(config.listen_port, 8080)
        self.assertEqual(config.refresh_margin_seconds, 30.0)
        self.assertEqual(config.ca_cert_override, "PEM")

    def test_rejects_empty_token_argv(self) -> None:
        with self.assertRaises(ValidationError):
            JupyterDeployClientProxyConfig(token_argv=[])

    def test_rejects_out_of_range_port(self) -> None:
        with self.assertRaises(ValidationError):
            JupyterDeployClientProxyConfig(token_argv=["x"], listen_port=70000)

    def test_rejects_nonpositive_timeout(self) -> None:
        with self.assertRaises(ValidationError):
            JupyterDeployClientProxyConfig(token_argv=["x"], token_command_timeout_seconds=0)
