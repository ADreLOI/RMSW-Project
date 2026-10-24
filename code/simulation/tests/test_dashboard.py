from dataclasses import asdict
import hashlib
import gzip
import http.client
from http.server import ThreadingHTTPServer
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import threading
import time
import unittest
import zipfile

from usv_sim.dashboard import Lab, handler_for
from usv_sim.evidence import SIMULATION, inventory, load_design, trace
from usv_sim.experiment import digest, dump
from usv_sim.model import Config, make_scenario, run
from usv_sim.workflow import run_bundle, validate_request
from usv_sim.verify import verify


class EvidenceTests(unittest.TestCase):
    def test_single_cli_uses_frozen_margins_and_protects_existing_output(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            root = Path(temporary)
            design = {"config": asdict(Config(width=4, height=3, timeout_s=60)),
                      "margins": {"trend": 4, "persistence": 4}}
            design["sha256"] = digest(design)
            dump(root / "design.json", design)
            command = [sys.executable, "-m", "usv_sim.experiment", "single", "--design", str(root / "design.json"), "--output", str(root / "single")]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(trace(root / "single" / "single.jsonl.gz")["margins"], design["margins"])
            original = (root / "single" / "single.json").read_bytes()
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 2)
            self.assertEqual((root / "single" / "single.json").read_bytes(), original)
            forbidden = subprocess.run([sys.executable, "-m", "usv_sim.experiment", "single", "--output", str(SIMULATION / "results/core")], capture_output=True, text=True)
            self.assertEqual(forbidden.returncode, 2)
            self.assertIn("outside the frozen core", forbidden.stderr)

    def test_frozen_evaluation_cannot_override_exponent(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            output = Path(temporary) / "untouched"
            outcome = subprocess.run([sys.executable, "-m", "usv_sim.experiment", "evaluate", "--exponent", "2.5", "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(outcome.returncode, 2)
            self.assertIn("frozen config", outcome.stderr)
            self.assertFalse(output.exists())

    def test_trace_terminal_is_exact_and_does_not_invent_queues(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            path = Path(temporary) / "trace.gz"
            c = Config(width=4, height=3, timeout_s=61)
            result, _ = run(c, make_scenario(c, 0, 5, False), "S1", log_path=path)
            data = trace(path)
            self.assertEqual(data["frames"][-1]["coverage"], result["coverage"])
            self.assertEqual(data["tracks"][-1][0], result["stop_s"])
            self.assertEqual(data["raw_schema"], 2)
            self.assertTrue(data["sampling"]["terminal_queues_recorded"])
            self.assertEqual(data["frames"][-1]["queues"], [[], []])
            self.assertEqual(data["frames"][-1]["targets"], [None, None])
            self.assertIsNone(data["frames"][-1]["radio"])
            self.assertEqual(sum(t is not None for t in data["first_seen"]), 12)
            self.assertEqual(data["raw_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                events = [json.loads(line) for line in stream]
            # Preserve support for the retained original raw-log schema.
            for event in events:
                event.pop("boats", None)
                event.pop("schema", None)
                if event["event"] == "stop":
                    event.pop("queues"); event.pop("targets")
            legacy = Path(temporary) / "legacy.gz"
            with gzip.open(legacy, "wt", encoding="utf-8") as stream:
                for event in events: stream.write(json.dumps(event) + "\n")
            old = trace(legacy)
            self.assertEqual(old["raw_schema"], 1)
            self.assertFalse(old["sampling"]["motion_states_recorded"])
            self.assertEqual(old["motion_states"], [])
            self.assertIsNone(old["frames"][-1]["queues"])
            self.assertIsNone(old["frames"][-1]["targets"])

    def test_trace_exact_task_state_and_post_exchange_order(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            path = Path(temporary) / "trace.gz"
            c = Config(width=6, height=3, timeout_s=43)
            run(c, make_scenario(c, 0, 5, False), "S2", log_path=path, forced_radio=lambda k: True)
            data = trace(path)
            self.assertEqual([s["t"] for s in data["motion_states"]], list(range(44)))
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                events = [json.loads(line) for line in stream]
            expected = {}
            for event in events:
                if "boats" in event:
                    t = event.get("t", 43 if event["event"] == "stop" else 0)
                    expected[t] = event["boats"]
            for state in data["motion_states"]:
                actual = expected[state["t"]]
                self.assertEqual(state["queues"], [b["queue"] for b in actual])
                self.assertEqual(state["targets"], [b["target"] for b in actual])
            # At 10 s, replenished queues must supersede the pre-exchange tick.
            tick = next(e for e in events if e["event"] == "tick" and e["t"] == 10)
            session = next(e for e in events if e["event"] == "session" and e["t"] == 10)
            self.assertNotEqual([b["queue"] for b in tick["boats"]], session["queues"])
            self.assertEqual(data["motion_states"][10]["queues"], session["queues"])

    def test_design_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            path = Path(temporary) / "design.json"
            data = {"config": asdict(Config()), "margins": {"trend": 4, "persistence": 4}}
            data["sha256"] = digest(data)
            dump(path, data)
            self.assertEqual(load_design(path), data)
            data["config"]["long_queue"] = 13
            dump(path, data)
            with self.assertRaises(ValueError): load_design(path)

    def test_invalid_experiment_inputs_are_rejected(self):
        for data in ({"seed": True}, {"length": 3}, {"slowdown": "false"}, {"timeout": 7201},
                     {"exponent": float("nan")}, {"policy": "oracle"}, {"path": "../../"}, {"seed": -1}):
            with self.subTest(data=data), self.assertRaises(ValueError): validate_request(data)

    def test_artifact_inventory_matches_zip_and_excludes_mutable_progress(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            root = Path(temporary)
            dump(root / "result.json", {"complete": True})
            dump(root / "job.json", {"status": "running"})
            hashes = inventory(root)
            dump(root / "job.json", {"status": "passed"})
            self.assertNotIn("job.json", hashes)
            with zipfile.ZipFile(root / "evidence.zip") as bundle:
                for name, expected in hashes.items():
                    self.assertEqual(hashlib.sha256(bundle.read(name)).hexdigest(), expected)
                self.assertNotIn("job.json", bundle.namelist())

    def test_verifier_rejects_modified_artifact(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            root = Path(temporary)
            dump(root / "runs.json", [])
            inventory(root)
            self.assertTrue(verify(root)["all_artifact_hashes_match"])
            dump(root / "runs.json", [{"changed": True}])
            with self.assertRaisesRegex(ValueError, "hash mismatch"): verify(root)

    def test_scientific_comparison_excludes_timing_but_checks_outcome(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            root = Path(temporary)
            row = {"seed": 1, "slowdown": True, "fade_length": 5, "policy": "S4-T", "coverage": 1,
                   "wall_s": 1, "work": {"forecast": {"arithmetic": 141, "cpu_ns": 123}}}
            dump(root / "reference" / "runs.json", [row])
            row["wall_s"] = 9; row["work"]["forecast"]["cpu_ns"] = 999
            dump(root / "new" / "runs.json", [row]); inventory(root / "new")
            self.assertTrue(verify(root / "new", root / "reference")["all_scientific_values_match"])
            row["coverage"] = .9
            dump(root / "new" / "runs.json", [row]); inventory(root / "new")
            with self.assertRaisesRegex(ValueError, "scientific run values differ"): verify(root / "new", root / "reference")


class DashboardIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.root = Path(self.temporary.name)
        core = self.root / "core"
        design = {"config": asdict(Config(width=4, height=3, timeout_s=60)),
                  "margins": {"trend": 4, "persistence": 4}}
        design["sha256"] = digest(design)
        dump(core / "frozen-design.json", design)
        self.lab = Lab(self.root / "jobs", core)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.lab))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.lab.close(); self.temporary.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers or {})
        response = connection.getresponse(); content = response.read(); code = response.status
        connection.close()
        return code, content

    def test_http_requires_local_token_and_rejects_traversal(self):
        code, _ = self.request("POST", "/api/jobs", {"action": "run"})
        self.assertEqual(code, 403)
        code, _ = self.request("POST", "/api/jobs", {"action": "run"},
                               {"X-Lab-Token": self.lab.token, "Origin": "https://example.org"})
        self.assertEqual(code, 403)
        for path in ("/api/trace?dataset=../../&run=1000-1-5-S1", "/api/download?name=../../pyproject.toml", "/api/job?id=../../"):
            code, _ = self.request("GET", path)
            self.assertEqual(code, 400)
        code, _ = self.request("GET", "/", headers={"Host": "unrelated.example"})
        self.assertEqual(code, 403)

    def test_real_job_api_produces_verified_replay_and_bundle(self):
        code, body = self.request("POST", "/api/jobs", {"action": "run", "request": {"timeout": 60}},
                                  {"X-Lab-Token": self.lab.token})
        self.assertEqual(code, 202)
        identity = json.loads(body)["id"]
        for _ in range(200):
            record = self.lab.snapshot(identity)
            if record["status"] in ("passed", "failed"): break
            time.sleep(.05)
        self.assertEqual(record["status"], "passed", record)
        code, body = self.request("GET", f"/api/job?id={identity}")
        job = json.loads(body)
        self.assertEqual(len(job["runs"]), 5)
        self.assertTrue(all(r["path_exponent"] == 2 for r in job["runs"]))
        code, body = self.request("GET", f"/api/trace?dataset={identity}&run=1000-1-5-S4-T")
        data = json.loads(body)
        self.assertEqual(code, 200)
        self.assertTrue(data["verified"])
        self.assertEqual(data["margins"], {"trend": 4, "persistence": 4})
        code, body = self.request("GET", f"/api/download?dataset={identity}&name=evidence.zip")
        self.assertEqual(code, 200)
        self.assertTrue(body.startswith(b"PK"))
        self.assertFalse((self.lab.core / "runs.json").exists(), "Exploration must not alter core evidence")


if __name__ == "__main__": unittest.main()
