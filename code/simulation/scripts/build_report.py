"""Regenerate evidence tables without overwriting the collaboratively edited report.

Run from any directory. Inputs default to the retained core evaluation; only the
six named tables and their provenance manifest under generated/ are written.
The initial report scaffolder is preserved in Git history, not rerun over prose.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[3]
POLICIES = ("S1", "S2", "S3", "S4-T", "S4-P")
INPUTS = ("runs.json", "paired-contrasts.csv", "condition-summary.csv",
          "outage-diagnostics.csv", "component-resources.csv", "frozen-design.json")


def csv_rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def table(spec, header, rows):
    return ("\\begin{tabular}{" + spec + "}\\toprule\n" +
            " & ".join(header) + r"\\\midrule" + "\n" +
            "\n".join(" & ".join(row) + r"\\" for row in rows) +
            "\n\\bottomrule\\end{tabular}\n")


def condition_key(row):
    slow = row["slowdown"]
    return (slow is True or slow == "True", int(row["fade_length"]), row["policy"])


def generate(results, destination):
    runs = json.loads((results / "runs.json").read_text(encoding="utf-8"))
    contrasts = csv_rows(results / "paired-contrasts.csv")
    summary = {condition_key(row): row for row in csv_rows(results / "condition-summary.csv")}
    outages = {condition_key(row): row for row in csv_rows(results / "outage-diagnostics.csv")}
    components = csv_rows(results / "component-resources.csv")
    expected = {(slow, length, policy, seed) for slow in (False, True)
                for length in (2, 5, 10) for policy in POLICIES for seed in range(1000, 1030)}
    actual = {(*condition_key(row), row["seed"]) for row in runs}
    if len(runs) != 900 or actual != expected:
        raise ValueError("Report inputs must contain the exact frozen 900-run matrix")
    expected_conditions = {(s, length, p) for s in (False, True) for length in (2, 5, 10) for p in POLICIES}
    if set(summary) != expected_conditions or set(outages) != expected_conditions:
        raise ValueError("Report summary/diagnostic matrix is incomplete")
    expected_contrasts = {(s, length, f"S4-T minus {p}") for s in (False, True)
                          for length in (2, 5, 10) for p in ("S2", "S3", "S4-P")}
    actual_contrasts = {(r["slowdown"] == "True", int(r["fade_length"]), r["comparison"]) for r in contrasts}
    if len(contrasts) != 18 or actual_contrasts != expected_contrasts:
        raise ValueError("Report contrast matrix is incomplete")
    component_keys = {(policy, component) for policy in POLICIES
                      for component in ("forecast", "allocation", "resync")}
    if len(components) != 15 or {(row["policy"], row["component"]) for row in components} != component_keys:
        raise ValueError("Report component matrix is incomplete")
    for row in components:
        group = [r for r in runs if r["policy"] == row["policy"]]
        work = [r["work"][row["component"]] for r in group]
        if int(row["runs"]) != len(group) or not math.isclose(
                float(row["mean_arithmetic"]), mean(w["arithmetic"] for w in work), rel_tol=1e-12, abs_tol=1e-10):
            raise ValueError(f"Component accounting mismatch: {row['policy']} {row['component']}")
        if not math.isclose(float(row["mean_gop"]), float(row["mean_arithmetic"]) / 1e9, rel_tol=1e-12, abs_tol=1e-15):
            raise ValueError(f"Component GOP mismatch: {row['policy']} {row['component']}")
        decisions = sum(w["decisions"] for w in work)
        if (not row["cpu_seconds_per_decision"]) != (decisions == 0):
            raise ValueError(f"Undefined component timing mismatch: {row['policy']} {row['component']}")
    for key, row in summary.items():
        group = [r for r in runs if condition_key(r) == key]
        for field, expected_value in (("coverage", mean(r["coverage"] for r in group)),
                                      ("link_availability", mean(r["link_availability"] for r in group)),
                                      ("completion_proportion", mean(r["complete"] for r in group))):
            if abs(float(row[field]) - expected_value) > 1e-10:
                raise ValueError(f"Summary mismatch for {key}: {field}")

    common_header = ["Progress", "$L$", r"$\Delta$ [s]", "95\\% CI [s]", "Change [\\%]"]
    primary, complete = [], []
    for row in contrasts:
        common = ["Slowdown" if row["slowdown"] == "True" else "Balanced", row["fade_length"]]
        values = [f"{float(row['mean_difference_s']):+.1f}",
                  f"$[{float(row['ci_low_s']):.1f}, {float(row['ci_high_s']):.1f}]$",
                  f"{float(row['relative_percent']):+.2f}"]
        complete.append(common + [row["comparison"].removeprefix("S4-T minus ")] + values)
        if row["role"] == "primary":
            primary.append(common + values)
    outputs = {
        "primary-contrasts.tex": table("llrrr", common_header, primary),
        "complete-contrasts.tex": table("lrlrrr", common_header[:2] + ["Reference"] + common_header[2:], complete),
    }
    diagnostics = []
    for slow in (False, True):
        rows = []
        for length in (2, 5, 10):
            for policy in POLICIES:
                row, outage = summary[(slow, length, policy)], outages[(slow, length, policy)]
                rows.append([str(length), policy, f"{round(float(row['completion_proportion']) * 30)}/30",
                             f"{100 * float(row['coverage']):.1f}",
                             f"{100 * float(row['link_availability']):.1f}",
                             f"{float(outage['mean_outage_s']):.1f}" if outage['mean_outage_s'] else "--"])
        diagnostics.append("\\par\\noindent\\textbf{" + ("Temporary slowdown" if slow else "Balanced progress") + "}\\par\n" +
                           table("rlrrrr", ["$L$", "Policy", "Done/30", "Coverage [\\%]", "Link [\\%]", "Outage [s]"], rows))
    outputs["condition-diagnostics.tex"] = "\n\\medskip\n".join(diagnostics)
    rows = []
    for policy in POLICIES:
        group = [r for r in runs if r["policy"] == policy]
        rows.append([policy, f"{sum(r['complete'] for r in group)}/180",
                     f"{100 * mean(r['coverage'] for r in group):.1f}",
                     f"{mean(r['redundant'] for r in group):.1f}",
                     f"{mean(r['distance_m'] for r in group):.0f}",
                     f"{mean(sum(r['idle_s']) for r in group):.0f}"])
    outputs["policy-diagnostics.tex"] = table("lrrrrr", ["Policy", "Done/180", "Coverage [\\%]", "Repeat", "Travel [m]", "Idle [s]"], rows)
    rows = []
    for policy in POLICIES:
        group = [r for r in runs if r["policy"] == policy]
        rows.append([policy, f"{mean(r['attempted_messages'] for r in group):.1f}",
                     f"{mean(r['delivered_messages'] for r in group):.1f}",
                     f"{mean(r['attempted_bytes'] for r in group) / 1000:.2f}",
                     f"{mean(r['delivered_bytes'] for r in group) / 1000:.2f}"])
    outputs["communication-diagnostics.tex"] = table("lrrrr", ["Policy", "Attempt msg", "Deliver msg", "Attempt kB", "Deliver kB"], rows)
    lookup = {(row["policy"], row["component"]): row for row in components}
    rows = []
    for policy in POLICIES:
        for component in ("forecast", "allocation", "resync"):
            row = lookup[(policy, component)]
            rows.append([policy, component, f"{float(row['mean_arithmetic']):.1f}",
                         f"{float(row['mean_gop']):.3g}",
                         f"{float(row['arithmetic_per_decision']):.1f}" if row['arithmetic_per_decision'] else "--",
                         f"{float(row['cpu_seconds_per_decision']) * 1e6:.2f}" if row['cpu_seconds_per_decision'] else "--"])
    outputs["component-diagnostics.tex"] = table("llrrrr", ["Policy", "Component", "Ops/run", "GOP/run", "Ops/decision", r"CPU $\mu$s/decision"], rows)
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        (destination / name).write_text(content, encoding="utf-8")
    provenance = {"generator": "code/simulation/scripts/build_report.py",
                  "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "runs": len(runs),
                  "inputs_sha256": {name: hashlib.sha256((results / name).read_bytes()).hexdigest() for name in INPUTS},
                  "outputs_sha256": {name: hashlib.sha256((destination / name).read_bytes()).hexdigest() for name in outputs},
                  "note": "Tables are descriptive except paired marginal bootstrap intervals copied from retained contrasts. Prose and bibliography are never overwritten."}
    (destination / "table-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "code/simulation/results/core")
    parser.add_argument("--output", type=Path, default=ROOT / "paper/Final_Report/generated")
    args = parser.parse_args()
    print(json.dumps(generate(args.results.resolve(), args.output.resolve()), indent=2))


if __name__ == "__main__":
    main()
