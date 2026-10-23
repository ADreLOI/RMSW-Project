"""Immutable experiment bundles and a repeatable test -> simulate -> verify workflow."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from .analysis import reconstruct, write_csv
from .evidence import SIMULATION, inventory, load_design, provenance, utc_now
from .experiment import dump, worker
from .model import Config, POLICIES


def new_id():
    return time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:8]


def validate_request(data):
    if not isinstance(data, dict) or set(data) - {"seed", "length", "slowdown", "policy", "exponent", "timeout"}:
        raise ValueError("Unknown experiment fields")
    request = {"seed": 1000, "length": 5, "slowdown": True, "policy": "all",
               "exponent": 2.0, "timeout": 7200, **data}
    for name, lo, hi in (("seed", 0, 2147483647), ("timeout", 60, 7200)):
        if type(request[name]) is not int or not lo <= request[name] <= hi:
            raise ValueError(f"{name} must be an integer in [{lo}, {hi}]")
    if type(request["length"]) is not int or request["length"] not in (2, 5, 10):
        raise ValueError("length must be 2, 5 or 10 exchanges")
    if type(request["slowdown"]) is not bool:
        raise ValueError("slowdown must be a boolean")
    if request["policy"] not in (*POLICIES, "all"):
        raise ValueError("Unknown policy")
    if type(request["exponent"]) not in (float, int) or not 1.5 <= request["exponent"] <= 3.0:
        raise ValueError("exponent must be in [1.5, 3.0]")
    return request


def run_bundle(destination, request, design_path, progress=lambda message, done, total: None):
    """One scenario, one or five policies, no tuning on evaluation seeds."""
    request = validate_request(request)
    destination = Path(destination)
    design = load_design(design_path)
    data = {**design["config"], "path_exponent": request["exponent"], "timeout_s": request["timeout"]}
    config = Config(**data)
    dump(destination / "request.json", request)
    if (destination / "provenance.json").exists():
        source = json.loads((destination / "provenance.json").read_text(encoding="utf-8"))
    else:
        source = provenance(destination, design, request)
    policies = POLICIES if request["policy"] == "all" else (request["policy"],)
    rows, checks = [], []
    for i, policy in enumerate(policies):
        progress(f"Simulating {policy}", i, len(policies))
        name = f"{request['seed']}-{int(request['slowdown'])}-{request['length']}-{policy}.jsonl.gz"
        path = destination / "raw" / name
        row = worker((asdict(config), request["seed"], request["length"], request["slowdown"],
                      policy, design["margins"], path))
        rebuilt, _ = reconstruct(path)
        assert rebuilt == {k: v for k, v in row.items() if k not in ("warnings", "wall_s")}
        rows.append(row)
        checks.append({"policy": policy, "independent_metrics_match": True, "raw": f"raw/{name}"})
        dump(destination / "runs.json", rows)
    dump(destination / "effective-config.json", data)
    dump(destination / "verification.json", {"raw_runs_reconstructed": len(rows), "checks": checks})
    simple = [{k: r[k] for k in ("policy", "seed", "slowdown", "fade_length", "complete", "completion_s",
                               "restricted_s", "coverage", "redundant", "attempted_bytes", "delivered_bytes",
                               "distance_m", "conflicts", "budget_failures")} for r in rows]
    write_csv(destination / "run-summary.csv", simple)
    dump(destination / "run-manifest.json", {"schema": 1, "completed_utc": utc_now(),
         "classification": "exploratory / reproduction; not added to frozen evaluation",
         "effective_config": data, "margins": design["margins"], "runs": len(rows),
         "design_sha256": design["sha256"], "source_tree_sha256": source["source_tree_sha256"]})
    progress("Verified all raw logs; packaging evidence", len(policies), len(policies))
    return rows


def pipeline(destination, preset="smoke", workers=2, benchmark=False, progress=lambda *args: None,
             design_path=None, request_data=None):
    destination = Path(destination)
    design_path = Path(design_path or SIMULATION / "results" / "core" / "frozen-design.json")
    design = load_design(design_path)
    provenance(destination, design, validate_request(request_data or {}) if preset == "scenario" else
               {"preset": preset, "workers": workers, "benchmark": benchmark})
    steps = []

    def command(name, args):
        progress(name, len(steps), 5 if benchmark else 4)
        record = {"name": name, "command": [sys.executable, *args], "started_utc": utc_now(), "status": "running"}
        steps.append(record)
        dump(destination / "pipeline.json", {"preset": preset, "steps": steps, "status": "running"})
        started = time.perf_counter()
        with (destination / f"{name}.log").open("w", encoding="utf-8") as log:
            outcome = subprocess.run([sys.executable, *args], cwd=SIMULATION, stdout=log,
                                     stderr=subprocess.STDOUT, text=True)
        record.update(exit_code=outcome.returncode, elapsed_s=time.perf_counter() - started,
                      status="passed" if outcome.returncode == 0 else "failed", finished_utc=utc_now())
        dump(destination / "pipeline.json", {"preset": preset, "steps": steps, "status": record["status"]})
        if outcome.returncode:
            raise RuntimeError(f"{name} failed; see {destination / (name + '.log')}")

    try:
        command("tests", ["-m", "unittest", "discover", "-s", "tests", "-v"])
        if preset == "full":
            command("evaluate", ["-m", "usv_sim.experiment", "evaluate", "--output", str(destination), "--workers", str(workers)])
            command("analyze", ["-m", "usv_sim.analysis", "--input", str(destination), "--paper", str(destination / "figures")])
        else:
            started = time.perf_counter()
            rows = run_bundle(destination, request_data or {}, design_path, progress)
            steps.append({"name": "paired-smoke", "status": "passed", "runs": len(rows),
                          "elapsed_s": time.perf_counter() - started})
            from .plots import export_figures
            export_figures(destination / "figures", rows)
            steps.append({"name": "figures", "status": "passed"})
        if benchmark:
            command("benchmark", ["-m", "usv_sim.benchmark", "--output", str(destination / "host-benchmark.json")])
        dump(destination / "pipeline.json", {"preset": preset, "steps": steps, "status": "passed", "finished_utc": utc_now()})
    except Exception:
        dump(destination / "pipeline.json", {"preset": preset, "steps": steps, "status": "failed", "finished_utc": utc_now()})
        raise
    finally:
        inventory(destination)
    progress("Evidence bundle ready", 1, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=("smoke", "full", "scenario"), default="smoke")
    parser.add_argument("--design", type=Path)
    parser.add_argument("--request", type=Path, help="Captured request.json, for the scenario preset")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--benchmark", action="store_true", help="Windows isolated RAM procedure; adds host timing")
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("workers must be 1..8")
    if (args.preset == "scenario") != (args.request is not None):
        parser.error("Use --preset scenario and --request together")
    request_data = validate_request(json.loads(args.request.read_text(encoding="utf-8"))) if args.request else None
    destination = (args.output or SIMULATION / "results" / "lab" / new_id()).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    print(f"Evidence directory: {destination}", flush=True)
    record = {"id": destination.name, "source": "cli", "owner_pid": os.getpid(), "action": "run" if args.preset == "scenario" else args.preset,
              "request": request_data or {}, "status": "running", "created_utc": utc_now(), "done": 0, "total": 1,
              "message": "Starting workflow"}
    def progress(message, done, total):
        record.update(message=message, done=done, total=total, updated_utc=utc_now())
        dump(destination / "job.json", record)
        print(f"{done}/{total} {message}", flush=True)
    progress("Starting workflow", 0, 1)
    try:
        pipeline(destination, args.preset, args.workers, args.benchmark, progress, args.design, request_data)
    except Exception as error:
        record.update(status="failed", message=str(error), finished_utc=utc_now())
        dump(destination / "job.json", record)
        raise
    record.update(status="passed", message="Complete · evidence verified and packaged", done=1, total=1, finished_utc=utc_now())
    dump(destination / "job.json", record)
    print(f"Completed: {destination / 'evidence.zip'}", flush=True)


if __name__ == "__main__":
    main()
