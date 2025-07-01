import unittest
from collections.abc import Callable
from unittest.mock import Mock, patch

from packaging.version import Version

from jupyter_deploy import verify_utils
from jupyter_deploy.enum import JupyterDeployTool


class TestVerifyInstallation(unittest.TestCase):
    @patch("jupyter_deploy.cmd_utils.check_executable_installation")
    def test_returns_true_when_check_exec_installation(self, mock_check: Mock) -> None:
        # Mock the check_executable_installation to return successful installation
        mock_check.return_value = (True, "2.0.0", None)
        result = verify_utils._check_installation("my-tool")

        # Verify
        self.assertTrue(result)
        mock_check.assert_called_once_with(executable_name="my-tool")

    @patch("jupyter_deploy.cmd_utils.check_executable_installation")
    def test_returns_false_when_check_exec_installation_not_found(self, mock_check: Mock) -> None:
        # Mock the check_executable_installation to return failed installation
        mock_check.return_value = (False, None, "Command 'my-tool' not found")
        result = verify_utils._check_installation("my-tool")

        # Verify
        self.assertFalse(result)
        mock_check.assert_called_once()

    @patch("jupyter_deploy.cmd_utils.check_executable_installation")
    def test_returns_true_with_version_check(self, mock_check: Mock) -> None:
        # Mock the check_executable_installation to return successful installation with version
        mock_check.return_value = (True, "2.5.0", None)

        # Call the function under test with a minimum version requirement
        result = verify_utils._check_installation("my-tool", min_version=Version("2.0.0"))

        # Verify
        self.assertTrue(result)
        mock_check.assert_called_once()

    @patch("jupyter_deploy.cmd_utils.check_executable_installation")
    def test_returns_false_when_version_check_fails(self, mock_check: Mock) -> None:
        mock_check.return_value = (True, "1.5.0", None)
        result = verify_utils._check_installation("my-tool", min_version=Version("2.0.0"))

        # Verify
        self.assertFalse(result)
        mock_check.assert_called_once()

    @patch("jupyter_deploy.cmd_utils.check_executable_installation")
    def test_raises_when_check_exec_raises(self, mock_check: Mock) -> None:
        # Mock the check_executable_installation to raise an exception
        mock_check.side_effect = Exception("Test exception")
        with self.assertRaises(Exception) as context:
            verify_utils._check_installation("my-tool")

        # Verify
        self.assertEqual(str(context.exception), "Test exception")
        mock_check.assert_called_once()


class TestVerifyMap(unittest.TestCase):
    def test_all_mapped_to_distinct_verification_method(self) -> None:
        methods: set[Callable] = set()

        for tool, verify_fn in verify_utils._TOOL_VERIFICATION_FN_MAP.items():
            with self.subTest(tool=tool, verify_fn=verify_fn):
                if verify_fn in methods:
                    self.fail(f"duplicate tool verification method for tool: {tool}")

        mapped_tools = set(verify_utils._TOOL_VERIFICATION_FN_MAP.keys())
        for tool in JupyterDeployTool:
            with self.subTest(tool=tool):
                self.assertIn(tool, mapped_tools, f"no verification function mapped for tool: {tool}")

    @patch("jupyter_deploy.verify_utils._check_installation")
    def test_all_verification_methods_should_pass_response(self, mock_check: Mock) -> None:
        for tool, verify_fn in verify_utils._TOOL_VERIFICATION_FN_MAP.items():
            mock_check.reset_mock()
            mock_check.return_value = True
            with self.subTest(tool=tool, verify_fn=verify_fn):
                self.assertTrue(verify_fn(None))
                mock_check.assert_called_once()


class TestVerifyToolsInstallation(unittest.TestCase):
    def test_return_true_for_empty_list(self) -> None:
        self.assertTrue(verify_utils.verify_tools_installation([]))

    @patch("jupyter_deploy.verify_utils._check_installation")
    def test_call_each_verification_method(self, mock_check: Mock) -> None:
        req1 = Mock()
        req2 = Mock()
        req1.name = "aws-cli"
        req1.version = None
        req2.name = "terraform"
        req2.version = None

        mock_check.return_value = True

        self.assertTrue(verify_utils.verify_tools_installation([req1, req2]))
        self.assertEqual(mock_check.call_count, 2)
        self.assertEqual(mock_check.mock_calls[0][2]["min_version"], None)

    @patch("jupyter_deploy.verify_utils._check_installation")
    def test_passes_min_versions(self, mock_check: Mock) -> None:
        req1 = Mock()
        req2 = Mock()
        req1.name = "aws-cli"
        req1.version = "1.0.0"
        req2.name = "terraform"
        req2.version = "2.0.0"

        mock_check.side_effect = [False, True]

        self.assertFalse(verify_utils.verify_tools_installation([req1, req2]))
        self.assertEqual(mock_check.call_count, 2)
        self.assertEqual(mock_check.mock_calls[0][2]["min_version"], Version("1.0.0"))
        self.assertEqual(mock_check.mock_calls[1][2]["min_version"], Version("2.0.0"))

    @patch("jupyter_deploy.verify_utils._check_installation")
    def test_skips_unrecognized_tools(self, mock_check: Mock) -> None:
        req1 = Mock()
        req2 = Mock()
        req3 = Mock()
        req1.name = "aws-cli"
        req1.version = None
        req2.name = "some-unknown-tool"
        req2.version = None
        req3.name = "jq"
        req3.version = None

        mock_check.return_value = True

        self.assertTrue(verify_utils.verify_tools_installation([req1, req2, req3]))
        self.assertEqual(mock_check.call_count, 2)

    @patch("jupyter_deploy.verify_utils._check_installation")
    def test_skip_version_verification_for_invalid_versions(self, mock_check: Mock) -> None:
        req1 = Mock()
        req2 = Mock()
        req1.name = "aws-cli"
        req1.version = "i-am-not-a-version"
        req2.name = "terraform"
        req2.version = None

        mock_check.return_value = False

        self.assertFalse(verify_utils.verify_tools_installation([req1, req2]))
        self.assertEqual(mock_check.call_count, 2)
        self.assertEqual(mock_check.mock_calls[0][2]["min_version"], None)
        self.assertEqual(mock_check.mock_calls[1][2]["min_version"], None)
