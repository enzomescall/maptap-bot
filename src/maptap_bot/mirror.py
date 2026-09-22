"""Serve the site's current frontend at a local origin, allowing static reads only."""

from pathlib import PurePosixPath
from urllib.parse import urlsplit

import httpx
from playwright.async_api import BrowserContext, Route

ORIGIN = "http://127.0.0.1:8765"
STATIC_SUFFIXES = {
    ".html", ".js", ".css", ".json", ".geojson", ".jpg", ".jpeg", ".png",
    ".webp", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".mp3", ".wav", ".ogg",
}
STATIC_HOSTS = {"maptap.gg", "tiles.maptap.gg", "www.gstatic.com"}


class Mirror:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.cache: dict[str, httpx.Response] = {}
        self.blocked: set[str] = set()

    async def install(self, context: BrowserContext) -> None:
        await context.route("**/*", self.serve)
        await context.route_web_socket("**/*", lambda socket: socket.close())

    async def serve(self, route: Route) -> None:
        request = route.request
        url = urlsplit(request.url)
        local = url.netloc == "127.0.0.1:8765"
        static = PurePosixPath(url.path).suffix.lower() in STATIC_SUFFIXES
        allowed = (local or url.hostname in STATIC_HOSTS) and (static or url.path == "/")
        if request.method != "GET" or not allowed:
            self.blocked.add(f"{request.method} {url.scheme}://{url.netloc}{url.path}")
            await route.abort()
            return

        source = "https://maptap.gg" + url.path if local else request.url.split("?")[0]
        # Keep asset versions, but exclude local game options from the HTML fetch.
        if url.query and url.path != "/":
            source += "?" + url.query
        if source not in self.cache:
            self.cache[source] = await self.client.get(source)
        response = self.cache[source]
        await route.fulfill(
            status=response.status_code,
            body=response.content,
            headers={
                "content-type": response.headers.get("content-type", "application/octet-stream"),
                "access-control-allow-origin": "*",
            },
        )
