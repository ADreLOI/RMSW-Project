"""Publication figures drawn from saved summary rows; the data never changes here.

The report pipeline (analysis.py, extension.py), run bundles (plots.py) and the
dashboard's figure downloads all call these functions inside plotstyle.paper().
"""
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .plotstyle import CENSORED_NOTE, COLORS, COLUMN_IN, DANGER, INK, MARKERS, MUTED, paper

CORE_POLICIES = ("S1", "S2", "S3", "S4-T", "S4-P")
LENGTHS = (2, 5, 10)
TIMEOUT_S = 7200


def typed(value):
    """Undo csv.DictWriter: str(bool)/str(float) round-trip exactly."""
    if value in ("True", "False"):
        return value == "True"
    if value in ("", "None"):
        return None
    try:
        number = float(value)
    except ValueError:
        return value
    return int(number) if number.is_integer() and "." not in value and "e" not in value.lower() else number


def read_rows(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return [{k: typed(v) for k, v in row.items()} for row in csv.DictReader(stream)]


def _condition(rows, slowdown, policy):
    return sorted((r for r in rows if r["slowdown"] == slowdown and r["policy"] == policy), key=lambda r: r["fade_length"])


def _censored_markers(ax, xs, ys, group, color, marker):
    """Re-draw points with any timed-out run as open markers (censoring stays visible)."""
    for x, y, r in zip(xs, ys, group):
        if r.get("completion_proportion", 1) < 1:
            ax.plot([x], [y], marker=marker, color=color, markerfacecolor="white", markersize=4.2, zorder=4, linestyle="none")


def mission_time(summary, policies, title=None, offset=0.0, ymax=7500):
    """Restricted mean time vs fade length, one panel per progress condition, shared y from 0.

    ymax=None scales to the data (still from 0) when no interval approaches the cutoff.
    """
    rows = [r for r in summary if r["policy"] in policies]
    top = ymax or max(r["ci_high_s"] for r in rows) * 1.15
    show_cutoff = top > TIMEOUT_S
    censored = any(r["completion_proportion"] < 1 for r in rows)
    with paper():
        fig, axs = plt.subplots(1, 2, figsize=(COLUMN_IN, 3.3 if len(policies) > 6 else 3.0), sharey=True)
        for ax, slow in zip(axs, (False, True)):
            for i, p in enumerate(policies):
                g = _condition(summary, slow, p)
                xs = np.array([r["fade_length"] for r in g]) + (i - (len(policies) - 1) / 2) * offset
                ys = [r["restricted_mean_s"] for r in g]
                ax.errorbar(xs, ys, yerr=[[r["restricted_mean_s"] - r["ci_low_s"] for r in g], [r["ci_high_s"] - r["restricted_mean_s"] for r in g]],
                            label=p, color=COLORS[p], marker=MARKERS[p], elinewidth=0.7)
                _censored_markers(ax, xs, ys, g, COLORS[p], MARKERS[p])
            ax.set_title("Temporary slowdown" if slow else "Balanced progress")
            ax.set_xticks(LENGTHS)
            ax.set_xlabel("Mean fade duration [exchanges]")
            ax.set_ylim(0, top)
            if show_cutoff:
                ax.axhline(TIMEOUT_S, color=DANGER, lw=0.6, ls=(0, (4, 3)))
        axs[0].set_ylabel("Restricted mean time [s]")
        if show_cutoff:
            axs[1].text(10.4, TIMEOUT_S - 120, "7200 s cutoff", color=DANGER, fontsize=7, ha="right", va="top")
        handles, labels = axs[0].get_legend_handles_labels()
        rows_legend = 2 if len(policies) > 6 else 1
        fig.legend(handles, labels, ncol=-(-len(policies) // rows_legend), loc="lower center", bbox_to_anchor=(0.5, 0.045),
                   handlelength=1.6, columnspacing=1)
        note = CENSORED_NOTE if censored else "Every run completed before the 7200 s cutoff; whiskers: marginal 95% paired-bootstrap interval"
        fig.text(0.5, 0.005, note, ha="center", va="bottom", fontsize=7, color=MUTED)
        if title:
            fig.suptitle(title)
        fig.tight_layout(rect=(0, 0.2 if rows_legend == 2 else 0.14, 1, 1))
    return fig


def resource_tradeoff(summary, policies=CORE_POLICIES):
    with paper():
        fig, axs = plt.subplots(1, 2, figsize=(COLUMN_IN, 2.9), sharey=True, sharex=True)
        for ax, slow in zip(axs, (False, True)):
            for p in policies:
                g = _condition(summary, slow, p)
                xs, ys = [r["attempted_bytes"] / 1000 for r in g], [r["restricted_mean_s"] for r in g]
                ax.scatter(xs, ys, color=COLORS[p], marker=MARKERS[p], label=p, s=22, zorder=3)
                for x, y, r in zip(xs, ys, g):
                    if r["completion_proportion"] < 1:
                        ax.scatter([x], [y], facecolor="white", edgecolor=COLORS[p], marker=MARKERS[p], s=22, zorder=4)
            ax.set_title("Temporary slowdown" if slow else "Balanced progress")
            ax.set_xlabel("Mean attempted payload [kB]")
            ax.set_xlim(left=0)
            ax.set_ylim(0, 7500)
        axs[0].set_ylabel("Restricted mean time [s]")
        handles, labels = axs[0].get_legend_handles_labels()
        fig.legend(handles, labels, ncol=len(policies), loc="lower center", bbox_to_anchor=(0.5, 0.045))
        fig.text(0.5, 0.005, CENSORED_NOTE, ha="center", va="bottom", fontsize=7, color=MUTED)
        fig.tight_layout(rect=(0, 0.17, 1, 1))
    return fig


def condition_bars(summary, slowdown, length, policies, study):
    """One condition: restricted mean with 95% CI, completed counts printed, censoring hatched."""
    rows = [next(r for r in summary if r["slowdown"] == slowdown and r["fade_length"] == length and r["policy"] == p) for p in policies]
    with paper():
        fig, ax = plt.subplots(figsize=(COLUMN_IN * (0.62 if len(policies) <= 5 else 1), 2.6))
        xs = np.arange(len(rows))
        for x, r in zip(xs, rows):
            p = r["policy"]
            censored = r["completion_proportion"] < 1
            ax.bar(x, r["restricted_mean_s"], width=0.62, color=COLORS[p] if not censored else "white",
                   edgecolor=COLORS[p], hatch="////" if censored else None, linewidth=0.9)
            ax.errorbar(x, r["restricted_mean_s"], yerr=[[r["restricted_mean_s"] - r["ci_low_s"]], [r["ci_high_s"] - r["restricted_mean_s"]]], color=INK, elinewidth=0.7)
            done = round(r["completion_proportion"] * r["n"])
            ax.text(x, r["ci_high_s"] + 140, f"{done}/{r['n']}", ha="center", va="bottom", fontsize=7, color=INK)
        ax.axhline(TIMEOUT_S, color=DANGER, lw=0.6, ls=(0, (4, 3)))
        ax.set_xticks(xs, [r["policy"] for r in rows])
        ax.set_ylim(0, 8200)
        ax.set_ylabel("Restricted mean time [s]")
        ax.grid(axis="x", visible=False)
        ax.set_title(f"{study}: {'temporary slowdown' if slowdown else 'balanced progress'}, mean fade {length} exchanges")
        fig.text(0.5, 0.005, "Labels: completed / runs. Hatched: some runs censored at 7200 s (counted as 7200).\nWhiskers: marginal 95% paired-bootstrap interval.",
                 ha="center", va="bottom", fontsize=6.5, color=MUTED)
        fig.tight_layout(rect=(0, 0.12, 1, 1))
    return fig


def contrasts(rows, slowdown, length, title):
    """Paired differences for one condition, symmetric x-axis around 0."""
    rows = [r for r in rows if r["slowdown"] == slowdown and r["fade_length"] == length]
    with paper():
        fig, ax = plt.subplots(figsize=(COLUMN_IN * 0.62, 0.45 + 0.3 * len(rows)))
        bound = max(1.0, *(max(abs(r["ci_low_s"]), abs(r["ci_high_s"])) for r in rows)) * 1.1
        for y, r in enumerate(reversed(rows)):
            first = r["comparison"].split(" minus ")[0]
            ax.errorbar(r["mean_difference_s"], y, xerr=[[r["mean_difference_s"] - r["ci_low_s"]], [r["ci_high_s"] - r["mean_difference_s"]]],
                        color=COLORS.get(first, INK), marker=MARKERS.get(first, "o"), elinewidth=0.8)
        ax.axvline(0, color=INK, lw=0.6)
        ax.set_yticks(range(len(rows)), [r["comparison"].replace(" minus ", " $-$ ") for r in reversed(rows)])
        ax.set_xlim(-bound, bound)
        ax.set_xlabel("Paired difference in restricted time [s] (negative: first policy faster)")
        ax.grid(axis="y", visible=False)
        ax.set_title(title)
        fig.tight_layout()
    return fig


def predictor_cost(warning, policy_predictors):
    names = {v: k for k, v in policy_predictors.items()}
    with paper():
        fig, ax = plt.subplots(figsize=(COLUMN_IN * 0.7, 3.0))
        for row in [w for w in warning if w["split"] == "extension-2000"]:
            policy = names[row["predictor"]]
            cost = row["arithmetic_per_decision"] + row["transcendental_per_decision"]
            label = f"{policy} {row['label']}".replace("(bound)", "(bound, not deployable)")
            ax.scatter(cost, row["f1"], color=COLORS[policy], marker=MARKERS[policy], s=26, label=label, zorder=3)
        ax.set_xscale("log")
        ax.set_ylim(0, 1)
        ax.set_xlabel("Counted operations per decision (log scale)")
        ax.set_ylabel("Held-out warning F1")
        ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), handletextpad=0.3)
        fig.tight_layout()
    return fig


