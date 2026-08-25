import aiohttp
import trustme
from harness import OriginTestCase


class TestTlsPinning(OriginTestCase):
    async def test_matching_pin_connects(self) -> None:
        port = await self._start_proxy({"Authorization": "x"})  # pins the origin's real CA
        async with aiohttp.ClientSession() as s, s.get(f"http://127.0.0.1:{port}/") as r:
            self.assertEqual(r.status, 200)

    async def test_wrong_pin_refuses_upstream(self) -> None:
        wrong_ca_pem = trustme.CA().cert_pem.bytes().decode()
        port = await self._start_proxy({"Authorization": "x"}, ca_pem=wrong_ca_pem)
        async with aiohttp.ClientSession() as s, s.get(f"http://127.0.0.1:{port}/") as r:
            self.assertEqual(r.status, 502)
