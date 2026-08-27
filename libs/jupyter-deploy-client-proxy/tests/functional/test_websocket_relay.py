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

    async def test_subprotocol_negotiated_end_to_end(self) -> None:
        # JupyterLab kernels request the v1 subprotocol (binary framing). The proxy must forward
        # it upstream AND echo the negotiated value back downstream, else the browser downgrades
        # to the v0 text protocol while the server speaks v1 and every kernel message fails to
        # deserialize. Regression guard: negotiation must survive both proxy legs.
        proto = "v1.kernel.websocket.jupyter.org"
        port = await self._start_proxy({"Authorization": "Bearer wstok"})
        async with (
            aiohttp.ClientSession() as s,
            s.ws_connect(f"http://127.0.0.1:{port}/ws", protocols=[proto]) as ws,
        ):
            # Downstream (browser-facing) leg echoed the negotiated subprotocol.
            self.assertEqual(ws.protocol, proto)
            # Binary frames round-trip as binary (never coerced to text).
            await ws.send_bytes(b"\x00\x01\x02kernel")
            msg = await ws.receive()
            self.assertEqual(msg.type, aiohttp.WSMsgType.BINARY)
            self.assertEqual(msg.data, b"\x00\x01\x02kernel")
            await ws.close()
        # Upstream leg saw the subprotocol too (aiohttp regenerated the handshake header).
        assert self.origin.ws_upgrade_headers is not None
        self.assertEqual(lower_keys(self.origin.ws_upgrade_headers)["sec-websocket-protocol"], proto)
        self.assertEqual(self.origin.ws_negotiated_protocol, proto)
