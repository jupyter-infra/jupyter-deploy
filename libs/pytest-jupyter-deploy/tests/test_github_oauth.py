"""Unit tests for GitHubOAuth2ProxyApplication auth methods."""

import unittest
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

from pytest_jupyter_deploy.oauth2_proxy.github import GitHubOAuth2ProxyApplication


def _make_app(
    is_ci: bool = False,
    ci_email: str | None = None,
    ci_password: str | None = None,
    ci_totp_fn: Mock | None = None,
    storage_state_path: Path | None = None,
) -> tuple[GitHubOAuth2ProxyApplication, Mock]:
    """Create a GitHubOAuth2ProxyApplication with a mocked Page."""
    page = Mock()
    app = GitHubOAuth2ProxyApplication(
        page=page,
        jupyterlab_url="https://app.example.com/lab",
        storage_state_path=storage_state_path or Path("/tmp/test-state.json"),
        is_ci=is_ci,
        ci_email=ci_email,
        ci_password=ci_password,
        ci_totp_fn=ci_totp_fn,
    )
    return app, page


class TestTryAuthSession(unittest.TestCase):
    def test_returns_true_when_oauth_proxy_session_valid(self) -> None:
        """No sign-in button visible → already authenticated."""
        app, page = _make_app()
        sign_in_button = Mock()
        sign_in_button.is_visible.return_value = False
        page.get_by_role.return_value = sign_in_button

        with patch.object(app, "save_storage_state") as mock_save:
            result = app._try_auth_session()

        assert result is True
        mock_save.assert_called_once()

    def test_returns_true_when_github_cookies_valid_auto_redirect(self) -> None:
        """Sign-in visible, click it, auto-redirect back to app domain."""
        app, page = _make_app()
        sign_in_button = Mock()
        sign_in_button.is_visible.return_value = True
        page.get_by_role.return_value = sign_in_button

        # After clicking sign-in, URL goes to app domain (not github.com)
        type(page).url = PropertyMock(return_value="https://app.example.com/lab")

        with patch.object(app, "save_storage_state"), patch.object(app, "_navigate_with_retry"):
            result = app._try_auth_session()

        assert result is True
        sign_in_button.click.assert_called_once()

    def test_returns_false_when_github_cookies_expired(self) -> None:
        """Sign-in visible, click it, lands on github.com/login → cookies expired."""
        app, page = _make_app()
        sign_in_button = Mock()
        sign_in_button.is_visible.return_value = True
        page.get_by_role.return_value = sign_in_button

        # After clicking, URL is github login page
        type(page).url = PropertyMock(return_value="https://github.com/login?client_id=abc")

        with patch.object(app, "_navigate_with_retry"):
            result = app._try_auth_session()

        assert result is False

    def test_returns_true_when_on_oauth_authorize_page(self) -> None:
        """Sign-in visible, click it, lands on authorize page → handles it."""
        app, page = _make_app()
        sign_in_button = Mock()
        sign_in_button.is_visible.return_value = True
        page.get_by_role.return_value = sign_in_button

        # First URL check: on authorize page; wait_for_url raises (still on github)
        type(page).url = PropertyMock(return_value="https://github.com/login/oauth/authorize?client_id=abc")
        page.wait_for_url.side_effect = Exception("timeout")

        with (
            patch.object(app, "save_storage_state"),
            patch.object(app, "_navigate_with_retry"),
            patch.object(app, "_handle_oauth_authorize_page") as mock_handle_oauth,
        ):
            result = app._try_auth_session()

        assert result is True
        mock_handle_oauth.assert_called_once()


class TestLoginWithAuthSession(unittest.TestCase):
    def test_succeeds_when_cookies_valid(self) -> None:
        app, page = _make_app()
        type(page).url = PropertyMock(return_value="https://app.example.com/lab")
        with patch.object(app, "_try_auth_session", return_value=True):
            # Should not raise
            app.login_with_auth_session()

    def test_raises_when_cookies_expired(self) -> None:
        app, page = _make_app()
        type(page).url = PropertyMock(return_value="https://github.com/login")

        with patch.object(app, "_try_auth_session", return_value=False), self.assertRaises(RuntimeError) as ctx:
            app.login_with_auth_session()

        assert "GitHub authentication required" in str(ctx.exception)
        assert "just auth-setup" in str(ctx.exception)


