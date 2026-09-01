import signal
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

from jupyter_deploy_client_proxy.constants import DROP_FROM_REQUEST_HEADERS, DROP_FROM_RESPONSE_HEADERS
from jupyter_deploy_client_proxy.credentials.bundle import ConnectBundle
from jupyter_deploy_client_proxy.utils import (
    _merge_bundle_headers_into_incoming,
    get_bundle_summary,
    get_forwarded_request_headers,
    get_forwarded_response_headers,
    get_seconds_until_refresh,
    get_shutdown_signals,
    is_loopback_request_allowed,
)


class TestIsLoopbackRequestAllowed(unittest.TestCase):
    def test_allows_loopback_origin_and_host(self) -> None:
        self.assertTrue(
            is_loopback_request_allowed({"Origin": "http://127.0.0.1:8888", "Host": "127.0.0.1:8888"}, 8888)
        )

    def test_allows_localhost_origin_and_host(self) -> None:
        self.assertTrue(
            is_loopback_request_allowed({"Origin": "http://localhost:8888", "Host": "localhost:8888"}, 8888)
        )

    def test_allows_missing_origin(self) -> None:
        # Non-browser clients / top-level navigations carry no Origin; the listener is not otherwise authed.
        self.assertTrue(is_loopback_request_allowed({"Host": "127.0.0.1:8888"}, 8888))

    def test_allows_missing_host_and_origin(self) -> None:
        self.assertTrue(is_loopback_request_allowed({}, 8888))

    def test_rejects_cross_origin(self) -> None:
        self.assertFalse(is_loopback_request_allowed({"Origin": "https://evil.com", "Host": "127.0.0.1:8888"}, 8888))

    def test_rejects_wrong_port_origin(self) -> None:
        self.assertFalse(is_loopback_request_allowed({"Origin": "http://127.0.0.1:9999"}, 8888))

    def test_rejects_non_loopback_host_dns_rebinding(self) -> None:
        self.assertFalse(is_loopback_request_allowed({"Host": "attacker.example:8888"}, 8888))


class TestMergeBundleHeadersIntoIncoming(unittest.TestCase):
    def test_injects_bundle_headers(self) -> None:
        self.assertEqual(
            _merge_bundle_headers_into_incoming({"Accept": "*/*"}, {"Authorization": "Bearer x"}),
            {"Accept": "*/*", "Authorization": "Bearer x"},
        )

    def test_bundle_wins_on_conflict(self) -> None:
        self.assertEqual(
            _merge_bundle_headers_into_incoming({"Authorization": "old"}, {"Authorization": "new"})["Authorization"],
            "new",
        )

    def test_does_not_mutate_incoming(self) -> None:
        incoming = {"Accept": "*/*"}
        _merge_bundle_headers_into_incoming(incoming, {"Authorization": "x"})
        self.assertNotIn("Authorization", incoming)


class TestGetForwardedRequestHeaders(unittest.TestCase):
    def test_drops_hop_by_hop_and_handshake_headers(self) -> None:
        incoming = {
            "Host": "localhost",
            "Connection": "keep-alive",
            "Upgrade": "websocket",
            "Sec-WebSocket-Key": "abc",
            "Accept": "*/*",
        }
        result = get_forwarded_request_headers(incoming, {"Authorization": "Bearer x"}, "10.0.0.1", 443)
        self.assertEqual(result, {"Accept": "*/*", "Authorization": "Bearer x"})

    def test_injects_bundle_headers(self) -> None:
        result = get_forwarded_request_headers({"Accept": "*/*"}, {"x-k8s-aws-id": "dep-1"}, "10.0.0.1", 443)
        self.assertEqual(result["x-k8s-aws-id"], "dep-1")

    def test_rewrites_origin_omitting_default_https_port(self) -> None:
        # Port 443 must be omitted so Origin's netloc matches the Host header aiohttp sends (no port).
        result = get_forwarded_request_headers({"Origin": "http://127.0.0.1:9999"}, {}, "10.0.0.1", 443)
        self.assertEqual(result["Origin"], "https://10.0.0.1")

    def test_rewrites_origin_including_non_default_port(self) -> None:
        result = get_forwarded_request_headers({"Origin": "http://127.0.0.1:9999"}, {}, "10.0.0.1", 8443)
        self.assertEqual(result["Origin"], "https://10.0.0.1:8443")

    def test_rewrites_referer_origin_preserving_path_and_query(self) -> None:
        result = get_forwarded_request_headers(
            {"Referer": "http://127.0.0.1:9999/lab/tree?a=1#frag"}, {}, "10.0.0.1", 443
        )
        self.assertEqual(result["Referer"], "https://10.0.0.1/lab/tree?a=1#frag")

    def test_rewrites_case_insensitively_preserving_key_casing(self) -> None:
        result = get_forwarded_request_headers({"origin": "http://127.0.0.1:9999"}, {}, "10.0.0.1", 443)
        self.assertEqual(result["origin"], "https://10.0.0.1")
        self.assertNotIn("Origin", result)

    def test_does_not_add_origin_when_absent(self) -> None:
        result = get_forwarded_request_headers({"Accept": "*/*"}, {}, "10.0.0.1", 443)
        self.assertNotIn("Origin", result)
        self.assertNotIn("Referer", result)


