import unittest
from unittest.mock import Mock, patch

from packaging.version import Version

from jupyter_deploy.provider.aws import aws_cli


class TestCheckAwsCliInstallation(unittest.TestCase):
    @patch("jupyter_deploy.cmd_utils.check_executable_installation")
    def test_returns_true_when_check_exec_installation(self, mock_check: Mock) -> None:
        # Mock the check_executable_installation to return successful installation
        mock_check.return_value = (True, "2.0.0", None)
        result = aws_cli.check_aws_cli_installation()

        # Verify
        self.assertTrue(result)
        mock_check.assert_called_once_with(executable_name="aws")

    @patch("jupyter_deploy.cmd_utils.check_executable_installation")
    def test_returns_false_when_check_exec_installation_not_found(self, mock_check: Mock) -> None:
        # Mock the check_executable_installation to return failed installation
        mock_check.return_value = (False, None, "Command 'aws' not found")
        result = aws_cli.check_aws_cli_installation()

        # Verify
        self.assertFalse(result)
        mock_check.assert_called_once()

    @patch("jupyter_deploy.cmd_utils.check_executable_installation")
    def test_returns_true_with_version_check(self, mock_check: Mock) -> None:
        # Mock the check_executable_installation to return successful installation with version
        mock_check.return_value = (True, "2.5.0", None)

        # Call the function under test with a minimum version requirement
        result = aws_cli.check_aws_cli_installation(min_version=Version("2.0.0"))

        # Verify
        self.assertTrue(result)
        mock_check.assert_called_once()

    @patch("jupyter_deploy.cmd_utils.check_executable_installation")
    def test_returns_false_when_version_check_fails(self, mock_check: Mock) -> None:
        mock_check.return_value = (True, "1.5.0", None)
        result = aws_cli.check_aws_cli_installation(min_version=Version("2.0.0"))

        # Verify
        self.assertFalse(result)
        mock_check.assert_called_once()

    @patch("jupyter_deploy.cmd_utils.check_executable_installation")
    def test_raises_when_check_exec_raises(self, mock_check: Mock) -> None:
        # Mock the check_executable_installation to raise an exception
        mock_check.side_effect = Exception("Test exception")
        with self.assertRaises(Exception) as context:
            aws_cli.check_aws_cli_installation()

        # Verify
        self.assertEqual(str(context.exception), "Test exception")
        mock_check.assert_called_once()
