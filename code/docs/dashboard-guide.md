# USV·PAC research lab: run, inspect, present, reproduce

The dashboard runs the actual Python simulator locally. All computation (simulation, verification, statistics, publication figures) happens in Python on this computer; the browser only draws recorded events. It includes an animated map, policy replay, the radio-link view, the frozen core study, the extension study (E1–E3), a raw-event log, a guided tour, an English/Italian interface, a presentation deck and automated verification workflows. New experiments are saved separately from the original study.

## Views at a glance

| Sidebar | View | What it shows |
|---|---|---|
| Simulate | **Live map** | Replayed mission on the 20 × 12 grid, scenario/policy setup, KPIs, per-boat state, synchronized comparison, coverage over time |
| Simulate | **Radio link** | Signal per exchange vs the −90 dBm threshold, fade episodes, warnings, link-state counts, session budget, causal forecast inspector, warning quality |
| Simulate | **Run log** | Every exchange in monospace, filterable (warnings, failures, budget, commits), time search, raw JSON inspector |
| Results | **Core study** | The frozen 900-run study per condition, figure downloads, run explorer, provenance |
| Results | **Extension** | E1 recovery, E2 predictors (quality, cost, hardware projection), E3 synthetic map accuracy, extension replays |
| Operate | **Runs & jobs** | Test, smoke and full workflows; job history, bundles and downloads |
| Learn | **Guide** | Architecture diagram (where computation happens), first-simulation walkthrough, policy glossary, reference of every control |
| Learn | **Presentation** | 16:9 deck built from the live views, in the style of the earlier USV·PAC slides |

The header always shows the replayed dataset, policy, seed, condition and the replay clock against the 7200 s timeout (the tick marks where the mission stopped; a red chip appears when it was censored). **Tour** opens a step-by-step overlay of every control; the Guide's **Run your first simulation** starts a shorter walkthrough. **EN / IT** switches the language (remembered per browser; `?lang=it` forces it). The wave button pauses decorative motion; `prefers-reduced-motion` is honoured automatically.

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

No browser build step, npm packages, CDN, remote fonts or hosted account is needed. Fonts (Poppins, Inter, OFL) are served locally from `web/fonts/`; monospace text uses DM Mono when installed, otherwise Cascadia Mono / Consolas. Initial Python package installation needs network access; subsequent simulation and dashboard use are local.

## Live map

1. Select a random seed, progress condition, fade duration and policy. For frozen evidence, use seeds 1000–1029, exponent 2 and cutoff 7200 s.
2. **Load recorded policies** loads available raw evidence for all five policies on that scenario. A fresh clone includes one representative S4-T trace; the bulk raw logs are intentionally excluded from Git.
3. **Run all five policies** regenerates that paired scenario in a new evidence bundle. **Run selected policy** runs only the selected configuration. Both use the frozen 4 dB warning margins.
4. Scrub the timeline, press Play, or choose 10× / 60× / 240× / 600× playback. The shared clock allows policies that stall to continue while completed policies hold their terminal state.
5. Click a comparison card to inspect that policy. The live metrics refer to the active policy at the displayed time, while each card also labels its final outcome.
6. Switch between global observed coverage and either boat's local knowledge. Trails show recorded movement; numbered task outlines (orange USV 1, teal USV 2) show unstarted claims; a cross marks an executing target; hatched cells were observed more than once (**Repeats**). The link line between the boats has one style per state: solid green connected, grey dashed faded, purple dash-dot budget exhausted, dotted out of range. Positions and task overlays remain observer data in every layer. The radio line anchors to positions at the last measured exchange, with its sample age stated.
7. Click the coverage, signal or budget chart to seek. In **Run log**, filter to warnings, unavailable radio, budget failures or committed allocations, or type a time. Click an exchange row to inspect its exact JSON, including serialized messages, queues, knowledge and counted work.
8. **Save map** exports a white-background PNG with policy, seed, simulation time and raw-log SHA-256. **Raw event log** (Run log) exports the original `.jsonl.gz`, including every observation and 1 s motion tick.

KPIs refer to the active policy at the replay time unless labelled "whole run": coverage (cells / 240), completion time or "Censored" at the timeout, redundant observations, datagrams, payload kB, missing information (worse boat at the last exchange; mission mean), coordination CPU (host-specific) and counted operations. Peak RAM is not measured per run and is shown as "not recorded"; see the host benchmark.

## Radio link

Link states per exchange come only from recorded fields: *budget exhausted* when `budget_failure` is set, *connected* when the radio delivered, *out of range* when `distance_failure` is set (the link fails even without a fade), otherwise *faded*. Grey bands mark contiguous fade episodes of the pre-generated scenario; amber triangles mark committed warnings; open circles are failed exchanges, which the predictor never receives. The budget panel shows offered datagrams (limit 4) and payload bytes (limit 8192) for the exchange at the replay time and for every exchange. Warning quality (precision, recall, F1, mean lead time) is the pooled held-out core result; per-run warning scores are not part of a trace.

