"""Figures for the critical-window analysis (critical.py); values come from its tables."""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

from .figures import read_rows
from .plotstyle import COLORS, COLUMN_IN, DANGER, GRID, INK, MARKERS, MUTED, WARNING, paper, save

ONLINE = ("S3", "S4-T", "S4-P")
LENGTHS = (2, 5, 10)
TIMEOUT_S = 7200


def outcome_distribution(runs, rates):
    """Mission times are bimodal: completion near 1.5 ks, or a stall at the cutoff."""
    with paper():
        fig, (left, right) = plt.subplots(1, 2, figsize=(COLUMN_IN, 2.8), gridspec_kw={"width_ratios": [1.6, 1]})
        for p in ONLINE:
            times = sorted(r["restricted_s"] for r in runs if r["policy"] == p and r["complete"])
            n = sum(r["policy"] == p for r in runs)
            xs = [1400] + [t for t in times for _ in (0, 1)] + [2000]
            ys = [0] + [v for i in range(len(times)) for v in (i / n, (i + 1) / n)] + [len(times) / n]
            left.plot(xs, ys, color=COLORS[p], label=p, lw=1.1)
        left.set_xlim(1400, 2000)
        left.set_ylim(0, 1)
        left.set_xlabel("Completion time [s]")
        left.set_ylabel("Missions completed (of 180)")
        left.legend(loc="lower right")
        left.text(1990, 0.97, "the rest stall at 7200 s", ha="right", va="top", fontsize=7, color=MUTED)
        policies = ("S1", "S2") + ONLINE
        balanced = {r["policy"]: r for r in _pooled(rates)}
        for i, p in enumerate(policies):
            r = balanced[p]
            right.bar(i, r["share"], 0.65, color=COLORS[p])
            right.errorbar(i, r["share"], yerr=[[r["share"] - r["low"]], [r["high"] - r["share"]]], color=INK, elinewidth=0.7, capsize=2)
        right.set_xticks(range(len(policies)), policies)
        right.grid(axis="x", visible=False)
        right.set_ylim(0, 1.05)
        right.set_ylabel("Stalled missions")
        right.set_title("Balanced progress, 90 seeds", fontsize=8)
        fig.tight_layout()
    return fig


def _pooled(rates):
    """Stall share per policy over the 90 balanced scenarios (slowdown repeats the same streams)."""
    out = []
    for p in ("S1", "S2") + ONLINE:
        g = [r for r in rates if r["policy"] == p and not r["slowdown"]]
        stalls, n = sum(r["stalls"] for r in g), sum(r["n"] for r in g)
        z = 1.959963984540054
        share = stalls / n
        centre = (share + z * z / (2 * n)) / (1 + z * z / n)
        half = z * np.sqrt(share * (1 - share) / n + z * z / (4 * n * n)) / (1 + z * z / n)
        out.append({"policy": p, "share": share, "low": max(0, centre - half), "high": min(1, centre + half)})
    return out


def critical_mechanism(timeline, facts):
    """Separation over the first 600 s with and without the two window exchanges."""
    with paper():
        fig, ax = plt.subplots(figsize=(COLUMN_IN, 2.6))
        lo, hi = (t - 5 for t in facts["window_s"][:1]), (t + 5 for t in facts["window_s"][-1:])
        ax.axvspan(next(lo), next(hi), color=WARNING, alpha=0.18, lw=0)
        ax.axhline(facts["radio_range_m"], color=DANGER, lw=0.7, ls=(0, (4, 3)))
        ax.text(5, facts["radio_range_m"] + 6, f"radio range {facts['radio_range_m']:.0f} m", color=DANGER, fontsize=7)
        ax.axhline(facts["fade_breaks_link_beyond_m"], color=MUTED, lw=0.6, ls=(0, (2, 2)))
        ax.text(5, facts["fade_breaks_link_beyond_m"] + 6, "a fade breaks the link beyond 100 m", color=MUTED, fontsize=7)
        for case, color, label in (("intact", COLORS["S3"], "window exchanges succeed: mission completes"),
                                   ("window_lost", DANGER, "both window exchanges lost: mission stalls")):
            g = [r for r in timeline if r["case"] == case and r["t"] <= 600]
            ax.plot([r["t"] for r in g], [r["separation_m"] for r in g], color=color, label=label, lw=1.1,
                    ls="-" if case == "intact" else (0, (5, 2)))
            lost = [r for r in g if not r["radio"]]
            ax.plot([r["t"] for r in lost], [r["separation_m"] for r in lost], ls="none", marker="x", color=color, markersize=3)
        ax.text(np.mean(facts["window_s"]), 15, "critical\nwindow", ha="center", fontsize=7, color=INK)
        ax.set_xlim(0, 600)
        ax.set_ylim(0, 440)
        ax.set_xlabel("Mission time [s]")
        ax.set_ylabel("Separation [m]")
        ax.legend(loc="upper right", fontsize=7)
        fig.text(0.5, -0.02, "S3, fade-free balanced mission. Crosses: missed exchanges. Stalled boats wait 326 m apart, 10 m out of range.",
                 ha="center", fontsize=7, color=MUTED)
        fig.tight_layout()
    return fig


