"""Single-engine web gateway. The engine makes every connection outbound."""
import asyncio
import hmac
import os
from pathlib import Path
import re
import secrets
import signal
import time
from urllib.parse import urlsplit

from aiohttp import BasicAuth, WSMsgType, web

from webapp import STATIC_DIR as WEB
API = {"catalog", "extension", "figure", "trace", "raw", "jobs", "job", "download"}
ASSETS = {"index.html", "i18n.js", "app.js", "connection.js", "config.js", "tokens.css", "style.css", "favicon.svg"}
CHUNK = 64 * 1024


def failure(status, message):
    return web.json_response({"error": message}, status=status)


def same_secret(a, b):
    return hmac.compare_digest(a.encode(), b.encode())


class Relay:
    def __init__(self, key, origin, password=None, browser_origin=None):
        self.key = key
        self.origin = origin.rstrip("/")
        parsed = urlsplit(self.origin)
        self.hosts = {parsed.netloc.lower()}
        if parsed.hostname in ("localhost", "127.0.0.1") and parsed.port:
            self.hosts = {f"localhost:{parsed.port}", f"127.0.0.1:{parsed.port}"}
        self.scheme = parsed.scheme
        self.password = password
        self.browser_origin = browser_origin
        self.tickets = {}
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
            origin = request.headers.get("Origin")
            same_origin = f"{self.scheme}://{request.host.lower()}"
            permitted = origin == same_origin or bool(self.browser_origin and origin == self.browser_origin)
            if origin and not permitted:
                return failure(403, "Browser origin not allowed")
            if request.method == "OPTIONS":
                if not permitted or request.path not in {"/live-ticket", *(f"/api/{name}" for name in API)}:
                    return failure(403, "Preflight not allowed")
                if request.headers.get("Access-Control-Request-Method") not in {"GET", "POST"}:
                    return failure(403, "Method not allowed")
                names = {x.strip().lower() for x in request.headers.get("Access-Control-Request-Headers", "").split(",") if x.strip()}
                if names - {"authorization", "content-type", "x-lab-token"}:
                    return failure(403, "Headers not allowed")
                return web.Response(status=204, headers={
                    "Access-Control-Allow-Methods": "GET, POST",
                    "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Lab-Token",
                    "Access-Control-Max-Age": "300"})
            if request.path == "/health" and request.method == "GET":
                return await handler(request)
            ticket_ok = False
            if request.path == "/live" and "ticket" in request.query:
                entry = self.tickets.pop(request.query["ticket"], None)
                ticket_ok = bool(entry and entry[0] > time.monotonic() and entry[1] == origin)
                if not ticket_ok:
                    return failure(401, "Live ticket expired or already used")
            if self.password and not ticket_ok:
                try:
                    auth = BasicAuth.decode(request.headers.get("Authorization", ""))
                except ValueError:
                    auth = None
                if not auth or auth.login != "lab" or not same_secret(auth.password, self.password):
                    if self.browser_origin and origin == self.browser_origin:
                        return failure(401, "Browser password required")
                    raise web.HTTPUnauthorized(headers={"WWW-Authenticate": 'Basic realm="USV Research Lab"'})
            if request.method == "POST" or request.path == "/live":
                if not permitted:
                    return failure(403, "Open the dashboard on its configured origin")
        return await handler(request)

    async def cors(self, request, response):
        # Streaming downloads prepare their headers before the middleware returns.
        if (self.browser_origin and request.headers.get("Origin") == self.browser_origin
                and not request.path.startswith("/_engine/") and request.host.lower() in self.hosts):
            response.headers["Access-Control-Allow-Origin"] = self.browser_origin
            response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
            response.headers["Vary"] = "Origin"

    async def live_ticket(self, request):
        now = time.monotonic()
        self.tickets = {key: entry for key, entry in self.tickets.items() if entry[0] > now}
        if len(self.tickets) >= 64:
            return failure(429, "Too many pending live connections")
        ticket = secrets.token_urlsafe(32)
        self.tickets[ticket] = (now + 30, request.headers.get("Origin"))
        return web.json_response({"ticket": ticket}, headers={"Cache-Control": "no-store"})

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
        app.on_response_prepare.append(self.cors)
        app.router.add_get("/_engine/connect", self.connect)
        app.router.add_post("/_engine/reply/{id}", self.reply)
        app.router.add_get("/live", self.live)
        app.router.add_route("*", "/live-ticket", self.ticket_route)
        app.router.add_get("/health", self.health)
        app.router.add_route("*", "/api/{name}", self.api)
        app.router.add_get("/{name:.*}", self.asset)
        return app

    async def ticket_route(self, request):
        if request.method != "POST":
            return failure(405, "POST required")
        return await self.live_ticket(request)

    async def health(self, request):
        online = self.engine is not None and self.engine.prepared and not self.engine.closed
        return web.json_response({"service": "usv-web", "engine_connected": online})


async def main():
    port = int(os.getenv("PORT", "8768"))
    origin = os.getenv("LAB_PUBLIC_ORIGIN") or os.getenv("RENDER_EXTERNAL_URL") or f"http://127.0.0.1:{port}"
    parsed = urlsplit(origin)
    password = os.getenv("LAB_WEB_PASSWORD")
    if parsed.hostname not in ("127.0.0.1", "localhost") and (parsed.scheme != "https" or not password):
        raise SystemExit("Set an HTTPS LAB_PUBLIC_ORIGIN and LAB_WEB_PASSWORD for hosted access.")
    key = os.environ["LAB_ENGINE_KEY"]
    if not key:
        raise SystemExit("LAB_ENGINE_KEY must be set")
    browser_origin = os.getenv("LAB_BROWSER_ORIGIN") or None
    if browser_origin:
        browser = urlsplit(browser_origin)
        if browser.scheme != "https" or not browser.netloc or browser.path or browser.query or browser.fragment or browser.username:
            raise SystemExit("LAB_BROWSER_ORIGIN must be an HTTPS origin without a path.")
    relay = Relay(key, origin, password, browser_origin)
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
