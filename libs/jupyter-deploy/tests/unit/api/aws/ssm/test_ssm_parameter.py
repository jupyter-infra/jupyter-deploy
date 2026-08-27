import unittest
from unittest.mock import Mock

from botocore.exceptions import ClientError

from jupyter_deploy.api.aws.ssm import ssm_parameter


class TestGetParameterValue(unittest.TestCase):
    def test_returns_value_with_decryption_default_true(self) -> None:
        mock_client = Mock()
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "-----BEGIN CERTIFICATE-----\n..."}}

        result = ssm_parameter.get_parameter_value(mock_client, "/jd/cert/pin")

        self.assertEqual(result, "-----BEGIN CERTIFICATE-----\n...")
        mock_client.get_parameter.assert_called_once_with(Name="/jd/cert/pin", WithDecryption=True)

    def test_with_decryption_false_flows_through(self) -> None:
        mock_client = Mock()
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "hello"}}

        result = ssm_parameter.get_parameter_value(mock_client, "/x", with_decryption=False)

        self.assertEqual(result, "hello")
        mock_client.get_parameter.assert_called_once_with(Name="/x", WithDecryption=False)

    def test_raises_on_empty_value(self) -> None:
        mock_client = Mock()
        mock_client.get_parameter.return_value = {"Parameter": {"Value": ""}}

        with self.assertRaises(ValueError):
            ssm_parameter.get_parameter_value(mock_client, "/x")

    def test_raises_on_missing_parameter_key(self) -> None:
        mock_client = Mock()
        mock_client.get_parameter.return_value = {}

        with self.assertRaises(ValueError):
            ssm_parameter.get_parameter_value(mock_client, "/x")

    def test_raises_when_get_parameter_raises(self) -> None:
        mock_client = Mock()
        mock_client.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "not found"}}, "GetParameter"
        )

        with self.assertRaises(ClientError):
            ssm_parameter.get_parameter_value(mock_client, "/x")
