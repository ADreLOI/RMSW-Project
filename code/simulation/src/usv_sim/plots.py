"""Publication exports for a paired exploratory mission (no inferential intervals)."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLORS = {"S1": "#64748b", "S2": "#c96a42", "S3": "#b68b22", "S4-T": "#087f81", "S4-P": "#8466af"}


def export_figures(destination, rows):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with plt.rc_context({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False}):
        fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
        fields = [("restricted_s", "Restricted mission time [s]", 1),
                  ("coverage", "Final observed coverage [%]", 100),
                  ("attempted_bytes", "Attempted payload [kB]", .001)]
        for ax, (field, label, scale) in zip(axes, fields):
            bars = ax.bar([r["policy"] for r in rows], [r[field] * scale for r in rows],
                          color=[COLORS[r["policy"]] for r in rows], width=.6)
            ax.set_ylabel(label)
            ax.grid(axis="y", alpha=.16)
            ax.set_axisbelow(True)
            for bar, row in zip(bars, rows):
                if not row["complete"]:
                    bar.set_hatch("///")
        fig.suptitle("One paired synthetic scenario · hatched bars: incomplete at cutoff", fontsize=12)
        fig.tight_layout()
        for extension in ("png", "pdf", "svg"):
            fig.savefig(destination / f"paired-mission.{extension}", dpi=180)
        plt.close(fig)