def map_curves(maps, slowdown=True, length=5):
    """Mean synthetic-map RMSE curve per (study, policy) for one condition."""
    curves = {}
    for study in ("core", "extension"):
        for policy in sorted({m["policy"] for m in maps if m["study"] == study}):
            g = [m for m in maps if m["study"] == study and m["policy"] == policy and m["slowdown"] == slowdown and m["fade_length"] == length]
            if g:
                curves[(study, policy)] = ([t for t, _ in g[0]["curve"]], np.mean([[y for _, y in m["curve"]] for m in g], 0).tolist())
    return curves


def map_rmse(curves, extension_policies=("S1", "S2", "S3", "S4-T", "S4-G", "S4-O")):
    with paper():
        fig, axs = plt.subplots(1, 2, figsize=(COLUMN_IN, 2.7), sharey=True)
        for ax, study, policies in zip(axs, ("core", "extension"), (CORE_POLICIES, extension_policies)):
            for p in policies:
                if (study, p) in curves:
                    t, y = curves[(study, p)]
                    ax.plot(t, y, label=p + (" (bound)" if p == "S4-O" else ""), color=COLORS[p], marker=MARKERS[p], markevery=4)
            ax.set_title(f"{'Frozen core' if study == 'core' else 'Extension (recovery)'}: slowdown, mean fade 5")
            ax.set_xlabel("Mission time [s]")
            ax.set_xlim(0, 4000)
            ax.set_ylim(bottom=0)
            ax.axhline(0.5, color=MUTED, ls=":", lw=0.8)
            ax.legend(ncol=2)
        axs[0].set_ylabel("Synthetic map RMSE [m]")
        fig.tight_layout()
    return fig


