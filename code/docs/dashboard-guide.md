# USV Research Lab: run, inspect, present, reproduce

The dashboard runs the actual Python simulator locally. It includes an animated map, five-policy replay, frozen statistical results, a raw-event inspector, an interactive presentation and automated verification workflows. New experiments are saved separately from the original study.

## Start on Windows

Open PowerShell in the repository root:

```powershell
.\Run-Lab.ps1 -Setup
```

This first command creates a project-local virtual environment, installs the existing Python dependencies, then opens the dashboard. Later, use:

```powershell
.\Run-Lab.ps1
```

The dashboard is at `http://127.0.0.1:8768`. Keep that terminal running; Ctrl+C stops it after queued work finishes. If the port is occupied, use `-Port 8769`. The launcher finds the project from its own location, so it also works when called by absolute path from another directory.

If the execution policy blocks the script, run the equivalent Python commands in an allowed shell; changing the machine's execution policy is unnecessary:

```powershell
cd code/simulation
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e .
.venv/Scripts/python.exe -m usv_sim.dashboard
```

On Linux/macOS, replace `.venv/Scripts/python.exe` with `.venv/bin/python`. After editable installation, `usv-dashboard` and `usv-workflow` are also available. Without an editable install, set `PYTHONPATH=src` from `code/simulation`. Python 3.10+ is required. The recorded environment is in `results/core/environment.json`.

No browser build step, npm packages, CDN, remote fonts or hosted account is needed. Initial Python package installation needs network access; subsequent simulation and dashboard use are local.

## Mission lab

1. Select a random seed, progress condition, fade duration and policy. For frozen evidence, use seeds 1000–1029, exponent 2 and cutoff 7200 s.
2. **Load recorded policies** loads available raw evidence for all five policies on that scenario. A fresh clone includes one representative S4-T trace; the bulk raw logs are intentionally excluded from Git.
3. **Run all five policies** regenerates that paired scenario in a new evidence bundle. **Run selected policy** runs only the selected configuration. Both use the frozen 4 dB warning margins.
4. Scrub the timeline, press Play, or choose 10× / 60× / 240× / 600× playback. The shared clock allows policies that stall to continue while completed policies hold their terminal state.
5. Click a comparison card to inspect that policy. The live metrics refer to the active policy at the displayed time, while each card also labels its final outcome.
6. Switch between global observed coverage and either boat's local knowledge. Trails show movement; task outlines show unstarted reservations; filled task cells show an executing target at the recorded snapshot. The line between boats uses the last exchange's radio availability.
7. Click the coverage or signal graph to seek. Filter the decision table to warnings, unavailable radio or committed allocations. Click an exchange row to inspect its exact JSON, including serialized messages, queues, knowledge and counted work.
8. **Save map** exports a PNG with policy, seed, simulation time and raw-log SHA-256. Chart arrow buttons export editable SVG. **Download full raw event log** exports the original `.jsonl.gz`, including every observation and 1 s motion tick.

Positions and observations come from exact 1 s model events; movement is interpolated between adjacent samples. Queue and radio states are snapshots every 10 s, not continuous measurements. Older logs omit terminal queues, so the end frame reports those as unavailable. Decorative map contours do not represent measured seabed data.

**Exploratory settings** allow exponent 1.5–3.0 and a 60–7200 s cutoff. These runs never enter the frozen evaluation. A shortened cutoff can end before the scheduled slowdown, which occurs at 600–900 s. Changing settings does not change an already recorded mission: run the selected settings to create new evidence. The source strip identifies the data actually displayed.

## Study evidence

The study page always uses the retained `results/core/` dataset, independently of the active exploratory run. Progress and fade filters select one of six conditions, containing 30 seeds × five policies = 150 records. The run table additionally filters complete or incomplete missions. Replay opens the corresponding raw trace; if it is absent locally, run that scenario to regenerate a separate reproduction.

| Metric | Meaning and units | Interpretation |
|---|---|---|
| Completion time | Seconds to first full global coverage; null if incomplete | Excludes return and upload |
| Restricted time | Completion time, or 7200 s at administrative cutoff | Keeps incomplete missions in policy comparisons |
| Coverage | Distinct observed cell centers / 240 | Does not establish physical map accuracy |
| Completion count | Completed missions out of 30 per condition | Descriptive count; no interval shown |
| Repeated observations | Total arrivals observed minus distinct observed cells | Includes transit through an already observed center |
| Distance | Sum of both boats' traveled meters | Finite-speed Manhattan paths, not calibrated dynamics |
| Idle time | Boat-seconds without an active motion task | Both boats' times may be summed; this can exceed mission time |
| Attempted / delivered payload | Serialized UTF-8 JSON bytes; kB = 1000 bytes | Failed radio attempts count; network headers excluded |
| Knowledge gap | Observed cells missing from a boat's local map / all cells | Denominator is the full 240-cell grid, not observed cells only |
| Link availability | Available sampled exchanges / sampled exchanges | Physical model availability; S1 still sends no online messages |
| Warning precision | Matched alerts / eligible alerts | Null when undefined, never silently zero |
| Warning recall | Matched outages / eligible outages | Two consecutive failed exchanges define an outage event |
| F1 | Harmonic balance of precision and recall | Uses collapsed alerts, one-to-one matching and boundary exclusions |
| Arithmetic / GOP | Counted binary64 arithmetic; GOP = operations / 10^9 | Logical tests, logarithms and square roots are separate |
| CPU time | Host process CPU nanoseconds; repeated decision benchmark shown in µs | Host-specific, distinct from simulated mission seconds |
| Process peak memory | Isolated Windows process high-water working set, MiB = 2^20 bytes | Includes runtime and geometry cache; not incremental Python allocation |

