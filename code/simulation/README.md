# Two-USV simulator and visual research lab

Implements the revised plan downloaded on 23 October 2026. Five configurations share the specified common allocator and atomic protocol: S1 fixed partition, S2 reactive short queue, S3 always-long queue, S4-T trend-triggered reservation, S4-P persistence-triggered reservation. No external robotics implementation was copied.

## Open the dashboard

From the repository root on Windows, run `.\Run-Lab.ps1 -Setup` once, then `.\Run-Lab.ps1`. It opens `http://127.0.0.1:8768` and keeps a local Python engine running. Alternatively, from this directory:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e .
.venv/Scripts/python.exe -m usv_sim.dashboard
```

Linux/macOS use `.venv/bin/python`. With an existing environment, install editable code or set `PYTHONPATH=src`. Python 3.10+ is required; NumPy, Matplotlib and psutil are the existing dependencies. No npm/browser build or online service is needed. Use `--port 8769` if 8768 is occupied, or `--no-browser` to start the engine alone.

The dashboard includes a 1 s trajectory replay, knowledge/task layers, five-policy synchronized comparison, coverage/signal charts, event inspection, frozen study statistics, run table, host benchmark, experiment/test controls and an interactive five-scene presentation. PNG maps, SVG charts, raw logs and evidence ZIPs can be downloaded. See the [full operating and metric guide](../docs/dashboard-guide.md).

## Automated workflows

With the package installed, from this directory:

```text
python -m unittest discover -s tests -v
python -m usv_sim.workflow --preset smoke
python -m usv_sim.workflow --preset full --workers 4
python -m usv_sim.verify results/lab/<id> --reference results/core
```

Every workflow creates a new `results/lab/<UTC-id>/`, retaining source/tests, settings, frozen reference, environment, raw events, reconstructed metrics, figures, step logs, hashes, reproduction instructions and `evidence.zip`. A custom `--output` must be a new directory. CLI jobs in the default lab directory also appear in dashboard activity. New runs never extend or overwrite the retained frozen evaluation or the paper.

`smoke` runs tests, five paired missions at seed 1000 / slowdown / L=5, independent reconstruction and PNG/PDF/SVG export. `full` runs tests, all 900 frozen evaluation missions, all-log reconstruction, bootstrap analysis and publication figures. `--benchmark` optionally adds repeated CPU and isolated process-memory profiling; the RAM procedure currently uses Windows `peak_wset` and fails explicitly elsewhere.

An exported bundle includes `REPRODUCE.md`. To replay a captured exploratory request in a fresh directory:

```text
python -m usv_sim.workflow --preset scenario --design path/to/frozen-design.json --request path/to/request.json --output results/lab/new-reproduction
```

`verify` checks file hashes and exact deterministic mission values against a reference, excluding `wall_s` and component `cpu_ns`. Timings, process memory and gzip headers can differ across regenerations. In restricted environments the HTTP integration tests require normal localhost socket access; no remote network is used by tests.

## Retained study

`results/core/frozen-design.json` records margins, settings, disjoint pilot/evaluation seeds, warning rules and bootstrap settings. Evaluation verifies its hash. Both selected warning margins are 4 dB. The core evaluation is 5 policies x 2 progress conditions x 3 fade lengths x 30 paired seeds = 900 missions, after a separate 300-mission pilot. Optional oracle and distance-loss sensitivity studies were not part of that core evaluation.

Core artifacts include `runs.json`, condition summaries, paired contrasts, fixed-route warning replay, warning summary, component resources, outage/mechanism diagnostics, host benchmark/saved inputs, raw-log hashes and verification. Bulk `raw/*.jsonl.gz` logs are local and ignored by Git; the workflow regenerates them. `examples/` supplies a representative S4-T trace so a fresh clone can inspect one mission before generating others. The older self-contained `results/core/replay.html` remains a historical replay; use the dashboard for current controls and explicit terminal-state handling.

Lower-level commands remain available for controlled use:

```text
python -m usv_sim.experiment single --policy S4-T --seed 1000 --length 5 --slowdown --output results/single
python -m usv_sim.experiment pilot --output results/new-study
python -m usv_sim.experiment evaluate --output results/new-study --workers 4
python -m usv_sim.analysis --input results/new-study --paper results/new-study/figures
python -m usv_sim.benchmark --output results/new-study/host-benchmark.json
```

`single` uses frozen margins and writes its settings. `pilot` creates a new freeze; do not retune on evaluation outcomes. Existing CLI output replacement requires explicit `--overwrite`. Evaluation rejects a path-exponent override instead of claiming an unchanged freeze. For reproduction of the retained study, prefer the full workflow, which copies the existing freeze and writes fresh evidence.

No software error is recoded as a timeout. Incomplete completion time is null; restricted time is 7200 s. Intervals resample whole paired seeds within each condition, with marginal 95% coverage and no simultaneous family-wise claim.

S1 completed all 180 missions, S2 none, S3 158, S4-T 156 and S4-P 162. The no-rendezvous model allows empty queues beyond radio range. Trend prediction shows no consistent advantage over always-long queues or persistence. Counts, bytes and host resource measurements do not establish measured energy, battery lifetime or map accuracy.

Read the [plan mapping](../docs/plan-to-code.md), [operation conventions](../docs/operation-counts.md), [architecture](../docs/architecture.md), [work log](../docs/work-log.md) and [agent handoff](../docs/agent-handoff.md). Author reproduction, mentor review, report reconciliation and course submission remain separate follow-up.
