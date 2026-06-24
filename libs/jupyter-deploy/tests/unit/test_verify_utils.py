import unittest
from collections.abc import Callable
from unittest.mock import Mock, patch

from jupyter_deploy import verify_utils
from jupyter_deploy.enum import JupyterDeployTool
from jupyter_deploy.verify_utils import ToolRequiredError


class TestVerifyInstallation(unittest.TestCase):
    @patch("jupyter_deploy.cmd_utils.check_executable_installation")
    def test_succeeds_when_tool_is_installed(self, mock_check: Mock) -> None:
        # Mock the check_executable_installation to return successful installation
        mock_check.return_value = (True, "2.0.0", None)
        # Should not raise
        verify_utils._check_installation("my-tool")
        mock_check.assert_called_once_with(executable_name="my-tool", version_cmds=None)

    @patch("jupyter_deploy.cmd_utils.check_executable_installation")
    def test_raises_when_tool_not_installed(self, mock_check: Mock) -> None:
        # Mock the check_executable_installation to return failed installation
        mock_check.return_value = (False, None, "Command 'my-tool' not found")

        with self.assertRaises(ToolRequiredError) as context:
            verify_utils._check_installation("my-tool", installation_url="https://example.com")

        self.assertEqual(context.exception.tool_name, "my-tool")
        self.assertEqual(context.exception.installation_url, "https://example.com")
        self.assertEqual(context.exception.error_msg, "Command 'my-tool' not found")
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
    def test_all_verification_methods_should_pass_through_to_check_installation(self, mock_check: Mock) -> None:
        for tool, verify_fn in verify_utils._TOOL_VERIFICATION_FN_MAP.items():
            mock_check.reset_mock()
            with self.subTest(tool=tool, verify_fn=verify_fn):
                # Should not raise
                verify_fn()
                mock_check.assert_called_once()


class TestCheckYqInstallation(unittest.TestCase):
    @patch("jupyter_deploy.verify_utils._check_installation")
    def test_passes_tool_name_and_install_url(self, mock_check: Mock) -> None:
        verify_utils._check_yq_installation()
        mock_check.assert_called_once_with(
            tool_name="yq",
            installation_url="https://github.com/mikefarah/yq/#install",
        )

    @patch("jupyter_deploy.cmd_utils.check_executable_installation")
    def test_raises_when_yq_not_installed(self, mock_check: Mock) -> None:
        mock_check.return_value = (False, None, "Command 'yq' not found")

        with self.assertRaises(ToolRequiredError) as context:
            verify_utils._check_yq_installation()

        self.assertEqual(context.exception.tool_name, "yq")

    def test_yq_is_mapped(self) -> None:
        self.assertIs(
            verify_utils._TOOL_VERIFICATION_FN_MAP[JupyterDeployTool.YQ],
            verify_utils._check_yq_installation,
        )


class TestVerifyToolsInstallation(unittest.TestCase):
    def test_succeeds_for_empty_list(self) -> None:
        # Should not raise
        verify_utils.verify_tools_installation([])

    @patch("jupyter_deploy.verify_utils._check_installation")
    def test_calls_each_verification_method(self, mock_check: Mock) -> None:
        req1 = Mock()
        req2 = Mock()
        req1.name = "aws-cli"
        req1.version = None
        req2.name = "terraform"
        req2.version = None

        # Should not raise
        verify_utils.verify_tools_installation([req1, req2])
        self.assertEqual(mock_check.call_count, 2)

    @patch("jupyter_deploy.verify_utils._check_installation")
    def test_raises_on_first_missing_tool(self, mock_check: Mock) -> None:
        req1 = Mock()
        req2 = Mock()
        req1.name = "aws-cli"
        req1.version = None
        req2.name = "terraform"
        req2.version = None

        mock_check.side_effect = [ToolRequiredError("aws", None, None), None]

        with self.assertRaises(ToolRequiredError):
            verify_utils.verify_tools_installation([req1, req2])

        # Should only call once before raising
        self.assertEqual(mock_check.call_count, 1)

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

        # Should not raise, should call twice (skip the unknown tool)
        verify_utils.verify_tools_installation([req1, req2, req3])
        self.assertEqual(mock_check.call_count, 2)
