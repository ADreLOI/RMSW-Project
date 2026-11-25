# Post-hoc link-loss analysis (12 November 2026)

Requested at the tutor meeting of 12 November 2026: show how often the link is lost, normalise outcomes by the number of lost links, add a resilience measure, and compare communication cost.

**Status.** Declared post-evaluation analysis. It is not part of the pre-specified plan, promotes no contrast to a primary test and tunes nothing. It reads `results/core/{runs.json, mechanism-diagnostics.csv, frozen-design.json}` (hashes in `manifest.json`) and does not modify them. The only new executions are the 300 ideal-link reference runs described below; they are not core evidence.

Regenerate from `code/simulator`:

```text
python -m usv_sim.linkloss --output results/posthoc/link-loss-2026-11-12
```

## Definitions

- **Outage:** at least two consecutive missed exchanges (the frozen event rule). Lengths are in 10 s exchange intervals.
- **Distance failure:** a missed exchange whose clear-state signal is already below the −90 dBm cutoff (separation above about 316 m). It would have failed without any fade.
- **Fade exposure:** fraction of faded slots among the first 128 exchanges (1280 s) of the seed's disturbance stream. It is fixed before any policy runs, so it is the exogenous measure of how bad the channel was.
- **Ideal-link reference:** the same policy, seed and progress setting with the fade stream disabled; only distance limits the link.
- **Retention:** ideal-link time divided by restricted time under fades (1 = unaffected). Undefined for S2, which does not finish even with an ideal link.
- Ratios "per outage" are ratios of sums over the 30 paired seeds, with 2000-resample percentile bootstrap intervals. Correlations are Spearman rank correlations with bootstrap intervals over runs.

## Files

| File | Content |
|---|---|
| `per-run.csv` | One derived row for each of the 900 frozen runs |
| `link-loss-summary.csv`, `fig-link-loss` | Outages per run and per hour, mean outage length, availability, share of missed exchanges due to distance; also for completed runs only |
| `per-100-outages.csv`, `fig-per-100-outages` | Unfinished missions, idle time, reservations and warnings normalised by outages |
| `resilience.csv`, `fig-resilience`, `ideal-link-runs.csv` | Retention and delay against the ideal-link reference |
| `correlations.csv`, `fig-time-vs-link` | Spearman correlations per policy: all conditions, per condition, completed runs only |
| `communication-cost.csv`, `fig-cost-benefit` | Attempted and delivered traffic against mission time |

## What the numbers show

1. **How often the link is lost.** In completed missions the online policies (S3, S4-T, S4-P) lose the link 7–10 times per mission hour, with mean outages of 49–115 s and availability 0.78–0.85. The fixed partition S1 sees up to 17 short outages per hour at L = 2 (30 s each) because at a constant 200 m every fade breaks its link.
2. **Distance, not only fades.** In completed online missions 31–50 % of missed exchanges are distance failures: the allocator does not use separation as a decision parameter. In unfinished missions the share is 99 %.
3. **Per 100 outages.** Unfinished missions per 100 outages: 1.6–8.2 for S3, S4-T and S4-P, with wide overlapping intervals; no policy is separated from the others. S4-T had a committed reservation before 82 % of eligible outages and a timely warning before 37 % (S4-P: 71 % and 26 %), yet its outcomes match S3, which reserves nothing in advance.
4. **Resilience.** With an ideal link S3 and both S4 variants finish every mission (1425 s balanced, about 1494 s with slowdown); S2 finishes none, so its failure is not caused by fades. Under fades mean retention is 0.81–0.95. The loss is concentrated in stalls: among completed missions the mean delay against the ideal link is 12 s (S3), 29 s (S4-T) and 32 s (S4-P), while each unfinished mission costs about 5700 s.
5. **Correlations.** Fade exposure correlates weakly but consistently with restricted time for the online policies (Spearman 0.26 S3, 0.31 S4-T, 0.34 S4-P; intervals exclude zero) and not for S1 (−0.01). A run's own availability correlates more strongly (−0.53 to −0.61), but that direction is partly reversed: stalled boats drift apart and lose the link. Timely warnings do not correlate with time (S4-T −0.07, S4-P 0.13; intervals include zero).
6. **Communication cost.** Attempted traffic follows mission duration (Spearman 0.85–0.92). Per completed mission: S3 92 kB, S4-T 83 kB, S4-P 82 kB, S1 0 kB. The S4 queue rule sends about 10 % fewer bytes than the always-long queue at a similar completion time (1489 and 1493 s against 1471 s). S2 attempts about 319 kB and delivers 4 % of it. Delivered share falls from 0.70 to 0.41 as mean time rises.

## Limits

- Counts and bytes are not energy. No bitrate, transmit power or duty cycle is modelled, so no joule or battery figure is derived.
- Outage counts depend on mission length and route; per-outage ratios in unfinished runs are dominated by one long distance outage. Use the completed-run columns for the working regime.
- Own-run link metrics are outcomes as well as causes. Only fade exposure is exogenous.
- These are 30 seeds per condition on one fixed map and start geometry.
