# Headless replay render checks

Run from the repository root with Node and the project's Python dependencies installed:

```powershell
node code/docs/validation/headless-replay-qa.cjs --python python --output code/docs/validation/headless-replay-qa.json
```

The exact command used for the retained 23 October 2026 result was:

```powershell
& 'C:/Users/andre/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' code/docs/validation/headless-replay-qa.cjs --python C:/Python313/python.exe --output code/docs/validation/headless-replay-qa.json
```

`headless-replay-qa.cjs` executes the dashboard JavaScript in a Node VM with a minimal DOM and canvas mock. It independently reconstructs the retained legacy S4-T raw trace, or uses the tracked example when bulk logs are absent. It then generates and reconstructs five new 120-second schema-2 runs, one per policy. Temporary logs stay under the ignored `results/lab/` directory and are removed after checking their resolved directory boundary.

For each trace it renders all three knowledge layers at time 0, 10, 55.5 seconds and termination. These 72 combinations exercise map drawing, per-boat state, forecast markup, coverage and sampled signal charts, metrics and event-table rendering. The script checks unique HTML IDs, rejects NaN/undefined output, checks displayed global coverage against raw first-observation times, and requires the observer-record qualification for local knowledge layers. The retained result passed and records SHA-256 hashes of the web assets it checked.

These checks do not run a browser. They do not verify actual painting, responsive layout, button dispatch, downloads or network behavior. The parent's separately retained browser QA covers those actions. The short generated runs are engineering checks, not additions to the frozen 900-mission evaluation.

The three web assets and the QA script were formatted using the already installed Prettier binary:

```powershell
& 'C:/Users/andre/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'C:/Users/andre/node_modules/prettier/bin/prettier.cjs' --write code/simulation/src/usv_sim/web/app.js code/simulation/src/usv_sim/web/index.html code/simulation/src/usv_sim/web/style.css code/docs/validation/headless-replay-qa.cjs
```