def paired_mission(rows):
    """Run-bundle figure: one paired scenario, hatched bars are incomplete at the cutoff."""
    with paper():
        fig, axes = plt.subplots(1, 3, figsize=(COLUMN_IN, 2.3))
        fields = [("restricted_s", "Restricted mission time [s]", 1, (0, 7500)),
                  ("coverage", "Final observed coverage [%]", 100, (0, 100)),
                  ("attempted_bytes", "Attempted payload [kB]", .001, None)]
        for ax, (field, label, scale, limits) in zip(axes, fields):
            for x, r in enumerate(rows):
                p = r["policy"]
                ax.bar(x, r[field] * scale, width=.62, color=COLORS[p] if r["complete"] else "white",
                       edgecolor=COLORS[p], hatch=None if r["complete"] else "////", linewidth=.9)
            ax.set_xticks(range(len(rows)), [r["policy"] for r in rows], rotation=0)
            ax.set_ylabel(label)
            ax.grid(axis="x", visible=False)
            if limits:
                ax.set_ylim(*limits)
        fig.suptitle("One paired synthetic scenario; hatched bars: incomplete at the cutoff")
        fig.tight_layout()
    return fig


def load_extension(root):
    root = Path(root)
    design = json.loads((root / "extension-design.json").read_text(encoding="utf-8"))
    return (design, read_rows(root / "condition-summary.csv"), read_rows(root / "paired-contrasts.csv"),
            read_rows(root / "predictor-warning-quality.csv"))
