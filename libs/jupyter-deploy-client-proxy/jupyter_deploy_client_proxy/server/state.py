"""The on-disk proxy status contract.

The proxy publishes its lifecycle state to ``<log_dir>/status.json`` so an out-of-process
reader (``jd proxy status``) can observe liveness + endpoint. This module owns the payload
schema and the atomic write; the proxy only supplies the live state, config, and bundle.
"""

from __future__ import annotations

import os

import aiofiles
import aiofiles.os
from pydantic import BaseModel

from jupyter_deploy_client_proxy.constants import STATUS_FILE_NAME
from jupyter_deploy_client_proxy.credentials.bundle import ConnectBundle
from jupyter_deploy_client_proxy.enums import ProxyState
from jupyter_deploy_client_proxy.server.config import JupyterDeployClientProxyConfig


class ProxyStatus(BaseModel):
    """The ``status.json`` payload.

    Attributes:
        state: the proxy's current lifecycle state.
        pid: the proxy process id (so a reader can check the process is still alive).
        port: the actual bound loopback port, or None before the listener is up.
        expires_at: ISO-8601 instant the current credential expires, or None before the
            first bundle.
    """

    state: ProxyState
    pid: int
    port: int | None = None
    expires_at: str | None = None


async def write_proxy_status(
    state: ProxyState,
    config: JupyterDeployClientProxyConfig,
    bundle: ConnectBundle | None,
    port: int | None = None,
) -> None:
    """Write the current status to ``<config.log_dir>/status.json``.

    No-op when there is no ``log_dir`` (stderr mode). File I/O goes through ``aiofiles`` so
    a slow disk never blocks the event loop.
    """
    log_dir = config.log_dir
    if log_dir is None:
        return
    status = ProxyStatus(
        state=state,
        pid=os.getpid(),
        port=port,
        expires_at=bundle.expires_at.isoformat() if bundle is not None else None,
    )
    await aiofiles.os.makedirs(log_dir, exist_ok=True)
    async with aiofiles.open(log_dir / STATUS_FILE_NAME, "w") as f:
        await f.write(status.model_dump_json())
