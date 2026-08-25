import aiohttp
from harness import OriginTestCase, lower_keys


class TestWebSocketRelay(OriginTestCase):
    async def test_echo_through_upgrade(self) -> None:
        port = await self._start_proxy({"Authorization": "Bearer wstok"})
        async with aiohttp.ClientSession() as s, s.ws_connect(f"http://127.0.0.1:{port}/ws") as ws:
            await ws.send_str("ping")
            msg = await ws.receive()
            self.assertEqual(msg.data, "ping")
            await ws.close()

    async def test_headers_injected_on_upgrade_handshake(self) -> None:
        port = await self._start_proxy({"Authorization": "Bearer wstok", "x-k8s-aws-id": "dep-9"})
        async with aiohttp.ClientSession() as s, s.ws_connect(f"http://127.0.0.1:{port}/ws") as ws:
            await ws.close()
        assert self.origin.ws_upgrade_headers is not None
        seen = lower_keys(self.origin.ws_upgrade_headers)
        self.assertEqual(seen["authorization"], "Bearer wstok")
        self.assertEqual(seen["x-k8s-aws-id"], "dep-9")
