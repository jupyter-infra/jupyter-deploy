import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import InstructionNotFoundError
from jupyter_deploy.provider.aws.aws_secretsmanager_runner import AwsSecretsManagerRunner
from jupyter_deploy.provider.resolved_argdefs import StrResolvedInstructionArgument


class TestAwsSecretsManagerRunner(unittest.TestCase):
    @patch("jupyter_deploy.provider.aws.aws_secretsmanager_runner.boto3")
    def test_get_secret_value_returns_secret_string(self, mock_boto3: Mock) -> None:
        mock_client: Mock = Mock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": "my-secret-value",
            "ARN": "arn:aws:secretsmanager:us-west-2:123:secret:test",
            "Name": "test",
        }

        runner = AwsSecretsManagerRunner(NullDisplay(), region_name="us-west-2")
        result = runner.execute_instruction(
            instruction_name="get-secret-value",
            resolved_arguments={
                "secret_id": StrResolvedInstructionArgument(
                    argument_name="secret_id",
                    value="arn:aws:secretsmanager:us-west-2:123:secret:test",
                ),
            },
        )

        self.assertEqual(result["SecretString"].value, "my-secret-value")
        mock_client.get_secret_value.assert_called_once_with(
            SecretId="arn:aws:secretsmanager:us-west-2:123:secret:test"
        )

    @patch("jupyter_deploy.provider.aws.aws_secretsmanager_runner.boto3")
    def test_unknown_instruction_raises_error(self, mock_boto3: Mock) -> None:
        runner = AwsSecretsManagerRunner(NullDisplay(), region_name="us-west-2")

        with self.assertRaises(InstructionNotFoundError):
            runner.execute_instruction(
                instruction_name="unknown-instruction",
                resolved_arguments={},
            )
