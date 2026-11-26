# Agent handoff: RMSW / II2202

## Objective and current state

Andrea Lo Iacono and Ettore Mugisha Cirillo are studying whether short-horizon radio prediction improves two-boat coverage under intermittent communication. The redefined research plan is the authority. The repository now separates paper and code, implements all five configurations, retains a completed 900-run evaluation following a separate 300-run pilot, and provides a local visual research dashboard with experiment automation and evidence bundles.

Start with the root `AGENTS.md`; it contains scientific invariants, preservation rules and commands. Read `dashboard-guide.md` to operate the application and `architecture.md` before editing it. `work-log.md` records completed work and validation, including the earlier report setup.

On 2026-11-26, public relay access and Andrea's seminar deck were merged and published from main (seminar merge `040f92a`). The operator verified the rapid workflow, engine shutdown and automatic reconnection. The current local integration merges `dev-paper` (`ad681a4`) into main, with a user-authorized commit but no push. Earlier implementation work used `implementation/research-plan-simulator` and PR #1. Inspect live Git/PR state before relying on these notes and preserve other checkouts.

The operator authorized public browser access to the hosted relay. Pages builds enable automatic connection to the configured `LAB_RELAY_URL`; Render opts in with `LAB_PUBLIC_ACCESS=1` and retains `LAB_BROWSER_ORIGIN=https://adreloi.github.io` plus its private `LAB_ENGINE_KEY`. Public visitors can submit allowed jobs and access evidence while the engine is connected. Offline requests fail with 503 instead of being queued for reconnection. This is intentionally public access, not viewer authentication through CORS.

The Windows launcher adds menu item 9 to save a remote URL and engine credential in ignored `.lab-launcher/remote.xml`, encrypted for the current Windows user/PC. Items 1/2 then use that profile; items 3/4 retain the local pair. Explicit environment settings take precedence. See `deployment.md` for operator steps and `work-log.md` for validation limits.

## Scientific status

The frozen study uses a 20×12 grid, finite speed/turn cost, pre-generated two-state radio fades, bounded atomic coordination and optional temporary slowdown. Evaluation contains five policies × six conditions × 30 seed pairs. Both warning margins were selected as 4 dB on separate pilot fixed-route replay. The common allocator, tie rules and serialization matter; read `plan-to-code.md` and the research-plan method sections.

Across 180 missions per policy, completion counts are S1=180, S2=0, S3=158, S4-T=156, S4-P=162. S2 can exhaust tasks beyond radio range; no rendezvous controller exists. Trend warnings do not show a consistent advantage over an always-long queue or persistence. Fixed-route held-out warning F1 is about 0.175 for both predictors. Zero task conflicts and message-budget failures were observed in the frozen evaluation.

Incomplete mission completion time is null, restricted time is 7200 s. Statistical intervals resample whole paired seeds within each condition, 2000 times, and are marginal 95%. Resource quantities are operation/byte counts and host CPU/RAM observations; no measured energy, battery lifetime, map accuracy, calibrated vessel physics or field performance is established.

The dashboard does not change the scientific model. New run controls can explore exponent and cutoff while retaining the frozen reference and recording the effective configuration. These results remain separate from `results/core/`. A new controller or baseline belongs in a documented new design, not a quiet fix to make existing results favorable.

## Implementation and evidence entry points

The split deployment adds `Manage-Lab.cmd`, `compose.yaml`, `webapp.relay` and `usv_sim.engine`. See [deployment](deployment.md). The original standalone dashboard also remains available.

| Need | Read / run |
|---|---|
| Scientific contract | `paper/research-plan/sections/02.*`, `docs/plan-to-code.md` |
| Protocol, motion, predictor | `code/simulator/usv_sim/model.py` |
| Raw-log check | `analysis.reconstruct(path)`; `tests/test_simulator.py` |
| Dashboard API / queue | `dashboard.py`; `tests/test_dashboard.py` |
| Browser visualization / charts | `code/webapp/static/{index.html,style.css,app.js}` |
| Provenance / trace | `evidence.py` |
| Automated execution | `workflow.py`, root `code/simulator/scripts/Run-Study.ps1` |
| Exact science comparison | `verify.py` |
| Current frozen evidence | `code/simulator/results/core/` |
| New run history | `code/simulator/results/lab/` (ignored bulk outputs) |
| Publication report | `paper/Final_Report/main.tex`, modular sections and `generated/` |
| Validation record | `work-log.md`, `docs/validation/` |

The event stream is the authority for replay. New schema-2 logs record exact task/motion state each second and at termination. Radio and forecasts remain 10 s samples. Post-exchange state supersedes its pre-exchange tick at the same time. Legacy logs retain sampled task state and unavailable terminal queues; the dashboard never invents these. Numbered markers, model x/y axes, sample ages, local knowledge panels and a causal forecast inspector make the observer's information distinct from a boat's available information. No decorative bathymetry or inferred vessel yaw is shown.