def blackout_map(rows):
    """Effect of one full blackout of each duration starting at each exchange."""
    durations = sorted({r["duration_s"] for r in rows})
    cmap = ListedColormap(["#eef1f5", "#f3d58a", WARNING, DANGER])
    with paper():
        fig, axs = plt.subplots(len(ONLINE), 1, figsize=(COLUMN_IN, 4.2), sharex=True)
        for ax, p in zip(axs, ONLINE):
            g = [r for r in rows if r["policy"] == p]
            starts = sorted({r["start_s"] for r in g})
            grid = np.zeros((len(durations), len(starts)))
            for r in g:
                delay = r["restricted_s"] - 1425
                grid[durations.index(r["duration_s"]), starts.index(r["start_s"])] = (
                    3 if not r["complete"] else 2 if delay > 30 else 1 if delay > 0 else 0)
            step = starts[1] - starts[0]
            ax.pcolormesh(np.r_[starts, starts[-1] + step] - step / 2, np.arange(len(durations) + 1), grid,
                          cmap=cmap, vmin=-0.5, vmax=3.5, shading="flat")
            ax.set_yticks(np.arange(len(durations)) + 0.5, [f"{d} s" for d in durations])
            ax.set_ylabel(p)
            ax.grid(False)
        axs[-1].set_xlabel("Blackout start [s] (fade-free balanced mission, completes at 1425 s)")
        handles = [plt.Rectangle((0, 0), 1, 1, color=cmap(i)) for i in range(4)]
        fig.legend(handles, ["no effect", "delay 1 to 30 s", r"delay $>$ 30 s", "stall at 7200 s"], ncol=4, loc="lower center", bbox_to_anchor=(0.5, 0.0))
        fig.supylabel("Blackout duration", fontsize=9)
        fig.tight_layout(rect=(0, 0.06, 1, 1))
    return fig


def stall_vs_theory(rates, summary):
    """Observed stall share and restricted mean against the stationary-chain prediction."""
    ci = {(r["slowdown"], r["fade_length"], r["policy"]): r for r in summary}
    with paper():
        fig, (left, right) = plt.subplots(1, 2, figsize=(COLUMN_IN, 2.8))
        ls = np.linspace(1, 12, 200)
        q = next(r["theory_stall_probability"] for r in rates if r["theory_stall_probability"]) / (1 - 1 / 2)
        left.plot(ls, q * (1 - 1 / ls), color=INK, lw=1, label=r"$q\,(1-1/L)$, $q=0.2$")
        right_x = []
        for i, p in enumerate(ONLINE):
            g = sorted((r for r in rates if r["policy"] == p and not r["slowdown"]), key=lambda r: r["fade_length"])
            xs = np.array(LENGTHS) + (i - 1) * 0.25
            ys = [r["stall_share"] for r in g]
            left.errorbar(xs, ys, yerr=[[r["stall_share"] - r["stall_share_low"] for r in g], [r["stall_share_high"] - r["stall_share"] for r in g]],
                          ls="none", marker=MARKERS[p], color=COLORS[p], label=p, elinewidth=0.7)
            obs = [ci[(False, r["fade_length"], p)] for r in g]
            right.errorbar(xs, [o["restricted_mean_s"] for o in obs],
                           yerr=[[o["restricted_mean_s"] - o["ci_low_s"] for o in obs], [o["ci_high_s"] - o["restricted_mean_s"] for o in obs]],
                           ls="none", marker=MARKERS[p], color=COLORS[p], elinewidth=0.7)
            right.plot(LENGTHS, [r["expected_restricted_mean_s"] for r in g], color=COLORS[p], lw=0.8, ls=(0, (3, 2)))
        left.set_xlabel("Mean fade duration L [exchanges]")
        left.set_ylabel("Share of missions stalled")
        left.set_xlim(1, 11)
        left.set_xticks(LENGTHS)
        left.set_ylim(0, 0.45)
        left.legend(fontsize=7, loc="upper left")
        right.set_xlabel("Mean fade duration L [exchanges]")
        right.set_ylabel("Restricted mean time [s]")
        right.set_xticks(LENGTHS)
        right.set_ylim(0, 4000)
        right.text(0.98, 0.03, "points: observed, 95% paired bootstrap\ndashed: expected from the stall probability",
                   transform=right.transAxes, fontsize=7, color=MUTED, va="bottom", ha="right")
        left.set_title("Balanced progress", fontsize=8)
        right.set_title("Balanced progress", fontsize=8)
        fig.tight_layout()
    return fig


def write_all(tables, facts, runs, folder, core=None):
    core = Path(core) if core else Path(__file__).resolve().parents[2] / "results" / "core"
    rates = tables["stall-rates"]
    save(outcome_distribution(runs, rates), folder, "fig-outcome-distribution")
    save(stall_vs_theory(rates, read_rows(core / "condition-summary.csv")), folder, "fig-stall-vs-theory")
    if "timeline" in tables:
        save(critical_mechanism(tables["timeline"], facts), folder, "fig-critical-mechanism")
        save(blackout_map(tables["blackout-map"]), folder, "fig-blackout-map")
