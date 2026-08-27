import unittest
from unittest.mock import MagicMock, Mock, patch

from jupyter_deploy.api.http import ip_echo


class TestGetObservedIp(unittest.TestCase):
    @patch("jupyter_deploy.api.http.ip_echo.urllib.request.urlopen")
    def test_returns_trimmed_ipv4_from_echo(self, mock_urlopen: Mock) -> None:
        resp = MagicMock()
        resp.read.return_value = b"203.0.113.7\n"
        mock_urlopen.return_value.__enter__.return_value = resp

        self.assertEqual(ip_echo.get_observed_ip("198.51.100.5", 80, "/ip"), "203.0.113.7")
        # URL is composed from the supplied host/port/path (nothing hardcoded).
        self.assertEqual(mock_urlopen.call_args.args[0], "http://198.51.100.5:80/ip")

    @patch("jupyter_deploy.api.http.ip_echo.urllib.request.urlopen")
    def test_rejects_non_ipv4(self, mock_urlopen: Mock) -> None:
        resp = MagicMock()
        resp.read.return_value = b"not-an-ip"
        mock_urlopen.return_value.__enter__.return_value = resp

        with self.assertRaises(ValueError):
            ip_echo.get_observed_ip("198.51.100.5", 80, "/ip")

    @patch("jupyter_deploy.api.http.ip_echo.urllib.request.urlopen")
    def test_raises_when_request_fails(self, mock_urlopen: Mock) -> None:
        mock_urlopen.side_effect = OSError("connection refused")

        with self.assertRaises(OSError):
            ip_echo.get_observed_ip("198.51.100.5", 80, "/ip")
