"""Figures for the post-hoc link-loss analysis (see linkloss.py); values come from its tables."""
import matplotlib.pyplot as plt
import numpy as np

from .plotstyle import COLORS, COLUMN_IN, DANGER, MARKERS, MUTED, paper, save

POLICIES = ("S1", "S2", "S3", "S4-T", "S4-P")
LENGTHS = (2, 5, 10)
PANELS = ((False, "Balanced progress"), (True, "Temporary slowdown"))
TIMEOUT_S = 7200


def _series(rows, slowdown, policy, key):
    g = sorted((r for r in rows if r["slowdown"] == slowdown and r["policy"] == policy), key=lambda r: r["fade_length"])
    return [r[key] for r in g]


def _legend(fig, ax, ncol, y=0.0):
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, ncol=ncol, loc="lower center", bbox_to_anchor=(0.5, y), handlelength=1.6, columnspacing=1)


def _lines(rows, specs, policies, height):
    """One row of panels per (key, label, ylim) spec, columns are the progress conditions."""
    with paper():
        fig, axs = plt.subplots(len(specs), 2, figsize=(COLUMN_IN, height), sharex=True, sharey="row", squeeze=False)
        for row, (key, label, ylim) in enumerate(specs):
            for ax, (slow, title) in zip(axs[row], PANELS):
                for p in policies:
                    ys = _series(rows, slow, p, key)
                    if all(y is not None for y in ys):
                        ax.plot(LENGTHS, ys, color=COLORS[p], marker=MARKERS[p], label=p)
                if row == 0:
                    ax.set_title(title)
                if row == len(specs) - 1:
                    ax.set_xlabel("Mean fade duration [exchanges]")
                ax.set_xticks(LENGTHS)
                if ylim:
                    ax.set_ylim(*ylim)
            axs[row][0].set_ylabel(label)
        _legend(fig, axs[0][0], len(policies), y=0.02)
        fig.tight_layout(rect=(0, 0.08, 1, 1))
    return fig


def link_loss(summary):
    """How often the link is lost, and how much of it is due to distance rather than fades."""
    fig = _lines(summary, (("completed_outages_per_hour", "Outages per mission hour", (0, None)),
                           ("completed_link_availability", "Link availability", (0, 1)),
                           ("completed_share_missed_by_distance", "Missed exchanges\ndue to distance", (0, 1))),
                 ("S1", "S3", "S4-T", "S4-P"), 5.4)
    with paper():
        fig.text(0.5, 0.0, "Completed missions only. S2 completes none; its stalled runs are a single distance outage.",
                 ha="center", fontsize=7, color=MUTED)
    return fig


def resilience(rows):
    """Performance retained under fades relative to the same policy with an ideal link."""
    return _lines(rows, (("mean_retention", "Retention (ideal time / time)", (0, 1.05)),
                         ("completion_proportion", "Completed missions", (0, 1.05))), ("S1", "S3", "S4-T", "S4-P"), 4.0)


def time_vs_link(runs, correlations):
    """Per-run completion time against exogenous fade exposure and against the run's own availability."""
    policies = ("S3", "S4-T", "S4-P")
    rho = {(r["policy"], r["x"]): r for r in correlations if r["scope"] == "all conditions" and r["y"] == "restricted_s"}
    specs = (("fade_exposure", "Fade exposure of the seed stream"), ("link_availability", "Link availability of the run"))
    with paper():
        fig, axs = plt.subplots(2, 3, figsize=(COLUMN_IN, 4.4), sharey=True, sharex="row")
        for row, (key, label) in enumerate(specs):
            for ax, p in zip(axs[row], policies):
                g = [r for r in runs if r["policy"] == p]
                done = [r for r in g if r["complete"]]
                cut = [r for r in g if not r["complete"]]
                ax.plot([r[key] for r in done], [r["restricted_s"] for r in done], ls="none", marker=MARKERS[p],
                        color=COLORS[p], alpha=0.55, markersize=2.6, markeredgewidth=0)
                ax.plot([r[key] for r in cut], [r["restricted_s"] for r in cut], ls="none", marker=MARKERS[p],
                        color=COLORS[p], markerfacecolor="white", markersize=3.2)
                c = rho[(p, key)]
                ax.text(0.97, 0.62, rf"$\rho$ = {c['spearman_rho']:.2f}" + f"\n[{c['ci_low']:.2f}, {c['ci_high']:.2f}]",
                        transform=ax.transAxes, ha="right", va="top", fontsize=7.5, color=MUTED)
                ax.axhline(TIMEOUT_S, color=DANGER, lw=0.6, ls=(0, (4, 3)))
                if row == 0:
                    ax.set_title(p)
                ax.set_xlabel(label)
            axs[row][0].set_ylabel("Restricted time [s]")
        fig.text(0.5, 0.0, "Open marker: run censored at the 7200 s cutoff. Spearman rank correlation over 180 runs, 95% bootstrap interval.",
                 ha="center", fontsize=7, color=MUTED)
        fig.tight_layout(rect=(0, 0.03, 1, 1))
    return fig


