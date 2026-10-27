# Project work log

Record completed work, actual checks, evidence locations and remaining limits here. Entries describe work done; proposed research changes belong in a separate decision record until implemented and evaluated.

## 23 October 2026 — revised-plan implementation and paper setup

Relevant commits: `472e8bb` (implementation and separation), `8ee8b64` (source/evidence review notes), `dff1764` (stronger reconstruction and print polish). See Git history for exact changes.

- Inspected the active revised research plan and assigned report requirements. Downloaded the live plan into `paper/research-plan/` and preserved the assigned source under `paper/professor-template-2026/`.
- Separated the repository into `paper/` and `code/`. Moved the earlier proposal without changing its file contents. Left the older dirty local checkout untouched.
- Created the modular final-report working draft using the professor's template, with plan-derived organization, generated evidence tables/figures, GitHub icon and link box styling. Preserved the assigned typography/margins. The KTH logo is excluded under the report-formatting requirement.
- Created and populated the final-report Overleaf project linked in the repository README. Verified an Overleaf compile and inspected its PDF. No course submission was made. Later paper edits require live-state inspection and coordinated synchronization.
- Implemented finite-speed two-boat motion, turns, center observations, seed-independent scenario generation, radio fading, slowdown, atomic bounded serialization, common greedy allocation, five policies, OLS/persistence prediction, and event-based warning scoring.
- Ran the 300-mission pilot: 60 fixed-route references plus 240 online runs. Selected 4 dB margins for both methods using pilot event F1 and the specified tie rule; froze the design before evaluation.
- Ran the full 900-mission evaluation. Rebuilt coverage, distance, local knowledge, idle time, communication totals, termination and related metrics from all 900 raw logs. Checked the paired matrix and retained SHA-256 hashes.
- Generated condition summaries, paired bootstrap contrasts, warning replay/quality, component operations, outage/mechanism diagnostics, publication figures and LaTeX tables. Profiled saved decision inputs separately for host CPU and isolated Windows process memory.
- Added the initial self-contained replay and 15 meaningful simulator tests, with Linux GitHub Actions passing on the implementation branch.

Evidence: `code/simulation/results/core/`, the representative compressed example in `examples/`, and `paper/Final_Report/generated/`. Bulk raw logs remain local/ignored and reproducible. Initial replay screenshot and Overleaf PDF QA were saved in the surrounding workspace's `tmp/project-qa/`.

Observed completion counts: S1 180/180; S2 0/180; S3 158/180; S4-T 156/180; S4-P 162/180. The reactive baseline stalls without reconnection behavior. Trend prediction shows no consistent benefit over long queues or persistence. No measured energy, device-lifetime or physical map-accuracy claim follows from this experiment.

## 23 October 2026 — visual research dashboard and automation

Requested scope: make the simulation visual and presentable; automate experiments, data inspection and testing; retain a traceable record; provide context for other agents/tools.

### Implemented

- Added the local **USV Research Lab** browser interface: animated survey map, 1 s recorded tracks, exact coverage times, local/global knowledge layers, trails, queue/target overlays, radio state, time scrubber, playback speeds and synchronized policy cards.
- Added recorded coverage/signal charts, seek-on-chart interaction, decision filters and exact raw session inspection. Added PNG map exports with raw hash, SVG chart downloads, compressed raw-log downloads and evidence ZIP exports.
- Added the frozen evidence page: condition filters, mission-time bootstrap intervals, completion counts, paired contrasts, attempted/delivered bytes, fixed-route warning quality, component operation counts, host CPU/memory procedure and individual-run explorer.
- Added a five-scene interactive presentation grounded in the actual study, including the stalled baseline and absence of a consistent trend advantage. Added keyboard navigation, full-screen support and print styling.
- Added a loopback-only Python server with fixed allowed actions, validated requests, origin/token checks, bounded serial job queue, persistent activity and explicit failures/interruption state.
- Added single/all-policy experiment actions. Each saves its own settings, effective configuration, captured source/tests, environment, Git revision/dirty paths, frozen reference, raw logs, independent checks, figures, checksum inventory and archive.
- Added the PowerShell launcher and portable CLI workflow: tests → simulate → reconstruct → analyze/plot → hash → package. Full evaluation outputs stay in their new bundle, including publication figures; the workflow does not overwrite the paper or frozen core.
- Added portable bundle reproduction instructions, a captured-request scenario preset, and artifact/scientific comparison tooling. Deterministic comparisons exclude only host CPU/wall timing fields.
- Fixed the older single-run CLI to use the frozen selected margins rather than hardcoded zero margins. Prevented evaluation's optional exponent flag from silently overriding a frozen design. Existing CLI output replacement now requires an explicit overwrite flag; the new workflow always creates a fresh directory.
- Corrected terminal replay handling: legacy logs do not record final queues/targets or a final radio measurement, so the new view reports missing state instead of cloning stale state.
- Added root agent instructions, a cross-tool handoff, this work log, an architecture/API description and a detailed dashboard/metric/reproduction guide.

