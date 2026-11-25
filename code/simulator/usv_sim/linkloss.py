"""Post-hoc link-loss, resilience, correlation and communication-cost analysis.

Requested at the tutor meeting of 12 November 2026: relate mission outcomes to how
often the boat-to-boat link is lost. This module reads the frozen core summaries
(`runs.json`, `mechanism-diagnostics.csv`) and never writes into `results/core/`.

It is a declared post-evaluation analysis, not part of the pre-specified plan:
no setting is tuned, no contrast is promoted to a primary test, and correlations
between a run's own link availability and its completion time are descriptive
(a stalled pair drifts apart and loses the link, so causation runs both ways).
The exogenous covariate is the fade exposure of the seed-matched disturbance
stream, which no policy can influence.

The optional ideal-link reference executes NEW runs (same seeds, fades disabled).
They are written to the post-hoc bundle only and are not core evidence.

    python -m usv_sim.linkloss --output results/posthoc/link-loss-2026-11-12
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import numpy as np

from .model import Config, make_scenario, run

POLICIES = ("S1", "S2", "S3", "S4-T", "S4-P")
ONLINE = POLICIES[1:]
REFERENCE_S = 1280  # closed-form balanced S1 duration; window for fade exposure
BOOTSTRAP = 2000


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rank(values):
    """Average ranks (ties share the mean rank), as used by Spearman's rho."""
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values))
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[order[j + 1]] == values[order[i]]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(x, y):
    """Spearman rank correlation; None when either variable is constant."""
    if len(x) < 3:
        return None
    rx, ry = rank(x), rank(y)
    if rx.std() == 0 or ry.std() == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def fade_exposure(c: Config, seed, fade_length):
    """Fraction of faded exchange slots in the first REFERENCE_S seconds of the stream.

    Exchange k happens at t = k * exchange_s, so the window is slots 1..REFERENCE_S/exchange_s.
    """
    fades = make_scenario(c, seed, fade_length, False).fades[1:REFERENCE_S // c.exchange_s + 1]
    return sum(fades) / len(fades)


def load_core(core):
    core = Path(core)
    runs = json.loads((core / "runs.json").read_text(encoding="utf-8"))
    with (core / "mechanism-diagnostics.csv").open(encoding="utf-8", newline="") as stream:
        mechanism = {(int(r["seed"]), r["slowdown"] == "True", int(r["fade_length"]), r["policy"]): r
                     for r in csv.DictReader(stream)}
    return runs, mechanism


def ideal_link_reference(c: Config, seeds, margins):
    """New runs with the fade stream disabled: what each policy does when only distance limits the link."""
    rows = {}
    for slowdown in (False, True):
        for seed in seeds:
            scenario = make_scenario(c, seed, 2, slowdown)
            scenario = replace(scenario, fades=tuple(False for _ in scenario.fades))
            for policy in POLICIES:
                result, _ = run(c, scenario, policy, margins=margins)
                rows[(seed, slowdown, policy)] = {
                    "seed": seed, "slowdown": slowdown, "policy": policy,
                    "complete": result["complete"], "restricted_s": result["restricted_s"],
                    "link_availability": result["link_availability"],
                    "attempted_bytes": result["attempted_bytes"],
                    "delivered_bytes": result["delivered_bytes"]}
    return rows


def per_run(runs, mechanism, c: Config, ideal=None):
    """One derived row per frozen run."""
    reference = {(r["seed"], r["slowdown"], r["fade_length"]): r["restricted_s"]
                 for r in runs if r["policy"] == "S1"}
    exposure = {}
    rows = []
    for r in runs:
        key = (r["seed"], r["slowdown"], r["fade_length"])
        if key[::2] not in exposure:
            exposure[key[::2]] = fade_exposure(c, r["seed"], r["fade_length"])
        m = mechanism[(r["seed"], r["slowdown"], r["fade_length"], r["policy"])]
        w = r["warnings"]
        lengths = w["outage_lengths"]
        opportunities = r["stop_s"] // c.exchange_s
        missed = round((1 - r["link_availability"]) * opportunities)
        row = {
            "seed": r["seed"], "slowdown": r["slowdown"], "fade_length": r["fade_length"], "policy": r["policy"],
            "complete": r["complete"], "restricted_s": r["restricted_s"], "stop_s": r["stop_s"],
            "fade_exposure": exposure[key[::2]],
            "link_availability": r["link_availability"],
            "outages": len(lengths), "outage_s": sum(lengths) * c.exchange_s,
            "outages_per_hour": len(lengths) * 3600 / r["stop_s"],
            "missed_exchanges": missed, "distance_failures": r["distance_failures"],
            "fade_failures": missed - r["distance_failures"],
            "eligible_outages": w["eligible_outages"],
            "alerts": w["alerts"], "timely_alerts": w["true_positives"], "false_alarms": w["false_positives"],
            "outages_with_prior_reservation": int(m["outages_with_prior_reservation"]),
            "idle_s": float(sum(r["idle_s"])),
            "excess_over_s1_s": r["restricted_s"] - reference[key],
            "attempted_bytes": r["attempted_bytes"], "delivered_bytes": r["delivered_bytes"],
            "attempted_messages": r["attempted_messages"], "delivered_messages": r["delivered_messages"],
            "reservations": r["reservations"],
        }
        if ideal is not None:
            base = ideal[(r["seed"], r["slowdown"], r["policy"])]
            row["ideal_link_s"] = base["restricted_s"]
            row["retention"] = base["restricted_s"] / r["restricted_s"]
            row["delay_vs_ideal_s"] = r["restricted_s"] - base["restricted_s"]
        rows.append(row)
    return rows


def groups(rows):
    out = defaultdict(list)
    for r in rows:
        out[(r["slowdown"], r["fade_length"], r["policy"])].append(r)
    for group in out.values():
        group.sort(key=lambda r: r["seed"])
    return out


def ratio(group, numerator, denominator, scale=1.0, rng=None):
    """Ratio of sums over paired seeds with a percentile bootstrap interval."""
    n = np.array([r[numerator] for r in group], dtype=float)
    d = np.array([r[denominator] for r in group], dtype=float)
    if d.sum() == 0:
        return None, None, None
    value = scale * n.sum() / d.sum()
    if rng is None:
        return value, None, None
    index = rng.integers(0, len(group), size=(BOOTSTRAP, len(group)))
    dn = d[index].sum(axis=1)
    samples = scale * n[index].sum(axis=1)[dn > 0] / dn[dn > 0]
    low, high = np.percentile(samples, [2.5, 97.5])
    return float(value), float(low), float(high)


def mean(group, key):
    return float(np.mean([r[key] for r in group]))


def link_loss_summary(rows):
    """A1: how often and for how long the link is lost."""
    out = []
    for (slowdown, fade_length, policy), g in sorted(groups(rows).items(), key=order):
        done = [r for r in g if r["complete"]]
        out.append({
            "slowdown": slowdown, "fade_length": fade_length, "policy": policy, "n": len(g),
            "link_availability": mean(g, "link_availability"),
            "outages_per_run": mean(g, "outages"),
            "outages_per_hour": mean(g, "outages_per_hour"),
            "mean_outage_s": ratio(g, "outage_s", "outages")[0],
            "outage_time_share": ratio(g, "outage_s", "stop_s")[0],
            "missed_exchanges_per_run": mean(g, "missed_exchanges"),
            "share_missed_by_distance": ratio(g, "distance_failures", "missed_exchanges")[0],
            "completion_proportion": mean(g, "complete"),
            "restricted_mean_s": mean(g, "restricted_s"),
            # Stalled runs are one long distance outage; completed runs show the working regime.
            "completed_runs": len(done),
            "completed_link_availability": mean(done, "link_availability") if done else None,
            "completed_outages_per_hour": mean(done, "outages_per_hour") if done else None,
            "completed_mean_outage_s": ratio(done, "outage_s", "outages")[0] if done else None,
            "completed_share_missed_by_distance": ratio(done, "distance_failures", "missed_exchanges")[0] if done else None,
        })
    return out


def per_100_outages(rows, seed=20261112):
    """A2: outcomes normalised by the number of link outages experienced."""
    rng = np.random.default_rng(seed)
    out = []
    for (slowdown, fade_length, policy), g in sorted(groups(rows).items(), key=order):
        row = {"slowdown": slowdown, "fade_length": fade_length, "policy": policy,
               "outages": sum(r["outages"] for r in g), "eligible_outages": sum(r["eligible_outages"] for r in g)}
        for name, numerator, denominator, scale in (
                ("incomplete_missions_per_100_outages", "incomplete", "outages", 100),
                ("idle_s_per_outage", "idle_s", "outages", 1),
                ("excess_over_s1_s_per_outage", "excess_over_s1_s", "outages", 1),
                ("reserved_before_per_100_eligible", "outages_with_prior_reservation", "eligible_outages", 100),
                ("timely_alerts_per_100_eligible", "timely_alerts", "eligible_outages", 100),
                ("false_alarms_per_100_outages", "false_alarms", "outages", 100),
                ("attempted_kb_per_outage", "attempted_kb", "outages", 1)):
            value, low, high = ratio(g, numerator, denominator, scale, rng)
            row[name], row[name + "_low"], row[name + "_high"] = value, low, high
        out.append(row)
    return out


def resilience(rows):
    """Performance retained relative to the same policy and seed with fades disabled.

    Retention is ideal-link time divided by restricted time under fades (1 = unaffected).
    It is undefined where the policy does not finish even with an ideal link: there the
    failure is not caused by fades, and a ratio of two censored times would read as 1.
    """
    out = []
    for (slowdown, fade_length, policy), g in sorted(groups(rows).items(), key=order):
        defined = all(r["ideal_link_s"] < 7200 for r in g)
        out.append({
            "slowdown": slowdown, "fade_length": fade_length, "policy": policy,
            "ideal_link_mean_s": mean(g, "ideal_link_s"),
            "ideal_link_completion": float(np.mean([r["ideal_link_s"] < 7200 for r in g])),
            "restricted_mean_s": mean(g, "restricted_s"),
            "completion_proportion": mean(g, "complete"),
            "mean_retention": mean(g, "retention") if defined else None,
            "min_retention": min(r["retention"] for r in g) if defined else None,
            "mean_delay_vs_ideal_s": mean(g, "delay_vs_ideal_s") if defined else None,
            "delay_s_per_outage": ratio(g, "delay_vs_ideal_s", "outages")[0] if defined else None,
            "delay_s_per_outage_completed_runs": ratio([r for r in g if r["complete"]], "delay_vs_ideal_s", "outages")[0]
                if defined and any(r["complete"] for r in g) else None,
        })
    return out


CORRELATIONS = (
    ("fade_exposure", "restricted_s", "exogenous fade exposure vs restricted completion time"),
    ("fade_exposure", "outages", "exogenous fade exposure vs outages experienced"),
    ("link_availability", "restricted_s", "own link availability vs restricted completion time (endogenous)"),
    ("outages", "restricted_s", "outages experienced vs restricted completion time (endogenous)"),
    ("outages", "idle_s", "outages experienced vs idle time (endogenous)"),
    ("stop_s", "attempted_bytes", "mission duration vs attempted bytes"),
    ("timely_alerts", "restricted_s", "timely alerts vs restricted completion time"),
    ("reservations", "restricted_s", "committed reservation actions vs restricted completion time"),
)


def correlations(rows, seed=20261112):
    """A3: Spearman correlations per policy, pooled over conditions and per condition."""
    rng = np.random.default_rng(seed)
    out = []
    by_policy = defaultdict(list)
    for r in rows:
        by_policy[r["policy"]].append(r)
    scopes = [("all conditions", p, g) for p, g in by_policy.items()]
    scopes += [(f"slowdown={s} L={l}", p, g) for (s, l, p), g in groups(rows).items()]
    scopes += [("completed runs only", p, [r for r in g if r["complete"]]) for p, g in by_policy.items()]
    for scope, policy, g in scopes:
        for x, y, label in CORRELATIONS:
            a = np.array([r[x] for r in g], dtype=float)
            b = np.array([r[y] for r in g], dtype=float)
            rho = spearman(a, b)
            low = high = None
            if rho is not None and len(g) >= 30:
                samples = []
                for index in rng.integers(0, len(g), size=(BOOTSTRAP, len(g))):
                    value = spearman(a[index], b[index])
                    if value is not None:
                        samples.append(value)
                low, high = (float(v) for v in np.percentile(samples, [2.5, 97.5]))
            out.append({"scope": scope, "policy": policy, "x": x, "y": y, "label": label, "n": len(g),
                        "spearman_rho": rho, "ci_low": low, "ci_high": high})
    out.sort(key=lambda r: (r["scope"] != "all conditions", r["scope"], r["x"], r["y"], POLICIES.index(r["policy"])))
    return out


def communication_cost(rows):
    """A4: radio traffic set against mission time."""
    out = []
    for (slowdown, fade_length, policy), g in sorted(groups(rows).items(), key=order):
        done = [r for r in g if r["complete"]]
        out.append({
            "slowdown": slowdown, "fade_length": fade_length, "policy": policy,
            "restricted_mean_s": mean(g, "restricted_s"), "completion_proportion": mean(g, "complete"),
            "attempted_kb": mean(g, "attempted_kb"), "delivered_kb": mean(g, "delivered_kb"),
            "delivery_ratio": ratio(g, "delivered_bytes", "attempted_bytes")[0],
            "wasted_kb": mean(g, "attempted_kb") - mean(g, "delivered_kb"),
            "attempted_messages": mean(g, "attempted_messages"),
            "attempted_bytes_per_s": ratio(g, "attempted_bytes", "stop_s")[0],
            "attempted_kb_completed_runs": mean(done, "attempted_kb") if done else None,
            "ideal_link_attempted_kb": mean(g, "ideal_attempted_kb") if "ideal_attempted_kb" in g[0] else None,
        })
    return out


def order(item):
    (slowdown, fade_length, policy), _ = item
    return slowdown, fade_length, POLICIES.index(policy)


def write_csv(path, rows):
    fields = list(rows[0])
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: ("" if v is None else v) for k, v in r.items()})