def per_100_outages(rows):
    """Outcomes normalised by the number of outages experienced, with bootstrap intervals."""
    specs = (("incomplete_missions_per_100_outages", "Unfinished missions\nper 100 outages", ("S3", "S4-T", "S4-P")),
             ("reserved_before_per_100_eligible", "Outages preceded by a\ncommitted reservation [%]", ("S4-T", "S4-P")),
             ("timely_alerts_per_100_eligible", "Outages with a\ntimely warning [%]", ("S4-T", "S4-P")))
    width = 0.24
    with paper():
        fig, axs = plt.subplots(len(specs), 2, figsize=(COLUMN_IN, 5.6), sharex=True, sharey="row")
        for row, (key, label, policies) in enumerate(specs):
            for ax, (slow, title) in zip(axs[row], PANELS):
                for i, p in enumerate(policies):
                    g = sorted((r for r in rows if r["slowdown"] == slow and r["policy"] == p), key=lambda r: r["fade_length"])
                    ys = np.array([r[key] for r in g])
                    xs = np.arange(len(LENGTHS)) + (i - (len(policies) - 1) / 2) * width
                    err = [ys - [r[key + "_low"] for r in g], [r[key + "_high"] for r in g] - ys]
                    ax.bar(xs, ys, width * 0.92, color=COLORS[p], label=p, yerr=err, error_kw={"elinewidth": 0.7})
                if row == 0:
                    ax.set_title(title)
                ax.set_xticks(range(len(LENGTHS)), LENGTHS)
                ax.grid(axis="x", visible=False)
                ax.set_ylim(0, None)
                if row == len(specs) - 1:
                    ax.set_xlabel("Mean fade duration [exchanges]")
            axs[row][0].set_ylabel(label)
        _legend(fig, axs[0][0], 3)
        fig.tight_layout(rect=(0, 0.05, 1, 1))
    return fig


def cost_benefit(rows):
    """Radio traffic against mission time: one point per policy and condition."""
    with paper():
        fig, axs = plt.subplots(1, 2, figsize=(COLUMN_IN, 3.1))
        for p in POLICIES:
            g = [r for r in rows if r["policy"] == p]
            axs[0].plot([r["attempted_kb"] for r in g], [r["restricted_mean_s"] for r in g], ls="none",
                        marker=MARKERS[p], color=COLORS[p], label=p)
            if p != "S1":
                axs[1].plot([r["restricted_mean_s"] for r in g], [r["delivery_ratio"] for r in g], ls="none",
                            marker=MARKERS[p], color=COLORS[p])
        axs[0].set_xlabel("Attempted traffic per mission [kB]")
        axs[0].set_ylabel("Restricted mean time [s]")
        axs[0].set_ylim(0, 7500)
        axs[0].axhline(TIMEOUT_S, color=DANGER, lw=0.6, ls=(0, (4, 3)))
        axs[1].set_xlabel("Restricted mean time [s]")
        axs[1].set_ylabel("Delivered / attempted bytes")
        axs[1].set_ylim(0, 1)
        _legend(fig, axs[0], len(POLICIES))
        fig.tight_layout(rect=(0, 0.07, 1, 1))
    return fig


def write_all(tables, folder):
    save(link_loss(tables["link-loss-summary"]), folder, "fig-link-loss")
    save(time_vs_link(tables["per-run"], tables["correlations"]), folder, "fig-time-vs-link")
    save(per_100_outages(tables["per-100-outages"]), folder, "fig-per-100-outages")
    save(cost_benefit(tables["communication-cost"]), folder, "fig-cost-benefit")
    if "resilience" in tables:
        save(resilience(tables["resilience"]), folder, "fig-resilience")
