"""Thin typer CLI over the proxy runtime.

Parses argv, builds a :class:`Proxy`, and runs it in the foreground until Ctrl-C.
All behavior lives in ``server/`` — this module is only the argv-to-Proxy glue.
"""

from __future__ import annotations

import asyncio
import contextlib
import shlex
from pathlib import Path
from typing import Annotated

import typer

from jupyter_deploy_client_proxy.constants import DEFAULT_IDLE_TIMEOUT_SECONDS, DEFAULT_REFRESH_MARGIN_SECONDS
from jupyter_deploy_client_proxy.server.config import JupyterDeployClientProxyConfig, LogLevel
from jupyter_deploy_client_proxy.server.proxy import JupyterDeployClientProxy
from jupyter_deploy_client_proxy.utils import get_shutdown_signals

app = typer.Typer(
    add_completion=False,
    help="Route an app from localhost to a jupyter-deploy-managed remote host, over pinned TLS.",
)


async def _serve(proxy: JupyterDeployClientProxy) -> int:
    """Run the proxy until it is told to stop; return the process exit code.

    Stops on an OS shutdown signal (exit 0) or on the proxy's own request — refresh permanently
    broken, or no client activity within the idle timeout — in which case the proxy chooses the
    code. Either way teardown is proxy.stop(), in the finally.
    """
    # proxy.stop() flushes + closes the logger and deletes the status file; the finally
    # covers every exit path — SIGINT (KeyboardInterrupt), SIGTERM/SIGHUP (below), and an
    # error during start() — so a stopped proxy always cleans up after itself.
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    for sig in get_shutdown_signals():
        # add_signal_handler is unavailable off the main thread / on some platforms; the
        # process still terminates on those signals, just without the graceful cleanup.
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(sig, stop_event.set)
    try:
        port = await proxy.start()
        print(f"listening on http://127.0.0.1:{port}", flush=True)
        # Wait for whichever comes first: an external signal, or the proxy asking to stop itself.
        waiters = [
            asyncio.create_task(stop_event.wait()),
            asyncio.create_task(proxy.shutdown_requested.wait()),
        ]
        try:
            await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in waiters:
                task.cancel()
            await asyncio.gather(*waiters, return_exceptions=True)
        # A signal always wins the race for exit code 0: the user asked for this, so even if the
        # proxy had just decided to stop itself, reporting a failure would be misleading.
        return 0 if stop_event.is_set() else proxy.shutdown_exit_code
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
    idle_timeout_seconds: Annotated[
        float,
        typer.Option(
            "--idle-timeout-seconds",
            min=0,
            help="Max idle time before shutting down (0 = never, default = 2 hours); live connections count.",
        ),
    ] = DEFAULT_IDLE_TIMEOUT_SECONDS,
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
        idle_timeout_seconds=idle_timeout_seconds,
        ca_cert_override=ca_cert.read_text() if ca_cert else None,
        log_dir=log_dir,
        log_level=log_level,
    )
    proxy = JupyterDeployClientProxy(config)
    try:
        exit_code = asyncio.run(_serve(proxy))
    except KeyboardInterrupt as e:
        raise typer.Exit(code=130) from e
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


def main() -> None:
    """Console-script entry point."""
    app()
