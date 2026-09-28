"""Idle auto-shutdown against a real origin, driving the real proxy.

The unit tests poke ``_idle_loop`` directly; these run the whole thing — listener bound, requests
and WebSockets flowing through to the trustme origin — because what counts as "activity" is a
property of the request path, not of the watchdog. A unit test asserting the counters would happily
pass while ``_handle`` forgot to stamp them.

Timeouts here are sub-second by necessity. They are compared against real elapsed time, so the
assertions are one-sided: "did NOT shut down" is checked after a wait several times the timeout, and
"did shut down" is awaited with generous slack, never on a fixed sleep.
"""

import asyncio
import json
import shlex
from pathlib import Path

import aiohttp
from harness import OriginTestCase, write_bundle_argv, write_expiring_then_failing_argv

from jupyter_deploy_client_proxy.constants import REFRESH_FAILED_EXIT_CODE
from jupyter_deploy_client_proxy.server.proxy import JupyterDeployClientProxy

_IDLE_TIMEOUT_SECONDS = 0.3


class TestIdleShutdown(OriginTestCase):
    async def _start(self, idle_timeout_seconds: float = _IDLE_TIMEOUT_SECONDS) -> int:
        argv = write_bundle_argv(self.tmp, "127.0.0.1", self.origin.port, self.origin.ca_pem, {"Authorization": "sub"})
        self.proxy = JupyterDeployClientProxy(self._config(argv, idle_timeout_seconds=idle_timeout_seconds))
        return await self.proxy.start()

    async def test_shuts_itself_down_when_nothing_connects(self) -> None:
        await self._start()
        assert self.proxy is not None

        await asyncio.wait_for(self.proxy.shutdown_requested.wait(), timeout=10)

        # A clean stop: the proxy did what it was configured to do, so nothing failed.
        self.assertEqual(self.proxy.shutdown_exit_code, 0)

    async def test_requests_keep_it_alive(self) -> None:
        port = await self._start()
        assert self.proxy is not None

        # Poll well past the timeout; each request has to push the deadline out.
        async with aiohttp.ClientSession() as session:
            for _ in range(6):
                await asyncio.sleep(_IDLE_TIMEOUT_SECONDS / 2)
                async with session.get(f"http://127.0.0.1:{port}/still-here") as response:
                    self.assertEqual(response.status, 200)
                self.assertFalse(self.proxy.shutdown_requested.is_set())

    async def test_shuts_down_once_requests_stop(self) -> None:
        port = await self._start()
        assert self.proxy is not None

        async with aiohttp.ClientSession() as session, session.get(f"http://127.0.0.1:{port}/hello") as response:
            self.assertEqual(response.status, 200)

        await asyncio.wait_for(self.proxy.shutdown_requested.wait(), timeout=10)

    async def test_open_websocket_holds_it_open_without_traffic(self) -> None:
        # The case a request-only timer would get wrong: a kernel running a long silent computation
        # sends nothing for minutes, but pulling its tunnel would lose the session.
        port = await self._start()
        assert self.proxy is not None

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(f"http://127.0.0.1:{port}/ws") as ws:
                await asyncio.sleep(_IDLE_TIMEOUT_SECONDS * 4)  # several idle windows, zero frames
                self.assertFalse(self.proxy.shutdown_requested.is_set())
                await ws.close()

            # With the socket closed there is nothing left holding it up.
            await asyncio.wait_for(self.proxy.shutdown_requested.wait(), timeout=10)

    async def test_zero_timeout_never_shuts_down(self) -> None:
        await self._start(idle_timeout_seconds=0)
        assert self.proxy is not None

        await asyncio.sleep(_IDLE_TIMEOUT_SECONDS * 4)

        self.assertFalse(self.proxy.shutdown_requested.is_set())
        self.assertIsNone(self.proxy._idle_task)


class TestIdleShutdownConsoleScript(OriginTestCase):
    """The same behaviour through the console script, which is what `jd` actually launches."""

    async def test_process_exits_zero_and_removes_status_file(self) -> None:
        argv = write_bundle_argv(self.tmp, "127.0.0.1", self.origin.port, self.origin.ca_pem, {"Authorization": "sub"})
        log_dir = f"{self.tmp}/idle-logs"
        proc = await asyncio.create_subprocess_exec(
            "jupyter-deploy-client-proxy",
            "--token-command",
            shlex.join(argv),
            "--listen-port",
            "0",
            "--idle-timeout-seconds",
            str(_IDLE_TIMEOUT_SECONDS),
            "--log-dir",
            log_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            assert proc.stdout is not None
            line = (await asyncio.wait_for(proc.stdout.readline(), timeout=15)).decode()
            self.assertIn("listening on", line)

            returncode = await asyncio.wait_for(proc.wait(), timeout=15)

            # Exit 0 and no status file: indistinguishable from a user-requested stop, because it is
            # one — the user configured it. Only a failure (REFRESH_FAILED_EXIT_CODE) leaves a trace.
            self.assertEqual(returncode, 0)
            self.assertNotEqual(returncode, REFRESH_FAILED_EXIT_CODE)
            self.assertFalse(Path(log_dir, "status.json").exists())
        finally:
            if proc.returncode is None:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=15)


class TestRefreshFailureShutdownConsoleScript(OriginTestCase):
    """A proxy whose token command turns permanently broken exits, and says so."""

    async def test_process_exits_78_and_keeps_status_file(self) -> None:
        argv = write_expiring_then_failing_argv(
            self.tmp, "127.0.0.1", self.origin.port, self.origin.ca_pem, {"Authorization": "sub"}
        )
        log_dir = Path(self.tmp, "failed-logs")
        proc = await asyncio.create_subprocess_exec(
            "jupyter-deploy-client-proxy",
            "--token-command",
            shlex.join(argv),
            "--listen-port",
            "0",
            "--refresh-margin-seconds",
            "0",
            "--idle-timeout-seconds",
            "0",  # isolate the refresh-failure path: no idle timer can race it
            "--log-dir",
            str(log_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            assert proc.stdout is not None
            line = (await asyncio.wait_for(proc.stdout.readline(), timeout=15)).decode()
            self.assertIn("listening on", line)

            returncode = await asyncio.wait_for(proc.wait(), timeout=20)

            self.assertEqual(returncode, REFRESH_FAILED_EXIT_CODE)
            # Unlike a clean stop, the status file survives — it is the only thing left to tell a
            # reader the proxy died rather than being stopped, and why.
            status_path = Path(log_dir, "status.json")
            self.assertTrue(status_path.exists())
            self.assertEqual(json.loads(status_path.read_text())["state"], "failed")
        finally:
            if proc.returncode is None:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=15)
