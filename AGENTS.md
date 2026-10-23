# RMSW / II2202 agent instructions

This is a controlled synthetic experiment about two unmanned surface vehicles (USVs), not a calibrated marine simulator. Preserve the agreed research design and make claims that the retained evidence supports.

## Start here

1. Read `code/docs/agent-handoff.md`, `code/docs/work-log.md`, and `code/docs/plan-to-code.md`.
2. Read the relevant sections of `paper/research-plan/`. This is the live-plan snapshot downloaded on 23 October 2026. It supersedes the earlier proposal.
3. Inspect `git status`, branch and remotes before editing. Preserve other authors' work. There is an older dirty checkout outside this implementation checkout; do not modify it.
4. Use `code/docs/dashboard-guide.md` for commands, controls and metric definitions. Read `code/docs/architecture.md` before changing the event/replay boundary.

## Repository boundaries

- `paper/` contains LaTeX, references, templates and publication figures only.
- `code/` contains implementation, data and technical documentation. Root metadata, this file and the launcher are intentional exceptions.
- Do not overwrite an active Overleaf project from a potentially stale local source. Coordinate and inspect its live state before paper synchronization.
- Preserve `paper/Proposal/`, `paper/professor-template-2026/` and the research-plan snapshot as reference sources.
- `results/core/` is retained frozen evidence. New experiments belong in unique `code/simulation/results/lab/<UTC-id>/` directories. Do not add exploratory runs to the 900-run table.
- Bulk raw logs, local environments and lab output are ignored by Git. Retain their hashes and reproduction commands. Never commit credentials or private data.

## Scientific invariants

- Five policies: S1 fixed partition; S2 short queue 3; S3 long queue 12; S4-T trend-triggered extension; S4-P persistence-triggered extension. The executing task is excluded from queue capacity.
- All online policies use the same allocator, tie rules, serialized messages and atomic commit. No independent task stealing or rendezvous is present.
- Motion: 20×12 cells, 20 m side, 2 m/s, 1 s ticks, 5 s per heading change. Observation occurs only on arrival at a cell center, including transit.
- Policy-independent pre-generated disturbance streams: seed-matched fades, and boat 1 half-speed for 300 s at an integer onset in [600,900]. Never let a predictor inspect future scenario states.
- Radio: 10 s exchanges, −40 dBm at 1 m, exponent 2, fade 0/−10 dB, cutoff −90 dBm. Atomic limit: four datagrams / 8192 serialized payload bytes. Network headers are excluded.
- Forecast: five successful timestamped samples; trend residual ordinary least squares plus relative motion; persistence warmup/control; project four exchanges to check two consecutive failures with onset within three. Frozen margins: 4 dB for both.
- Pilot seeds 0–9: 60 fixed-route references + 240 online missions. Evaluation 1000–1029: five policies × two progress conditions × three mean fade durations × 30 seeds = 900.
- Timeout is 7200 s. Incomplete completion time is null; restricted time is 7200. Software errors must fail the job, never become scientific timeouts.
- Paired bootstrap: 2000 resamples of whole seeds within each condition. Marginal 95% intervals; six primary contrasts do not imply simultaneous coverage.
- Resource counts are separate from host CPU/RAM measurements. Neither establishes measured energy, battery lifetime, or physical map accuracy.
- Core findings are adverse to a strong forecast claim: S1 180/180 completed; S2 0; S3 158; S4-T 156; S4-P 162. No consistent trend advantage over strong controls.

Changing these assumptions creates a new design/experiment. Document why, retain the original, and keep sensitivity results distinct. Consult the user's current instructions and the research plan for scope; routine fixes within the agreed scope can proceed.

## Commands

From the repository root on Windows:

```powershell
.\Run-Lab.ps1 -Setup       # once: local venv, dependencies, then dashboard
.\Run-Lab.ps1              # opens http://127.0.0.1:8768
.\Run-Lab.ps1 -Action Test
.\Run-Lab.ps1 -Action Smoke
.\Run-Lab.ps1 -Action Full -Workers 4
```

From `code/simulation`, with an installed editable package (or `PYTHONPATH=src`):

```text
python -m unittest discover -s tests -v
python -m usv_sim.dashboard --no-browser
python -m usv_sim.workflow --preset smoke
python -m usv_sim.workflow --preset full --workers 4
python -m usv_sim.verify results/lab/<id> --reference results/core
```

The localhost integration tests need socket access. If a restricted runner forbids loopback connections, run those tests with the environment's authorized local-network permission; do not silently skip or claim they passed. No remote service is required. The optional RAM benchmark currently uses Windows `peak_wset`.

## Verification and handoff

- Run relevant meaningful tests. Simulation/protocol changes also require raw-log reconstruction and a new independent evaluation as appropriate; compare deterministic scientific values, excluding host timing.
- For UI changes inspect the actual browser, including replay, run submission, evidence filters, downloads and presentation. A Python test is not browser QA.
- Queue snapshots are every 10 s; motion and observations are exact 1 s events. Older logs omit terminal queues. Show missing terminal state as unavailable, never carry stale ownership forward as fact.
- Keep dashboard writes on the loopback server, with token/origin checks, fixed allowed actions, validated inputs and bounded paths. Do not expose it publicly.
- Update the work log with what changed, actual validation, output locations and remaining limitations. Update the handoff if architecture or research interpretation changes.
- Do not merge the open PR, submit the course work, or claim independent human review unless that action is separately requested and verified.