def analyse(core, with_ideal=True):
    core = Path(core)
    runs, mechanism = load_core(core)
    freeze = json.loads((core / "frozen-design.json").read_text(encoding="utf-8"))
    c = Config(**freeze["config"])
    ideal = None
    if with_ideal:
        ideal = ideal_link_reference(c, sorted({r["seed"] for r in runs}), freeze["margins"])
    rows = per_run(runs, mechanism, c, ideal)
    for r in rows:
        r["incomplete"] = int(not r["complete"])
        r["attempted_kb"] = r["attempted_bytes"] / 1000
        r["delivered_kb"] = r["delivered_bytes"] / 1000
        if ideal is not None:
            r["ideal_attempted_kb"] = ideal[(r["seed"], r["slowdown"], r["policy"])]["attempted_bytes"] / 1000
    tables = {
        "per-run": rows,
        "link-loss-summary": link_loss_summary(rows),
        "per-100-outages": per_100_outages(rows),
        "correlations": correlations(rows),
        "communication-cost": communication_cost(rows),
    }
    if ideal is not None:
        tables["resilience"] = resilience(rows)
        tables["ideal-link-runs"] = list(ideal.values())
    return tables


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    simulation = Path(__file__).resolve().parents[1]
    parser.add_argument("--core", type=Path, default=simulation / "results" / "core")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-ideal", action="store_true", help="skip the new fade-free reference runs")
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args(argv)
    if args.output.resolve() == args.core.resolve() or args.core.resolve() in args.output.resolve().parents:
        parser.error("Refusing to write inside the frozen core bundle")
    args.output.mkdir(parents=True, exist_ok=True)
    tables = analyse(args.core, with_ideal=not args.no_ideal)
    for name, rows in tables.items():
        write_csv(args.output / f"{name}.csv", rows)
    if not args.no_figures:
        from .charts import linkloss_figures
        linkloss_figures.write_all(tables, args.output)
    inputs = ["runs.json", "mechanism-diagnostics.csv", "frozen-design.json"]
    manifest = {
        "kind": "post-hoc analysis; not part of the pre-specified core evaluation",
        "requested": "tutor meeting, 12 November 2026",
        "inputs_sha256": {name: sha256(args.core / name) for name in inputs},
        "bootstrap_resamples": BOOTSTRAP, "bootstrap_seed": 20261112,
        "fade_exposure_window_s": REFERENCE_S,
        "ideal_link_reference": None if args.no_ideal else
            "300 new runs: evaluation seeds, both progress settings, fade stream disabled; not core evidence",
        "outputs": sorted(p.name for p in args.output.iterdir() if p.name != "manifest.json"),
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Post-hoc link-loss analysis written to {args.output}")


if __name__ == "__main__":
    main()