class TestLoginWith2fa(unittest.TestCase):
    def test_skips_2fa_when_cookies_valid(self) -> None:
        """If _try_auth_session returns True, no credentials used."""
        totp_fn = Mock()
        app, page = _make_app(ci_totp_fn=totp_fn)

        with patch.object(app, "_try_auth_session", return_value=True):
            app.login_with_2fa("bot@example.com", "s3cret", totp_fn)

        # No credential input or TOTP generation
        page.fill.assert_not_called()
        totp_fn.assert_not_called()

    def test_full_2fa_flow_when_cookies_expired(self) -> None:
        """Full flow: email + password + TOTP + OAuth authorize."""
        totp_fn = Mock(return_value="123456")
        app, page = _make_app(ci_totp_fn=totp_fn)

        # After 2FA, land on OAuth authorize page, then app
        url_sequence = iter(
            [
                "https://github.com/login",  # during _try_auth_session check
                "https://github.com/login/oauth/authorize?client_id=abc",  # after 2FA
                "https://github.com/login/oauth/authorize?client_id=abc",  # second read in if
            ]
        )
        type(page).url = PropertyMock(side_effect=url_sequence)

        # wait_for_url for TOTP page succeeds, then for redirect away from authorize raises
        def wait_for_url_side_effect(url_pattern: object, **kwargs: object) -> None:
            pass

        page.wait_for_url.side_effect = wait_for_url_side_effect

        with (
            patch.object(app, "_try_auth_session", return_value=False),
            patch.object(app, "save_storage_state") as mock_save,
            patch.object(app, "_handle_oauth_authorize_page"),
        ):
            # Make the first wait_for_url (TOTP page) succeed,
            # then the second (redirect away from two-factor) succeed,
            # then the third (redirect away from github) raise to trigger _handle_oauth_authorize_page
            page.wait_for_url.side_effect = [None, None, Exception("timeout")]

            app.login_with_2fa("bot@example.com", "s3cret", totp_fn)

        # Verify credentials were filled
        page.fill.assert_any_call('input[name="login"]', "bot@example.com")
        page.fill.assert_any_call('input[name="password"]', "s3cret")
        page.click.assert_any_call('input[type="submit"]')
        # Verify TOTP was generated and filled
        totp_fn.assert_called_once()
        page.fill.assert_any_call("#app_totp", "123456")
        # Verify storage state was saved
        mock_save.assert_called_once()

    def test_2fa_direct_redirect_no_oauth_page(self) -> None:
        """After 2FA, app auto-redirects (no OAuth authorize page)."""
        totp_fn = Mock(return_value="654321")
        app, page = _make_app(ci_totp_fn=totp_fn)

        # After 2FA, URL is already on app domain
        type(page).url = PropertyMock(return_value="https://app.example.com/lab")

        with (
            patch.object(app, "_try_auth_session", return_value=False),
            patch.object(app, "save_storage_state") as mock_save,
        ):
            app.login_with_2fa("bot@example.com", "s3cret", totp_fn)

        mock_save.assert_called_once()


class TestEnsureAuthenticated(unittest.TestCase):
    def test_ci_mode_dispatches_to_login_with_2fa(self) -> None:
        totp_fn = Mock()
        app, _ = _make_app(is_ci=True, ci_email="bot@example.com", ci_password="s3cret", ci_totp_fn=totp_fn)

        with patch.object(app, "login_with_2fa") as mock_2fa:
            app.ensure_authenticated()

        mock_2fa.assert_called_once_with("bot@example.com", "s3cret", totp_fn)

    def test_local_mode_dispatches_to_login_with_auth_session(self) -> None:
        app, _ = _make_app(is_ci=False)

        with patch.object(app, "login_with_auth_session") as mock_session:
            app.ensure_authenticated()

        mock_session.assert_called_once()

    def test_ci_mode_raises_without_credentials(self) -> None:
        app, _ = _make_app(is_ci=True)

        with self.assertRaises(RuntimeError) as ctx:
            app.ensure_authenticated()

        assert "--ci --ci-dir" in str(ctx.exception)
