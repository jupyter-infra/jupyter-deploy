"""The exec-credential connection bundle contract.

A token command (e.g. ``jd proxy connect-info``) emits, on stdout, a single JSON
object describing the whole connection state. The proxy is cloud-blind: it never
interprets individual fields beyond what it needs to connect and inject headers.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ConnectBundle(BaseModel):
    """Connection state emitted by the token command.

    Attributes:
        host: upstream host to dial (an IP or hostname; resolved live by the token command).
        port: upstream TLS port.
        ca_cert: PEM the proxy pins as the sole trusted CA. May be empty when a static
            ``--ca-cert`` override supplies the pin instead.
        headers: opaque name->value map injected on every forwarded request and the WS
            upgrade. The proxy never special-cases individual header names.
        expires_at: the proxy re-execs the token command on a margin before this instant.
    """

    host: str
    port: int = Field(gt=0, le=65535)
    ca_cert: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    expires_at: datetime
