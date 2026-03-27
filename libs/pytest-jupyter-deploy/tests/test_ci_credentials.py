"""Unit tests for CI credential fetching."""

import subprocess
import unittest
from unittest.mock import Mock, call, patch

from pytest_jupyter_deploy.oauth2_proxy.ci_credentials import fetch_ci_credentials


class TestFetchCiCredentials(unittest.TestCase):
    @patch("pytest_jupyter_deploy.oauth2_proxy.ci_credentials.subprocess.run")
    def test_returns_email_password_and_totp_fn(self, mock_run: Mock) -> None:
        mock_run.side_effect = [
            Mock(stdout="bot@example.com\n"),
            Mock(stdout="s3cret\n"),
        ]

        email, password, totp_fn = fetch_ci_credentials("/ci/dir")

        assert email == "bot@example.com"
        assert password == "s3cret"
        assert callable(totp_fn)
        mock_run.assert_has_calls(
            [
                call(
                    ["uv", "run", "jd", "show", "-v", "github_bot_account_email", "--text", "--path", "/ci/dir"],
                    capture_output=True,
                    text=True,
                    check=True,
                ),
                call(
                    ["uv", "run", "python", "scripts/auth_bot_secret.py", "/ci/dir", "password"],
                    capture_output=True,
                    text=True,
                    check=True,
                ),
            ]
        )

    @patch("pytest_jupyter_deploy.oauth2_proxy.ci_credentials.subprocess.run")
    def test_totp_fn_spawns_new_subprocess_each_call(self, mock_run: Mock) -> None:
        mock_run.side_effect = [
            Mock(stdout="bot@example.com\n"),
            Mock(stdout="s3cret\n"),
            Mock(stdout="123456\n"),
            Mock(stdout="654321\n"),
        ]

        _, _, totp_fn = fetch_ci_credentials("/ci/dir")

        first_code = totp_fn()
        second_code = totp_fn()

        assert first_code == "123456"
        assert second_code == "654321"
        # 2 initial calls (email, password) + 2 totp calls = 4 total
        assert mock_run.call_count == 4
        totp_call = call(
            ["uv", "run", "python", "scripts/auth_bot_secret.py", "/ci/dir", "totp"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert mock_run.call_args_list[2] == totp_call
        assert mock_run.call_args_list[3] == totp_call

    @patch("pytest_jupyter_deploy.oauth2_proxy.ci_credentials.subprocess.run")
    def test_subprocess_failure_raises(self, mock_run: Mock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, "uv", stderr="not found")

        with self.assertRaises(subprocess.CalledProcessError):
            fetch_ci_credentials("/ci/dir")
