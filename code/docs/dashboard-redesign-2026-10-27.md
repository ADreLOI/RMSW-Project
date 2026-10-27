# Dashboard redesign, 27 October 2026

Branch `ui/dashboard-redesign` (local). Design only: no simulation, allocation, predictor, logging or result data changed.

## Run it

```powershell
.\Run-Lab.ps1            # or, from code/simulation:
python -m usv_sim.dashboard --port 8768
```

Open `http://127.0.0.1:8768` (add `?lang=it` for Italian). No new dependency: no Node, build step or CDN. Fonts are local files under `src/usv_sim/web/fonts/` (OFL).

## Where the computation happens

Python on the local machine does everything; the browser only draws recorded events. Run → `POST /api/jobs` → queue in `dashboard.py` (one worker) → `workflow.run_bundle` → `model.run` per policy → raw logs, CSV, figures and hashes in `results/lab/<id>/` → `GET /api/job`, `/api/trace` → replay. The Guide view shows this as a diagram.

## What changed per view

| View | Change |
|---|---|
| Shell | Grouped sidebar (Simulate / Results / Operate / Learn); header with dataset, policy, seed, condition, elapsed vs 7200 s timeout and censored chip; EN/IT toggle; tour; motion pause |
| Live map | Token colours; cell states incl. "observed more than once"; per-state link line; always-visible legend; KPI grid with units (peak RAM shown as "not recorded") |
| Radio link (new) | Signal timeline with threshold, fade bands, warnings, failed samples; link-state counts; session budget (4 datagrams / 8192 B); forecast inspector; warning quality |
| Run log (new) | Monospace exchange table with link-state labels, budget filter, time search, JSON inspector |
| Core study | Same evidence; censored bars hatched with completed/runs labels; matplotlib figure downloads |
| Extension (new) | E1 time (same axis as core), recovery trips/idle, contrasts; E2 F1 vs cost, metric table by split, hardware projection; E3 map RMSE with shared axes; extension replays. S4-O labelled as a bound |
| Runs & jobs | Restyled; progress bars; bundle figure download |
| Guide (new) | Architecture diagram, first-simulation steps, policy glossary, reference of every control (same text as the tour) |
| Presentation | 16:9 deck in the earlier slides' style (wordmark, section label, mono counter, progress bar, breathing dot field on the title only), seven slides from live charts |

## Files

- `web/tokens.css`: the only palette (accent `#2670df`, USV 1 orange, USV 2 teal, cell/link states, amber warning, red timeout, 11 fixed policy colours). `plotstyle.py` reads it, so browser and paper share colours.
- `web/i18n.js`: one EN/IT dictionary; `tests/test_dashboard.py` checks key parity and coverage.
- `plotstyle.py`, `figures.py`, `scripts/build_figures.py`: one publication style (Computer Modern, 300 dpi, axes from zero, censoring visible).

## Design decisions

- The deck's blue is the single interface accent instead of indigo, as requested; the deck's teal is kept for USV 2 and USV 1 keeps the earlier orange, so the accent never encodes a vessel.
- Motion: functional 150–250 ms transitions in working views; the breathing dot field and slide reveals appear only in the Guide hero and the presentation, pausable and off under reduced motion.
- No 3D/WebGL. No invented metrics: values not in the data are shown as "not recorded".

## Checklist

One accent only · colour never alone (labels, dash patterns, hatching, icons) · identical axes across policy charts (0–8000 s core/extension time, shared y in map RMSE, symmetric contrast axes) · censored runs hatched/open and labelled · no 3D · no invented metrics · components built from shared tokens.
