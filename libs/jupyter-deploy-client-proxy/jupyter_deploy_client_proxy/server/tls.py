"""Pinned-TLS client context.

The proxy is the TLS *client* and trusts exactly one cert — the upstream's
self-signed PEM — instead of the system CA store. Hostname checking is disabled
because the pin is on the cert/key, not the address: the upstream is dialed by a
raw IP that changes across host stop/start.
"""

from __future__ import annotations

import ssl

from jupyter_deploy_client_proxy.constants import ALPN_PROTOCOLS


def build_pinned_ssl_context(ca_cert_pem: str) -> ssl.SSLContext:
    """Build a client SSL context that pins ``ca_cert_pem`` as the sole trusted CA.

    Offers only ``http/1.1`` in ALPN (deliberate — h2 buys nothing on this leg).

    Raises:
        ValueError: if ``ca_cert_pem`` is empty.
        ssl.SSLError: if the PEM cannot be loaded.
    """
    if not ca_cert_pem.strip():
        raise ValueError("ca_cert_pem is empty; nothing to pin")

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cadata=ca_cert_pem)
    context.set_alpn_protocols(ALPN_PROTOCOLS)
    return context
