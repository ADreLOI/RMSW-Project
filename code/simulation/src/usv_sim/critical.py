"""Post-hoc critical-window analysis of the frozen core (requested 24 November 2026).

Finding examined here: in every online mission the two boats first separate beyond
radio range at the same moment (about 260 s). If both exchanges just before that
split are lost, the last committed allocation leaves the boats waiting out of range
and the mission stalls; otherwise it completes. This module

1. derives the critical window from fade-free reference runs (no frozen data used),
2. scores the rule "both window exchanges faded -> stall" on the 900 frozen runs,
3. compares observed stall rates with the stationary-chain probability q(1 - 1/L),
4. runs an intervention: the same 540 online scenarios with the window forced
   faded, and forced clear (new runs, written only to the output bundle),
5. maps the effect of a full link blackout of D exchanges starting at every
   exchange of an otherwise ideal balanced mission (new runs), and
6. records the separation timeline of an intact and a window-lost mission.

It reads `results/core/` and never writes there. Results are descriptive and were
found after inspecting the frozen outcomes; the intervention is the check.

    python -m usv_sim.critical --output results/posthoc/critical-window-2026-11-24
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

from .model import Config, make_scenario, run

ONLINE = ("S3", "S4-T", "S4-P")
POLICIES = ("S1", "S2", "S3", "S4-T", "S4-P")
LENGTHS = (2, 5, 10)
BLACKOUTS = (1, 2, 3, 6, 12)  # exchanges (10 s each)
BLACKOUT_DB = -1000.0  # a "fade" this deep removes the link at any distance
THEORY_SEEDS = range(10**6, 10**6 + 5000)  # disjoint from pilot (0-9) and evaluation (1000-1029)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def range_m(c: Config):
    """Clear-state separation at which the received signal reaches the cutoff."""
    return c.d0_m * 10 ** ((c.p0_dbm - c.threshold_dbm) / (10 * c.path_exponent))


def fade_range_m(c: Config):
    """Separation beyond which a fade alone breaks the link."""
    return c.d0_m * 10 ** ((c.p0_dbm + c.fade_db - c.threshold_dbm) / (10 * c.path_exponent))


def ideal(scenario):
    return replace(scenario, fades=tuple(False for _ in scenario.fades))


def with_fades(scenario, indices, value):
    fades = list(scenario.fades)
    for k in indices:
        fades[k] = value
    return replace(scenario, fades=tuple(fades))


def critical_window(c: Config, margins, policy="S3", width=2):
    """Exchange indices just before the first distance failure of the fade-free mission."""
    _, sessions = run(c, ideal(make_scenario(c, 0, 2, False)), policy, margins=margins)
    split = next(s["k"] for s in sessions if s["distance_failure"])
    return tuple(range(split - width, split)), split


def wilson(successes, n, z=1.959963984540054):
    if n == 0:
        return None, None
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def theory_probability(c: Config, length, window_size=2):
    """P(all window exchanges faded) for the stationary two-state chain."""
    return c.fade_fraction * (1 - 1 / length) ** (window_size - 1)


def empirical_probability(c: Config, length, window):
    hits = sum(all(make_scenario(c, seed, length, False).fades[k] for k in window) for seed in THEORY_SEEDS)
    return hits / len(THEORY_SEEDS)


# ---------------------------------------------------------------- frozen runs

def rule_table(runs, c: Config, window):
    """Per frozen run: did the window fade, and did the mission stall?"""
    streams = {}
    rows = []
    for r in runs:
        key = (r["seed"], r["fade_length"])
        if key not in streams:
            fades = make_scenario(c, r["seed"], r["fade_length"], False).fades
            streams[key] = all(fades[k] for k in window)
        rows.append({"seed": r["seed"], "slowdown": r["slowdown"], "fade_length": r["fade_length"], "policy": r["policy"],
                     "window_faded": streams[key], "stalled": not r["complete"], "restricted_s": r["restricted_s"],
                     "coverage": r["coverage"]})
    return rows


def confusion(rows):
    out = []
    for policy in POLICIES:
        g = [r for r in rows if r["policy"] == policy]
        tp = sum(r["window_faded"] and r["stalled"] for r in g)
        fp = sum(r["window_faded"] and not r["stalled"] for r in g)
        fn = sum(not r["window_faded"] and r["stalled"] for r in g)
        tn = sum(not r["window_faded"] and not r["stalled"] for r in g)
        out.append({"policy": policy, "runs": len(g), "window_faded_and_stalled": tp,
                    "window_faded_but_completed": fp, "window_clear_but_stalled": fn,
                    "window_clear_and_completed": tn, "agreement": (tp + tn) / len(g)})
    return out


def stall_rates(rows, runs, c: Config, window):
    """Observed stall share per condition against the stationary-chain prediction."""
    done = defaultdict(list)
    for r in runs:
        if r["complete"]:
            done[(r["slowdown"], r["fade_length"], r["policy"])].append(r["restricted_s"])
    theory = {L: theory_probability(c, L, len(window)) for L in LENGTHS}
    sim = {L: empirical_probability(c, L, window) for L in LENGTHS}
    out = []
    for slowdown in (False, True):
        for L in LENGTHS:
            for policy in POLICIES:
                g = [r for r in rows if r["policy"] == policy and r["slowdown"] == slowdown and r["fade_length"] == L]
                stalls = sum(r["stalled"] for r in g)
                low, high = wilson(stalls, len(g))
                completed = done[(slowdown, L, policy)]
                mean_done = float(np.mean(completed)) if completed else None
                p = theory[L] if policy in ONLINE else None
                out.append({
                    "slowdown": slowdown, "fade_length": L, "policy": policy, "n": len(g),
                    "stalls": stalls, "stall_share": stalls / len(g), "stall_share_low": low, "stall_share_high": high,
                    "window_faded": sum(r["window_faded"] for r in g),
                    "theory_stall_probability": p, "stream_frequency_5000_seeds": sim[L] if p is not None else None,
                    "observed_restricted_mean_s": float(np.mean([r["restricted_s"] for r in g])),
                    "completed_mean_s": mean_done,
                    "expected_restricted_mean_s": (1 - p) * mean_done + p * c.timeout_s if p is not None and mean_done else None,
                })
    return out


# ---------------------------------------------------------------- new runs

def _intervention(task):
    cdata, margins, policy, seed, length, slowdown, window = task
    c = Config(**cdata)
    scenario = make_scenario(c, seed, length, slowdown)
    out = {"policy": policy, "seed": seed, "fade_length": length, "slowdown": slowdown,
           "natural_window_faded": all(scenario.fades[k] for k in window)}
    for label, value in (("forced_fade", True), ("forced_clear", False)):
        result, _ = run(c, with_fades(scenario, window, value), policy, margins=margins)
        out[f"{label}_complete"] = result["complete"]
        out[f"{label}_restricted_s"] = result["restricted_s"]
    return out


def _blackout(task):
    cdata, margins, policy, start, duration = task
    c = replace(Config(**cdata), fade_db=BLACKOUT_DB)
    scenario = with_fades(ideal(make_scenario(c, 0, 2, False)), range(start, start + duration), True)
    result, sessions = run(c, scenario, policy, margins=margins)
    return {"policy": policy, "duration_exchanges": duration, "duration_s": duration * c.exchange_s,
            "start_k": start, "start_s": start * c.exchange_s, "complete": result["complete"],
            "restricted_s": result["restricted_s"], "coverage": result["coverage"],
            "final_separation_m": sessions[-1]["d"] if sessions else None}


def intervention(c: Config, margins, window, seeds, workers):
    tasks = [(asdict(c), margins, p, s, L, sl, window) for p in ONLINE for sl in (False, True) for L in LENGTHS for s in seeds]
    with ProcessPoolExecutor(workers) as pool:
        return list(pool.map(_intervention, tasks, chunksize=8))


def intervention_summary(rows):
    out = []
    for policy in ONLINE:
        g = [r for r in rows if r["policy"] == policy]
        out.append({"policy": policy, "scenarios": len(g),
                    "stall_when_window_forced_faded": sum(not r["forced_fade_complete"] for r in g),
                    "stall_when_window_forced_clear": sum(not r["forced_clear_complete"] for r in g),
                    "mean_s_forced_faded": float(np.mean([r["forced_fade_restricted_s"] for r in g])),
                    "mean_s_forced_clear": float(np.mean([r["forced_clear_restricted_s"] for r in g])),
                    "max_completed_s_forced_clear": max((r["forced_clear_restricted_s"] for r in g if r["forced_clear_complete"]), default=None)})
    return out


def blackout_map(c: Config, margins, last_start, workers):
    tasks = [(asdict(c), margins, p, k, d) for p in ONLINE for d in BLACKOUTS for k in range(1, last_start + 1)]
    with ProcessPoolExecutor(workers) as pool:
        return list(pool.map(_blackout, tasks, chunksize=16))


def timeline(c: Config, margins, window):
    rows = []
    base = ideal(make_scenario(c, 0, 2, False))
    for label, scenario in (("intact", base), ("window_lost", with_fades(base, window, True))):
        result, sessions = run(c, scenario, "S3", margins=margins)
        for s in sessions:
            rows.append({"case": label, "t": s["t"], "separation_m": s["d"], "radio": s["radio"],
                         "committed": s["committed"], "complete": result["complete"]})
    return rows


# ---------------------------------------------------------------- output

def write_csv(path, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: ("" if v is None else v) for k, v in r.items()})


def analyse(core, workers=4, new_runs=True):
    core = Path(core)
    freeze = json.loads((core / "frozen-design.json").read_text(encoding="utf-8"))
    runs = json.loads((core / "runs.json").read_text(encoding="utf-8"))
    c = Config(**freeze["config"])
    margins = freeze["margins"]
    window, split = critical_window(c, margins)
    windows = {p: critical_window(c, margins, p) for p in ONLINE}
    if any(w != (window, split) for w in windows.values()):
        raise RuntimeError(f"Online policies split at different exchanges: {windows}")
    rows = rule_table(runs, c, window)
    tables = {"rule-per-run": rows, "rule-confusion": confusion(rows),
              "stall-rates": stall_rates(rows, runs, c, window)}
    facts = {"window_exchanges": list(window), "window_s": [k * c.exchange_s for k in window],
             "first_out_of_range_s": split * c.exchange_s, "radio_range_m": range_m(c),
             "fade_breaks_link_beyond_m": fade_range_m(c)}
    if new_runs:
        seeds = freeze["evaluation_seeds"]
        tables["intervention-runs"] = intervention(c, margins, window, seeds, workers)
        tables["intervention-summary"] = intervention_summary(tables["intervention-runs"])
        last = math.ceil(1425 / c.exchange_s)  # fade-free S3 mission length
        tables["blackout-map"] = blackout_map(c, margins, last, workers)
        tables["timeline"] = timeline(c, margins, window)
    return tables, facts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    simulation = Path(__file__).resolve().parents[2]
    parser.add_argument("--core", type=Path, default=simulation / "results" / "core")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--no-new-runs", action="store_true", help="only score the frozen runs")
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args(argv)
    if args.output.resolve() == args.core.resolve() or args.core.resolve() in args.output.resolve().parents:
        parser.error("Refusing to write inside the frozen core bundle")
    args.output.mkdir(parents=True, exist_ok=True)
    tables, facts = analyse(args.core, args.workers, not args.no_new_runs)
    for name, rows in tables.items():
        write_csv(args.output / f"{name}.csv", rows)
    if not args.no_figures:
        from . import critical_figures
        runs = json.loads((args.core / "runs.json").read_text(encoding="utf-8"))
        critical_figures.write_all(tables, facts, runs, args.output, args.core)
    inputs = ["runs.json", "frozen-design.json"]
    manifest = {
        "kind": "post-hoc analysis; not part of the pre-specified core evaluation",
        "requested": "24 November 2026, after the 12 November tutor feedback on results",
        "inputs_sha256": {name: sha256(args.core / name) for name in inputs},
        "facts": facts,
        "theory_stream_seeds": [THEORY_SEEDS.start, THEORY_SEEDS.stop - 1],
        "new_runs": None if args.no_new_runs else {
            "intervention": "540 scenarios (S3, S4-T, S4-P x 2 progress x 3 fade lengths x 30 evaluation seeds), "
                            "each run twice: window forced faded (-10 dB) and forced clear",
            "blackout_map": f"S3, S4-T, S4-P on the fade-free balanced mission; full blackout ({BLACKOUT_DB} dB) "
                            f"of {list(BLACKOUTS)} exchanges starting at every exchange",
            "status": "new executions for diagnosis only; not core evidence"},
        "outputs": sorted(p.name for p in args.output.iterdir() if p.name not in ("manifest.json", "README.md")),
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Critical-window analysis written to {args.output}")


if __name__ == "__main__":
    main()
