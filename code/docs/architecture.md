# Simulator and research dashboard architecture

## Data path

```text
research-plan snapshot -> frozen-design.json (pilot-selected margins)
                                |
              model.py + independent scenario streams
                                |
                  streamed raw/*.jsonl.gz
                                |
           reconstruct() checks independently rebuilt metrics
                /                               \
     analysis.py / publication exports       evidence.trace()
                |                               |
       tables + bootstrap intervals      dashboard JSON endpoints
                                                |
                               local HTML / CSS / JS / canvas / SVG
```

The browser never implements the scientific simulator or tunes parameters. It requests Python jobs and renders verified recorded events. Playback is a visualization of a completed run, not a real-time hardware controller. The server reports progress at policy or workflow-step boundaries; the replay becomes available after verification.

## Modules and ownership

| File under `code/simulation/src/usv_sim/` | Responsibility |
|---|---|
| `model.py` | Configuration, scenario streams, finite-speed motion, radio, allocator, predictors, protocol, raw events |
| `events.py` | Outage definition, collapsed alerts, one-to-one matching, boundary exclusions |
| `experiment.py` | Pilot freeze, parallel evaluation, single mission, environment metadata |
| `analysis.py` | Independent reconstruction, whole-seed bootstrap, descriptive tables, publication figures |
| `benchmark.py` | Saved input CPU batches, incremental Python allocations, isolated process high-water RAM |
| `evidence.py` | Frozen-design validation, source snapshot, hashes, archives, verified browser traces |
| `workflow.py` | Fresh output directories, recorded steps, tests, scenario/full evaluation, figures, archive |
| `verify.py` | Artifact integrity; exact scientific comparison excluding CPU/wall timings |
| `plots.py` | PNG/PDF/SVG for exploratory paired missions; no inferential intervals |
| `dashboard.py` | Loopback HTTP server, bounded serial job queue, persisted activity, downloads |
| `web/` | Buildless browser UI, canvas replay, SVG charts, run explorer, event inspector, presentation |
| `replay.py` | Legacy standalone seed-1000 replay generator; dashboard is the preferred interface |

No JavaScript build step, CDN, remote font, browser framework or robotics dependency is needed. NumPy, Matplotlib and psutil are the existing Python dependencies. Web assets are included in the package.

## Evidence model

Core evidence is retained under `results/core/`; custom jobs go to `results/lab/<UTC timestamp>-<random suffix>/`. The timestamp and random suffix prevent collisions. The CLI rejects an existing output directory. The server executes one queued job at a time, and accepts at most four active/queued jobs. Full evaluation uses a two-process simulation pool by default; the CLI permits 1–8 workers.

Each scenario bundle contains:

- `request.json`, `effective-config.json`, `frozen-design.json`: applied settings and their frozen reference.
- `provenance.json`: UTC creation, full source hashes, source-tree digest, Git base revision and dirty paths, host/library versions, request.
- `source/`: Python modules, web assets, tests, scripts, pyproject and simulator README copied before execution.
- `raw/*.jsonl.gz`, `runs.json`, `run-summary.csv`, `verification.json`: recorded events and independently verified results.
- `figures/paired-mission.{png,pdf,svg}` for a paired scenario; a full workflow exports analysis figures/tables instead.
- `pipeline.json` and step logs for automated workflows; test jobs retain `tests.log` and `test-result.json`.
- `artifact-sha256.json`, `evidence.zip`, `REPRODUCE.md`: checksums, portable archive and exact regeneration instructions.
- `job.json`: mutable UI progress, intentionally excluded from the immutable inventory/archive. JSON state replacement is atomic.

`pipeline.json` is finalized before packaging. A failed job retains its partial evidence and error diagnostics. A server restart marks unfinished server-owned jobs interrupted; live CLI jobs retain their own progress. There is no automatic resume or silent retry of scientific jobs.

The inventory proves byte integrity, not scientific correctness. Independent reconstruction supplies a different check, rebuilding coverage, travel, local knowledge, message counts, bytes, redundancy, idle time and termination from raw events. `verify.py --reference` compares deterministic mission records, including warning events and operation counts. CPU and wall times are excluded; gzip headers and host memory can also vary.

## Replay representation

`evidence.trace()` first calls `analysis.reconstruct()`. It then derives exact first-observation times for each cell, all observation events, and one position/idle sample per simulation second. Canvas interpolates positions only between adjacent 1 s samples. Coverage never uses an invented sensor footprint.

Queue ownership, local knowledge after exchange, radio signal and warning fields use recorded exchange snapshots. Between exchanges, local knowledge additionally receives that boat's observed arrivals. Old logs lack final queue/target state; the terminal frame contains null queues/targets and no radio sample rather than cloning an earlier frame. The UI labels the sampling interval and missing terminal state.

There is one shared clock across loaded policies. A policy that ends earlier holds its actual terminal position and coverage while another continues. A comparison's duration is the maximum of its loaded runs. Chart lines end at each run's recorded termination. The decorative contour lines do not affect the grid world or imply bathymetry.

## HTTP contract

| Endpoint | Function |
|---|---|
| `GET /api/catalog` | Frozen rows, design, precomputed statistics, host benchmark, trace availability, session token |
| `GET /api/trace?dataset=core&run=1000-1-5-S4-T` | Verified replay; `dataset` may instead be a known job ID |
| `GET /api/raw?...` | Original compressed raw event file |
| `GET /api/jobs`, `/api/job?id=...` | Persisted activity, selected run results, provenance and test log |
| `POST /api/jobs` | JSON `{action, request}`; fixed actions `run`, `tests`, `smoke`, `full` |
| `GET /api/download?dataset=...&name=...` | Allowlisted evidence/figure exports |

The server binds to `127.0.0.1`, validates the Host header, checks an unpredictable session token and same-origin POSTs, and serves allowlisted paths. It cannot execute arbitrary client commands. Experiment bounds are validated on the server, including seed type/range, policy, fade duration, timeout and exponent. This is a local research interface, not a multi-user deployment.

## Extending the project

Add new measurements to raw events first, with unit/meaning documented. Build independent verification before exposing a derived number as evidence. Preserve the distinction between a scientific change and a visualization improvement. Adding rendezvous or more realistic motion is a new experiment design, not a repair to make current results look better. See `agent-handoff.md` for decision boundaries.