Positions and observations come from exact 1 s model events; movement is interpolated between adjacent samples. New schema-2 logs additionally record exact task/motion states every second and at termination, including discrete activity and commanded translation speed. A turning/idle boat does not move at that command. Legacy schema-1 logs retain 10 s sampled tasks and omit terminal queues, so those states are labeled sampled or unavailable. Radio remains a 10 s measurement in both schemas. The map shows model coordinates and cell-center bookkeeping, with no invented bathymetry or sensor footprint.

The causal forecast inspector shows delivered signal history at the selected issuance time and its four stored projections. Subsequent measured signals are excluded from that view. The separate observer signal chart includes failed exchanges, which were not received by the predictor. Use **Slowdown onset** to inspect the scenario's actual onset, and inspect the per-boat panel for exact activity, task state and missing local observations.

**Exploratory settings** allow exponent 1.5–3.0 and a 60–7200 s cutoff. These runs never enter the frozen evaluation. A shortened cutoff can end before the scheduled slowdown, which occurs at 600–900 s. Changing settings does not change an already recorded mission: run the selected settings to create new evidence. The source strip identifies the data actually displayed.

## Core study

The Core study page always uses the retained `results/core/` dataset, independently of the active exploratory run. Progress and fade filters select one of six conditions, containing 30 seeds × five policies = 150 records. The run table additionally filters complete or incomplete missions. Replay opens the corresponding raw trace; if it is absent locally, run that scenario to regenerate a separate reproduction.

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

Bars that include runs censored at 7200 s are hatched and labelled with completed / runs. The download icon on the mission-time and contrast cards returns a **publication figure** (`/api/figure`, PNG at 300 dpi) drawn by matplotlib from the retained summaries in the report's style; the other chart buttons export the browser chart as a paper-style PNG (white background, black serif text, 3× resolution).

## Extension

The Extension page reads `results/extension/` through the read-only `/api/extension` endpoint and never mixes it with core numbers: E1 mission time (same 0–8000 s axis as the core chart), recovery trips and idle time; primary/secondary/context paired contrasts; E2 held-out warning F1 against counted operations (log scale) and the full metric table per split; the assumption-based hardware projection per profile; E3 synthetic map RMSE over time with identical y-axes for core and extension logs. S4-O reads true future fades and is labelled as a bound, never as a deployable policy. Extension traces (seeds 2000–2029) can be replayed from its run explorer; new runs from the setup panel always use the core design.

## Runs, tests and automation

The **Runs & jobs** page exposes three actions:

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

Open **Presentation** for seven 16:9 slides in the style of the earlier USV·PAC deck (wordmark, section label, mono counter, progress bar, breathing signal field on the title slide): title, question, mechanism, radio link, core outcome, extension, reproducibility. Use Previous / Next, the dots or ← / →. The mechanism slide animates the active mission with its real data; the link, outcome and extension slides reuse the live charts. Choose the scenario and timeline in Mission lab first. Full screen opens a focused layout and also requests native fullscreen where supported. Embedded browsers can use the focused layout without native fullscreen. Exit with the visible button or Escape. Browser Print exports the current scene.

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

Redraw the report figures in the shared style with `python code/simulation/scripts/build_figures.py`; it reads only retained CSV/JSON summaries, so plotted values cannot change. Colours come from `web/tokens.css` through `usv_sim/plotstyle.py`. Regenerate the report's four outcome/contrast tables and appendix resource tables from the retained data with `python code/simulation/scripts/build_report.py` from the repository root. It checks the complete matrix, records input/output hashes, and writes only generated tables. Prose, bibliography and template files remain edited sources. `python code/simulation/scripts/package_report.py --output <new.zip>` creates a paper-only Overleaf package with source hashes. Inspect/back up live Overleaf before synchronizing, then compile and inspect the PDF; ZIP creation alone does not verify the live draft.

- `AGENTS.md`: scientific rules and essential commands for any coding tool.
- `code/docs/agent-handoff.md`: architecture, findings, known limits and a ready-to-copy handoff prompt.
- `code/docs/work-log.md`: what was done and verified, including the earlier report/repository work.
- `code/docs/architecture.md`: module responsibilities, event/replay boundary and API.
- `code/docs/operation-counts.md`: precise accounting conventions.

If the engine disconnects, inspect the terminal and restart the launcher. If a raw trace is unavailable, run the paired scenario; the browser never fabricates a missing trace. If tests cannot open a socket in a restricted execution environment, grant the runner its normal localhost permission and rerun; do not treat a permission failure as a scientific result. If a job fails, inspect `tests.log`, `error.log` or the named workflow log before rerunning in a fresh directory.
