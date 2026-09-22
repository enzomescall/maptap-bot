"""Network isolation is essential even if the upstream frontend changes."""

import unittest
from unittest.mock import AsyncMock, Mock

import httpx

from maptap_bot.mirror import Mirror, ORIGIN


class MirrorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fetched = []

        def fetch(request):
            self.fetched.append(str(request.url))
            return httpx.Response(200, text="asset", headers={"content-type": "text/javascript"})

        self.client = httpx.AsyncClient(transport=httpx.MockTransport(fetch))
        self.mirror = Mirror(self.client)

    async def asyncTearDown(self):
        await self.client.aclose()

    def route(self, url, method="GET"):
        return Mock(request=Mock(url=url, method=method), abort=AsyncMock(), fulfill=AsyncMock())

    async def test_static_frontend_is_mirrored_and_cached(self):
        route = self.route(ORIGIN + "/js/game-init.js?v=16")
        await self.mirror.serve(route)
        await self.mirror.serve(route)
        self.assertEqual(self.fetched, ["https://maptap.gg/js/game-init.js?v=16"])
        self.assertEqual(route.fulfill.call_count, 2)
        route.abort.assert_not_called()

    async def test_backend_requests_and_every_write_are_blocked(self):
        for url, method in [
            (ORIGIN + "/js/game-init.js", "POST"),
            (ORIGIN + "/api/score", "GET"),
            ("https://firestore.googleapis.com/data.json", "GET"),
            ("https://us-central1-jjexperiment-12af6.cloudfunctions.net/saveScore", "POST"),
            ("https://www.googletagmanager.com/gtag/js", "GET"),
            ("https://maptap.gg.evil.example/asset.js", "GET"),
        ]:
            with self.subTest(url=url, method=method):
                route = self.route(url, method)
                await self.mirror.serve(route)
                route.abort.assert_awaited_once()
                route.fulfill.assert_not_called()
        self.assertEqual(self.fetched, [])

    async def test_game_options_do_not_reach_upstream(self):
        await self.mirror.serve(self.route(ORIGIN + "/?devmode=1&overrideday=September20"))
        self.assertEqual(self.fetched, ["https://maptap.gg/"])

    async def test_redirects_do_not_escape_the_allowlist(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(302, headers={"location": "https://example.com/backend"})
        )) as client:
            mirror = Mirror(client)
            route = self.route(ORIGIN + "/asset.js")
            await mirror.serve(route)
            self.assertEqual(route.fulfill.call_args.kwargs["status"], 302)
            self.assertNotIn("location", route.fulfill.call_args.kwargs["headers"])