class TestGetForwardedResponseHeaders(unittest.TestCase):
    def test_drops_hop_by_hop(self) -> None:
        upstream = {"Content-Type": "application/json", "Transfer-Encoding": "chunked", "Content-Length": "5"}
        self.assertEqual(get_forwarded_response_headers(upstream), {"Content-Type": "application/json"})


class TestGetBundleSummary(unittest.TestCase):
    def test_redacts_header_values_and_ca_cert(self) -> None:
        bundle = ConnectBundle(
            host="10.0.0.1",
            port=443,
            ca_cert="-----BEGIN CERTIFICATE-----\nSECRETPEM\n-----END CERTIFICATE-----",
            headers={"Authorization": "Bearer super-secret-token", "x-k8s-aws-id": "dep-1"},
            expires_at=datetime(2026, 6, 10, 18, 1, tzinfo=UTC),
        )
        summary = get_bundle_summary(bundle)
        self.assertIn("Authorization", summary)
        self.assertIn("x-k8s-aws-id", summary)
        self.assertIn("10.0.0.1:443", summary)
        self.assertNotIn("super-secret-token", summary)
        self.assertNotIn("SECRETPEM", summary)


@patch("jupyter_deploy_client_proxy.utils.datetime")
class TestGetSecondsUntilRefresh(unittest.TestCase):
    def test_subtracts_margin(self, mock_datetime: Mock) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        mock_datetime.now.return_value = now
        self.assertEqual(get_seconds_until_refresh(now + timedelta(seconds=60), margin_seconds=15), 45.0)

    def test_margin_exceeds_remaining_falls_back_to_fraction(self, mock_datetime: Mock) -> None:
        # 5s left, 15s margin: a plain lifetime-minus-margin sleep is -10 (would spin); instead we
        # refresh at a fraction of what's left (5 * 0.5 = 2.5s), never 0.
        now = datetime(2026, 1, 1, tzinfo=UTC)
        mock_datetime.now.return_value = now
        self.assertEqual(get_seconds_until_refresh(now + timedelta(seconds=5), margin_seconds=15), 2.5)

    def test_already_expired_floors_to_minimum(self, mock_datetime: Mock) -> None:
        # Past expiry (clock skew): never returns <= 0 — floors to MIN_REFRESH_SLEEP_SECONDS (1.0).
        now = datetime(2026, 1, 1, tzinfo=UTC)
        mock_datetime.now.return_value = now
        self.assertEqual(get_seconds_until_refresh(now - timedelta(seconds=30), margin_seconds=15), 1.0)

    def test_reads_current_utc_clock(self, mock_datetime: Mock) -> None:
        fixed = datetime(2026, 1, 1, tzinfo=UTC)
        mock_datetime.now.return_value = fixed
        self.assertEqual(get_seconds_until_refresh(fixed + timedelta(seconds=120), margin_seconds=15), 105.0)
        mock_datetime.now.assert_called_once_with(UTC)


class TestGetShutdownSignals(unittest.TestCase):
    def test_includes_sigterm(self) -> None:
        self.assertIn(signal.SIGTERM, get_shutdown_signals())

    def test_includes_sighup_when_available(self) -> None:
        sighup = getattr(signal, "SIGHUP", None)
        if sighup is not None:
            self.assertIn(sighup, get_shutdown_signals())

    def test_omits_signals_absent_on_platform(self) -> None:
        # Simulate a platform (e.g. Windows) without SIGHUP.
        class _FakeSignal:
            SIGTERM = signal.SIGTERM

        with patch("jupyter_deploy_client_proxy.utils.signal", _FakeSignal):
            self.assertEqual(get_shutdown_signals(), [signal.SIGTERM])


class TestDropFromRequestHeaders(unittest.TestCase):
    def test_every_member_is_dropped_case_insensitively(self) -> None:
        for name in DROP_FROM_REQUEST_HEADERS:
            with self.subTest(header=name):
                # Use realistic (title-cased) casing to also assert the drop is case-insensitive.
                result = get_forwarded_request_headers({name.title(): "v", "X-Keep": "1"}, {}, "10.0.0.1", 443)
                self.assertNotIn(name.title(), result)
                self.assertNotIn(name, {k.lower() for k in result})
                self.assertEqual(result["X-Keep"], "1")


class TestDropFromResponseHeaders(unittest.TestCase):
    def test_every_member_is_dropped_case_insensitively(self) -> None:
        for name in DROP_FROM_RESPONSE_HEADERS:
            with self.subTest(header=name):
                result = get_forwarded_response_headers({name.title(): "v", "X-Keep": "1"})
                self.assertNotIn(name.title(), result)
                self.assertNotIn(name, {k.lower() for k in result})
                self.assertEqual(result["X-Keep"], "1")
