"""Unit tests for the kubernetes.services helpers."""

import json
import unittest
from unittest.mock import Mock, patch

from pytest_jupyter_deploy.kubernetes.services import get_service_port


def _service(ports: list[dict]) -> Mock:
    return Mock(stdout=json.dumps({"spec": {"ports": ports}}))


class TestGetServicePort(unittest.TestCase):
    @patch("pytest_jupyter_deploy.kubernetes.services.run_kubectl")
    def test_single_port(self, mock_run: Mock) -> None:
        mock_run.return_value = _service([{"name": "https", "port": 8443}])
        self.assertEqual(get_service_port("web-app", "router"), (8443, "https"))
        mock_run.assert_called_once_with("get", "service", "web-app", "-n", "router", "-o", "json", check=True)

    @patch("pytest_jupyter_deploy.kubernetes.services.run_kubectl")
    def test_unnamed_port(self, mock_run: Mock) -> None:
        mock_run.return_value = _service([{"port": 8090}])
        self.assertEqual(get_service_port("web-app", "router"), (8090, ""))

    @patch("pytest_jupyter_deploy.kubernetes.services.run_kubectl")
    def test_several_ports_raise(self, mock_run: Mock) -> None:
        mock_run.return_value = _service([{"name": "http", "port": 8090}, {"name": "https", "port": 8443}])
        with self.assertRaises(ValueError):
            get_service_port("web-app", "router")

    @patch("pytest_jupyter_deploy.kubernetes.services.run_kubectl")
    def test_no_port_raises(self, mock_run: Mock) -> None:
        mock_run.return_value = _service([])
        with self.assertRaises(ValueError):
            get_service_port("web-app", "router")
