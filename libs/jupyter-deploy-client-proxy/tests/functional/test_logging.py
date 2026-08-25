"""Functional coverage of the three logging behaviors, driving the real proxy:
a/ file-based, b/ size rotation, c/ stream-only (stderr, via the console script)."""

import asyncio
import shlex
import shutil
from pathlib import Path

import aiohttp
from harness import OriginTestCase, write_bundle_argv

from jupyter_deploy_client_proxy.server.config import JupyterDeployClientProxyConfig, LogLevel
from jupyter_deploy_client_proxy.server.proxy import JupyterDeployClientProxy

_LOG_GLOB = "[0-9][0-9][0-9][0-9].log"


class TestFileLogging(OriginTestCase):
    async def test_writes_lifecycle_and_request_lines_to_file(self) -> None:
        log_dir = Path(self.tmp) / "proxy-logs"
        argv = write_bundle_argv(self.tmp, "127.0.0.1", self.origin.port, self.origin.ca_pem, {"Authorization": "x"})
        self.proxy = JupyterDeployClientProxy(
            JupyterDeployClientProxyConfig(token_argv=argv, log_dir=log_dir, log_level=LogLevel.DEBUG)
        )
        port = await self.proxy.start()
        async with aiohttp.ClientSession() as s, s.get(f"http://127.0.0.1:{port}/lab") as r:
            await r.read()
        await self.proxy.stop()
        self.proxy = None  # already stopped; skip teardown double-stop

        files = sorted(log_dir.glob(_LOG_GLOB))
        self.assertTrue(files, "expected a 0000.log file")
        content = "".join(p.read_text() for p in files)
        self.assertIn("listening on", content)
        self.assertIn("GET /lab -> 200", content)  # per-request DEBUG line
        self.assertIn("proxy stopped", content)


class TestLogRotation(OriginTestCase):
    async def test_rolls_across_multiple_files_under_load(self) -> None:
        log_dir = Path(self.tmp) / "rotating-logs"
        argv = write_bundle_argv(self.tmp, "127.0.0.1", self.origin.port, self.origin.ca_pem, {"Authorization": "x"})
        self.proxy = JupyterDeployClientProxy(
            JupyterDeployClientProxyConfig(
                token_argv=argv,
                log_dir=log_dir,
                log_level=LogLevel.DEBUG,
                log_max_bytes=200,  # tiny → the DEBUG request lines roll files quickly
                log_backup_count=50,  # keep them all so we can count rollovers
            )
        )
        port = await self.proxy.start()
        async with aiohttp.ClientSession() as s:
            for i in range(30):
                async with s.get(f"http://127.0.0.1:{port}/req{i}") as r:
                    await r.read()
        await self.proxy.stop()
        self.proxy = None

        files = sorted(log_dir.glob(_LOG_GLOB))
        self.assertGreater(len(files), 1, "expected the log to roll over into multiple files")


class TestLogDirRecovery(OriginTestCase):
    async def test_reopens_after_log_dir_deleted_mid_session(self) -> None:
        log_dir = Path(self.tmp) / "recover-logs"
        argv = write_bundle_argv(self.tmp, "127.0.0.1", self.origin.port, self.origin.ca_pem, {"Authorization": "x"})
        self.proxy = JupyterDeployClientProxy(
            JupyterDeployClientProxyConfig(token_argv=argv, log_dir=log_dir, log_level=LogLevel.DEBUG)
        )
        port = await self.proxy.start()
        async with aiohttp.ClientSession() as s:
            async with s.get(f"http://127.0.0.1:{port}/before") as r:
                await r.read()
            shutil.rmtree(log_dir)  # nuke the whole log dir out of band, mid-session
            self.assertFalse(log_dir.exists())
            async with s.get(f"http://127.0.0.1:{port}/after") as r:  # its DEBUG log line triggers recovery
                await r.read()
        await self.proxy.stop()
        self.proxy = None

        self.assertTrue(log_dir.exists(), "log dir was not recreated after out-of-band deletion")
        files = sorted(log_dir.glob(_LOG_GLOB))
        self.assertTrue(files, "logger did not reopen a file after deletion")
        self.assertIn("GET /after -> 200", "".join(p.read_text() for p in files))


class TestStreamLogging(OriginTestCase):
    async def test_logs_to_stderr_when_no_log_dir(self) -> None:
        argv = write_bundle_argv(self.tmp, "127.0.0.1", self.origin.port, self.origin.ca_pem, {"Authorization": "x"})
        proc = await asyncio.create_subprocess_exec(
            "jupyter-deploy-client-proxy",
            "--token-command",
            shlex.join(argv),
            "--listen-port",
            "0",  # no --log-dir → stderr handler
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            assert proc.stdout is not None
            line = (await asyncio.wait_for(proc.stdout.readline(), timeout=15)).decode()
            port = int(line.strip().rsplit(":", 1)[1])
            async with aiohttp.ClientSession() as s, s.get(f"http://127.0.0.1:{port}/") as r:
                await r.read()
        finally:
            proc.terminate()
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        self.assertIn("listening on", stderr.decode())
