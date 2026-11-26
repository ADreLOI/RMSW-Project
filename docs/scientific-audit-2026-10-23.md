# Scientific fidelity audit — 23 October 2026

## Scope and authority

Compared the full reviewed research plan (`paper/research-plan/main.tex`, preamble, front matter, all introduction/method/planning sections and bibliography structure) with `model.py`, `events.py`, `experiment.py`, `analysis.py`, `evidence.py`, their tests, the retained design and run records. The coordinator downloaded the current Overleaf plan again and found no source changes after newline normalization. The plan's synthetic assumptions remain the experiment's contract.

The core implementation follows that contract. This audit does **not** establish realistic vessel dynamics, a calibrated maritime channel, valid sonar measurements, navigational safety or field performance. More detailed physics would require a new research design and validation data; adding it silently would invalidate the controlled comparison.

## Findings against the reviewed plan

| Area | Audit conclusion |
|---|---|
| Coverage and motion | Correct 20×12 grid, specified starts, adjacent-center motion, 2 m/s, stationary 5 s heading-change penalty, 1 s steps, cell-entry observations including transit. No fabricated sensor footprint. |
| Disturbances and pairing | Stationary two-state fades with the specified transition probabilities; separate pre-generated fade/slowdown streams; matched disturbances across policies. Half-speed interval is applied before motion at integer ticks from onset through onset+299. |
| Policies and allocation | All five configurations present. Online policies share projected-finish greedy allocation, task/boat tie rules, executing-task protection, queue release and 3/12 unstarted capacities. This is a study-defined allocator, not a CBBA implementation. |
| Communication | Distance-loss formula, fade offsets, 10 s opportunities, threshold and atomic four-datagram/8192-byte budget match. Retained UTF-8 payloads make bytes reproducible. No latency, headers, packet-level losses or real distributed consensus are modeled. |
| Prediction | Uses delivered causal history, actual timestamps, five-sample residual least squares plus relative motion, persistence warmup, four projections for a three-opportunity onset horizon, and pilot-selected margins. No future scenario access in deployable predictors. |
| Events and analysis | Two-miss outages, collapsed alerts, chronological one-to-one matching, boundary exclusions, undefined metrics, paired whole-seed bootstrap and common-timeout censoring match the plan. Software exceptions propagate rather than becoming timeouts. |
| Evidence and resource accounting | Raw observations, positions, local/global coverage, link/claims, bytes, outcomes and separate workload/host resource measurements are retained. No energy or battery-lifetime conversion is supported. |
| Planned optional work | The oracle diagnostic and full n=2.5 sensitivity remain unperformed. Both are explicitly optional; neither is needed to claim completion of the core 900-run matrix. An exploratory exponent control alone is not the planned full paired sensitivity. |
| Human review | Automated reproduction does not satisfy the plan's separate requirement that both authors rerun representative evidence and jointly review interpretation. That remains author work. |

The stalled reactive baseline is a material limitation of the experiment, not an implementation error to hide. With no rendezvous or task stealing, empty queues and distance loss can cause permanent disconnection. Its 0/180 completions make the primary comparison strongly about maintaining enough work to survive loss of contact. S3 and persistence must remain visible when discussing prediction: S1 completed 180/180, S3 158/180, S4-T 156/180 and S4-P 162/180. These findings do not establish a consistent benefit from the trend predictor.

## Fidelity repairs in this change

1. **Exact recorded task state.** Added raw event schema 2 without changing algorithms, settings or scientific result fields. Initial, 1 s tick, exchange and terminal events now retain task queues/targets, grid cell/direction, movement phase, commanded speed and remaining edge/turn. The browser trace exposes `motion_states`. Post-exchange state supersedes the pre-exchange tick at the same time. Terminal queues/targets are recorded instead of inferred. Full coverage sets are still rebuilt causally from observations and commits, avoiding unnecessary per-tick duplication.
2. **Honest legacy behavior.** Original schema-1 logs remain valid. They have exact recorded positions/observations and only 10 s sampled task state. They expose an empty `motion_states` list and unavailable terminal queues/targets; missing state is never invented. Radio and forecasts remain scheduled measurements even with schema-2 motion states.
3. **Verification survives optimized Python.** Replaced raw-log reconstruction's `assert` checks with explicit `ValueError` validation. `python -O` can no longer disable those checks while the browser labels a trace verified. Added state/position geometry, task ownership/bounds, timestamp, terminal and censoring checks.
4. **Exact frozen matrix validation.** Analysis now verifies the frozen-design hash and exact membership of seed/progress/fade/policy rows. Matching row count alone previously could accept a substituted seed or condition. Duplicate rows are rejected explicitly.

`speed_mps` in a motion state is commanded translation speed. A turning or idle boat has zero translation despite that command. Grid heading describes the selected edge direction; there is no continuous yaw, acceleration or turn radius. Presentation must describe these as discrete model states. No bathymetry, sea surface, current, obstacle or collision behavior can be inferred from decorative visuals.

## Verification

- The expanded 32-test suite passed, including real localhost HTTP job execution. The restricted sandbox initially rejected its two loopback connections in the 31-test intermediate suite; the complete suite passed with authorized local-network access. The other 29 intermediate tests passed in the sandbox too.
- New checks cover a complete hand-calculated one-boat sweep; exact slowdown boundaries; recorded turning; task snapshots between exchanges; same-time exchange ordering; schema-1 compatibility; falsified snapshot geometry; invented observation timestamps; altered totals under normal and optimized Python; and frozen matrix/hash substitution.
- The retained 900 schema-1 raw logs are independently rechecked against their saved scientific records and retained SHA-256 values. New schema-2 runs are compared against the same seed across all six conditions and five policies, excluding only host CPU/wall timing. Machine-readable results are in [`validation/scientific-audit.json`](validation/scientific-audit.json).
- A fresh complete 900-run workflow after integration is the coordinator's final regression check. Its output belongs in a new lab bundle and must not replace `results/core/`.

The scientific model and frozen core are preserved. Schema changes improve what can be observed and checked; they do not improve or select mission outcomes.
