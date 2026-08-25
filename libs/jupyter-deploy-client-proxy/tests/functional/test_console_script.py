import asyncio
import shlex

import aiohttp
from harness import OriginTestCase, write_bundle_argv


class TestConsoleScript(OriginTestCase):
    async def test_serves_then_terminates(self) -> None:
        argv = write_bundle_argv(self.tmp, "127.0.0.1", self.origin.port, self.origin.ca_pem, {"Authorization": "sub"})
        proc = await asyncio.create_subprocess_exec(
            "jupyter-deploy-client-proxy",
            "--token-command",
            shlex.join(argv),
            "--listen-port",
            "0",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            assert proc.stdout is not None
            line = (await asyncio.wait_for(proc.stdout.readline(), timeout=15)).decode()
            self.assertIn("listening on", line)
            port = int(line.strip().rsplit(":", 1)[1])
            async with aiohttp.ClientSession() as s, s.get(f"http://127.0.0.1:{port}/hello") as r:
                self.assertEqual(r.status, 200)
        finally:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=15)
