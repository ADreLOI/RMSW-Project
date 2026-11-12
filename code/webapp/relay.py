"""Single-engine web gateway. The engine makes every connection outbound."""
import asyncio
import hmac
import os
from pathlib import Path
import re
import secrets
import signal
from urllib.parse import urlsplit

from aiohttp import BasicAuth, WSMsgType, web

from webapp import STATIC_DIR as WEB
API = {"catalog", "extension", "figure", "trace", "raw", "jobs", "job", "download"}
ASSETS = {"index.html", "i18n.js", "app.js", "tokens.css", "style.css", "favicon.svg"}
CHUNK = 64 * 1024


def failure(status, message):
    return web.json_response({"error": message}, status=status)


def same_secret(a, b):
    return hmac.compare_digest(a.encode(), b.encode())


class Relay:
    def __init__(self, key, origin, password=None):
        self.key = key
        self.origin = origin.rstrip("/")
        parsed = urlsplit(self.origin)
        self.hosts = {parsed.netloc.lower()}
        if parsed.hostname in ("localhost", "127.0.0.1") and parsed.port:
            self.hosts = {f"localhost:{parsed.port}", f"127.0.0.1:{parsed.port}"}
        self.scheme = parsed.scheme
        self.password = password
        self.engine = None
        self.session = None
        self.pending = {}
        self.latest = None
        self.viewers = set()

    @web.middleware
    async def access(self, request, handler):
        if request.path.startswith("/_engine/"):
            if not same_secret(request.headers.get("Authorization", ""), "Bearer " + self.key):
                return failure(403, "Engine credential required")
        else:
            if request.host.lower() not in self.hosts:
                return failure(403, "Unknown host")
            if self.password:
                try:
                    auth = BasicAuth.decode(request.headers.get("Authorization", ""))
                except ValueError:
                    auth = None
                if not auth or auth.login != "lab" or not same_secret(auth.password, self.password):
                    raise web.HTTPUnauthorized(headers={"WWW-Authenticate": 'Basic realm="USV Research Lab"'})
            if request.method == "POST" or request.path == "/live":
                if request.headers.get("Origin") != f"{self.scheme}://{request.host.lower()}":
                    return failure(403, "Open the dashboard on its configured origin")
        return await handler(request)

    def broadcast(self, snapshot):
        snapshot["session"] = self.session
        self.latest = snapshot
        for queue in self.viewers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(snapshot)

    async def connect(self, request):
        if self.engine is not None:
            return failure(409, "An engine is already connected")
        ws = web.WebSocketResponse(heartbeat=20)
        self.engine = ws
        try:
            await ws.prepare(request)
            self.session = secrets.token_hex(8)
            self.broadcast({"online": True})
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    self.broadcast({"online": True, "sample": msg.json()})
        finally:
            self.engine = None
            self.broadcast({"online": False})
            for _, done, _ in list(self.pending.values()):
                if not done.done():
                    done.set_exception(ConnectionError("Engine disconnected"))
        return ws

    async def live(self, request):
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        queue = asyncio.Queue(maxsize=1)
        self.viewers.add(queue)
        queue.put_nowait(self.latest or {"online": False})

        async def send():
            while True:
                await ws.send_json(await queue.get())

        sender = asyncio.create_task(send())
        try:
            async for _ in ws:
                pass
        finally:
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
            self.viewers.discard(queue)
        return ws

    async def api(self, request):
        name = request.match_info["name"]
        if name not in API or (request.method != "GET" and (name, request.method) != ("jobs", "POST")):
            raise web.HTTPNotFound()
        engine = self.engine
        if engine is None or not engine.prepared or engine.closed:
            return failure(503, "Simulation engine offline")
        if len(self.pending) >= 32:
            return failure(503, "Engine busy")
        body = await request.text() if request.method == "POST" else ""
        ident = secrets.token_hex(16)
        loop = asyncio.get_running_loop()
        done = loop.create_future()
        def expire():
            if not done.done():
                done.set_exception(TimeoutError("Engine did not start a response"))
        timer = loop.call_later(180, expire)
        self.pending[ident] = request, done, timer
        try:
            await engine.send_json({"id": ident, "method": request.method, "path": request.raw_path,
                                    "token": request.headers.get("X-Lab-Token", ""), "body": body})
            return await done
        except (OSError, asyncio.TimeoutError) as error:
            return failure(502, str(error) or "Engine timed out")
        finally:
            timer.cancel()
            self.pending.pop(ident, None)

    async def reply(self, request):
        item = self.pending.pop(request.match_info["id"], None)
        if item is None or item[1].done():
            return failure(410, "Request expired")
        browser, done, timer = item
        timer.cancel()
        headers = {"Content-Type": request.headers["Content-Type"], "Cache-Control": "no-store",
                   "X-Content-Type-Options": "nosniff"}
        for name in ("Content-Length", "Content-Disposition"):
            if name in request.headers:
                headers[name] = request.headers[name]
        response = web.StreamResponse(status=int(request.headers["X-Lab-Status"]), headers=headers)
        try:
            await response.prepare(browser)
            async for chunk in request.content.iter_chunked(CHUNK):
                await response.write(chunk)
            await response.write_eof()
        except BaseException:
            if browser.transport:
                browser.transport.close()
            raise
        finally:
            if not done.done():
                done.set_result(response)
        return web.Response(status=204)

    async def asset(self, request):
        name = request.match_info["name"] or "index.html"
        if name not in ASSETS and not re.fullmatch(r"fonts/[\w-]+\.(ttf|woff2|txt)", name):
            raise web.HTTPNotFound()
        return web.FileResponse(WEB / name, headers={
            "Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                                       "img-src 'self' data: blob:; object-src 'none'; frame-ancestors 'none'",
        })

    def application(self):
        app = web.Application(middlewares=[self.access], client_max_size=8192)
        app.router.add_get("/_engine/connect", self.connect)
        app.router.add_post("/_engine/reply/{id}", self.reply)
        app.router.add_get("/live", self.live)
        app.router.add_get("/health", self.health)
        app.router.add_route("*", "/api/{name}", self.api)
        app.router.add_get("/{name:.*}", self.asset)
        return app

    async def health(self, request):
        online = self.engine is not None and self.engine.prepared and not self.engine.closed
        return web.json_response({"service": "usv-web", "engine_connected": online})


async def main():
    port = int(os.getenv("PORT", "8768"))
    origin = os.getenv("LAB_PUBLIC_ORIGIN") or f"http://127.0.0.1:{port}"
    parsed = urlsplit(origin)
    password = os.getenv("LAB_WEB_PASSWORD")
    if parsed.hostname not in ("127.0.0.1", "localhost") and (parsed.scheme != "https" or not password):
        raise SystemExit("Set an HTTPS LAB_PUBLIC_ORIGIN and LAB_WEB_PASSWORD for hosted access.")
    key = os.environ["LAB_ENGINE_KEY"]
    if not key:
        raise SystemExit("LAB_ENGINE_KEY must be set")
    relay = Relay(key, origin, password)
    runner = web.AppRunner(relay.application(), access_log=None, shutdown_timeout=3)
    await runner.setup()
    try:
        site = web.TCPSite(runner, os.getenv("LAB_WEB_BIND", "127.0.0.1"), port)
        await site.start()
        ready = os.getenv("LAB_READY_FILE")
        if ready:
            Path(ready).touch()
        stop = asyncio.Event()
        if os.name != "nt":
            asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stop.set)
        marker = os.getenv("LAB_STOP_FILE")
        while not stop.is_set() and not (marker and Path(marker).exists()):
            await asyncio.sleep(.25)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
