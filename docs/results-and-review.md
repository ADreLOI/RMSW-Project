# Results and review boundary

Core: 900 executions, five configurations × two progress settings × three fade-persistence levels × 30 paired seeds. Separate pilot: 60 fixed-route runs tuned both margins to 4 dB and 240 online runs checked behavior. Evaluation seeds were disjoint.

All 900 logs passed reconstruction of coverage, observations, travel, idle, communication, reservations, and information gaps. This checks accounting, not maritime fidelity. No crashes were recoded as timeouts. Confidence intervals are marginal percentile paired-bootstrap intervals.

| Configuration | Completed / 180 |
|---|---:|
| S1 fixed partition | 180 |
| S2 reactive short queue | 0 |
| S3 always-long queue | 158 |
| S4-T trend reservation | 156 |
| S4-P persistence reservation | 162 |

Reactive boats can become idle outside range after exhausting queues. The plan has no rendezvous controller, so stalls are retained. The contrast with S2 cannot establish forecast value. S4-T's mean restricted time exceeded S3 in all six conditions. Held-out F1 was 0.1749 for trend and 0.1755 for persistence. The draft reports these null/adverse findings.

All per-condition estimates are in `condition-summary.csv` and `paired-contrasts.csv`; per-run values are in `runs.json`. Operations, attempted/delivered bytes, repeated CPU timings, isolated peak RAM, and incremental Python profiles describe this implementation. They are not joules, battery hours, or vessel lifetime.

Completed: implementation, tests, pilot, frozen evaluation, log reconstruction, paired analysis, fixed-route warning replay, host benchmark, provenance, interactive trajectory replay, and report draft.

Authors still need to independently reproduce/review code, check references, consider any separately frozen common recovery extension, discuss with the mentor, revise final prose, and submit. No Canvas submission, opponent message, or claim of completed human review has been made.
