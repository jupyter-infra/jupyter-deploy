import unittest
from unittest.mock import Mock

import botocore.exceptions

from jupyter_deploy.api.aws.ssm.ssm_session import describe_instance_information


class TestDescribeInstanceInformation(unittest.TestCase):
    """Tests for the describe_instance_information function."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_ssm_client = Mock()
        self.instance_id = "i-1234567890abcdef0"

    def test_successful_describe_instance_information(self) -> None:
        """Test that describe_instance_information returns the first item when information is available."""
        # Setup
        # Using dict instead of strict typing for mocking purposes
        instance_info = {
            "InstanceId": self.instance_id,
            "PingStatus": "Online",
            # LastPingDateTime should be a datetime object but Mock will handle it
            "AgentVersion": "1.0.0.0",
            "IsLatestVersion": True,
            "PlatformType": "Linux",
            "PlatformName": "Amazon Linux",
            "PlatformVersion": "2",
            "ResourceType": "EC2Instance",
        }
        self.mock_ssm_client.describe_instance_information.return_value = {"InstanceInformationList": [instance_info]}

        # Execute
        result = describe_instance_information(self.mock_ssm_client, self.instance_id)

        # Assert
        self.mock_ssm_client.describe_instance_information.assert_called_once_with(
            Filters=[{"Key": "InstanceIds", "Values": [self.instance_id]}]
        )
        self.assertEqual(result, instance_info)

    def test_empty_instance_information_list(self) -> None:
        """Test that describe_instance_information raises ValueError when no information is available."""
        # Setup
        self.mock_ssm_client.describe_instance_information.return_value = {"InstanceInformationList": []}

        # Execute & Assert
        with self.assertRaises(ValueError) as context:
            describe_instance_information(self.mock_ssm_client, self.instance_id)

        self.assertEqual(str(context.exception), "SSM:DescribeInstanceInformation returned an empty list")
        self.mock_ssm_client.describe_instance_information.assert_called_once_with(
            Filters=[{"Key": "InstanceIds", "Values": [self.instance_id]}]
        )

    def test_api_call_exception_bubbles_up(self) -> None:
        """Test that exceptions from the API call are not swallowed but bubble up."""
        # Setup
        error = botocore.exceptions.ClientError(
            {
                "Error": {
                    "Code": "InvalidInstanceId",
                    "Message": "The instance ID is not valid",
                }
            },
            "DescribeInstanceInformation",
        )
        self.mock_ssm_client.describe_instance_information.side_effect = error

        # Execute & Assert
        with self.assertRaises(botocore.exceptions.ClientError) as context:
            describe_instance_information(self.mock_ssm_client, self.instance_id)

        # Verify the exception is the same one we set up
        self.assertIs(context.exception, error)
        self.mock_ssm_client.describe_instance_information.assert_called_once_with(
            Filters=[{"Key": "InstanceIds", "Values": [self.instance_id]}]
        )
