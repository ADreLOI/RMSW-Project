# Plan to implementation

Authoritative source: unmodified `paper/research-plan/`, downloaded live on 23 October 2026. Older local plans differ in policy count and metrics and were not used to set this experiment.

| Requirement | Implementation |
|---|---|
| Grid, starts, finite speed, turning | `Config`, `Boat.tick`, `fixed_queues` in `model.py` |
| Ideal observations including transit | Every arrival at an adjacent cell centre; repeated entry counts again |
| Slowdown | Independent integer onset [600,900], half speed for 300 ticks, before motion |
| Stationary fades and distance loss | `make_scenario`, `signal`; target L=2/5/10, q=.2 |
| Common projected-finish allocator | `allocate`; executing task retained, only unstarted queues released |
| Deterministic ties | Task ID then boat ID; shortest paths minimize turns, horizontal-first ties |
| 3/12 queue capacity | Excludes executing task; only capacity changes across online policies |
| Atomic ownership | Two state datagrams, proposal, ack; budget and radio success required |
| No stealing or guaranteed reconnection | Empty queues idle; no rendezvous; timeouts retained |
| Causal trend and persistence | Only delivered sample history, actual timestamps, five-sample residual OLS |
| Three-exchange onset horizon | Four projected samples check two consecutive future misses |
| Pilot tuning and frozen evaluation | 60 reference + 240 online pilot runs; seeds 0–9 vs 1000–1029 |
| Paired randomness | Disturbance streams independent of policy decisions and execution order |
| Censoring and uncertainty | 2000 paired bootstrap resamples within each condition |
| Warning events and exclusions | `events.py`; first H onset and last H+1 alert boundary exclusions |
| Held-out warning replay | Both predictors on 180 identical fixed-route evaluation traces |
| True/local coverage | Local sets, pre-sync D_i and stopping gaps; known ⊆ true asserted |
| Exact communication bytes | Sorted-key compact UTF-8 JSON payloads retained in logs |
| Operations, CPU, RAM | Work counters, repeated saved-input timings, isolated peak process RAM |
| Accounting checks | All 900 evaluation logs reconstructed and checksummed |

Uniform implementation choices: row-major task IDs; current reported speed held constant in projected finish; no initial turn cost; initial common knowledge includes both start observations; movement continues within unused tick time after a waypoint; no final batch after full coverage; failed radio attempts transmit two state messages; oversized offered batches transmit zero.

The pilot revealed S2 stalls and some long-queue stalls. The original settings were retained to characterize the plan's explicit no-recovery limitation, without changing range, capacity, or recovery to favour prediction. Thus the main contrast has a strong reconnection/capacity interpretation. A common recovery controller would define a new study with a new freeze.

Not claimed: vessel dynamics, measured sea-channel calibration, sonar/localization error, collision avoidance, real distributed consensus, energy, battery endurance, or device lifetime. Optional oracle and n=2.5 sensitivity are outside this core evaluation.
