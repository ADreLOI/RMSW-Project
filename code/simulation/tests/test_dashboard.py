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


class InterfaceTests(unittest.TestCase):
    """Static checks of the browser assets, the shared palette and the read-only extension API."""
    WEB = SIMULATION / "src" / "usv_sim" / "web"

    def dictionary(self):
        import re
        text = (self.WEB / "i18n.js").read_text(encoding="utf-8")
        english, italian = text.split("\n  it: {", 1)
        italian = italian.split("\n};", 1)[0]
        keys = lambda block: re.findall(r'^\s+"([^"]+)":', block, re.M)
        return keys(english), keys(italian)

    def test_i18n_keys_match_and_cover_every_use(self):
        import re
        english, italian = self.dictionary()
        self.assertEqual(len(english), len(set(english)), "duplicate English keys")
        self.assertEqual(len(italian), len(set(italian)), "duplicate Italian keys")
        self.assertEqual(set(english), set(italian))
        html = (self.WEB / "index.html").read_text(encoding="utf-8")
        script = (self.WEB / "app.js").read_text(encoding="utf-8")
        used = set(re.findall(r'data-i18n(?:-aria|-html)?="([^"]+)"', html)) | set(re.findall(r'\bt\("([^"]+)"', script))
        families = {"policy.": 11, "policyLong.": 11, "pres.section.": 7, "job.status.": 6, "job.action.": 4, "work.": 3}
        for prefix, count in families.items():
            self.assertEqual(sum(k.startswith(prefix) for k in english), count, prefix)
        steps = set(re.findall(r'key: "(\w+)"', script))
        used |= {f"tourstep.{s}.{part}" for s in steps for part in "tb"}
        used |= {f"link.{s}{suffix}" for s in ("connected", "fade", "budget", "range") for suffix in ("", "Note")}
        used |= {f"arch.{a}{suffix}" for a in ("browser", "post", "queue", "workflow", "model", "results", "replay")
                 for suffix in ("", "Sub", "Code", "Long")}
        self.assertEqual(sorted(used - set(english)), [])

    def test_palette_is_shared_between_tokens_and_figures(self):
        from usv_sim.plotstyle import COLORS, USV, tokens
        css = tokens()
        self.assertEqual(set(COLORS), {"S1", "S2", "S3", "S4-T", "S4-P", "S4-E", "S4-K", "S4-G", "S4-L", "S4-M", "S4-O"})
        self.assertEqual(len(set(COLORS.values())), 11, "policy colours must be distinct")
        self.assertEqual(USV, (css["usv-1"], css["usv-2"]))
        self.assertNotIn(css["accent"], COLORS.values(), "the accent is reserved for interface elements")
        self.assertNotIn(css["accent"], USV)

    def test_figure_rows_round_trip_exactly(self):
        from usv_sim.figures import read_rows, typed
        self.assertIs(typed("True"), True)
        self.assertEqual(typed("30"), 30)
        self.assertEqual(typed(repr(0.1 + 0.2)), 0.1 + 0.2)
        self.assertIsNone(typed(""))
        rows = read_rows(SIMULATION / "results" / "core" / "condition-summary.csv")
        self.assertEqual(len(rows), 30)
        self.assertTrue(all(isinstance(r["slowdown"], bool) and isinstance(r["restricted_mean_s"], float) for r in rows))


class ExtensionApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.lab = Lab(Path(self.temporary.name) / "jobs")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.lab))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.lab.close(); self.temporary.cleanup()

    def get(self, path):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("GET", path)
        response = connection.getresponse()
        result = response.status, response.getheader("Content-Type"), response.read()
        connection.close()
        return result

    def test_run_names_accept_extension_policies_only(self):
        from usv_sim.dashboard import RUN_NAME
        for name in ("2000-1-5-S4-G", "1000-0-2-S4-O", "1000-1-10-S1"):
            self.assertTrue(RUN_NAME.fullmatch(name), name)
        for name in ("2000-1-5-S4-X", "2000-1-5-S5", "2000-2-5-S1", "2000-1-3-S1", "../2000-1-5-S1"):
            self.assertIsNone(RUN_NAME.fullmatch(name), name)
        code, _, _ = self.get("/api/trace?dataset=extension&run=2000-1-5-S4-X")
        self.assertEqual(code, 400)

    @unittest.skipUnless((SIMULATION / "results" / "extension" / "extension-design.json").exists(), "extension summaries absent")
    def test_extension_summary_comes_from_retained_files(self):
        code, kind, body = self.get("/api/extension")
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertEqual(data["design"]["policies"][-1], "S4-O")
        self.assertEqual(len(data["summary"]), 6 * len(data["design"]["policies"]))
        retained = json.loads((SIMULATION / "results" / "extension" / "runs.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["runs"]), len(retained))
        self.assertEqual({r["restricted_s"] for r in data["runs"]}, {r["restricted_s"] for r in retained})
        code, _, _ = self.get("/api/download?dataset=extension&name=../core/runs.json")
        self.assertEqual(code, 400)
        code, _, body = self.get("/api/download?dataset=extension&name=condition-summary.csv")
        self.assertEqual(code, 200)

    def test_figure_endpoint_is_whitelisted_and_returns_png(self):
        for path in ("/api/figure?name=../../x", "/api/figure?name=core-condition&slowdown=maybe&length=5",
                     "/api/figure?name=core-condition&slowdown=true&length=3"):
            code, _, _ = self.get(path)
            self.assertEqual(code, 400, path)
        code, kind, body = self.get("/api/figure?name=core-condition&slowdown=true&length=5")
        self.assertEqual((code, kind), (200, "image/png"))
        self.assertTrue(body.startswith(b"\x89PNG"))

    def test_static_assets_and_fonts(self):
        for path, kind in (("/tokens.css", "text/css"), ("/i18n.js", "text/javascript"), ("/fonts/Poppins-Bold.ttf", "font/ttf"),
                           ("/fonts/OFL.txt", "text/plain")):
            code, content_type, _ = self.get(path)
            self.assertEqual(code, 200, path)
            self.assertTrue(content_type.startswith(kind), (path, content_type))
        for path in ("/fonts/../dashboard.py", "/fonts/missing.ttf", "/dashboard.py"):
            code, _, _ = self.get(path)
            self.assertIn(code, (400, 404), path)


if __name__ == "__main__": unittest.main()
