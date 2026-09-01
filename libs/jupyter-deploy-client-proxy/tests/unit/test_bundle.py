import unittest
from datetime import UTC, datetime

from pydantic import ValidationError

from jupyter_deploy_client_proxy.credentials.bundle import ConnectBundle

VALID_BUNDLE = {
    "host": "203.0.113.7",
    "port": 443,
    "ca_cert": "-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----",
    "headers": {"Authorization": "Bearer k8s-aws-v1.xyz", "x-k8s-aws-id": "dep-123"},
    "expires_at": "2026-06-10T18:01:00Z",
}


class TestConnectBundle(unittest.TestCase):
    def test_parses_valid_payload(self) -> None:
        bundle = ConnectBundle.model_validate(VALID_BUNDLE)
        self.assertEqual(bundle.host, "203.0.113.7")
        self.assertEqual(bundle.port, 443)
        self.assertEqual(bundle.headers["x-k8s-aws-id"], "dep-123")
        self.assertEqual(bundle.expires_at, datetime(2026, 6, 10, 18, 1, tzinfo=UTC))

    def test_headers_default_empty(self) -> None:
        payload = {k: v for k, v in VALID_BUNDLE.items() if k != "headers"}
        self.assertEqual(ConnectBundle.model_validate(payload).headers, {})

    def test_ca_cert_default_empty(self) -> None:
        payload = {k: v for k, v in VALID_BUNDLE.items() if k != "ca_cert"}
        self.assertEqual(ConnectBundle.model_validate(payload).ca_cert, "")

    def test_rejects_missing_required_field(self) -> None:
        payload = {k: v for k, v in VALID_BUNDLE.items() if k != "host"}
        with self.assertRaises(ValidationError):
            ConnectBundle.model_validate(payload)

    def test_rejects_out_of_range_port(self) -> None:
        with self.assertRaises(ValidationError):
            ConnectBundle.model_validate({**VALID_BUNDLE, "port": 70000})

    def test_rejects_naive_expires_at(self) -> None:
        # A timezone-naive expires_at (no Z/offset) would crash the refresh math against an
        # aware `now`; the bundle contract rejects it up front.
        with self.assertRaises(ValidationError):
            ConnectBundle.model_validate({**VALID_BUNDLE, "expires_at": "2026-06-10T18:01:00"})

    def test_json_round_trips(self) -> None:
        bundle = ConnectBundle.model_validate(VALID_BUNDLE)
        self.assertEqual(ConnectBundle.model_validate_json(bundle.model_dump_json()), bundle)
