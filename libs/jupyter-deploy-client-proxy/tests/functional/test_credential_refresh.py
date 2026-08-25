import asyncio

import aiohttp
from harness import OriginTestCase, lower_keys, write_counter_emitter_argv

from jupyter_deploy_client_proxy.server.proxy import JupyterDeployClientProxy


class TestCredentialRefresh(OriginTestCase):
    async def test_injected_credential_rotates_before_expiry(self) -> None:
        argv = write_counter_emitter_argv(self.tmp, "127.0.0.1", self.origin.port, self.origin.ca_pem, ttl_seconds=2)
        self.proxy = JupyterDeployClientProxy(self._config(argv, refresh_margin_seconds=1.5))  # refresh ~0.5s later
        port = await self.proxy.start()

        async def current_counter() -> str:
            async with aiohttp.ClientSession() as s, s.get(f"http://127.0.0.1:{port}/") as r:
                data = await r.json()
            return lower_keys(data["headers"])["x-counter"]

        first = await current_counter()
        changed: str | None = None
        for _ in range(20):
            await asyncio.sleep(0.25)
            value = await current_counter()
            if value != first:
                changed = value
                break

        self.assertIsNotNone(changed, "X-Counter never changed; the refresh loop did not re-exec the token command")
        assert changed is not None
        self.assertGreater(int(changed), int(first))
