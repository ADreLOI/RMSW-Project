import asyncio
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import zipfile
from http.server import ThreadingHTTPServer

from aiohttp import BasicAuth, ClientSession, WSServerHandshakeError, web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request

from webapp.relay import Relay

PAGES = "https://adreloi.github.io"


class RelayAccessTests(unittest.IsolatedAsyncioTestCase):
    """Exercise access decisions without requiring a listening socket."""

    def request(self, method, path, **headers):
        return make_mocked_request(method, path, headers={
            "Host": "relay.example", "Origin": PAGES, **headers})

    async def accept(self, request):
        return web.Response(status=204)

    async def test_public_is_explicit_and_keeps_engine_authentication(self):
        relay = Relay("engine-key", "https://relay.example", "old-password", PAGES)
        request = self.request("POST", "/api/jobs")
        self.assertEqual((await relay.access(request, self.accept)).status, 401)
        relay = Relay("engine-key", "https://relay.example", "old-password", PAGES, public_access=True)
        self.assertEqual((await relay.access(request, self.accept)).status, 204)
        for credential, status in (("", 403), ("Bearer wrong", 403), ("Bearer engine-key", 204)):
            request = self.request("GET", "/_engine/connect", Authorization=credential)
            self.assertEqual((await relay.access(request, self.accept)).status, status)

    async def test_public_keeps_origin_and_host_checks(self):
        relay = Relay("engine-key", "https://relay.example", browser_origin=PAGES, public_access=True)
        for headers in ({"Origin": "https://evil.example"}, {"Origin": ""}, {"Host": "evil.example"}):
            response = await relay.access(self.request("POST", "/api/jobs", **headers), self.accept)
            self.assertEqual(response.status, 403)

    async def test_public_offline_jobs_are_rejected_without_queueing(self):
        relay = Relay("engine-key", "https://relay.example", browser_origin=PAGES, public_access=True)
        request = self.request("POST", "/api/jobs")
        request.match_info["name"] = "jobs"
        response = await relay.access(request, relay.api)
        self.assertEqual(response.status, 503)
        self.assertEqual(json.loads(response.text)["error"], "Simulation engine offline")
        self.assertFalse(relay.pending)


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await self.start_relay()

    async def start_relay(self, public_access=False):
        self.relay = Relay("engine-test-key", "http://127.0.0.1:1", "browser-test-password", PAGES,
                           public_access=public_access)
        self.client = TestClient(TestServer(self.relay.application()))
        await self.client.start_server()
        self.origin = str(self.client.make_url("")).rstrip("/")
        self.relay.hosts.add(self.origin.removeprefix("http://"))
        self.headers = {"Origin": PAGES, "Authorization": BasicAuth("lab", "browser-test-password").encode()}
        if public_access:
            self.headers.pop("Authorization")

    async def asyncTearDown(self):
        await self.client.close()

    async def ticket(self):
        response = await self.client.post("/live-ticket", headers=self.headers)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        return (await response.json())["ticket"]

    async def test_public_health_and_protected_api(self):
        response = await self.client.get("/health")
        self.assertEqual(response.status, 200)
        self.assertFalse((await response.json())["engine_connected"])
        response = await self.client.get("/api/catalog", headers={"Origin": PAGES})
        self.assertEqual(response.status, 401)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], PAGES)
        response = await self.client.get("/_engine/connect", headers=self.headers)
        self.assertEqual(response.status, 403)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        response = await self.client.get("/health", headers={"Host": "evil.example"})
        self.assertEqual(response.status, 403)

    async def test_preflight_exact_origin_and_headers(self):
        headers = {"Origin": PAGES, "Access-Control-Request-Method": "POST",
                   "Access-Control-Request-Headers": "authorization, content-type, x-lab-token"}
        response = await self.client.options("/api/jobs", headers=headers)
        self.assertEqual(response.status, 204)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], PAGES)
        self.assertNotIn("Access-Control-Allow-Credentials", response.headers)
        for override in ({"Origin": PAGES + ".evil.example"}, {"Origin": "null"},
                         {"Access-Control-Request-Method": "DELETE"}, {"Access-Control-Request-Headers": "X-Unknown"}):
            response = await self.client.options("/api/jobs", headers={**headers, **override})
            self.assertEqual(response.status, 403)

    async def test_one_use_expiring_origin_bound_live_ticket(self):
        ticket = await self.ticket()
        with self.assertRaises(WSServerHandshakeError):
            await self.client.ws_connect("/live?ticket=" + ticket, origin="https://evil.example")
        socket = await self.client.ws_connect("/live?ticket=" + ticket, origin=PAGES)
        self.assertFalse((await socket.receive_json())["online"])
        await socket.close()
        with self.assertRaises(WSServerHandshakeError):
            await self.client.ws_connect("/live?ticket=" + ticket, origin=PAGES)
        ticket = await self.ticket()
        self.relay.tickets[ticket] = (time.monotonic() - 1, PAGES)
        with self.assertRaises(WSServerHandshakeError):
            await self.client.ws_connect("/live?ticket=" + ticket, origin=PAGES)

    async def test_local_basic_auth_socket_is_still_supported(self):
        socket = await self.client.ws_connect("/live", origin=self.origin,
                                             auth=BasicAuth("lab", "browser-test-password"))
        self.assertFalse((await socket.receive_json())["online"])
        await socket.close()
        response = await self.client.post("/api/jobs", headers={"Authorization": self.headers["Authorization"]}, json={})
        self.assertEqual(response.status, 403)

    async def test_local_launcher_without_password_serves_assets_and_live(self):
        self.relay.password = None
        for path in ("/", "/config.js", "/connection.js"):
            response = await self.client.get(path)
            self.assertEqual(response.status, 200)
        socket = await self.client.ws_connect("/live", origin=self.origin)
        self.assertFalse((await socket.receive_json())["online"])
        await socket.close()

    async def test_streaming_response_has_cors_before_headers_are_sent(self):
        engine = await self.client.ws_connect("/_engine/connect", headers={"Authorization": "Bearer engine-test-key"})
        request = asyncio.create_task(self.client.get("/api/download?dataset=core&name=runs.json", headers=self.headers))
        command = await engine.receive_json(timeout=5)
        payload = b"x" * (200 * 1024)
        response = await self.client.post("/_engine/reply/" + command["id"], data=payload, headers={
            "Authorization": "Bearer engine-test-key", "X-Lab-Status": "200",
            "Content-Type": "application/octet-stream", "Content-Disposition": 'attachment; filename="evidence.zip"'})
        self.assertEqual(response.status, 204)
        result = await request
        self.assertEqual(result.headers["Access-Control-Allow-Origin"], PAGES)
        self.assertIn("Content-Disposition", result.headers["Access-Control-Expose-Headers"])
        self.assertEqual(await result.read(), payload)
        await engine.close()

    async def test_real_engine_job_replay_and_archive(self):
        await self.check_real_engine_job()

    async def test_public_engine_job_replay_and_archive(self):
        await self.client.close()
        await self.start_relay(public_access=True)
        await self.check_real_engine_job()

    async def test_public_access_waits_for_engine_and_keeps_engine_key_and_origin_checks(self):
        await self.client.close()
        await self.start_relay(public_access=True)
        for path, method in (("/api/catalog", "get"), ("/api/jobs", "post")):
            response = await getattr(self.client, method)(path, headers=self.headers)
            self.assertEqual(response.status, 503)
        response = await self.client.post("/live-ticket", headers={"Origin": "https://evil.example"})
        self.assertEqual(response.status, 403)
        response = await self.client.get("/_engine/connect", headers=self.headers)
        self.assertEqual(response.status, 403)
        socket = await self.client.ws_connect("/live?ticket=" + await self.ticket(), origin=PAGES)
        self.assertFalse((await socket.receive_json())["online"])
        engine = await self.client.ws_connect("/_engine/connect", headers={"Authorization": "Bearer engine-test-key"})
        self.assertTrue((await socket.receive_json(timeout=5))["online"])
        await engine.close()
        self.assertFalse((await socket.receive_json(timeout=5))["online"])
        response = await self.client.post("/api/jobs", headers=self.headers, json={"action": "run"})
        self.assertEqual(response.status, 503)
        self.assertFalse(self.relay.pending)
        await socket.close()

    async def check_real_engine_job(self):
        from usv_sim.dashboard import Lab, handler_for
        from usv_sim.engine import bridge
        with tempfile.TemporaryDirectory(prefix="rmsw-relay-test-") as temporary:
            lab = Lab(Path(temporary) / "jobs")
            lab.latest_sample = None
            lab.on_sample = lambda sample: setattr(lab, "latest_sample", sample)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(lab))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            task = asyncio.create_task(bridge(self.origin, "engine-test-key",
                                              f"http://127.0.0.1:{server.server_port}", lab))
            try:
                async with asyncio.timeout(30):
                    while not self.relay.engine or not self.relay.engine.prepared:
                        await asyncio.sleep(.01)
                    response = await self.client.get("/api/catalog", headers=self.headers)
                    catalog = await response.json()
                    self.assertEqual(len(catalog["runs"]), 900)
                    headers = {**self.headers, "X-Lab-Token": catalog["token"]}
                    response = await self.client.post("/api/jobs", headers=self.headers,
                                                      json={"action": "run", "request": {"timeout": 120}})
                    self.assertEqual(response.status, 403)
                    socket = await self.client.ws_connect("/live?ticket=" + await self.ticket(), origin=PAGES)
                    self.assertTrue((await socket.receive_json())["online"])
                    response = await self.client.post("/api/jobs", headers=headers,
                                                      json={"action": "run", "request": {"policy": "S4-T", "timeout": 120}})
                    self.assertEqual(response.status, 202)
                    identity = (await response.json())["id"]
                    while True:
                        response = await self.client.get("/api/job?id=" + identity, headers=self.headers)
                        record = await response.json()
                        if record["status"] in ("passed", "failed"):
                            break
                        await asyncio.sleep(.1)
                    self.assertEqual(record["status"], "passed", record)
                    while not (await socket.receive_json(timeout=5)).get("sample"):
                        pass
                    await socket.close()
                    response = await self.client.get(f"/api/trace?dataset={identity}&run=1000-1-5-S4-T", headers=self.headers)
                    self.assertEqual(response.status, 200)
                    self.assertEqual((await response.json())["result"]["stop_s"], 120)
                    response = await self.client.get(f"/api/download?dataset={identity}&name=evidence.zip", headers=self.headers)
                    with zipfile.ZipFile(io.BytesIO(await response.read())) as archive:
                        self.assertIn("runs.json", archive.namelist())
                        self.assertIn("artifact-sha256.json", archive.namelist())
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                await asyncio.to_thread(server.shutdown)
                server.server_close()
                thread.join()
                await asyncio.to_thread(lab.close)


if __name__ == "__main__":
    unittest.main()
