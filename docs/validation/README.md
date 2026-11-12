# Visual-lab validation · 23 October 2026

## Fidelity and report revision, 23–24 October

| Check | Evidence | Result |
|---|---|---|
| Scientific audit | `scientific-audit.json`, `../scientific-audit-2026-10-23.md` | 32 tests; all 900 original logs/hashes verified; 30 new scientific records matched before full integration |
| Final integrated workflow | `full-reproduction-evening.json`; local `results/lab/20261023T203550-5f2c5b0a/` | 32 tests; 900 schema-2 logs reconstructed; 950 hashes and all 900 scientific records match |
| Retained render checks | `headless-replay-qa.{cjs,json,md}` | 72 real legacy/new trace render combinations; mocks, not browser verification |
| Actual desktop browser | `browser-study-evening.json`, `dashboard-*-evening.png` | All six condition values match core; exact task state, causal forecast, local knowledge, endpoints and presentation checked |
| Actual downloads | `map-export-evening.png`, `forecast-export-evening.svg` | PNG map and SVG causal-forecast downloads succeeded |
| Live Overleaf and PDF | `report-20261024.json`, `overleaf-draft-20261024.png` | Zero errors/warnings/overfull boxes; 17 A4 pages, nine body pages; 25 active files match; six tables regenerate; three GitHub links |

The final PDF and Overleaf source ZIP are in the parent workspace's `output/pdf/`. The full report-source backups remain in `Project-source-snapshots/` outside the checkout. The work log records source preservation, checks actually performed and remaining research limits. The notices retained in Overleaf are underfull typesetting information, not compilation errors.

## Earlier dashboard acceptance

These are recorded checks, not an independent author review or physical validation.

| Check | Retained evidence | Result |
|---|---|---|
| Full workflow, first development pass | Local `results/lab/20261023T121244-747f2df2/`; `first-full-reproduction.json` | 943 artifact hashes verified; all 900 scientific run records exactly match core |
| Full workflow with expanded tests/source capture | Local `results/lab/20261023T122848-7b3ea8fa/`; `full-reproduction.json` | 25 tests passed; 900 raw logs independently reconstructed; 949 artifact hashes verified; all 900 scientific records match core |
| Browser-submitted smoke workflow | Local `results/lab/20261023T123214-38fbb5e5/` | 25 tests passed; all five paired logs reconstructed; figures/archive produced |
| Portable reproduction from extracted smoke ZIP | Local `results/lab/qa-portable-source/` and `qa-portable-reproduction/`; `portable-reproduction.json` | Executed the captured source and tests, not the checkout source; all 40 hashes verified and all five scientific records match the original bundle |
| Exploratory single mission | Local `results/lab/20261023T124241-341ebfd3/`; `exploratory-integrity.json` | Seed 2026, balanced, L=10, exponent 1.8, cutoff 180 s; correct separate configuration, verified raw log and 34 hashes |
| Statistical browser views | `browser-qa.json` | All six conditions' displayed completion counts and rounded mean restricted times match source rows; 150 rows per condition |
| Browser replay and event inspection | `browser-qa.json`, `dashboard-mission.png` | Five loaded policies; 700 s / 55.4% active coverage; local-knowledge layer selectable; warning row at 30 s seeks and shows exact JSON |
| Presentation | `browser-qa.json`, `dashboard-presentation.png` | All five scenes render; animation advances; focused mode and exit controls work; chart and caption do not overlap |
| Download | `browser-qa.json` | Actual SVG download succeeded and included the correct design/scenario/dataset metadata; map/figure/archive export paths exercised through UI/API |

Scientific comparison excludes only `wall_s` and component `cpu_ns`. It includes outcomes, warning-event scores, operation counts, coverage, communication, travel and idle metrics. Hash checks prove retained-file integrity, not external authenticity or scientific correctness by themselves.

Actual browser observations used the Codex in-app browser at 952×871 and a 1707×1067 presentation viewport. No unexpected browser console errors or horizontal page overflow were observed. There was no mobile-device test. Native fullscreen is browser-dependent; the application provides a focused layout as a fallback. The final screenshot was inspected after correcting chart/caption overlap in the large presentation viewport.

The SVG export's initial filename used the study filter even for a mission chart. Its embedded metadata was correct; the filename now identifies the mission's actual seed/progress/fade settings. Failed sandbox checks during development were rerun with normal localhost permission, as described in the work log. They were never counted as successful checks or scientific timeouts.

GitHub Actions runs the smoke workflow, compares its deterministic records with retained core evidence, reconstructs the tracked example, and uploads the evidence ZIP for 14 days. Artifact action usage follows the [official action documentation](https://github.com/actions/upload-artifact). The Linux [run for source commit b798db9](https://github.com/ADreLOI/RMSW-Project/actions/runs/39956781791) passed every step and uploaded the archive; metadata is retained in `github-ci.json`.

The final PNG download check exposed a data-URL limitation in the in-app browser. The export now uses a PNG Blob. Both the actual PNG download and the corrected scenario-named SVG download were then verified; their filenames and metadata checks are in `browser-qa.json`. The downloaded `map-export.png` was visually checked and includes units, condition, legend and raw-log hash.

The frozen `results/core/` and report sources were not overwritten by these workflows. New raw logs, extracted bundles and larger archives remain local/ignored; the checked-in JSON validation records and screenshots provide a compact review trail.
