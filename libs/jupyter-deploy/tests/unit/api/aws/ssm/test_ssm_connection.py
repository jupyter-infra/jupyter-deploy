import unittest
from unittest.mock import Mock

from jupyter_deploy.api.aws.ssm.ssm_connection import (
    CONNECTION_STATUS_CONNECTED,
    CONNECTION_STATUS_NOT_CONNECTED,
    get_connection_status,
)


class TestGetConnectionStatus(unittest.TestCase):
    def test_returns_connected(self) -> None:
        mock_client: Mock = Mock()
        mock_client.get_connection_status.return_value = {
            "Target": "i-123",
            "Status": "connected",
        }

        result = get_connection_status(mock_client, "i-123")

        self.assertEqual(result, CONNECTION_STATUS_CONNECTED)
        mock_client.get_connection_status.assert_called_once_with(Target="i-123")

    def test_returns_notconnected(self) -> None:
        mock_client: Mock = Mock()
        mock_client.get_connection_status.return_value = {
            "Target": "i-123",
            "Status": "notconnected",
        }

        result = get_connection_status(mock_client, "i-123")

        self.assertEqual(result, CONNECTION_STATUS_NOT_CONNECTED)
