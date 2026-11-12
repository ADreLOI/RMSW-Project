# Milestones and responsibilities: plan versus status (27 October 2026)

Source: research plan, Sections 1.3 (objectives O1–O4), 3.1 (milestones) and 3.2 (responsibilities), version of 7 October 2026. "Done" means the artifact exists and its automated checks pass. It does not mean both authors have reviewed or reproduced it, which the plan requires at every milestone.

## Objectives

| Objective (plan date) | Status | Evidence | Still missing |
|---|---|---|---|
| O1 (21 Oct): finite-speed scenario, comms model, static + reactive baselines, deterministic tests | **Done** | `model.py`; 32 core tests + 13 extension tests | Each author reruns the tests and one scenario (plan 3.2) |
| O2 (28 Oct): both predictors, long-backlog control, pilot, freeze | **Done 23 Oct** | `results/core/frozen-design.json` (margins 4 dB/4 dB) | Author review of the freeze rationale |
| O3 (11 Nov): paired comparisons, all runs and logs retained | **Done early**: 900 core runs; plus the 1980-run extension (27 Oct) | `results/core/`, `results/extension/` | Independent reproduction by both authors |
| O4 (25 Nov): time, warning quality, comms, CPU, memory, coverage-state disagreement; regenerable scripts | **Mostly done** | `analysis.py`, `extension.py analyze`, generated tables | Each author regenerates the tables; interpretation agreed together |

## Milestone table

| Plan window | Lead | Milestone | Status | Remaining action |
|---|---|---|---|---|
| 1 Oct | Both | Review wording, RQs, baselines, AI disclosure; submit plan | Done (plan revised 7 Oct) | – |
| 2–7 Oct | Both | Verify sources, repository licences, parameter provenance; define resource indicators and energy limits | **Partly done.** Indicators defined. Sources and licences verified on 27 Oct (`literature-and-code-2026-10-27.md`) | **Both:** read the cited sections of the new papers before final citation. Ettore: marine/application sources. Andrea: radio/prediction sources |
| 8–14 Oct | **Ettore** | Finite-speed coverage and static assignment pass deterministic tests | Done (code exists, tests pass) | **Ettore:** run `tests/test_simulator.py`, read `model.py` motion/S1 code, confirm the S1 closed form (1280 s, 4760 m) |
| 15–21 Oct | Both | Reactive allocator and ownership tests; basic outage reproducible | Done | **Both:** walk through one hand-checked allocation (`test_allocation_tie_rule`) |
| 22–28 Oct | **Andrea** | Both predictors, logging pilot, op-count and CPU/RAM checks; freeze | Done (23 Oct). Extended 27 Oct with 5 extra predictors + hardware projection | **Andrea:** check the operation-count formulas in `predictors.py` against `operation-counts.md`; decide whether the extension stays in the report |
| 29 Oct–11 Nov | **Andrea** | Paired core simulations with configs and raw logs | Done | Keep raw logs (ignored by Git, hashes retained); archive a copy outside OneDrive |
| 12–25 Nov | Both | Reproduce analysis, compare efficiency/resource costs, **discuss coverage-state and physical map accuracy**, write results and limitations | **In progress.** Draft results exist, the map-accuracy diagnostic was added 27 Oct, and the resource trade-off is quantified | **Both:** reproduce `extension.py all` on each laptop. **Ettore:** write the map-accuracy discussion (marine framing) and check the S-44 coefficients. **Andrea:** check the extension statistics |
| 26 Nov onward | Both | Review/revise report, presentation, aligned to verified Canvas dates | Not started | Compile in Overleaf (main body ≤ 10 pages), opposition, video/presentation |

## Responsibilities in plan 3.2 and concrete next tasks

**Ettore leads** the marine use-case framing, the coverage/finite-motion scenario and the first revision of Section 1.
- [ ] Revise Section 1 with the new related work: Zhao & Bai 2024 (USV bathymetry, energy under currents), Torroba 2022 (map uncertainty, KTH), Gielis 2022 and Amigoni 2017 (communication-restricted MRS), Yamamoto 2019 (maritime RSSI).
- [ ] Own the map-accuracy paragraph (Results E3 and Discussion). Explain what the synthetic S-44 diagnostic can and cannot say.
- [ ] Reproduce one run and the full test suite, then sign off the motion/coverage component.
- [ ] Optional, from the 27 Oct meeting: relate your earlier network-congestion prediction project to the predictor comparison (one sentence in Related Work, if it is published or citable).

**Andrea leads** the communication model, forecasting rules, experiment configuration, resource logging, analysis and first revision of Section 2.
- [ ] Review the extension design (`extension-design.json`) and the 27 Oct work-log entry about the discarded first Gilbert freeze.
- [ ] Revise Section 2 / Appendix D for E1–E3 in your own words. The current text is an assisted draft.
- [ ] Check the hardware assumption ranges against the STM32F407/H743 datasheets before quoting latency numbers.
- [ ] Sync Overleaf, compile and check the page limit. The extension adds about one page to the main body, which previously was 9 pages.

**Both**
- [ ] Each reruns `python -m unittest discover -s tests` and `python -m usv_sim.extension all --output results/extension-<name>` and confirms identical mission/warning/map numbers. CPU timings may differ.
- [ ] Agree on the headline: prediction beats reactive only when reactive can recover; it never beats the always-long queue, even with an oracle; computation cost is negligible next to communication.
- [ ] Mentor discussion: is the post-hoc extension acceptable as a clearly labelled second experiment?
- [ ] Update the AI-use paragraph (Claude Code now used in addition to ChatGPT/Codex) and check it against the course guideline.
