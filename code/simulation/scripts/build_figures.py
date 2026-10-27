"""Redraw the report figures in the shared publication style from saved summaries.

Reads only retained CSV/JSON outputs (no simulation, no log reconstruction), so
plotted values are the analysed values. Writes PNG (300 dpi) and PDF next to the
existing figures under paper/Final_Report/generated/ unless --output is given.
"""
import argparse
import json
from pathlib import Path
import sys

SIMULATION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIMULATION / "src"))

from usv_sim import figures  # noqa: E402
from usv_sim.plotstyle import save  # noqa: E402

ROOT = SIMULATION.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, default=SIMULATION / "results" / "core")
    parser.add_argument("--extension", type=Path, default=SIMULATION / "results" / "extension")
    parser.add_argument("--output", type=Path, default=ROOT / "paper" / "Final_Report" / "generated")
    args = parser.parse_args()
    core = figures.read_rows(args.core / "condition-summary.csv")
    save(figures.mission_time(core, figures.CORE_POLICIES), args.output, "mission-time")
    save(figures.resource_tradeoff(core, figures.CORE_POLICIES), args.output, "resource-tradeoff")
    design, summary, _, warning = figures.load_extension(args.extension)
    maps = json.loads((args.extension / "map-accuracy-runs.json").read_text(encoding="utf-8"))
    out = args.output / "extension"
    save(figures.mission_time(summary, design["policies"], offset=0.08, ymax=None), out, "extension-mission-time")
    save(figures.predictor_cost(warning, design["policy_predictors"]), out, "predictor-cost-quality")
    save(figures.map_rmse(figures.map_curves(maps)), out, "map-rmse-time")
    print(f"Figures written to {args.output}")


if __name__ == "__main__":
    main()
