"""Run the existing lab privately and connect it to a web gateway."""
import asyncio
import logging
import os
from pathlib import Path
import re
import signal
import threading
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout, WSMsgType
from http.server import ThreadingHTTPServer

from .dashboard import Lab, handler_for, own_data
from .evidence import SIMULATION
from .relay import API, CHUNK

LOG = logging.getLogger("usv.engine")


async def forward(cmd, local, remote, session, auth):
    """Only call a known endpoint on our own loopback server, never a supplied URL."""
    path, method = cmd["path"], cmd["method"]
    endpoint = urlsplit(path)
    if (endpoint.scheme or endpoint.netloc or endpoint.fragment or
            endpoint.path not in {"/api/" + name for name in API} or
            not (method == "GET" or (method == "POST" and endpoint.path == "/api/jobs")) or
            not re.fullmatch("[0-9a-f]{32}", cmd["id"])):
        raise ValueError("Invalid gateway command")
    reply = remote + "/_engine/reply/" + cmd["id"]
    headers = {"Origin": local, "X-Lab-Token": cmd["token"], "Content-Type": "application/json"}
    async with session.request(method, local + path, headers=headers, allow_redirects=False,
                               data=cmd["body"].encode() if method == "POST" else None) as upstream:
        outgoing = {**auth, "X-Lab-Status": str(upstream.status)}
        for name in ("Content-Type", "Content-Length", "Content-Disposition"):
            if name in upstream.headers:
                outgoing[name] = upstream.headers[name]
        async with session.post(reply, data=upstream.content.iter_chunked(CHUNK), headers=outgoing,
                                allow_redirects=False) as ack:
            ack.raise_for_status()


async def bridge(remote, key, local, lab):
    auth = {"Authorization": "Bearer " + key}
    async with ClientSession(timeout=ClientTimeout(total=None, sock_connect=10), auto_decompress=False) as session:
        while True:
            active = set()

            async def handle(cmd):
                try:
                    await forward(cmd, local, remote, session, auth)
                except (ClientError, OSError, ValueError):
                    LOG.exception("Could not forward request %s", cmd.get("id"))
                    if re.fullmatch("[0-9a-f]{32}", cmd.get("id", "")):
                        try:
                            async with session.post(remote + "/_engine/reply/" + cmd["id"],
                                                    headers={**auth, "X-Lab-Status": "502"},
                                                    json={"error": "Engine request failed"},
                                                    allow_redirects=False) as ack:
                                await ack.read()
                        except (ClientError, OSError):
                            LOG.warning("Gateway unavailable for error response")

            async def samples(ws):
                previous = None
                while True:
                    current = lab.latest_sample
                    if current is not previous and current is not None:
                        await ws.send_json(current)
                        previous = current
                    await asyncio.sleep(.1)

            try:
                async with session.ws_connect(remote + "/_engine/connect", headers=auth, heartbeat=20) as ws:
                    LOG.info("Connected to %s", remote)
                    publisher = asyncio.create_task(samples(ws))
                    try:
                        async for msg in ws:
                            if msg.type == WSMsgType.TEXT:
                                task = asyncio.create_task(handle(msg.json()))
                                active.add(task)
                                task.add_done_callback(active.discard)
                    finally:
                        publisher.cancel()
                        await asyncio.gather(publisher, return_exceptions=True)
            except (ClientError, OSError, asyncio.TimeoutError) as error:
                LOG.warning("Gateway unavailable (%s), retrying in 3 seconds", error)
            finally:
                for task in active:
                    task.cancel()
                await asyncio.gather(*active, return_exceptions=True)
            await asyncio.sleep(3)


async def main():
    remote = (os.getenv("LAB_RELAY_URL") or "http://127.0.0.1:8768").rstrip("/")
    url = urlsplit(remote)
    if (url.scheme not in ("https", "http") or not url.hostname or url.username or url.password
            or url.path or url.fragment or url.query or
            (url.scheme == "http" and url.hostname not in ("127.0.0.1", "localhost", "web"))):
        raise ValueError("LAB_RELAY_URL must be an HTTPS origin (HTTP allowed for local testing)")
    key = os.environ["LAB_ENGINE_KEY"]
    if not key:
        raise ValueError("LAB_ENGINE_KEY must be set")
    root = Path(os.getenv("LAB_DATA") or SIMULATION / "results/lab")
    with own_data(root):
        def publish(sample):
            lab.latest_sample = sample

        lab = Lab(root, on_sample=publish)
        lab.latest_sample = None
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(lab))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        local = f"http://127.0.0.1:{server.server_port}"
        LOG.info("Engine ready at %s; connecting to %s", local, remote)
        link = asyncio.create_task(bridge(remote, key, local, lab))
        stop = asyncio.Event()
        if os.name != "nt":
            asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stop.set)
        marker = os.getenv("LAB_STOP_FILE")
        ready = os.getenv("LAB_READY_FILE")
        if ready:
            Path(ready).touch()
        try:
            while not stop.is_set() and not (marker and Path(marker).exists()):
                if link.done():
                    await link
                await asyncio.sleep(.25)
        finally:
            link.cancel()
            await asyncio.gather(link, return_exceptions=True)
            await asyncio.to_thread(server.shutdown)
            server.server_close()
            thread.join()
            LOG.info("Finishing queued work before shutdown")
            await asyncio.to_thread(lab.close)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
