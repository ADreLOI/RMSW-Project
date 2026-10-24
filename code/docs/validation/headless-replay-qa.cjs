/* Run from any directory: node headless-replay-qa.cjs --python python
 * Optional --output path.json retains the result. Uses real Python traces and a
 * minimal DOM/canvas mock. Actual browser layout and interactions need browser QA.
 */
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const cp = require("node:child_process");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const repo = path.resolve(__dirname, "../../..");
const web = path.join(repo, "code/simulation/src/usv_sim/web");
const option = (name, fallback) => {
  const index = process.argv.indexOf(name);
  return index < 0 ? fallback : process.argv[index + 1];
};
const python = option("--python", process.env.USV_PYTHON || "python");
const html = fs.readFileSync(path.join(web, "index.html"), "utf8");
const ids = [...html.matchAll(/id="([^"]+)"/g)].map((match) => match[1]);
assert.equal(new Set(ids).size, ids.length, "HTML IDs must be unique");
const elements = new Map();
const noop = () => {};
const context = new Proxy(
  {},
  {
    get: (object, key) => object[key] ?? noop,
    set: (object, key, value) => ((object[key] = value), true),
  },
);
function element(id) {
  if (!elements.has(id))
    elements.set(id, {
      id,
      innerHTML: "",
      textContent: "",
      dataset: {},
      style: {},
      checked: true,
      value: "",
      classList: { toggle: noop },
      setAttribute: noop,
      addEventListener: noop,
      getBoundingClientRect: () => ({ width: 720, height: 440 }),
      getContext: () => context,
      querySelector: () => element("mock-svg"),
    });
  return elements.get(id);
}
ids.forEach(element);
element("knowledge").value = "global";
element("timeline").max = 7200;
element("event-filter").value = "all";
const document = {
  getElementById: (id) => elements.get(id) || null,
  querySelectorAll: () => [],
  addEventListener: noop,
  body: { classList: { toggle: noop } },
};
const sandbox = {
  document,
  console,
  window: { devicePixelRatio: 1, addEventListener: noop },
  requestAnimationFrame: noop,
};
vm.createContext(sandbox);
const app = fs.readFileSync(path.join(web, "app.js"), "utf8");
vm.runInContext(
  app.replace(/\ninit\(\);\s*$/, "") +
    "\nglobalThis.qa={state,drawAll,renderComparison,renderMissionCharts,renderEvents};",
  sandbox,
);
const source = String.raw`import json,tempfile
from pathlib import Path
from usv_sim.evidence import trace
from usv_sim.model import Config,make_scenario,run,POLICIES
legacy_path=Path('code/simulation/results/core/raw/1000-1-5-S4-T.jsonl.gz')
if not legacy_path.exists():
 legacy_path=Path('code/simulation/examples/trend-seed1000-slowdown-L5.jsonl.gz')
traces=[trace(legacy_path)]
base=Path('code/simulation/results/lab').resolve()
base.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=base) as root:
 assert Path(root).resolve().is_relative_to(base)
 for policy in POLICIES:
  output=Path(root)/(policy+'.jsonl.gz')
  config=Config(timeout_s=120)
  run(config,make_scenario(config,1000,5,True),policy,
      margins={'trend':4,'persistence':4},log_path=output)
  traces.append(trace(output))
 print(json.dumps(traces))`;
const execution = cp.spawnSync(python, ["-c", source], {
  cwd: repo,
  encoding: "utf8",
  maxBuffer: 25e6,
  env: { ...process.env, PYTHONPATH: path.join(repo, "code/simulation/src") },
});
assert.equal(
  execution.status,
  0,
  execution.stderr || "Python trace generation failed",
);
const checks = [];
for (const trace of JSON.parse(execution.stdout)) {
  trace.dataset = "headless-qa";
  trace.name = `1000-1-5-${trace.policy}`;
  sandbox.qa.state.traces = { [trace.policy]: trace };
  sandbox.qa.state.active = trace.policy;
  sandbox.qa.renderComparison();
  for (const layer of ["global", "0", "1"]) {
    element("knowledge").value = layer;
    for (const time of [0, 10, 55.5, trace.result.stop_s]) {
      sandbox.qa.state.t = time;
      sandbox.qa.drawAll();
      sandbox.qa.renderMissionCharts();
      sandbox.qa.renderEvents();
      for (const id of [
        "boat-states",
        "forecast-chart",
        "live-coverage",
        "coverage-chart",
        "signal-chart",
      ])
        assert(
          !/NaN|undefined/.test(element(id).innerHTML),
          `${id} at ${trace.policy} / ${time}`,
        );
      const coverage =
        (100 *
          trace.first_seen.filter((at) => at != null && at <= time).length) /
        trace.first_seen.length;
      assert(
        element("live-coverage").innerHTML.startsWith(
          coverage.toLocaleString("en-GB", {
            maximumFractionDigits: 1,
            minimumFractionDigits: 1,
          }),
        ),
      );
      if (layer !== "global")
        assert(
          element("observer-note").textContent.includes(
            "task overlays remain observer records",
          ),
        );
    }
  }
  checks.push({
    policy: trace.policy,
    raw_schema: trace.raw_schema,
    motion_states: trace.motion_states.length,
    time_samples: [0, 10, 55.5, trace.result.stop_s],
    knowledge_layers: ["global", "0", "1"],
    result: "passed",
  });
}
const hashes = {};
for (const name of ["app.js", "index.html", "style.css"])
  hashes[name] = crypto
    .createHash("sha256")
    .update(fs.readFileSync(path.join(web, name)))
    .digest("hex");
const report = {
  created_utc: new Date().toISOString(),
  status: "passed",
  node: process.version,
  python,
  unique_html_ids: ids.length,
  checked_web_sha256: hashes,
  checks,
  limits:
    "DOM/canvas mocks check render logic and markup only. They do not verify browser painting, layout, downloads, network APIs, or interactive event dispatch. Browser QA is separate.",
  command:
    "node code/docs/validation/headless-replay-qa.cjs --python python --output code/docs/validation/headless-replay-qa.json",
};
const output = option("--output");
if (output)
  fs.writeFileSync(
    path.resolve(output),
    JSON.stringify(report, null, 2) + "\n",
  );
process.stdout.write(JSON.stringify(report, null, 2) + "\n");
