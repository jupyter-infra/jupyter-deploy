"""The on-disk proxy status contract.

The proxy publishes its lifecycle state to ``<log_dir>/status.json`` so an out-of-process
reader (``jd proxy status``) can observe liveness + endpoint. This module owns the payload
schema and the write; the proxy only supplies the live state, config, and bundle.

The write is a plain in-place truncate-and-write, not atomic — a reader that opens the file
mid-write can see a partial payload (it recovers by treating an unparseable file as "no
status yet"). A temp-file-plus-``os.replace`` rename can be layered on later if that race
proves to matter in practice.
"""

from __future__ import annotations

import contextlib
import os

import aiofiles
import aiofiles.os
import psutil
from pydantic import BaseModel

from jupyter_deploy_client_proxy.constants import STATUS_FILE_NAME, STATUS_SCHEMA_VERSION
from jupyter_deploy_client_proxy.credentials.bundle import ConnectBundle
from jupyter_deploy_client_proxy.enums import ProxyState
from jupyter_deploy_client_proxy.server.config import JupyterDeployClientProxyConfig


class ProxyStatus(BaseModel):
    """The ``status.json`` payload.

    Attributes:
        schema_version: the payload shape version, so a consumer reading a file written by a
            different proxy version can pick the right interpretation. Bump on incompatible
            changes (see ``STATUS_SCHEMA_VERSION``).
        state: the proxy's current lifecycle state.
        pid: the proxy process id (so a reader can check the process is still alive).
        process_created_at: the process creation time (epoch seconds). Recorded so a reader
            can distinguish this exact process from a recycled PID before signaling it —
            killing a reused PID could hit an unrelated process.
        port: the actual bound loopback port, or None before the listener is up.
        expires_at: ISO-8601 instant the current credential expires, or None before the
            first bundle.
    """

    schema_version: int = STATUS_SCHEMA_VERSION
    state: ProxyState
    pid: int
    process_created_at: float
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
        process_created_at=psutil.Process().create_time(),
        port=port,
        expires_at=bundle.expires_at.isoformat() if bundle is not None else None,
    )
    await aiofiles.os.makedirs(log_dir, exist_ok=True)
    async with aiofiles.open(log_dir / STATUS_FILE_NAME, "w") as f:
        await f.write(status.model_dump_json())


async def delete_proxy_status(config: JupyterDeployClientProxyConfig) -> None:
    """Remove ``<config.log_dir>/status.json`` if present. No-op without a ``log_dir``.

    A clean shutdown deletes the status file rather than publishing a terminal state: its
    absence is how ``jd proxy status`` cheaply tells a dead run from a live one across a
    project's run history (an existence check, no parse), and it closes the window where a
    recycled PID could be misread as the old proxy. The rotating logs remain for history.
    """
    log_dir = config.log_dir
    if log_dir is None:
        return
    with contextlib.suppress(FileNotFoundError):
        await aiofiles.os.remove(log_dir / STATUS_FILE_NAME)
