import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jupyter_deploy_client_proxy.enums import ProxyState
from jupyter_deploy_client_proxy.exceptions import ProxyError
from jupyter_deploy_client_proxy.server.config import JupyterDeployClientProxyConfig, LogLevel
from jupyter_deploy_client_proxy.server.proxy import JupyterDeployClientProxy


class TestProxyInit(unittest.TestCase):
    def test_builds_logger_from_config(self) -> None:
        config = JupyterDeployClientProxyConfig(
            token_argv=["true"],
            log_dir=Path("/does/not/need/to/exist"),
            log_level=LogLevel.DEBUG,
            log_max_bytes=4242,
            log_backup_count=9,
        )
        with patch("jupyter_deploy_client_proxy.server.proxy.create_logger") as mock_create_logger:
            proxy = JupyterDeployClientProxy(config)
        # __init__ forwards the logging config to create_logger (level as its string value).
        mock_create_logger.assert_called_once_with("DEBUG", config.log_dir, 4242, 9)
        self.assertIs(proxy._config, config)
        self.assertEqual(proxy.state, ProxyState.STARTING)


class TestProxyBeforeStart(unittest.TestCase):
    """Pure-logic guards on the proxy's public API before start() — the branches the
    functional suite never hits (it always starts the proxy)."""

    def _proxy(self) -> JupyterDeployClientProxy:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config = JupyterDeployClientProxyConfig(token_argv=["true"], log_dir=Path(tmp.name))
        return JupyterDeployClientProxy(config)

    def test_initial_state_is_starting(self) -> None:
        self.assertEqual(self._proxy().state, ProxyState.STARTING)

    def test_port_before_start_raises(self) -> None:
        with self.assertRaises(ProxyError):
            _ = self._proxy().port

    def test_current_bundle_before_start_raises(self) -> None:
        with self.assertRaises(ProxyError):
            _ = self._proxy().current_bundle
