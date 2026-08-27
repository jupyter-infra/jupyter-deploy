from __future__ import annotations

import urllib.request


def get_observed_ip(host: str, port: int, path: str, timeout: float = 5.0) -> str:
    """Return the SERVER-observed caller IPv4 from a plaintext IP-echo endpoint.

    A client-side "what is my IP" probe is unreliable behind NAT (the address the server
    actually sees for the real connection can differ), so we ask the server directly. The
    echo endpoint returns only the source IP; no secret is sent over this plaintext hop. The
    ``host``/``port``/``path`` are supplied by the caller, so nothing about the endpoint is
    hardcoded here. Provider-agnostic: it is a plain HTTP GET, not tied to any cloud.

    Raises:
        OSError: if the request fails (network error / timeout).
        ValueError: if the response is not a plausible IPv4 address.
    """
    url = f"http://{host}:{port}{path}"
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - fixed http scheme, IP echo
        ip: str = resp.read().decode().strip()
    parts = ip.split(".")
    if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        raise ValueError(f"IP echo returned an unexpected value: {ip!r}")
    return ip
