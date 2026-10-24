"""Build browser views from recorded events; never invent missing terminal state."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

from .analysis import read_events, reconstruct
from .experiment import digest, dump, environment
from .model import Config

SIMULATION = Path(__file__).resolve().parents[2]
REPOSITORY = SIMULATION.parents[1]


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_design(path):
    design = json.loads(Path(path).read_text(encoding="utf-8"))
    unsigned = {k: v for k, v in design.items() if k != "sha256"}
    if digest(unsigned) != design.get("sha256"):
        raise ValueError("Frozen design hash mismatch")
    Config(**design["config"])
    return design


def provenance(destination, design, request):
    """Capture executable source, settings and host before starting a run."""
    destination = Path(destination)
    files = sorted((SIMULATION / "src" / "usv_sim").rglob("*"))
    files += sorted((SIMULATION / "tests").glob("*.py"))
    files += sorted((SIMULATION / "scripts").glob("*.py"))
    files += [SIMULATION / "pyproject.toml", SIMULATION / "README.md"]
    hashes = {}
    for source in files:
        if not source.is_file() or "__pycache__" in source.parts:
            continue
        relative = source.relative_to(SIMULATION)
        target = destination / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        hashes[str(relative).replace("\\", "/")] = sha256(source)
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPOSITORY, text=True,
            stderr=subprocess.DEVNULL).splitlines()
    except (OSError, subprocess.CalledProcessError):
        status = None
    record = {"schema": 1, "created_utc": utc_now(), "request": request,
              "design_sha256": design["sha256"], "source_sha256": hashes,
              "source_tree_sha256": digest(hashes), "git_status": status,
              "environment": environment(),
              "limits": "Synthetic coverage and radio model. Host timing is not energy. "
                        "Exploratory runs do not extend the frozen evaluation."}
    dump(destination / "provenance.json", record)
    dump(destination / "frozen-design.json", design)
    preset = "scenario" if "policy" in request else request.get("preset", "smoke")
    request_option = " --request request.json" if preset == "scenario" else ""
    benchmark_option = " --benchmark" if request.get("benchmark") else ""
    command = ("python -m unittest discover -s source/tests -v" if request.get("action") == "tests" else
               f"python -m usv_sim.workflow --preset {preset} --design frozen-design.json{request_option}{benchmark_option} --output ../reproduced-bundle")
    (destination / "REPRODUCE.md").write_text(
        "# Reproduce this evidence bundle\n\nExtract the ZIP into its own folder. Python 3.10+ is required.\n\n"
        "```powershell\npython -m pip install -e source\n"
        f"{command}\n"
        "```\n\nThe output directory must be new. The workflow runs its captured tests first. "
        "CPU timings, process memory, wall times and gzip headers can change between hosts. "
        "For mission bundles, compare scientific values using `python -m usv_sim.verify ../reproduced-bundle --reference .`.\n\n"
        "`artifact-sha256.json` covers retained files; mutable `job.json` progress is excluded. "
        "The frozen design records the original protocol; `effective-config.json` and `request.json` "
        "record exploratory overrides when applicable. Source under `source/` was copied before the run.\n",
        encoding="utf-8")
    return record


def inventory(destination):
    root = Path(destination)
    hashes = {str(p.relative_to(root)).replace("\\", "/"): sha256(p)
              for p in sorted(root.rglob("*")) if p.is_file()
              and p.name not in ("artifact-sha256.json", "evidence.zip", "job.json")}
    dump(root / "artifact-sha256.json", hashes)
    with zipfile.ZipFile(root / "evidence.zip", "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in [*hashes, "artifact-sha256.json"]:
            bundle.write(root / name, name)
    return hashes


def trace(path):
    """1 s tracks + exchange snapshots + exact observation times + raw sessions.

    Schema-2 logs additionally record exact one-second task/motion states; a
    session at the same timestamp supersedes its pre-exchange tick snapshot.
    Legacy logs retain sampled ownership and unavailable terminal tasks.
    """
    path = Path(path)
    result, _ = reconstruct(path)  # Fail closed if independent totals disagree.
    frames, tracks, sessions, observations, motion_states = [], [], [], [], []
    counts = {}
    covered = set()
    total_observations = 0
    first_seen = None
    positions = None
    idle = [0, 0]
    sent = received = 0
    start = terminal = None

    def recorded_state(event, t):
        boats = event.get("boats")
        if boats is None:
            return
        state = {"t": t, "queues": [b["queue"] for b in boats],
                 "targets": [b["target"] for b in boats],
                 "headings": [b["heading"] for b in boats],
                 "modes": [b["mode"] for b in boats],
                 "speed_mps": [b["speed_mps"] for b in boats],
                 "cells": [b["cell"] for b in boats],
                 "edge_targets": [b["edge_target"] for b in boats],
                 "edge_remaining_m": [b["edge_remaining_m"] for b in boats],
                 "turn_remaining_s": [b["turn_remaining_s"] for b in boats]}
        if motion_states and motion_states[-1]["t"] == t:
            motion_states[-1] = state
        else:
            motion_states.append(state)

    for event in read_events(path):
        kind = event["event"]
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "start":
            start = event
            config = Config(**event["config"])
            first_seen = [None] * config.cells
            positions = [list(config.centre(0)), list(config.centre((config.width + 1) // 2))]
            tracks.append([0, *positions[0], *positions[1], 0, 0])
        elif kind == "observe":
            covered.add(event["cell"])
            total_observations += 1
            if first_seen[event["cell"]] is None:
                first_seen[event["cell"]] = event["t"]
            observations.append([event["t"], event["boat"], event["cell"]])
        elif kind == "initial_allocation":
            recorded_state(event, 0)
            initial = [0, (config.width + 1) // 2]
            frames.append({"t": 0, "xy": positions, "known": [initial, initial],
                           "queues": event["queues"], "targets": [None, None],
                           "coverage": len(covered) / config.cells, "redundant": 0,
                           "sent_bytes": 0, "received_bytes": 0, "radio": None,
                           "r": None, "warning": False, "committed": False})
        elif kind == "tick":
            positions, idle = event["xy"], event["idle"]
            tracks.append([event["t"], *positions[0], *positions[1], *idle])
            recorded_state(event, event["t"])
        elif kind == "session":
            recorded_state(event, event["t"])
            sent += event["bytes_attempted"]
            received += event["bytes_delivered"]
            sessions.append(event)
            frame = {k: event[k] for k in ("t", "known", "queues", "targets", "r",
                                          "radio", "warning", "committed", "fade", "d")}
            frame.update(xy=positions, coverage=len(covered) / config.cells,
                         redundant=total_observations - len(covered),
                         sent_bytes=sent, received_bytes=received)
            frames.append(frame)
        elif kind == "stop":
            terminal = event
            recorded_state(event, result["stop_s"])
    # Always append a distinct terminal state, even if an exchange shares its time.
    frames.append({"t": result["stop_s"], "xy": positions, "known": terminal["known"],
                   "queues": terminal.get("queues"), "targets": terminal.get("targets"),
                   "coverage": result["coverage"], "redundant": result["redundant"],
                   "sent_bytes": sent, "received_bytes": received, "radio": None,
                   "r": None, "warning": False, "committed": False, "terminal": True})
    return {"schema": 2, "raw_schema": start.get("schema", 1), "config": asdict(config), "scenario": start["scenario"],
            "margins": start["margins"], "policy": start["policy"], "result": result,
            "frames": frames, "tracks": tracks, "motion_states": motion_states, "first_seen": first_seen,
            "observations": observations, "sessions": sessions, "event_counts": counts,
            "raw_sha256": sha256(path), "verified": True,
            "sampling": {"motion_s": 1, "queues_s": 1 if motion_states else config.exchange_s,
                         "radio_s": config.exchange_s,
                         "motion_states_recorded": bool(motion_states),
                         "terminal_queues_recorded": "queues" in terminal}}
