# Visual-lab validation · 23 October 2026

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

GitHub Actions now runs the smoke workflow, compares its deterministic records with retained core evidence, reconstructs the tracked example, and uploads the evidence ZIP for 14 days. Artifact action usage follows the [official action documentation](https://github.com/actions/upload-artifact). The live CI outcome is recorded in the work log after the branch is pushed.

The frozen `results/core/` and report sources were not overwritten by these workflows. New raw logs, extracted bundles and larger archives remain local/ignored; the checked-in JSON validation records and screenshots provide a compact review trail.
