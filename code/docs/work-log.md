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
