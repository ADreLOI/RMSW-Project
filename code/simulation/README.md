# Two-USV simulator

Implements the live revised plan downloaded on 23 October 2026. Configurations: S1 fixed partition, S2 reactive short queue, S3 always-long queue, S4-T trend-triggered reservation, S4-P persistence-triggered reservation. All online configurations share an allocator and atomic protocol. No external robotics code was copied.

Use Python 3.10+. Recorded environment: Python 3.13, NumPy 1.26.4, Matplotlib 3.10.8, psutil 7.2.2; see `results/core/environment.json`. From this directory:

```powershell
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
python -m usv_sim.experiment pilot --output results/core
python -m usv_sim.experiment evaluate --output results/core --workers 4
python -m usv_sim.analysis --input results/core --paper ../../paper/Final_Report/generated
python -m usv_sim.benchmark --output results/core/host-benchmark.json
python -m usv_sim.replay --output results/core/replay.html
python scripts/build_report.py
```

With an existing environment, set `$env:PYTHONPATH='src'` instead of installing editable code. Linux/macOS use `.venv/bin/activate`; the isolated RAM benchmark currently uses Windows `peak_wset` and explicitly errors elsewhere. Other simulation, tests, and analysis are portable.

The provided `frozen-design.json` records margins, settings, disjoint pilot/evaluation seeds, event rules, and bootstrap settings; evaluation verifies its hash. For exact reproduction of the existing evaluation, keep that freeze and start at `evaluate`. Running `pilot` intentionally creates a new freeze. Both selected margins are 4 dB. Optional oracle and distance-loss sensitivity were not run.

For one mission:

```powershell
python -m usv_sim.experiment single --policy S4-T --seed 1000 --length 5 --slowdown --output results/single
python -m http.server 8766 --bind 127.0.0.1 --directory results/core
```

Open `http://127.0.0.1:8766/replay.html`, or open the self-contained file directly. The replay contains all five policies for seed 1000, slowdown, L=5; it reads retained evidence without changing the experiment.

Evidence in `results/core/`: `runs.json`, `condition-summary.csv`, `paired-contrasts.csv`, `held-out-warning-replay.json`, `warning-summary.json`, `host-benchmark.json`, `benchmark-inputs.json`, `raw-log-sha256.json`, `verification.json`, pilot files, and `replay.html`. Streamed bulk `raw/*.jsonl.gz` logs remain local and are ignored by Git; the commands regenerate them. `examples/` supplies a representative trace.

No software error is recoded as a timeout. Administrative timeouts retain `completion_s: null` and contribute 7200 s to restricted mean time. Intervals resample whole paired seeds within each condition; six primary intervals are marginal, without a simultaneous family-wise claim.

S2 stalls in every evaluated run under the specified no-rendezvous model. The long-queue control prevents interpreting capacity as forecast value. See [plan mapping](../docs/plan-to-code.md), [operation counts](../docs/operation-counts.md), and [review boundary](../docs/results-and-review.md). Independent author reproduction, source review, mentor feedback, and submission remain human follow-up work.
