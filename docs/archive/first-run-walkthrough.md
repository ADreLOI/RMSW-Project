# Your first simulation run

Open [USV Research Lab](http://127.0.0.1:8768/#mission). The older `8767/replay.html` page is a historical replay; use port 8768 for the current controls, exact task records, graphs and automation.

The core study is implemented and verified. It compares five methods across 900 synthetic missions. It models grid visits, movement time, turning, radio availability and shared task information. It does not model waves, real sonar measurements, collisions or vessel safety.

## Start with the worked example

New terms

- **Random seed**, a number that lets you repeat the same generated disturbances.
- **Policy**, the rule a boat follows to choose how much work to keep assigned.
- **Radio fade**, a temporary reduction in the modeled received signal.

1. In **Mission lab**, set **Random seed** to `1000`, choose **Slowdown**, and leave **Mean fade duration** at **5 exchanges · 50 s**. Each exchange happens every ten simulated seconds. Fifty seconds is the target average faded-state duration, not a promise that every disconnection lasts fifty seconds.
2. Click **Run all five policies**. Wait for the completed message. This computes and verifies the missions, then loads their recorded events for playback. It saves a separate output directory and does not alter the frozen study.
3. Press Play at 60× or drag the time control. Both numbered boats move through the 240-cell survey. Shading records a visit to a cell center. Numbered outlines are assigned tasks that have not started; a cross is the executing task. The radio line uses the last measured positions and signal, with its age displayed.
4. Click **Slowdown onset**. In this example that is `813 s`, or `13:33`. Boat 1's commanded speed changes from 2 to 1 m/s until `1113 s`. At onset, S4-T has observed 149/240 cells. Its task state is recorded at 813 s; its latest radio/forecast information is from 810 s. The different timestamps are intentional.
5. Switch **Coverage layer** to **Boat 1 knowledge** or **Boat 2 knowledge**. The shading now shows what that boat knows. Both positions and task overlays remain observer records. The per-boat panels show any observed cells missing from its knowledge.
6. Scroll to **A synchronized comparison** and click another method. Every card shares the same simulated clock. A finished mission holds its final state while an unfinished one continues to the stopping limit.

| Method | Rule |
|---|---|
| S1 | Divide the area before departure; exchange no task messages. |
| S2 | Keep three unstarted tasks per boat; refill when communication succeeds. |
| S3 | Keep twelve unstarted tasks at every successful exchange. |
| S4-T | Normally keep three; extend to twelve when the signal-and-motion forecast warns of disconnection. |
| S4-P | Use the same extension action, with a warning based on the latest received signal. |

The executing task is separate from those queue capacities. In the worked example, S1 finishes at 1425 s; S3, S4-T and S4-P finish at 1493 s. S2 reaches only 23.8% and remains unfinished at 7200 s. Those are results from one scenario, not the whole study.

## Inspect a decision

The **Causal forecast inspector** shows only received measurements available when a forecast was issued, plus the stored predictions. At 813 s, the most recent forecast was issued at 810 s. The separate observer signal chart also contains failed exchanges, which were not received by the predictor.

In **Every exchange has a record**, choose a warning or click the row at 30 s. The replay seeks there and shows the original decision, tasks and serialized message contents. **Download full raw event log** saves the complete record.

## Read the study results

Open **Study evidence**. Compare balanced progress with slowdown, and the three fade settings. Each method has 30 matched scenarios per condition. Read completion counts and observed area alongside the time chart. An unfinished mission contributes 7200 s to that chart; it is not called completed.

Across the 180 missions per method, completion counts are S1 180, S2 0, S3 158, S4-T 156 and S4-P 162. The trend forecast does not consistently improve on always keeping twelve tasks or using the latest signal. S2 stops moving before the slowdown begins in every retained run, which limits what its comparison can establish about unequal progress. These findings are reported in the draft.

## Run checks, save evidence and present

- **Runs & verification → Run test suite** runs the 32 implementation tests and saves the output.
- **Run smoke workflow** runs the tests, one five-method comparison, checks the raw records, creates figures and packages the evidence.
- **Run 900-mission workflow** repeats the frozen full study in a new directory. Allow several minutes.
- Inspect a completed run and download **Evidence ZIP** for settings, source, raw events, results, figures, file-integrity checks and reproduction instructions. Use **Replay** to reopen it.
- **Save map** exports a PNG. The chart download buttons export SVG files. **Presentation** provides five guided scenes, including the observed limitations.

If the engine is stopped, open PowerShell in the repository and run ` .\Run-Lab.ps1 `, keeping that terminal open. Run ` .\Run-Lab.ps1 -Setup ` if dependencies are missing. Closing the browser does not erase saved evidence. See [dashboard-guide.md](dashboard-guide.md) for detailed controls and [agent-handoff.md](agent-handoff.md) for context to share with another tool.