The fidelity audit is in `scientific-audit-2026-10-23.md`. Explicit reconstruction checks survive `python -O`, and analysis verifies the exact frozen matrix and design hash. All 900 original raw hashes remain unchanged. The integrated workflow `results/lab/20261023T203550-5f2c5b0a/` passed 32 tests, reconstructed 900 new schema-2 logs and matched every scientific record against core exactly, excluding host CPU/wall timing. Its 950 inventoried files passed integrity verification. Browser evidence and retained headless checks are under `validation/`.

The browser is buildless and local. Python's standard-library HTTP server runs a serial fixed-action queue and uses validated requests, loopback binding, Host/origin/token checks and allowlisted exports. It is not intended for public hosting. Presentation mode is a five-scene interactive browser presentation, not a PowerPoint artifact. Bulk raw logs are ignored by Git; a fresh clone can inspect the included S4-T example and regenerate all other traces.

## Reproduce and validate

From the repository root on Windows, use `.\code/simulator/scripts/Run-Study.ps1 -Setup` once, then `.\code/simulator/scripts/Run-Study.ps1`. From `code/simulator`, with dependencies installed:

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

The report revision now covers the full reviewed plan, including all 18 paired contrasts, 30 condition diagnostics, delivered/attempted communication, component work, warning lead times, local information and the stalled baseline's limits. Six supplementary tables regenerate with `python code/simulator/scripts/build_report.py` from the repository root. This command writes generated tables only; it preserves edited prose and references. `package_report.py --output <new.zip>` creates a source package with hashes. Live Overleaf was backed up before synchronization. Final compilation, source comparison and PDF inspection are recorded in the work log; they do not imply course submission or human author review. The assigned template and existing GitHub links/icons remain in use.

## Remaining research decisions

Independent author reproduction and review, mentor interpretation of the stalled baseline, literature/source verification, and the final submission remain human follow-up. Optional oracle and radio-exponent sensitivities were not part of the original core evaluation. Exploratory controls can generate clearly separated evidence for a future decision, but do not silently redefine the protocol or claim a favorable result.

All 180 S2 runs stopped moving between 265 and 520 s, before the earliest slowdown at 600 s. This post-evaluation diagnostic limits the intended unequal-progress interpretation and is explicit in the report. A separate recovery study must retain strong controls and freeze its own design. Portable non-Windows process-memory benchmarking, cancel/resume and an exportable slide-deck artifact remain possible engineering work. Preserve the evidence and document scientific changes first.

## Copyable context for another tool

> Work in the RMSW-Project implementation checkout. First read AGENTS.md, docs/agent-handoff.md, docs/work-log.md and the relevant research-plan method sections. Preserve the frozen 900-run evidence, paper/code separation and collaborator changes. Run the local dashboard through code/simulator/scripts/Run-Study.ps1 or python -m usv_sim.dashboard. New experiments must use fresh results/lab bundles with source/settings/raw events/hashes and independent reconstruction. Current results do not establish a trend-forecast advantage: completion S1 180, S2 0, S3 158, S4-T 156, S4-P 162 out of 180 each. State precisely what you changed and actually tested, update the work log, and distinguish local verification from Overleaf upload, merge, human review or course submission.

## Update 27 October 2026: extension study E1–E3

A separately frozen extension lives in `code/simulator/results/extension/`, with design `extension-design.json` and seeds 2000–2029. Its purpose is to address the meeting's requests and the S2 stall without touching the core. Read `literature-and-code-2026-10-27.md` for verified sources and `milestones-status-2026-10-27.md` for plan-versus-status and per-author tasks. Key interpretation: with a common rendezvous rule, prediction beats reactive by 7–10% but never beats the always-long queue, even with a fade oracle. Predictor computation is negligible next to radio traffic. The synthetic map RMSE separates stalled coordination (2.5 m) from completed missions (about 0.34 m). Run it with `python -m usv_sim.extension all --output <fresh dir>`. The dashboard does not yet display extension policies.

## 25 November integration

The `dev-code` post-hoc analyses are integrated on `dev-code-deploy` in the new
`code/simulator` layout. See its README for retained outputs and reproduction
commands. New figure modules live under `usv_sim/charts`. Core science and its
interpretation are unchanged. The agreed hosting implementation now
exports GitHub Pages with historical data and five verified demo logs, and uses a
Render relay for authenticated PC access. See deployment.md for the precise
settings and publication gate (successful push to main). Browser credentials
stay in memory; exact-origin CORS and one-use live tickets protect cross-origin
access. Local combined mode remains supported. No hosted service was deployed,
and the merge/implementation remain uncommitted for the user's review.
