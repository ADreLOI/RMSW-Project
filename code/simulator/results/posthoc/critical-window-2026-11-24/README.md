# Critical-window analysis (24 November 2026)

**Question.** Why do the core results show no pattern across fade duration, and what actually decides whether an online mission finishes?

**Status.** Declared post-evaluation analysis, found after inspecting the frozen outcomes. It reads `results/core/{runs.json, frozen-design.json}` (hashes in `manifest.json`) and writes nothing there. Two sets of new runs check the finding by intervention; they are diagnostics, not core evidence.

```text
python -m usv_sim.critical --output results/posthoc/critical-window-2026-11-24
```

## Definitions

- **Radio range:** 316 m, where the clear-state signal reaches the −90 dBm cutoff. A −10 dB fade breaks the link only beyond 100 m.
- **Split:** the first exchange at which the fade-free mission is out of range. It is exchange 26 (260 s) for S3, S4-T and S4-P alike, because the map, start points and allocator are fixed.
- **Critical window:** the two exchanges before the split, at 240 s (282 m) and 250 s (304 m). The window is derived from fade-free runs, not from the frozen outcomes.
- **Window faded:** both window exchanges are faded in the seed's pre-generated stream. This is fixed before any policy runs.
- **Blackout:** a link loss at any distance (fade depth −1000 dB), used only for the vulnerability map.

## Findings

1. **Outcomes are bimodal.** Completed online missions take 1425–1985 s; every other mission stalls at the 7200 s cutoff. The restricted mean therefore mainly counts stalls (2 to 7 of 30 per condition). Figure `fig-outcome-distribution`.
2. **One window decides S3.** "Window faded ⇒ stall" agrees with all 180 S3 runs (22 stalls, 158 completions), 178 of 180 S4-T runs and 176 of 180 S4-P runs (`rule-confusion.csv`).
3. **The intervention confirms it.** On the 180 online scenarios per policy, forcing the window faded stalls S3 in 180, S4-T in 178 and S4-P in 174; forcing it clear stalls S3 in 0, S4-T in 2 and S4-P in 0 (`intervention-summary.csv`).
4. **Mechanism.** If the 240 s and 250 s exchanges fail, the last committed allocation is the one from 230 s. Its queues end with the boats 326 m apart, 10 m out of range, and without a rendezvous rule they wait for the rest of the mission. With the 250 s allocation they finish 304 m apart and reconnect at 370 s. Figure `fig-critical-mechanism`.
5. **Fade duration only changes the odds of hitting the window.** The fade fraction is 0.2 for every L. The probability that both window exchanges are faded is q(1 − 1/L) = 0.10, 0.16 and 0.18 for L = 2, 5, 10 (stream check over 5000 fresh seeds: 0.095, 0.170, 0.183). The observed S3 stall shares 2/30, 6/30 and 3/30 are inside their 95 % Wilson intervals around these values, so the peak at L = 5 is sampling noise. The expected S3 restricted means are 2003, 2351 and 2489 s against observed 1811, 2582 and 2030 s. Figure `fig-stall-vs-theory`.
6. **The rest of the mission is robust for S3, not for S4.** On the fade-free balanced mission (`blackout-map.csv`, figure `fig-blackout-map`), S3 stalls only when a blackout covers both window exchanges. Any blackout of up to 120 s that starts after 400 s delays S3 by at most 20 s. S4-T and S4-P hold a short queue unless warned, so a 120 s blackout after 400 s delays them by 55 s and 59 s on average (up to 95 s). Early long blackouts are the reverse: a 120 s blackout stalls S3 at 11 start times, S4-T at 6 and S4-P at 3.
7. **Warnings are on at the window but cannot help.** S4-T warns from 180 s and S4-P from 210 s, so both already hold the long queue during the window. Their reservation action is exactly what S3 always has, so prediction can at best match S3 at the decisive moment.

## Consequences for the research questions

- RQ1: S2 fails at the split even with an ideal link (`../link-loss-2026-11-12/ideal-link-runs.csv`). The primary contrast measures this geometric failure, not forecast value.
- RQ2: the benefit of a long backlog is resilience to outages without precursors. S3 absorbs blackouts that cost S4 time, and S4 cannot beat S3 inside the window.
- RQ3: warning quality is irrelevant to the outcome in this design. The only outage that matters is predictable from motion, and the warnings do catch it, but the action available to them cannot change the result.
- Design limitation: with one map and fixed starts the whole outcome depends on two exchanges at a fixed moment and on a 10 m geometric margin. Random starts or a rendezvous rule would remove this artefact; they require a new, separately frozen experiment.

## Files

| File | Content |
|---|---|
| `rule-per-run.csv`, `rule-confusion.csv` | Window state and outcome for each frozen run; agreement per policy |
| `stall-rates.csv` | Stalls per condition with Wilson intervals, theory, stream frequency, observed and expected restricted means |
| `intervention-runs.csv`, `intervention-summary.csv` | 1080 new runs: window forced faded and forced clear |
| `blackout-map.csv` | 2145 new runs: blackouts of 10, 20, 30, 60, 120 s at every start exchange |
| `timeline.csv` | Separation and link state for the intact and window-lost S3 mission |
| `fig-*.png/pdf` | The four figures described above |

## Limits

- The finding was identified after seeing the results. The intervention tests it causally within the model, but it is not a pre-specified hypothesis.
- It is a property of this map, start geometry, allocator and missing rendezvous rule, not of USV coordination in general.
- Slowdown starts at 600 s or later, after the window, so slowdown and balanced conditions repeat the same stall pattern. Stall shares use the 90 balanced scenarios to avoid counting the same stream twice.
- The blackout map uses one fade-free mission. Delay values depend on the route and are not averages over seeds.
