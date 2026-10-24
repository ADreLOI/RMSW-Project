# Agent handoff: RMSW / II2202

## Objective and current state

Andrea Lo Iacono and Ettore Mugisha Cirillo are studying whether short-horizon radio prediction improves two-boat coverage under intermittent communication. The redefined research plan is the authority. The repository now separates paper and code, implements all five configurations, retains a completed 900-run evaluation following a separate 300-run pilot, and provides a local visual research dashboard with experiment automation and evidence bundles.

Start with the root `AGENTS.md`; it contains scientific invariants, preservation rules and commands. Read `dashboard-guide.md` to operate the application and `architecture.md` before editing it. `work-log.md` records completed work and validation, including the earlier report setup.

The active implementation branch is `implementation/research-plan-simulator`, tracked through [PR #1](https://github.com/ADreLOI/RMSW-Project/pull/1). It is a review branch, not a merged/submitted deliverable. Inspect live Git/PR state before relying on this note. There is an older dirty checkout outside this implementation checkout that must be preserved.

## Scientific status

The frozen study uses a 20×12 grid, finite speed/turn cost, pre-generated two-state radio fades, bounded atomic coordination and optional temporary slowdown. Evaluation contains five policies × six conditions × 30 seed pairs. Both warning margins were selected as 4 dB on separate pilot fixed-route replay. The common allocator, tie rules and serialization matter; read `plan-to-code.md` and the research-plan method sections.

Across 180 missions per policy, completion counts are S1=180, S2=0, S3=158, S4-T=156, S4-P=162. S2 can exhaust tasks beyond radio range; no rendezvous controller exists. Trend warnings do not show a consistent advantage over an always-long queue or persistence. Fixed-route held-out warning F1 is about 0.175 for both predictors. Zero task conflicts and message-budget failures were observed in the frozen evaluation.

Incomplete mission completion time is null, restricted time is 7200 s. Statistical intervals resample whole paired seeds within each condition, 2000 times, and are marginal 95%. Resource quantities are operation/byte counts and host CPU/RAM observations; no measured energy, battery lifetime, map accuracy, calibrated vessel physics or field performance is established.

The dashboard does not change the scientific model. New run controls can explore exponent and cutoff while retaining the frozen reference and recording the effective configuration. These results remain separate from `results/core/`. A new controller or baseline belongs in a documented new design, not a quiet fix to make existing results favorable.

## Implementation and evidence entry points

| Need | Read / run |
|---|---|
| Scientific contract | `paper/research-plan/sections/02.*`, `code/docs/plan-to-code.md` |
| Protocol, motion, predictor | `code/simulation/src/usv_sim/model.py` |
| Raw-log check | `analysis.reconstruct(path)`; `tests/test_simulator.py` |
| Dashboard API / queue | `dashboard.py`; `tests/test_dashboard.py` |
| Browser visualization / charts | `web/index.html`, `web/style.css`, `web/app.js` |
| Provenance / trace | `evidence.py` |
| Automated execution | `workflow.py`, root `Run-Lab.ps1` |
| Exact science comparison | `verify.py` |
| Current frozen evidence | `code/simulation/results/core/` |
| New run history | `code/simulation/results/lab/` (ignored bulk outputs) |
| Publication report | `paper/Final_Report/main.tex`, modular sections and `generated/` |
| Validation record | `work-log.md`, `code/docs/validation/` |

The event stream is the authority for replay. New schema-2 logs record exact task/motion state each second and at termination. Radio and forecasts remain 10 s samples. Post-exchange state supersedes its pre-exchange tick at the same time. Legacy logs retain sampled task state and unavailable terminal queues; the dashboard never invents these. Numbered markers, model x/y axes, sample ages, local knowledge panels and a causal forecast inspector make the observer's information distinct from a boat's available information. No decorative bathymetry or inferred vessel yaw is shown.

The fidelity audit is in `scientific-audit-2026-10-23.md`. Explicit reconstruction checks survive `python -O`, and analysis verifies the exact frozen matrix and design hash. All 900 original raw hashes remain unchanged. The integrated workflow `results/lab/20261023T203550-5f2c5b0a/` passed 32 tests, reconstructed 900 new schema-2 logs and matched every scientific record against core exactly, excluding host CPU/wall timing. Its 950 inventoried files passed integrity verification. Browser evidence and retained headless checks are under `validation/`.

The browser is buildless and local. Python's standard-library HTTP server runs a serial fixed-action queue and uses validated requests, loopback binding, Host/origin/token checks and allowlisted exports. It is not intended for public hosting. Presentation mode is a five-scene interactive browser presentation, not a PowerPoint artifact. Bulk raw logs are ignored by Git; a fresh clone can inspect the included S4-T example and regenerate all other traces.

## Reproduce and validate

From the repository root on Windows, use `.\Run-Lab.ps1 -Setup` once, then `.\Run-Lab.ps1`. From `code/simulation`, with dependencies installed:

```text
python -m unittest discover -s tests -v
python -m usv_sim.workflow --preset smoke
python -m usv_sim.workflow --preset full --workers 4
python -m usv_sim.verify results/lab/<id> --reference results/core
```

Each workflow produces a new directory with source snapshot, freeze, raw logs, outputs, step logs, checksum inventory, reproduction instructions and ZIP. Reproduction excludes host CPU/wall timing from deterministic comparisons. The optional isolated RAM benchmark uses Windows `peak_wset`; other workflows are portable. A restricted sandbox may need normal localhost network permission for integration tests.

Run the application in an actual browser after UI changes. Verify policy loading, seeking, local knowledge, incomplete endpoints, event inspection, experiment submission, filters, downloads and presentation navigation. Updating CSS or running Python unit tests alone does not verify browser behavior. The work log distinguishes checks actually performed from remaining author/mentor review.

## Existing artifacts and external projects

- Final-report Overleaf: `https://www.overleaf.com/project/6adaa2ee04fc36dc7bdb36ac`
- Research-plan Overleaf: `https://www.overleaf.com/project/6abd035913fae5baa946157b`
- GitHub: `https://github.com/ADreLOI/RMSW-Project`

The report revision now covers the full reviewed plan, including all 18 paired contrasts, 30 condition diagnostics, delivered/attempted communication, component work, warning lead times, local information and the stalled baseline's limits. Six supplementary tables regenerate with `python code/simulation/scripts/build_report.py` from the repository root. This command writes generated tables only; it preserves edited prose and references. `package_report.py --output <new.zip>` creates a source package with hashes. Live Overleaf was backed up before synchronization. Final compilation, source comparison and PDF inspection are recorded in the work log; they do not imply course submission or human author review. The assigned template and existing GitHub links/icons remain in use.

## Remaining research decisions

Independent author reproduction and review, mentor interpretation of the stalled baseline, literature/source verification, and the final submission remain human follow-up. Optional oracle and radio-exponent sensitivities were not part of the original core evaluation. Exploratory controls can generate clearly separated evidence for a future decision, but do not silently redefine the protocol or claim a favorable result.

All 180 S2 runs stopped moving between 265 and 520 s, before the earliest slowdown at 600 s. This post-evaluation diagnostic limits the intended unequal-progress interpretation and is explicit in the report. A separate recovery study must retain strong controls and freeze its own design. Portable non-Windows process-memory benchmarking, cancel/resume and an exportable slide-deck artifact remain possible engineering work. Preserve the evidence and document scientific changes first.

## Copyable context for another tool

> Work in the RMSW-Project implementation checkout. First read AGENTS.md, code/docs/agent-handoff.md, code/docs/work-log.md and the relevant research-plan method sections. Preserve the frozen 900-run evidence, paper/code separation and collaborator changes. Run the local dashboard through Run-Lab.ps1 or python -m usv_sim.dashboard. New experiments must use fresh results/lab bundles with source/settings/raw events/hashes and independent reconstruction. Current results do not establish a trend-forecast advantage: completion S1 180, S2 0, S3 158, S4-T 156, S4-P 162 out of 180 each. State precisely what you changed and actually tested, update the work log, and distinguish local verification from Overleaf upload, merge, human review or course submission.
