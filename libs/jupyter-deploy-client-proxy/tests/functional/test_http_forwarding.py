import aiohttp
from harness import OriginTestCase, lower_keys


class TestHttpForwarding(OriginTestCase):
    async def test_round_trip_preserves_path_and_injects_headers(self) -> None:
        port = await self._start_proxy({"Authorization": "Bearer tok", "x-k8s-aws-id": "dep-1"})
        async with aiohttp.ClientSession() as s, s.get(f"http://127.0.0.1:{port}/lab/api?x=1") as r:
            self.assertEqual(r.status, 200)
            data = await r.json()
        self.assertEqual(data["path"], "/lab/api")
        headers = lower_keys(data["headers"])
        self.assertEqual(headers["authorization"], "Bearer tok")
        self.assertEqual(headers["x-k8s-aws-id"], "dep-1")

    async def test_bundle_header_overrides_incoming(self) -> None:
        port = await self._start_proxy({"Authorization": "Bearer from-bundle"})
        incoming = {"Authorization": "from-browser"}
        async with aiohttp.ClientSession() as s, s.get(f"http://127.0.0.1:{port}/", headers=incoming) as r:
            data = await r.json()
        self.assertEqual(lower_keys(data["headers"])["authorization"], "Bearer from-bundle")

    async def test_rewrites_origin_to_upstream(self) -> None:
        port = await self._start_proxy({"Authorization": "x"})
        incoming = {"Origin": f"http://127.0.0.1:{port}", "Referer": f"http://127.0.0.1:{port}/lab?a=1"}
        async with aiohttp.ClientSession() as s, s.get(f"http://127.0.0.1:{port}/", headers=incoming) as r:
            data = await r.json()
        headers = lower_keys(data["headers"])
        self.assertEqual(headers["origin"], f"https://127.0.0.1:{self.origin.port}")
        self.assertEqual(headers["referer"], f"https://127.0.0.1:{self.origin.port}/lab?a=1")

    async def test_large_body_is_not_capped_by_client_max_size(self) -> None:
        # A ~2 MiB PUT (over aiohttp's default 1 MiB client_max_size) must pass — reproduces a
        # notebook save/upload on /api/contents. read()-ing the body would 413 at the proxy.
        port = await self._start_proxy({"Authorization": "x"})
        body = b"x" * (2 * 1024 * 1024)
        async with (
            aiohttp.ClientSession() as s,
            s.put(f"http://127.0.0.1:{port}/api/contents/nb.ipynb", data=body) as r,
        ):
            self.assertEqual(r.status, 200)

    async def test_repeated_response_headers_are_not_collapsed(self) -> None:
        # Upstream sends two Set-Cookie lines (Jupyter's `_xsrf` + `username-*`). A dict-based
        # forwarder would keep only the last, silently dropping a cookie; both must survive.
        port = await self._start_proxy({"Authorization": "x"})
        async with aiohttp.ClientSession() as s, s.get(f"http://127.0.0.1:{port}/multi-set-cookie") as r:
            self.assertEqual(r.status, 200)
            cookies = r.headers.getall("Set-Cookie")
        self.assertEqual(sorted(cookies), ["a=1; Path=/", "b=2; Path=/"])

    async def test_rejects_cross_origin_browser_request(self) -> None:
        # A hostile page must not be able to drive the loopback proxy: its Origin is not this
        # listener's, so the proxy rejects it BEFORE injecting the credential / rewriting Origin.
        port = await self._start_proxy({"Authorization": "x"})
        async with (
            aiohttp.ClientSession() as s,
            s.get(f"http://127.0.0.1:{port}/", headers={"Origin": "https://evil.com"}) as r,
        ):
            self.assertEqual(r.status, 403)

    async def test_forwarded_origin_matches_host_header(self) -> None:
        # The contract that broke live: the rewritten Origin's netloc MUST equal the Host header the
        # upstream receives, or the app's same-origin check blocks every API/websocket call. Both are
        # derived from (host, port) but by different code paths — our rewrite vs aiohttp's Host — so we
        # assert they agree on whatever the upstream actually saw. (The default-port-443 case, where
        # aiohttp drops the port and a naive rewrite would keep it, is pinned in the unit tests; the
        # functional harness binds an ephemeral port, which can't bind :443 without privileges.)
        port = await self._start_proxy({"Authorization": "x"})
        incoming = {"Origin": f"http://127.0.0.1:{port}"}
        async with aiohttp.ClientSession() as s, s.get(f"http://127.0.0.1:{port}/", headers=incoming) as r:
            data = await r.json()
        headers = lower_keys(data["headers"])
        self.assertEqual(headers["origin"], f"https://{headers['host']}")
