"""Loopback-only research dashboard with a serial, persistent experiment queue."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import traceback
from urllib.parse import parse_qs, urlsplit
import webbrowser
import psutil

from .evidence import SIMULATION, inventory, load_design, provenance, sha256, trace, utc_now
from .experiment import dump
from .model import POLICIES
from .plots import export_figures
from .workflow import new_id, pipeline, run_bundle, validate_request

WEB = Path(__file__).parent / "web"
CORE = SIMULATION / "results" / "core"
RUN_NAME = re.compile(r"\d{1,10}-[01]-(?:2|5|10)-(?:S1|S2|S3|S4-T|S4-P)")
JOB_ID = re.compile(r"\d{8}T\d{6}-[a-f0-9]{8}")


def read_json(path, fallback=None):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else fallback


def csv_rows(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


@lru_cache(maxsize=12)
def cached_trace(path, modified_ns, size):
    return trace(path)


class Lab:
    def __init__(self, root, core=CORE):
        self.root, self.core = Path(root).resolve(), Path(core).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.design = load_design(self.core / "frozen-design.json")
        self.token = secrets.token_urlsafe(32)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="experiment")
        self.lock = threading.RLock()
        self.jobs = {}
        for path in self.root.glob("*/job.json"):
            if not JOB_ID.fullmatch(path.parent.name):
                continue
            record = read_json(path)
            if record["status"] in ("running", "queued", "packaging") and not (record.get("source") == "cli" and psutil.pid_exists(record.get("owner_pid", -1))):
                record.update(status="interrupted", message="Server stopped before completion; partial evidence retained")
                dump(path, record)
            self.jobs[record["id"]] = record

    def close(self):
        self.executor.shutdown(wait=True)

    def record(self, identity, **fields):
        with self.lock:
            self.jobs[identity].update(fields, updated_utc=utc_now())
            dump(self.root / identity / "job.json", self.jobs[identity])

    def submit(self, action, data):
        if action not in ("run", "tests", "smoke", "full"):
            raise ValueError("Unknown action")
        if action == "run":
            data = validate_request(data)
        elif data:
            raise ValueError("This action does not accept experiment fields")
        with self.lock:
            if sum(j["status"] in ("running", "queued") for j in self.jobs.values()) >= 4:
                raise ValueError("Four jobs are already queued; wait for one to finish")
            identity = new_id()
            destination = self.root / identity
            destination.mkdir(exist_ok=False)
            self.jobs[identity] = {"id": identity, "action": action, "request": data, "status": "queued",
                                   "created_utc": utc_now(), "message": "Queued", "done": 0, "total": 1}
            self.record(identity)
        self.executor.submit(self.execute, identity)
        return self.snapshot(identity)

    def execute(self, identity):
        record = self.snapshot(identity)
        destination = self.root / identity
        self.record(identity, status="running", started_utc=utc_now())
        progress = lambda message, done, total: self.record(identity, message=message, done=done, total=total)
        try:
            action = record["action"]
            if action == "run":
                rows = run_bundle(destination, record["request"], self.core / "frozen-design.json", progress)
                export_figures(destination / "figures", rows)
            elif action in ("smoke", "full"):
                pipeline(destination, action, progress=progress)
            else:
                provenance(destination, self.design, {"action": "tests"})
                progress("Running scientific and dashboard tests", 0, 1)
                with (destination / "tests.log").open("w", encoding="utf-8") as stream:
                    completed = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                                               cwd=SIMULATION, stdout=stream, stderr=subprocess.STDOUT, text=True)
                dump(destination / "test-result.json", {"exit_code": completed.returncode, "passed": completed.returncode == 0})
                if completed.returncode:
                    raise RuntimeError("Test suite failed; inspect tests.log")
            self.record(identity, status="packaging", message="Hashing and packaging artifacts")
            inventory(destination)
            self.record(identity, status="passed", message="Complete · evidence verified and packaged", done=1, total=1,
                        finished_utc=utc_now())
            # job.json is mutable progress metadata; the immutable bundle excludes it.
        except Exception as error:
            (destination / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
            self.record(identity, status="failed", message=str(error), finished_utc=utc_now())
            inventory(destination)

    def snapshot(self, identity=None):
        with self.lock:
            for path in self.root.glob("*/job.json"):
                if JOB_ID.fullmatch(path.parent.name):
                    try:
                        external = read_json(path)
                    except json.JSONDecodeError:
                        continue  # A CLI process may be writing progress right now.
                    if external.get("source") == "cli":
                        self.jobs[external["id"]] = external
            data = self.jobs[identity] if identity else sorted(self.jobs.values(), key=lambda j: j["created_utc"], reverse=True)
            return json.loads(json.dumps(data))

    def run_path(self, dataset, name):
        if not RUN_NAME.fullmatch(name):
            raise ValueError("Invalid run identifier")
        if dataset == "core":
            path = self.core / "raw" / f"{name}.jsonl.gz"
            if not path.exists() and name == "1000-1-5-S4-T":
                path = SIMULATION / "examples" / "trend-seed1000-slowdown-L5.jsonl.gz"
        elif JOB_ID.fullmatch(dataset) and dataset in self.jobs:
            path = self.root / dataset / "raw" / f"{name}.jsonl.gz"
        else:
            raise ValueError("Invalid dataset identifier")
        if not path.is_file():
            raise FileNotFoundError("Raw trace is not retained here. Run this paired scenario to regenerate it in a new bundle.")
        return path

    def trace(self, dataset, name):
        path = self.run_path(dataset, name)
        stat = path.stat()
        data = cached_trace(str(path), stat.st_mtime_ns, stat.st_size)
        if dataset == "core":
            expected = read_json(self.core / "raw-log-sha256.json", {}).get(f"{name}.jsonl.gz")
            if expected and data["raw_sha256"] != expected:
                raise ValueError("Raw trace hash differs from the frozen evidence inventory")
        return {**data, "dataset": dataset, "name": name}

    def catalog(self):
        rows = read_json(self.core / "runs.json", [])
        available = {p.name.removesuffix(".jsonl.gz") for p in (self.core / "raw").glob("*.jsonl.gz")}
        if (SIMULATION / "examples" / "trend-seed1000-slowdown-L5.jsonl.gz").exists():
            available.add("1000-1-5-S4-T")
        tables = {name: csv_rows(self.core / f"{name}.csv") for name in
                  ("condition-summary", "paired-contrasts", "component-resources", "outage-diagnostics")
                  if (self.core / f"{name}.csv").exists()}
        return {"schema": 1, "token": self.token, "design": self.design, "runs": rows,
                "available_traces": sorted(available), "tables": tables,
                "warnings": read_json(self.core / "warning-summary.json", []),
                "benchmark": read_json(self.core / "host-benchmark.json", {}),
                "verification": read_json(self.core / "verification.json", {}),
                "evaluation": read_json(self.core / "evaluation-manifest.json", {}),
                "analysis": read_json(self.core / "analysis-manifest.json", {}),
                "environment": read_json(self.core / "environment.json", {}),
                "jobs": self.snapshot()}

    def download(self, dataset, name):
        if dataset == "core":
            allowed = {"runs.json", "frozen-design.json", "condition-summary.csv", "paired-contrasts.csv",
                       "component-resources.csv", "warning-summary.json", "verification.json", "host-benchmark.json",
                       "raw-log-sha256.json", "evaluation-manifest.json", "analysis-manifest.json", "environment.json"}
            if name not in allowed:
                raise ValueError("Unknown core export")
            return self.core / name
        if not JOB_ID.fullmatch(dataset) or dataset not in self.jobs:
            raise ValueError("Invalid dataset identifier")
        allowed = {"evidence.zip", "runs.json", "run-summary.csv", "provenance.json", "pipeline.json", "tests.log",
                   "error.log", "artifact-sha256.json", "test-result.json", "figures/paired-mission.png",
                   "figures/paired-mission.pdf", "figures/paired-mission.svg"}
        if name not in allowed:
            raise ValueError("Unknown job export")
        return self.root / dataset / name


def handler_for(lab):
    class Handler(BaseHTTPRequestHandler):
        server_version = "USVResearchLab/1.0"

        def log_message(self, format, *args):
            pass

        def send(self, code, data, content_type="application/json; charset=utf-8", filename=None):
            body = json.dumps(data, allow_nan=False, separators=(",", ":")).encode() if not isinstance(data, bytes) else data
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

        def do_GET(self):
            if not self.valid_host():
                self.send(403, {"error": "Loopback host required"}); return
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            arg = lambda key, default="": query.get(key, [default])[0]
            try:
                if url.path == "/api/catalog":
                    self.send(200, lab.catalog())
                elif url.path == "/api/jobs":
                    self.send(200, lab.snapshot())
                elif url.path == "/api/job":
                    record = lab.snapshot(arg("id"))
                    record["runs"] = read_json(lab.root / record["id"] / "runs.json", [])
                    log = lab.root / record["id"] / "tests.log"
                    record["test_log"] = log.read_text(encoding="utf-8")[-24000:] if log.exists() else None
                    record["provenance"] = read_json(lab.root / record["id"] / "provenance.json")
                    self.send(200, record)
                elif url.path == "/api/trace":
                    self.send(200, lab.trace(arg("dataset", "core"), arg("run")))
                elif url.path == "/api/raw":
                    path = lab.run_path(arg("dataset", "core"), arg("run"))
                    self.send(200, path.read_bytes(), "application/gzip", path.name)
                elif url.path == "/api/download":
                    path = lab.download(arg("dataset", "core"), arg("name"))
                    self.send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream", path.name)
                elif url.path in ("/", "/index.html", "/app.js", "/style.css", "/favicon.svg"):
                    path = WEB / ("index.html" if url.path == "/" else url.path[1:])
                    self.send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "text/plain")
                else:
                    self.send(404, {"error": "Not found"})
            except (ValueError, KeyError) as error:
                self.send(400, {"error": str(error)})
            except FileNotFoundError as error:
                self.send(404, {"error": str(error)})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                traceback.print_exc()
                self.send(500, {"error": "Evidence could not be verified. See server diagnostics."})

        def do_POST(self):
            origin = self.headers.get("Origin")
            expected = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            if not self.valid_host() or (origin and origin not in expected) or self.headers.get("X-Lab-Token") != lab.token:
                self.send(403, {"error": "Open the local dashboard to submit jobs"}); return
            if self.path != "/api/jobs":
                self.send(404, {"error": "Not found"}); return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    raise ValueError("Invalid request size")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict) or set(body) - {"action", "request"}:
                    raise ValueError("Invalid job request")
                self.send(202, lab.submit(body.get("action"), body.get("request", {})))
            except (ValueError, TypeError) as error:
                self.send(400, {"error": str(error)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--data", type=Path, default=SIMULATION / "results" / "lab")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be 1024..65535")
    lab = Lab(args.data)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(lab))
    except OSError as error:
        lab.close()
        parser.exit(1, f"Cannot open port {args.port}: {error}. Try --port 8769.\n")
    print(f"USV Research Lab: http://127.0.0.1:{args.port}\nEvidence: {lab.root}\nCtrl+C stops the server after active work finishes.", flush=True)
    if not args.no_browser:
        webbrowser.open(f"http://127.0.0.1:{args.port}")
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        print("Finishing queued experiments before shutdown…", flush=True)
    finally:
        server.server_close()
        lab.close()


if __name__ == "__main__":
    main()
