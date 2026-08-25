"""Thin typer CLI over the proxy runtime.

Parses argv, builds a :class:`Proxy`, and runs it in the foreground until Ctrl-C.
All behavior lives in ``server/`` — this module is only the argv-to-Proxy glue.
"""

from __future__ import annotations

import asyncio
import shlex
from pathlib import Path
from typing import Annotated

import typer

from jupyter_deploy_client_proxy.constants import DEFAULT_REFRESH_MARGIN_SECONDS
from jupyter_deploy_client_proxy.server.config import JupyterDeployClientProxyConfig, LogLevel
from jupyter_deploy_client_proxy.server.proxy import JupyterDeployClientProxy

app = typer.Typer(
    add_completion=False,
    help="Route an app from localhost to a jupyter-deploy-managed remote host, over pinned TLS.",
)


async def _serve(proxy: JupyterDeployClientProxy) -> None:
    # proxy.stop() flushes + closes the logger; the finally covers cancellation (Ctrl-C)
    # at any point, including during start(), and runs inside the loop before it closes.
    try:
        port = await proxy.start()
        print(f"listening on http://127.0.0.1:{port}", flush=True)
        await asyncio.Event().wait()  # run until cancelled / Ctrl-C
    finally:
        await proxy.stop()


@app.callback(invoke_without_command=True)
def run(
    token_command: Annotated[
        str,
        typer.Option("--token-command", help="Command emitting a JSON connection bundle on stdout."),
    ],
    listen_port: Annotated[
        int,
        typer.Option("--listen-port", help="Loopback port to listen on (0 = ephemeral, printed on startup)."),
    ] = 0,
    ca_cert: Annotated[
        Path | None,
        typer.Option("--ca-cert", help="Static CA PEM to pin, overriding the bundle's ca_cert (no-cloud case)."),
    ] = None,
    refresh_margin_seconds: Annotated[
        float,
        typer.Option("--refresh-margin-seconds", help="Seconds before expires_at to re-exec the token command."),
    ] = DEFAULT_REFRESH_MARGIN_SECONDS,
    log_dir: Annotated[
        Path | None,
        typer.Option("--log-dir", help="Write 0000.log, 0001.log, … here (jd passes .jd-proxy/<id>). Default: stderr."),
    ] = None,
    log_level: Annotated[
        LogLevel,
        typer.Option("--log-level", help="DEBUG, INFO, WARNING, ERROR, or CRITICAL."),
    ] = LogLevel.INFO,
) -> None:
    """Run the proxy in the foreground until interrupted."""
    config = JupyterDeployClientProxyConfig(
        token_argv=shlex.split(token_command),
        listen_port=listen_port,
        refresh_margin_seconds=refresh_margin_seconds,
        ca_cert_override=ca_cert.read_text() if ca_cert else None,
        log_dir=log_dir,
        log_level=log_level,
    )
    proxy = JupyterDeployClientProxy(config)
    try:
        asyncio.run(_serve(proxy))
    except KeyboardInterrupt as e:
        raise typer.Exit(code=130) from e


def main() -> None:
    """Console-script entry point."""
    app()
