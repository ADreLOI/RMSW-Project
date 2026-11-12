"""Exercise a running test stack, including one small, retained S4-T job."""
import asyncio
import gzip
import io
import os
import sys
import time
import zipfile

from aiohttp import ClientConnectionError, ClientSession, ClientTimeout

ORIGIN = os.getenv("LAB_TEST_ORIGIN", "http://127.0.0.1:8768")


async def main():
    async with ClientSession(ORIGIN, timeout=ClientTimeout(total=90)) as client:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                async with client.get("/health") as r:
                    if (await r.json())["engine_connected"]:
                        break
            except ClientConnectionError:
                pass
            await asyncio.sleep(.5)
        else:
            raise RuntimeError("Engine did not connect within 60 seconds")
        async with client.get("/") as r:
            assert r.status == 200 and 'id="live-grid"' in await r.text()
        async with client.get("/api/catalog") as r:
            catalog = await r.json()
            assert r.status == 200 and len(catalog["runs"]) == 900
        async with client.get("/api/extension") as r:
            assert r.status == 200 and (await r.json())["runs"]
        async with client.get("/api/figure?name=core-mission-time") as r:
            assert r.status == 200 and (await r.read()).startswith(b"\x89PNG")
        async with client.get("/api/trace?dataset=core&run=1000-1-5-S4-T") as r:
            assert r.status == 200 and (await r.json())["policy"] == "S4-T"

        request = {"action": "run", "request": {"policy": "S4-T", "timeout": 120}}
        headers = {"X-Lab-Token": catalog["token"], "Origin": ORIGIN}
        for bad in ({"Origin": ORIGIN}, {**headers, "Origin": "https://invalid.example"}):
            async with client.post("/api/jobs", json=request, headers=bad) as r:
                assert r.status == 403

        async with (client.ws_connect("/live", origin=ORIGIN) as first,
                    client.ws_connect("/live", origin=ORIGIN) as second):
            assert (await first.receive_json())["online"] and (await second.receive_json())["online"]
            async with client.post("/api/jobs", json=request, headers=headers) as r:
                assert r.status == 202, await r.text()
                identity = (await r.json())["id"]

            async def watch(viewer):
                while True:
                    sample = (await viewer.receive_json(timeout=60)).get("sample")
                    if sample and sample["job"] == identity:
                        assert sample["visited"] and len(sample["xy"]) == 2 and sample["t"] > 0
                        return
            await asyncio.gather(watch(first), watch(second))

        for _ in range(90):
            async with client.get("/api/job", params={"id": identity}) as r:
                job = await r.json()
            if job["status"] in ("failed", "interrupted", "passed"):
                break
            await asyncio.sleep(1)
        assert job["status"] == "passed", job
        async with client.get("/api/raw", params={"dataset": identity, "run": "1000-1-5-S4-T"}) as r:
            assert r.status == 200 and "attachment" in r.headers["Content-Disposition"]
            assert b'"event":"session"' in gzip.decompress(await r.read())
        async with client.get("/api/download", params={"dataset": identity, "name": "evidence.zip"}) as r:
            archive = await r.read()
            assert r.status == 200 and int(r.headers["Content-Length"]) == len(archive)
            with zipfile.ZipFile(io.BytesIO(archive)) as z:
                assert "runs.json" in z.namelist() and z.testzip() is None
        print("Two live viewers, API, figures, frozen trace, new run and evidence downloads passed:", identity)


async def check_browser():
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(ORIGIN + "/?lang=en#map")
            await page.wait_for_selector("#engine-dot.on")
            await page.wait_for_function("Boolean(state.traces[state.active])")
            for name in ("link", "log", "core", "extension", "runs", "guide", "presentation", "map"):
                await page.locator(f'button[data-view="{name}"]').click()
                await page.wait_for_selector(f"#view-{name}.active")
            await page.locator('[data-lang="it"]').click()
            await page.locator("#run-form details.advanced summary").click()
            await page.fill("#timeout", "120")
            await page.click("#run-one")
            await page.wait_for_function("state.currentJob && lastSample?.job === state.currentJob")
            await page.wait_for_selector("#live-sample:visible")
            await page.wait_for_function("state.dataset === state.currentJob && Boolean(state.traces[state.active])",
                                         timeout=90000)
            assert not errors, errors
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
    if "--browser" in sys.argv:
        asyncio.run(check_browser())