The time chart and paired contrasts use the already computed 2000-resample bootstrap results. Entire seed pairs are resampled within each condition. Displayed 95% intervals are marginal; the six primary comparisons do not form a simultaneous confidence statement. A negative S4-T-minus-control contrast favors S4-T. Do not infer a forecast benefit from its comparison with the stalled S2 baseline alone.

The warning-quality and arithmetic charts pool all six equally sized conditions and are explicitly descriptive. Warning quality uses held-out fixed-route replay so both predictors see identical routes. The host benchmark links to saved inputs, repetitions, batches, procedure and limitations. None of these resource measurements establishes energy or battery-lifetime savings.

## Runs, tests and automation

The **Runs & verification** page exposes three actions:

- **Run test suite**: retains full output and exit status.
- **Run smoke workflow**: tests → five paired seed-1000 / slowdown / L=5 missions → independent reconstruction → PNG/PDF/SVG → checksums → ZIP.
- **Run 900-mission workflow**: tests → frozen evaluation with two worker processes → all-log reconstruction → statistical tables and publication figures → checksums → ZIP. This uses the supplied freeze and does not retune on evaluation seeds.

The equivalent commands, from the repository root:

```powershell
.\Run-Lab.ps1 -Action Test
.\Run-Lab.ps1 -Action Smoke
.\Run-Lab.ps1 -Action Full -Workers 4
```

Or from `code/simulation`:

```text
python -m usv_sim.workflow --preset smoke
python -m usv_sim.workflow --preset full --workers 4
python -m usv_sim.verify results/lab/<id> --reference results/core
```

Each invocation creates a unique `results/lab/<UTC-id>/`. CLI runs under that default path also appear in the dashboard's activity list. A user-specified `--output` must name a new directory; a custom output outside `results/lab` remains accessible directly on disk. Inspect a job for provenance, test output and results; download the evidence ZIP or reopen its replay. Failed/interrupted jobs are labeled explicitly and retain partial diagnostics. Jobs are serial in the dashboard; it accepts at most four active/queued jobs. There is no automatic cancellation or resume: closing the browser leaves the engine running, while Ctrl+C waits for queued work.

`--benchmark` adds the optional repeated CPU and isolated RAM procedure to a CLI workflow. The RAM procedure currently requires Windows and fails explicitly elsewhere. Core simulation, tests, dashboard and statistical analysis work on Linux/macOS too.

## Presentation

Open **Presentation** for five scenes: research question, visual mechanism, observed completion results, interpretation, reproducibility. Use Previous / Next, the dots or ← / →. The mechanism scene animates the active mission with its real data. Choose the scenario and timeline in Mission lab first. Full screen opens a focused layout and also requests native fullscreen where supported. Embedded browsers can use the focused layout without native fullscreen. Exit with the visible button or Escape. Browser Print exports the current scene.

The presentation is interactive HTML within the dashboard. It is not a PowerPoint file or a submitted course presentation. Its content deliberately includes the adverse results and the no-rendezvous limitation. Before a class presentation, select a representative mission, load all policies, and run the smoke workflow.

## Reproduce an exported bundle

Extract `evidence.zip` into a dedicated directory and follow its `REPRODUCE.md`. The archive includes the source and tests used for that run. Typical commands are:

```text
python -m pip install -e source
python -m usv_sim.workflow --preset scenario --design frozen-design.json --request request.json --output ../reproduced-bundle
python -m usv_sim.verify ../reproduced-bundle --reference .
```

Full-study bundles use `--preset full` without `--request`. Hash verification checks byte integrity; reference comparison checks deterministic scientific results and excludes CPU/wall timings. Gzip headers, timings and process memory may change on regeneration. Do not edit a bundle in place; derived checks should be saved outside it.

## Files and troubleshooting

- `AGENTS.md`: scientific rules and essential commands for any coding tool.
- `code/docs/agent-handoff.md`: architecture, findings, known limits and a ready-to-copy handoff prompt.
- `code/docs/work-log.md`: what was done and verified, including the earlier report/repository work.
- `code/docs/architecture.md`: module responsibilities, event/replay boundary and API.
- `code/docs/operation-counts.md`: precise accounting conventions.

If the engine disconnects, inspect the terminal and restart the launcher. If a raw trace is unavailable, run the paired scenario; the browser never fabricates a missing trace. If tests cannot open a socket in a restricted execution environment, grant the runner its normal localhost permission and rerun; do not treat a permission failure as a scientific result. If a job fails, inspect `tests.log`, `error.log` or the named workflow log before rerunning in a fresh directory.