### Validation recorded during development

- JavaScript syntax and Python compilation checked.
- Initial expanded suite: 21 tests passed, including a real HTTP-submitted five-policy job, verified replay, evidence download, token/origin/Host checks, path validation, input validation, frozen-design tampering and archive checksums.
- The first sandboxed run exposed the runner's temporary-directory and localhost socket restrictions. Tests were moved to workspace-scoped temporary directories and rerun with authorized localhost access; all 21 passed. This was an execution-environment issue, not a scientific timeout.
- First complete new full workflow: `results/lab/20261023T121244-747f2df2/`. Tests, 900 evaluations, independent reconstruction, statistical analysis, figures and packaging passed. Evaluation itself took about 29 host wall-clock seconds with four workers; this is not a portable performance guarantee.
- Browser-submitted five-policy scenario: `results/lab/20261023T121310-39c22425/`, seed 1000 / slowdown / L=5 / exponent 2 / 7200 s. All five raw logs verified; PNG/PDF/SVG and evidence ZIP generated.
- Actual browser inspection confirmed recorded policy loading, a synchronized time of 700 s, correct grid/trails/queues/coverage/radio display, run submission and rendered statistical charts. Further final checks and evidence are listed in `code/docs/validation/` when completed.

### Interpretation and remaining boundaries

The dashboard phase improves execution, inspection and reproducibility; it does not introduce a new controller or alter the frozen model. New exploratory results remain separate from the 900 frozen runs. The presentation is a local interactive browser artifact; it is not a PowerPoint file or a course submission. Optional RAM benchmarking remains Windows-specific. Playback becomes available after computation/verification; it is not a live hardware simulator. There is no cancel/resume behavior.

Independent author/mentor review, any decision to change the baseline or add recovery behavior, final paper reconciliation and course submission remain outstanding. No GitHub merge or new Overleaf synchronization is implied by dashboard completion.

### Final acceptance checks

- Expanded the suite to 25 tests, adding exact scientific comparison, artifact tampering, the selected-margin CLI behavior, overwrite protection and frozen-evaluation override rejection. The root PowerShell test launcher passed.
- Completed the full workflow again in `results/lab/20261023T122848-7b3ea8fa/`: 25 tests, 900 evaluations, 900 independent reconstructions, statistics, figures and archive. All 949 inventoried files matched their hashes; all 900 scientific run records matched the original core exactly, excluding host CPU/wall timing. Recorded in `validation/full-reproduction.json`.
- Submitted and completed the automated smoke workflow through the browser in `results/lab/20261023T123214-38fbb5e5/`. Extracted its archive, ran its captured source/tests from `qa-portable-source/`, and reproduced all five records in `qa-portable-reproduction/`. The portable output passed all 40 artifact hashes and exact science comparison.
- Submitted a separate exploratory S4-T mission, seed 2026 / balanced / L=10 / exponent 1.8 / cutoff 180 s, in `results/lab/20261023T124241-341ebfd3/`. Confirmed the actual configuration, 15% final coverage, correct 180 s endpoint, no invented terminal queues/radio sample and 34 valid artifact hashes.
- Compared actual browser-rendered completion counts and mean times with source data for all six conditions; every view matched. Checked all five presentation scenes, animation, focused presentation/exit, the local knowledge selector, decision selection and time seeking. The final browser log had zero unexpected console errors and no horizontal page overflow.
- Downloaded an actual SVG chart and inspected its embedded design/scenario metadata. Corrected its mission-specific filename. Saved and inspected map/presentation screenshots, and fixed a large-viewport chart/caption overlap.
- Added the smoke workflow and deterministic comparison to GitHub Actions, with downloadable evidence archives retained for 14 days. See `validation/README.md` for evidence paths and the later CI result.

