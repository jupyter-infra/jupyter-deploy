import unittest
from unittest.mock import Mock

from jupyter_deploy.api.aws.secretsmanager.secretsmanager_secret import get_secret_value


class TestGetSecretValue(unittest.TestCase):
    def test_returns_secret_string(self) -> None:
        mock_client: Mock = Mock()
        mock_client.get_secret_value.return_value = {
            "ARN": "arn:aws:secretsmanager:us-west-2:123456789012:secret:my-secret",
            "Name": "my-secret",
            "SecretString": "super-secret-value",
        }

        result = get_secret_value(mock_client, "arn:aws:secretsmanager:us-west-2:123456789012:secret:my-secret")

        self.assertEqual(result["SecretString"], "super-secret-value")
        mock_client.get_secret_value.assert_called_once_with(
            SecretId="arn:aws:secretsmanager:us-west-2:123456789012:secret:my-secret"
        )
