import ssl
import unittest

import trustme

from jupyter_deploy_client_proxy.server.tls import build_pinned_ssl_context


class TestBuildPinnedSslContext(unittest.TestCase):
    ca_pem: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.ca_pem = trustme.CA().cert_pem.bytes().decode()

    def test_builds_context_from_valid_pem(self) -> None:
        context = build_pinned_ssl_context(self.ca_pem)
        self.assertIsInstance(context, ssl.SSLContext)

    def test_disables_hostname_check_and_requires_cert(self) -> None:
        context = build_pinned_ssl_context(self.ca_pem)
        self.assertFalse(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_rejects_empty_pem(self) -> None:
        with self.assertRaises(ValueError):
            build_pinned_ssl_context("   ")

    def test_rejects_garbage_pem(self) -> None:
        with self.assertRaises(ssl.SSLError):
            build_pinned_ssl_context("-----BEGIN CERTIFICATE-----\nnope\n-----END CERTIFICATE-----")