No physical vessel test, mobile-device test, new Overleaf upload, course submission or GitHub merge was performed in this phase.

### GitHub verification and final export repair

Commit `b798db954613eac8a23cc119877c497d2469a610` passed the Linux [Simulator checks run](https://github.com/ADreLOI/RMSW-Project/actions/runs/39956781791): package installation, the 25-test/smoke workflow, exact scientific comparison, representative trace reconstruction and artifact upload all succeeded. The `paired-smoke-evidence` archive is retained for 14 days; metadata is in `validation/github-ci.json`.

The final browser export check exposed an in-app-browser limitation with the map's data-URL download. Replaced it with a PNG Blob download, matching the verified SVG mechanism. Actual PNG and SVG downloads then succeeded; the SVG filename and embedded metadata identify seed 1000 / slowdown / L=5. The PNG includes grid dimensions/units, condition, legend and raw-log hash, and clamps its filename/time to the active policy's actual endpoint. The updated browser record and `validation/map-export.png` retain the result. This repair changes export transport/context only, not simulation or statistics.

## 23–24 October 2026 — reviewed-plan fidelity, layout and live report draft

The user authorized parallel agents to improve the layout and simulation's fidelity to the whole reviewed plan, and to develop the live Overleaf draft. Three agents handled scientific audit, web layout and report coverage; the coordinator owned source backups, integration, browser/PDF verification, documentation and GitHub synchronization.

### Scope and source preservation

- Read all reviewed-plan sections, including related work, precise research questions, procedure, analysis, assistance disclosure and project risks. The live plan was downloaded again on 23 October and matched the preserved snapshot after newline normalization.
- Downloaded the live final-report project before editing, again on resuming 24 October, and after final synchronization. Backups are in the parent workspace's `Project-source-snapshots/2026-10-23-evening/` and `Project-source-snapshots/2026-10-24/`. Active sources were compared before replacement. Existing template, plan, proposal, shared files and the older dirty checkout were preserved.
- The existing Overleaf project treats a ZIP upload as a file attachment. The active modular sources, bibliography and generated tables were therefore synchronized into their existing folders through the UI. Unused reference/transfer files were retained; the checked source package identifies the 25 active sources/figures/notes.

### Simulation and interface changes

- Added raw schema 2 with exact task/motion snapshots at initialization, each one-second tick, each exchange and stopping. Snapshots include unstarted queues, executing tasks, discrete activity, grid direction, commanded speed and edge/turn remainder. Post-exchange state replaces the tick snapshot at the same timestamp. Radio and issued forecasts remain scheduled ten-second samples.
- Preserved original schema-1 logs. Legacy task state remains explicitly sampled and terminal task state unavailable, rather than inferred. Locally known coverage is reconstructed causally from observations and delivered state.
- Replaced reconstruction assertions with explicit validation that also runs under optimized Python. Added geometry, timestamp, task ownership/bounds, commanded-speed, event-order, terminal and censoring checks. Analysis now requires the freeze hash and exact seed/condition/policy matrix.
- Enlarged the map and text, improved responsive navigation and setup layout, and removed decorative seabed contours, geographic north and inferred vessel bow orientation. Numbered observer markers use model coordinates. Trails preserve all recorded corners. Radio links anchor to sampled positions with sample age shown.
- Added per-boat knowledge/task/activity panels and actual slowdown-window navigation. Local layers explicitly change coverage knowledge while position/task overlays remain observer records. The causal forecast inspector shows delivered history available at issuance and stored projections, without later observed signals.
- Preserved experiment actions, raw-event inspection, condition filters, plots, downloads and presentation controls. A disconnected-browser response is handled without presenting a failed evidence verification.

These changes improve observation and verification of the specified synthetic model. They do not add hydrodynamics, currents, sonar error, collision avoidance, calibrated marine radio, a recovery controller or a new scientific baseline.

### Report and reproducible tables

- Expanded the draft around the exact research questions and the full plan: protocol/forecast equations and causality; pilot/freeze; paired effects and uncertainty; all 18 contrasts and 30 condition diagnostics; redundant observations, coverage, travel and summed boat idle; attempted/delivered communication; separate component workload/CPU accounting; outage durations, warning leads, committed extensions and local information gaps; validity, ethics, sustainability and reproduction.
- Retained the adverse result. All 180 reactive short-queue runs stopped moving between 265 and 520 s, before the earliest slowdown at 600 s. This post-evaluation explanatory finding limits the intended unequal-progress comparison. The report does not identify a consistent trend-predictor advantage over always-long queues or persistence.
- Checked primary literature used by the revision and corrected Gordon's conference metadata in the active report only. `paper/Final_Report/DRAFT-NOTES.md` records the evidence and source-check scope. The preserved plan bibliography was unchanged.
- Replaced the historical prose scaffolder with a generated-table-only `scripts/build_report.py`. Six tables are derived from retained inputs, with matrix/accounting checks and input/output hashes in `generated/table-provenance.json`. It does not overwrite prose, references or the template. `scripts/package_report.py` packages only the active paper files and records their hashes, rejecting an existing output path.
- Live Overleaf compilation first exposed a moving-argument path command and a narrow filename column. These were repaired without shrinking prescribed text. Final compile on 24 October had zero errors, zero warnings, no overfull boxes and five underfull typesetting notices. All pages were rendered; final appendix flow was checked again after its layout adjustment.
- Final PDF is 17 A4 pages, with nine main-body pages, references starting on page 11, and all three GitHub links present. All 25 active live source/figure/note files match the checkout after newline normalization; all six generated tables reproduce exactly. Machine record: `validation/report-20261024.json`. PDF/source package are in the parent workspace's `output/pdf/`.

### Verification retained

- Expanded 32-test suite passed, including actual localhost HTTP jobs, optimized-interpreter tampering, one-boat hand calculation, slowdown boundaries, sampled/one-second task handling, exact terminal states and frozen-matrix substitution.
- All 900 original raw logs independently reconstructed and their retained hashes remained unchanged. Thirty new records across all six conditions/five policies matched core before the full integration run; details are in `validation/scientific-audit.json` and `scientific-audit-2026-10-23.md`.
- Preliminary integrated workflow: `results/lab/20261023T203229-38eea530/`. Final stable-source workflow: `results/lab/20261023T203550-5f2c5b0a/`. The latter passed 32 tests, generated/reconstructed all 900 schema-2 missions, rebuilt statistical figures/tables, verified 950 inventoried files, and matched all 900 scientific records exactly against core. Only host wall time and component CPU timings are excluded. See `validation/full-reproduction-evening.json`.
- Retained runnable Node render checks cover 72 legacy/new-policy/time/knowledge combinations. They use DOM/canvas mocks and are explicitly separate from browser testing: `validation/headless-replay-qa.{cjs,json,md}`.
- Actual browser checks covered a fresh five-policy run, exact task state at the 813 s slowdown onset, commanded half speed, sampled radio/causal forecast age, local knowledge, stalled S2 terminal queues/activity and held S1 completion. All six statistical conditions matched retained completion counts and rounded restricted means. Actual PNG/SVG downloads succeeded. Five presentation scenes, playback, focus mode and exit were checked. No horizontal overflow was observed in checked desktop layouts.
- Source-linked screenshots, SVG/PNG exports and statistical checks are in `validation/*evening*`. On resuming 24 October the local engine was restarted; further final browser/CI records are kept alongside these files.

The course work remains a draft for both authors to reproduce, understand and review. Optional full n=2.5 sensitivity and oracle diagnostics remain unperformed. No GitHub merge, course submission, human author replication, mentor acceptance, physical-vessel test or measured energy saving is implied.

### Guided first run on 24 October

The user requested a simulation walkthrough. Added `first-run-walkthrough.md`, linked from the README, and opened the current lab instead of the historical port-8767 replay. Started a local background engine with process/log metadata in ignored `.analysis_tmp/server/active.json`. A new browser-submitted five-method scenario, `results/lab/20261024T100432-39e3bc0f/`, passed reconstruction and all 39 retained artifact hashes; all five scientific records match core. `validation/walkthrough-run-20261024.json` records the comparison. The worked example is seed 1000, slowdown, L=5, paused at 813 s; it demonstrates half speed, exact tasks, sampled forecasts and the methods' different outcomes. Saved `validation/walkthrough-mission-20261024.png`. Both the operating guide and handoff explain how to restart the engine and reopen saved evidence.

## 27 October 2026: literature/code search and extension study E1–E3 (Claude Code)

Requested after the Andrea–Ettore meeting of 27 October. The meeting asked for three things: find recent, well-cited papers and public repositories with comparable code or data, compare more prediction models and their hardware cost, and discuss map accuracy. Work happened in the `RMSW-Project/RMSW-Project` checkout on the local branch `improve/simulation-literature`, created from `origin/implementation/research-plan-simulator`. The checkout's older uncommitted September proposal edits were stashed, not discarded (`git stash list`: "backup: modifiche locali proposal settembre"). Nothing was pushed.

- **Literature and code.** `literature-and-code-2026-10-27.md` gives a verified matrix with Crossref metadata and citation counts, repository licences and an honest reuse verdict. No public repository combines multi-USV seabed coverage, an intermittent radio link and task reallocation. The credibility argument therefore rests on model forms from the literature, closed-form checks and log reconstruction.
- **Simulator hooks.** `model.run` gained `predictor=` and `recovery=`; both default to off. Re-running the frozen keys with the hooks off matches `results/core/runs.json` (tested). Recovery travel is flagged `transit`, is never a claim, and `analysis.validate_snapshot`/`reconstruct` accept it. Legacy logs are unaffected because the key appears only when true.
- **New modules.** `predictors.py` (EWMA, Kalman, Gilbert HMM, logistic, MLP, fade oracle; counted work and memory), `hardware.py` (four processor profiles with explicit assumption ranges), `mapping.py` (synthetic seabed, S-44 TVU noise, IDW fill) and `extension.py` (tune/evaluate/analyze). Tests: `tests/test_extension.py`, 13 tests.
- **Freeze incident.** The first extension freeze fitted the Gilbert transitions from successful samples only. Along fixed routes a faded exchange never succeeds, so all transitions were zero. The defect was found from the tuning output before any evaluation result was inspected. The bundle was deleted, `fit_gilbert` was changed to use the pilot fade sequence as a labelled calibration campaign, and the design was re-frozen (sha256 `a36193c7e359…`) and re-run.
- **Results.** 1980 extension runs, all reconstructed. Recovery: 180/180 completions for every policy. S4-T minus S2 is −108 to −175 s; S4-T minus S3 is +13 to +28 s (S3 better); no predictor, not even the oracle (held-out F1 0.85), beats S3. Deployable predictors' F1 is 0.185–0.193, except logistic at 0.106. Projected worst-case decision latency is 0.41 ms (MLP, Cortex-M4F). Synthetic map RMSE: core S2 2.50 m (34% S-44 1a), all extension policies 0.33–0.35 m.
- **Report.** Added `sections/03b_extension.tex`, `sections/appendix_extension.tex`, 14 BibTeX entries (12 generated from Crossref, plus IHO S-44 and the arXiv hardware source), and edits to the introduction, discussion, conclusion and AI-use paragraph. No LaTeX distribution is installed locally. A static check found no missing citations, labels, inputs or images, but the document has **not been compiled**. Expect about one extra main-body page.
- **Verification actually run.** Core suite 32/32 and extension suite 13/13 pass with the venv at `%USERPROFILE%\.venvs\rmsw`. The first core run inside the OneDrive path failed one dashboard test with a Windows long-path DLL error, an environment issue. The 900 copied core raw logs match `raw-log-sha256.json`.
- **Not done.** No push, PR update, Overleaf upload, compilation or browser QA of the dashboard (the dashboard does not yet show extension policies). There has been no human review.
