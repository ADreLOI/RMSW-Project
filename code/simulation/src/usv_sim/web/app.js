"use strict";
const $ = (id) => document.getElementById(id);
const POLICIES = ["S1", "S2", "S3", "S4-T", "S4-P"];
const NAMES = {
  S1: "Fixed partition",
  S2: "Reactive short queue",
  S3: "Always-long queue",
  "S4-T": "Trend-triggered reservation",
  "S4-P": "Persistence-triggered reservation",
};
const COLORS = {
  S1: "#64748b",
  S2: "#c96a42",
  S3: "#b68b22",
  "S4-T": "#087f81",
  "S4-P": "#8466af",
};
const BOAT = ["#cf7148", "#087f81"];
const state = {
  catalog: null,
  traces: {},
  active: "S4-T",
  dataset: "core",
  t: 0,
  playing: false,
  slowdown: true,
  view: "mission",
  slide: 0,
  jobs: [],
  generation: 0,
  currentJob: null,
  selectedJob: null,
};
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
const fmt = (n, digits = 0) =>
  n == null
    ? "—"
    : Number(n).toLocaleString("en-GB", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
const clock = (t) =>
  `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const activeTrace = () => state.traces[state.active];
let toastTimer;
function toast(message, error = false) {
  $("toast").textContent = message;
  $("toast").classList.toggle("error", error);
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(
    () => {
      $("toast").hidden = true;
    },
    error ? 12000 : 5500,
  );
}
async function api(url, body) {
  const options = body
    ? {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Lab-Token": state.catalog.token },
        body: JSON.stringify(body),
      }
    : {};
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) throw Error(result.error || `Request failed (${response.status})`);
  return result;
}
function view(name) {
  if (!["mission", "evidence", "presentation", "activity"].includes(name)) name = "mission";
  state.view = name;
  document
    .querySelectorAll(".view")
    .forEach((e) => e.classList.toggle("active", e.id === `view-${name}`));
  document
    .querySelectorAll(".nav-item")
    .forEach((e) => e.classList.toggle("active", e.dataset.view === name));
  $("page-label").textContent = {
    mission: "Mission lab",
    evidence: "Study evidence",
    presentation: "Presentation",
    activity: "Runs & verification",
  }[name];
  history.replaceState(null, "", `#${name}`);
  if (name === "presentation") renderSlide();
  if (name === "mission") drawAll();
  window.scrollTo({ top: 0, behavior: "instant" });
}
function request() {
  return {
    seed: +$("seed").value,
    length: +$("length").value,
    slowdown: state.slowdown,
    exponent: +$("exponent").value,
    timeout: +$("timeout").value,
    policy: "all",
  };
}
function nameFor(policy, req = request()) {
  return `${req.seed}-${Number(req.slowdown)}-${req.length}-${policy}`;
}
function urlForTrace(policy, dataset = state.dataset, req = request()) {
  return `/api/trace?dataset=${encodeURIComponent(dataset)}&run=${encodeURIComponent(nameFor(policy, req))}`;
}
function traceMatches(data, req, dataset) {
  return (
    data &&
    data.dataset === dataset &&
    data.result.seed === req.seed &&
    data.result.slowdown === req.slowdown &&
    data.result.fade_length === req.length &&
    data.result.path_exponent === req.exponent &&
    data.config.timeout_s === req.timeout
  );
}
function setSetup(req) {
  $("seed").value = req.seed;
  $("length").value = req.length;
  $("exponent").value = req.exponent ?? 2;
  $("timeout").value = req.timeout ?? 7200;
  state.slowdown = req.slowdown;
  $("progress-description").textContent = state.slowdown
    ? "Boat 1 at half speed for 300 s"
    : "Both boats maintain 2 m/s";
  document
    .querySelectorAll("[data-slow]")
    .forEach((e) => e.classList.toggle("selected", (e.dataset.slow === "true") === state.slowdown));
}
async function loadSelected(reset = false) {
  const generation = ++state.generation;
  const policy = $("policy").value;
  try {
    const req = request(),
      dataset = state.dataset;
    const trace = traceMatches(state.traces[policy], req, dataset)
      ? state.traces[policy]
      : await api(urlForTrace(policy));
    if (generation !== state.generation) return;
    if (Object.values(state.traces).some((d) => !traceMatches(d, req, dataset))) state.traces = {};
    state.traces[policy] = trace;
    state.active = policy;
    if (reset) state.t = 0;
    activateTrace();
    renderComparison();
    renderMissionCharts();
    renderEvents();
    drawAll();
  } catch (error) {
    if (generation === state.generation)
      toast(`${error.message} The map retains its last loaded mission.`, true);
  }
}
function activateTrace() {
  const trace = activeTrace();
  if (!trace) return;
  const r = trace.result;
  $("active-policy").innerHTML = `${esc(trace.policy)} <span>${NAMES[trace.policy]}</span>`;
  const maximum = Math.max(...Object.values(state.traces).map((d) => d.result.stop_s));
  $("timeline").max = maximum;
  $("duration-display").textContent = clock(maximum);
  state.t = Math.min(state.t, maximum);
  $("timeline").value = state.t;
  const label = trace.dataset === "core" ? "Frozen evaluation trace" : "Separate run bundle";
  $("source-label").textContent =
    `${label} · seed ${r.seed} · ${r.slowdown ? "slowdown" : "balanced"} · L=${r.fade_length} · n=${r.path_exponent} · independently verified`;
  $("raw-download").href =
    `/api/raw?dataset=${encodeURIComponent(trace.dataset)}&run=${encodeURIComponent(trace.name)}`;
  $("queue-note").textContent = `Tasks sampled every ${trace.config.exchange_s} s`;
}
function frameAt(trace, t) {
  const frames = trace.frames;
  let low = 0,
    high = frames.length - 1;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    if (frames[middle].t <= t) low = middle;
    else high = middle - 1;
  }
  return frames[low];
}
function trackAt(trace, t) {
  const time = Math.min(Math.max(0, t), trace.result.stop_s);
  const a = trace.tracks[Math.floor(time)] || trace.tracks.at(-1);
  const b = trace.tracks[Math.ceil(time)] || a;
  const fraction = time - Math.floor(time);
  return [time, ...a.slice(1, 5).map((v, i) => v + fraction * (b[i + 1] - v)), a[5], a[6]];
}
function canvasContext(canvas) {
  const box = canvas.getBoundingClientRect();
  if (!box.width || !box.height) return null;
  const scale = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.round(box.width * scale),
    height = Math.round(box.height * scale);
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  return { ctx, width: box.width, height: box.height };
}
function drawMap(canvas, trace, time, mini = false) {
  const surface = canvasContext(canvas);
  if (!surface || !trace) return;
  const { ctx, width, height } = surface;
  const c = trace.config;
  const t = Math.min(time, trace.result.stop_s);
  const frame = frameAt(trace, t);
  const track = trackAt(trace, t);
  const paddingX = mini ? 12 : width < 400 ? 28 : 48,
    paddingY = mini ? 10 : 38;
  const cell = Math.min((width - 2 * paddingX) / c.width, (height - 2 * paddingY) / c.height);
  const ox = (width - c.width * cell) / 2,
    oy = (height - c.height * cell) / 2;
  const project = (x, y) => [ox + (x / c.cell_m) * cell, oy + (c.height - y / c.cell_m) * cell];
  const cellXY = (id) => [
    ox + (id % c.width) * cell,
    oy + (c.height - 1 - Math.floor(id / c.width)) * cell,
  ];
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#eaf1ee";
  ctx.fillRect(0, 0, width, height);
  // Subtle contour curves are decorative; the computational world is the grid.
  if (!mini) {
    ctx.strokeStyle = "#d9e5de";
    ctx.lineWidth = 0.6;
    for (let i = 0; i < 7; i++) {
      ctx.beginPath();
      ctx.ellipse(
        width * 0.7,
        height * 0.7,
        width * (0.34 + i * 0.08),
        height * (0.34 + i * 0.08),
        -0.2,
        0,
        2 * Math.PI,
      );
      ctx.stroke();
    }
  }
  let known = null;
  const layer = $("knowledge").value;
  if (!mini && layer !== "global") {
    const boat = +layer;
    known = new Set(frame.known[boat]);
    for (const [at, id, task] of trace.observations)
      if (at > frame.t && at <= t && boat === id) known.add(task);
  }
  for (let id = 0; id < c.width * c.height; id++) {
    const seen = known ? known.has(id) : trace.first_seen[id] != null && trace.first_seen[id] <= t;
    const [x, y] = cellXY(id);
    ctx.fillStyle = seen ? "#b7d3c1" : "#f4f7f1";
    ctx.fillRect(x, y, cell, cell);
    ctx.strokeStyle = seen ? "#a9c7b5" : "#d6e1d7";
    ctx.lineWidth = 0.5;
    ctx.strokeRect(x, y, cell, cell);
  }
  if ($("show-queues").checked && frame.queues)
    frame.queues.forEach((queue, boat) => {
      ctx.strokeStyle = BOAT[boat];
      ctx.lineWidth = mini ? 0.8 : 1.3;
      for (const id of queue) {
        const [x, y] = cellXY(id);
        ctx.strokeRect(x + cell * 0.18, y + cell * 0.18, cell * 0.64, cell * 0.64);
      }
      if (frame.targets?.[boat] != null) {
        const [x, y] = cellXY(frame.targets[boat]);
        ctx.fillStyle = BOAT[boat] + "44";
        ctx.fillRect(x + 1, y + 1, cell - 2, cell - 2);
      }
    });
  if ($("show-trails").checked)
    for (let boat = 0; boat < 2; boat++) {
      ctx.beginPath();
      ctx.strokeStyle = BOAT[boat];
      ctx.globalAlpha = mini ? 0.42 : 0.65;
      ctx.lineWidth = mini ? 1 : 1.4;
      let previous = null;
      for (let i = 0; i <= Math.floor(t) && i < trace.tracks.length; i += mini ? 4 : 2) {
        const record = trace.tracks[i],
          point = project(record[1 + boat * 2], record[2 + boat * 2]);
        if (!previous) ctx.moveTo(...point);
        else if (point[0] !== previous[0] || point[1] !== previous[1]) ctx.lineTo(...point);
        previous = point;
      }
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
  const points = [project(track[1], track[2]), project(track[3], track[4])];
  if (!trace.headings) {
    let headings = [0, 0];
    trace.headings = trace.tracks.map((record, i) => {
      if (i)
        for (let boat = 0; boat < 2; boat++) {
          const previous = trace.tracks[i - 1],
            dx = record[1 + boat * 2] - previous[1 + boat * 2],
            dy = record[2 + boat * 2] - previous[2 + boat * 2];
          if (dx || dy) headings[boat] = Math.atan2(-dy, dx) + Math.PI / 2;
        }
      return [...headings];
    });
  }
  if (frame.radio != null) {
    ctx.beginPath();
    ctx.strokeStyle = frame.radio ? "#538d7a" : "#b77e67";
    ctx.lineWidth = mini ? 0.8 : 1;
    ctx.setLineDash(frame.radio ? [3, 4] : [5, 5]);
    ctx.moveTo(...points[0]);
    ctx.lineTo(...points[1]);
    ctx.stroke();
    ctx.setLineDash([]);
  }
  points.forEach(([x, y], boat) => {
    const size = mini ? 3.5 : 6.5;
    if (!mini) {
      ctx.beginPath();
      ctx.fillStyle = BOAT[boat] + "18";
      ctx.arc(x, y, 14, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(trace.headings[Math.floor(t)][boat]);
    ctx.beginPath();
    ctx.fillStyle = BOAT[boat];
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = mini ? 0.8 : 1.5;
    ctx.moveTo(0, -size * 1.45);
    ctx.lineTo(size, size);
    ctx.lineTo(0, size * 0.65);
    ctx.lineTo(-size, size);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
    if (!mini) {
      ctx.fillStyle = BOAT[boat];
      ctx.font = "600 9px Segoe UI";
      ctx.fillText(`0${boat + 1}`, x + 10, y - 9);
    }
  });
  if (!mini) {
    ctx.font = "8px Segoe UI";
    ctx.fillStyle = "#829b8e";
    ctx.textAlign = "center";
    for (let x = 0; x <= c.width; x += 5)
      ctx.fillText(`${x * c.cell_m}`, ox + x * cell, oy + c.height * cell + 13);
    ctx.textAlign = "right";
    for (let y = 0; y <= c.height; y += 4)
      ctx.fillText(`${y * c.cell_m}`, ox - 9, oy + (c.height - y) * cell + 3);
    ctx.textAlign = "left";
  }
}
function drawAll() {
  const trace = activeTrace();
  if (!trace) return;
  const t = Math.min(state.t, trace.result.stop_s),
    f = frameAt(trace, t);
  drawMap($("map"), trace, state.t);
  document.querySelectorAll(".compare-card").forEach((card) => {
    const data = state.traces[card.dataset.policy];
    drawMap(card.querySelector("canvas"), data, state.t, true);
    card.querySelector(".compare-coverage").textContent =
      `${fmt((100 * data.first_seen.filter((v) => v != null && v <= Math.min(state.t, data.result.stop_s)).length) / data.first_seen.length, 1)}%`;
  });
  const n = trace.first_seen.filter((v) => v != null && v <= t).length;
  $("live-coverage").innerHTML = `${fmt((n / trace.first_seen.length) * 100, 1)}<em> %</em>`;
  $("live-cells").textContent =
    `${n} of ${trace.first_seen.length} cells${t >= trace.result.stop_s ? " · final" : ""}`;
  $("coverage-fill").style.width = `${(n / trace.first_seen.length) * 100}%`;
  $("live-signal").innerHTML = f.r == null ? "—" : `${fmt(f.r, 1)}<em> dBm</em>`;
  $("live-radio").textContent = f.terminal
    ? "Mission ended · no new exchange"
    : f.radio == null
      ? "No exchange yet"
      : f.radio
        ? "Available at last exchange"
        : "Unavailable at last exchange";
  $("live-bytes").innerHTML = `${fmt(f.sent_bytes / 1000, 1)}<em> kB</em>`;
  $("live-delivered").textContent = `${fmt(f.received_bytes / 1000, 1)} kB delivered`;
  $("live-warning").textContent = f.terminal
    ? "Ended"
    : !trace.policy.startsWith("S4")
      ? "Not used"
      : !f.committed
        ? "No decision"
        : f.warning
          ? "Positive"
          : "Negative";
  $("live-queues").textContent = f.queues
    ? `Queues: ${f.queues.map((q) => q.length).join(" / ")} unstarted tasks`
    : "Terminal queues not recorded";
  $("map-clock").textContent = `${clock(t)}${t >= trace.result.stop_s ? " · END" : " SIM"}`;
  $("time-display").textContent = clock(state.t);
  $("timeline").value = state.t;
  document.querySelectorAll(".time-cursor").forEach((line) => {
    const x = 48 + (432 * state.t) / +line.dataset.duration;
    line.setAttribute("x1", Math.min(480, x));
    line.setAttribute("x2", Math.min(480, x));
  });
  const slideMap = $("slide-map");
  if (slideMap) drawMap(slideMap, trace, state.t);
}
function renderComparison() {
  const entries = POLICIES.filter((p) => state.traces[p]);
  if (!entries.length) return;
  $("comparison").innerHTML = entries
    .map((p) => {
      const r = state.traces[p].result;
      return `<button class="compare-card ${p === state.active ? "selected" : ""}" data-policy="${p}" style="--policy-color:${COLORS[p]}" aria-label="Inspect ${p}, ${NAMES[p]}"><div class="compare-top"><span>${p}</span><span class="compare-outcome">${r.complete ? "Complete" : "Cutoff"} · ${fmt(r.stop_s)} s</span></div><canvas aria-label="${p} synchronized mission map"></canvas><div class="compare-bottom"><span><strong class="compare-coverage">0%</strong> observed</span><span>${fmt(r.attempted_bytes / 1000)} kB final</span></div></button>`;
    })
    .join("");
}
async function loadComparison(policies = POLICIES) {
  if (!Array.isArray(policies)) policies = POLICIES;
  const generation = ++state.generation;
  const dataset = state.dataset,
    req = request();
  $("load-comparison").disabled = true;
  const settled = await Promise.allSettled(policies.map((p) => api(urlForTrace(p, dataset, req))));
  $("load-comparison").disabled = false;
  if (generation !== state.generation) return;
  let missing = 0;
  if (
    settled.some((r) => r.status === "fulfilled") &&
    Object.values(state.traces).some((d) => !traceMatches(d, req, dataset))
  )
    state.traces = {};
  settled.forEach((r, i) => {
    if (r.status === "fulfilled") state.traces[policies[i]] = r.value;
    else missing++;
  });
  if (missing)
    toast(
      `${missing} raw traces are not available locally. Run all five policies to regenerate the comparison.`,
      true,
    );
  if (!activeTrace()) state.active = POLICIES.find((p) => state.traces[p]) || state.active;
  $("policy").value = state.active;
  activateTrace();
  renderComparison();
  renderMissionCharts();
  renderEvents();
  drawAll();
}
function setTime(t) {
  state.t = Math.min(Math.max(0, t), +$("timeline").max);
  drawAll();
}
function setPlaying(on) {
  state.playing = on;
  $("play").classList.toggle("playing", on);
  $("play").setAttribute("aria-label", on ? "Pause simulation" : "Play simulation");
  $("play").innerHTML = on ? "Ⅱ" : '<svg><use href="#i-play"/></svg>';
}
let lastFrame = 0,
  renderAt = 0;
function animate(timestamp) {
  const elapsed = Math.min((timestamp - lastFrame) / 1000, 0.1);
  lastFrame = timestamp;
  if (state.playing && !document.hidden && ["mission", "presentation"].includes(state.view)) {
    state.t = Math.min(+$("timeline").max, state.t + elapsed * +$("speed").value);
    if (timestamp - renderAt > 40) {
      drawAll();
      renderAt = timestamp;
    }
    if (state.t >= +$("timeline").max) setPlaying(false);
  }
  requestAnimationFrame(animate);
}

// SVG charts use local, recorded numbers; exported figures retain text and units.
function text(x, y, value, className = "chart-label", anchor = "start") {
  return `<text x="${x}" y="${y}" class="${className}" text-anchor="${anchor}">${esc(value)}</text>`;
}
function chartShell(title, content, height = 240) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 510 ${height}" role="img" aria-label="${esc(title)}"><title>${esc(title)}</title><style>text{font-family:Arial,sans-serif}.chart-label{font-size:9px;fill:#6c8277}.chart-value{font-size:10px;fill:#274c41;font-weight:600}.legend-label{font-size:8px;fill:#72857a}.grid-line{stroke:#e9eee7;stroke-width:1}.time-cursor{stroke:#b5c9bf;stroke-width:1;stroke-dasharray:3 3}</style>${content}</svg>`;
}
function lineChart(
  id,
  series,
  { title, min = 0, max = 100, duration = 7200, unit = "", threshold, markers = [] } = {},
) {
  const left = 48,
    right = 480,
    top = 20,
    bottom = 190;
  const x = (t) => left + ((right - left) * t) / duration;
  const y = (v) => bottom - ((bottom - top) * (v - min)) / (max - min);
  let content = "";
  for (let i = 0; i < 5; i++) {
    const value = min + ((max - min) * i) / 4,
      at = y(value);
    content += `<line x1="${left}" x2="${right}" y1="${at}" y2="${at}" class="grid-line"/>${text(left - 8, at + 3, fmt(value), "chart-label", "end")}`;
  }
  for (let i = 0; i <= 4; i++)
    content += text(
      x((duration * i) / 4),
      208,
      fmt(((duration / 60) * i) / 4),
      "chart-label",
      "middle",
    );
  content += text(left, 10, unit) + text(right, 222, "Simulation time [min]", "chart-label", "end");
  if (threshold != null)
    content += `<line x1="${left}" x2="${right}" y1="${y(threshold)}" y2="${y(threshold)}" stroke="#bf7865" stroke-width="1" stroke-dasharray="4 3"/>`;
  series.forEach((s, i) => {
    const d = s.values
      .map(([at, value], j) => `${j ? "L" : "M"}${x(at).toFixed(2)},${y(value).toFixed(2)}`)
      .join(" ");
    content += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="1.8"><title>${esc(s.name)}</title></path>`;
    content += `<circle cx="${left + i * 83}" cy="235" r="2.5" fill="${s.color}"/>${text(left + 7 + i * 83, 238, s.name, "legend-label")}`;
  });
  for (const marker of markers)
    content += `<circle cx="${x(marker.t)}" cy="${y(marker.r)}" r="2.5" fill="#bd8f32"><title>Warning at ${marker.t} s, ${fmt(marker.r, 1)} dBm</title></circle>`;
  content += `<line class="time-cursor" data-duration="${duration}" x1="48" x2="48" y1="20" y2="190"/>`;
  $(id).innerHTML = chartShell(title, content, 250);
  $(id)
    .querySelector("svg")
    .addEventListener("click", (event) => {
      const rect = event.currentTarget.getBoundingClientRect();
      setTime(
        ((((event.clientX - rect.left) / rect.width) * 510 - left) / (right - left)) * duration,
      );
    });
}
function renderMissionCharts() {
  const entries = POLICIES.filter((p) => state.traces[p]);
  if (!entries.length) return;
  const duration = Math.max(...entries.map((p) => state.traces[p].result.stop_s));
  const series = entries.map((p) => {
    const d = state.traces[p];
    const first = d.first_seen.filter((t) => t != null).sort((a, b) => a - b);
    const values = [[0, 0]];
    first.forEach((t, i) => {
      values.push([t, (i / d.first_seen.length) * 100], [t, ((i + 1) / d.first_seen.length) * 100]);
    });
    values.push([d.result.stop_s, d.result.coverage * 100]);
    return { name: p, color: COLORS[p], values };
  });
  lineChart("coverage-chart", series, {
    title: "Observed coverage by policy",
    duration,
    unit: "Observed coverage [%]",
  });
  const trace = activeTrace();
  if (!trace) return;
  const samples = trace.sessions,
    signals = samples.map((s) => s.r);
  const min = Math.floor(Math.min(-95, ...signals) / 5) * 5,
    max = Math.ceil(Math.max(-65, ...signals) / 5) * 5;
  lineChart(
    "signal-chart",
    [{ name: state.active, color: COLORS[state.active], values: samples.map((s) => [s.t, s.r]) }],
    {
      title: `${state.active} received radio signal`,
      min,
      max,
      duration,
      unit: "Received signal [dBm]",
      threshold: trace.config.threshold_dbm,
      markers: samples.filter((s) => s.warning),
    },
  );
}
function barChart(
  id,
  data,
  { title, unit = "", max, suffix = "", digits = 0, secondary = false, ticks } = {},
) {
  const left = 48,
    right = 480,
    top = 24,
    bottom = 183;
  max = max ?? Math.max(1, ...data.map((d) => d.hi ?? Math.max(d.value, d.other || 0))) * 1.16;
  const y = (v) => bottom - ((bottom - top) * v) / max,
    spacing = (right - left) / data.length;
  let content = text(left, 11, unit);
  for (const value of ticks || [0, max / 4, max / 2, max * 0.75, max]) {
    const at = y(value);
    content += `<line x1="${left}" x2="${right}" y1="${at}" y2="${at}" class="grid-line"/>${text(left - 8, at + 3, fmt(value, max <= 1 ? 2 : 0), "chart-label", "end")}`;
  }
  data.forEach((d, i) => {
    const center = left + spacing * (i + 0.5),
      width = Math.min(42, spacing * 0.48),
      x = secondary ? center - width * 0.85 : center - width / 2;
    const w = secondary ? width * 0.8 : width;
    content += `<rect x="${x}" y="${y(d.value)}" width="${w}" height="${bottom - y(d.value)}" rx="2" fill="${d.color || COLORS[d.name] || "#087f81"}"><title>${esc(d.name)}: ${fmt(d.value, digits)} ${esc(unit)}</title></rect>`;
    if (secondary)
      content += `<rect x="${center + width * 0.08}" y="${y(d.other)}" width="${w}" height="${bottom - y(d.other)}" rx="2" fill="${d.color || COLORS[d.name]}" opacity=".32"><title>${esc(d.name)} delivered: ${fmt(d.other, digits)}</title></rect>`;
    if (d.lo != null)
      content += `<path d="M${center},${y(d.lo)}V${y(d.hi)}M${center - 4},${y(d.lo)}H${center + 4}M${center - 4},${y(d.hi)}H${center + 4}" stroke="#315749" stroke-width="1.2" fill="none"/>`;
    content +=
      text(
        center,
        Math.max(17, y(d.hi ?? d.value) - 8),
        `${fmt(d.value, digits)}${suffix}`,
        "chart-value",
        "middle",
      ) + text(center, 202, d.name, "chart-label", "middle");
  });
  if (secondary)
    content += `<rect x="130" y="220" width="7" height="7" fill="#087f81"/>${text(142, 227, "Attempted", "legend-label")}<rect x="250" y="220" width="7" height="7" fill="#087f81" opacity=".32"/>${text(262, 227, "Delivered", "legend-label")}`;
  $(id).innerHTML = chartShell(title, content, 242);
}
function contrastChart(rows) {
  const left = 160,
    right = 465,
    low = Math.min(0, ...rows.map((r) => +r.ci_low_s)),
    high = Math.max(0, ...rows.map((r) => +r.ci_high_s));
  const pad = (high - low || 1) * 0.16,
    x = (v) => left + ((right - left) * (v - low + pad)) / (high - low + pad * 2);
  let content = text(left, 12, "Difference in restricted time [s]");
  for (let i = 0; i <= 4; i++) {
    const value = low - pad + ((high - low + 2 * pad) * i) / 4,
      at = x(value);
    content += `<line x1="${at}" x2="${at}" y1="24" y2="181" class="grid-line"/>${text(at, 205, fmt(value), "chart-label", "middle")}`;
  }
  content += `<line x1="${x(0)}" x2="${x(0)}" y1="24" y2="181" stroke="#94ac9a" stroke-dasharray="3 3"/>`;
  rows.forEach((r, i) => {
    const y = 48 + i * 52;
    content += text(12, y + 3, r.comparison.replace(" minus ", " − "));
    content += `<path d="M${x(+r.ci_low_s)},${y}H${x(+r.ci_high_s)}M${x(+r.ci_low_s)},${y - 5}V${y + 5}M${x(+r.ci_high_s)},${y - 5}V${y + 5}" stroke="#087f81" stroke-width="1.5"/><circle cx="${x(+r.mean_difference_s)}" cy="${y}" r="4" fill="#087f81"><title>${fmt(+r.mean_difference_s, 1)} s [${fmt(+r.ci_low_s, 1)}, ${fmt(+r.ci_high_s, 1)}]</title></circle>`;
  });
  content +=
    text(168, 228, "← Faster trend policy", "legend-label") +
    text(465, 228, "Slower trend policy →", "legend-label", "end");
  $("contrast-chart").innerHTML = chartShell(
    "Paired S4-T time differences with 95% intervals",
    content,
    242,
  );
}
function warningChart() {
  const rows = state.catalog.warnings;
  let content = "";
  const methods = ["Precision", "Recall", "F1"];
  const top = 22,
    bottom = 183,
    y = (v) => bottom - (bottom - top) * v;
  for (let i = 0; i <= 4; i++)
    content += `<line x1="48" x2="480" y1="${y(i / 4)}" y2="${y(i / 4)}" class="grid-line"/>${text(40, y(i / 4) + 3, fmt(i / 4, 2), "chart-label", "end")}`;
  rows.forEach((row, j) =>
    methods.forEach((metric, i) => {
      const value = row[metric.toLowerCase()],
        x = 95 + i * 140 + j * 29;
      if (value != null)
        content += `<rect x="${x}" y="${y(value)}" width="24" height="${bottom - y(value)}" fill="${j ? COLORS["S4-P"] : COLORS["S4-T"]}" rx="2"><title>${row.method} ${metric}: ${fmt(value, 3)}</title></rect>${text(x + 12, y(value) - 7, fmt(value, 2), "chart-value", "middle")}`;
    }),
  );
  methods.forEach((metric, i) => {
    content += text(121 + i * 140, 202, metric, "chart-label", "middle");
  });
  content += `<circle cx="162" cy="225" r="3" fill="${COLORS["S4-T"]}"/>${text(170, 228, "Trend", "legend-label")}<circle cx="270" cy="225" r="3" fill="${COLORS["S4-P"]}"/>${text(278, 228, "Persistence", "legend-label")}`;
  $("warning-chart").innerHTML = chartShell(
    "Held-out fixed-route event warning quality",
    content,
    242,
  );
}
function workChart() {
  const resources = state.catalog.tables["component-resources"] || [],
    components = ["allocation", "forecast", "resync"],
    shades = ["#406b63", "#8bb3a1", "#cfdfd3"];
  const totals = POLICIES.map((p) =>
    components.map(
      (c) =>
        +(resources.find((r) => r.policy === p && r.component === c)?.mean_arithmetic || 0) / 1000,
    ),
  );
  const maximum = Math.max(1, ...totals.map((t) => t.reduce((a, b) => a + b, 0))) * 1.15;
  const y = (value) => 183 - (159 * value) / maximum;
  let content = text(48, 11, "Arithmetic [thousands of operations]");
  for (let i = 0; i <= 4; i++)
    content += `<line x1="48" x2="480" y1="${y((maximum * i) / 4)}" y2="${y((maximum * i) / 4)}" class="grid-line"/>${text(40, y((maximum * i) / 4) + 3, fmt((maximum * i) / 4), "chart-label", "end")}`;
  totals.forEach((values, i) => {
    let accumulated = 0;
    values.forEach((value, j) => {
      const x = 72 + i * 86;
      content += `<rect x="${x}" y="${y(accumulated + value)}" width="37" height="${(159 * value) / maximum}" fill="${shades[j]}"><title>${POLICIES[i]} ${components[j]}: ${fmt(value * 1000)} operations</title></rect>`;
      accumulated += value;
    });
    content += text(90.5 + i * 86, 202, POLICIES[i], "chart-label", "middle");
  });
  components.forEach((c, i) => {
    content += `<rect x="${94 + i * 115}" y="222" width="7" height="7" fill="${shades[i]}"/>${text(106 + i * 115, 229, c, "legend-label")}`;
  });
  $("work-chart").innerHTML = chartShell(
    "Mean component arithmetic across the frozen study",
    content,
    242,
  );
}
function conditionRows() {
  return state.catalog.runs.filter(
    (r) =>
      r.slowdown === ($("study-slow").value === "true") &&
      r.fade_length === +$("study-length").value,
  );
}
function renderEvidence() {
  const c = state.catalog,
    slow = $("study-slow").value === "true",
    length = +$("study-length").value;
  const match = (r) =>
    String(r.slowdown).toLowerCase() === String(slow) && +r.fade_length === length;
  const summaries = (c.tables["condition-summary"] || [])
    .filter(match)
    .sort((a, b) => POLICIES.indexOf(a.policy) - POLICIES.indexOf(b.policy));
  const rows = conditionRows();
  $("condition-label").textContent = `${rows.length} runs in this condition`;
  barChart(
    "time-chart",
    summaries.map((r) => ({
      name: r.policy,
      value: +r.restricted_mean_s,
      lo: +r.ci_low_s,
      hi: +r.ci_high_s,
    })),
    {
      title: "Restricted mission time with marginal 95% bootstrap intervals",
      unit: "Restricted time [s]",
      max: 8000,
    },
  );
  barChart(
    "completion-chart",
    POLICIES.map((p) => ({
      name: p,
      value: rows.filter((r) => r.policy === p && r.complete).length,
    })),
    {
      title: "Completed missions out of 30 per policy",
      unit: "Completed missions [of 30]",
      max: 33,
      ticks: [0, 10, 20, 30],
    },
  );
  contrastChart((c.tables["paired-contrasts"] || []).filter(match));
  barChart(
    "bytes-chart",
    summaries.map((r) => ({
      name: r.policy,
      value: +r.attempted_bytes / 1000,
      other: +r.delivered_bytes / 1000,
    })),
    { title: "Attempted and delivered serialized payload", unit: "Payload [kB]", secondary: true },
  );
  warningChart();
  workChart();
  renderRuns();
  $("verified-count").textContent =
    `${fmt(c.verification.raw_runs_reconstructed)} raw logs independently reconstructed`;
  $("design-hash").textContent = c.design.sha256;
  $("provenance-json").textContent = JSON.stringify(
    {
      evaluation: c.evaluation,
      analysis: c.analysis,
      verification: c.verification,
      environment: c.environment,
    },
    null,
    2,
  );
  const b = c.benchmark,
    timings = b.timings || {},
    memory = b.process_memory || [];
  const cards = [
    ["TREND FORECAST", timings.trend?.median_cpu_ns / 1000, "µs", "Median CPU per decision"],
    ["PERSISTENCE", timings.persistence?.median_cpu_ns / 1000, "µs", "Median CPU per decision"],
    ["TASK ALLOCATION", timings.allocation?.median_cpu_ns / 1000, "µs", "Median CPU per decision"],
  ];
  $("host-metrics").innerHTML =
    cards
      .map(
        ([name, value, unit, note]) =>
          `<div><span>${name}</span><strong>${Number.isFinite(value) ? fmt(value, 1) : "—"} <small>${unit}</small></strong><small>${note}</small></div>`,
      )
      .join("") +
    `<div><span>ISOLATED PROCESS PEAK</span><strong>${memory.length ? `${fmt(Math.min(...memory.map((r) => r.peak_process_rss_bytes)) / 1048576, 1)}–${fmt(Math.max(...memory.map((r) => r.peak_process_rss_bytes)) / 1048576, 1)}` : "—"} <small>MiB</small></strong><small>Windows high-water working set</small></div>`;
}
function renderRuns() {
  const outcome = $("outcome-filter").value;
  const rows = conditionRows().filter(
    (r) => outcome === "all" || r.complete === (outcome === "complete"),
  );
  $("runs-body").innerHTML = rows
    .map(
      (r) =>
        `<tr><td>${r.seed}</td><td><b style="color:${COLORS[r.policy]}">${r.policy}</b></td><td><span class="outcome ${r.complete ? "" : "timeout"}">${r.complete ? "Complete" : "Cutoff"}</span></td><td>${fmt(r.restricted_s)}${r.complete ? "" : " *"}</td><td>${fmt(100 * r.coverage, 1)}%</td><td>${r.redundant}</td><td>${fmt(r.attempted_bytes / 1000, 1)}</td><td><button data-replay="${nameFor(r.policy, { seed: r.seed, slowdown: r.slowdown, length: r.fade_length })}">Replay ↗</button></td></tr>`,
    )
    .join("");
  $("runs-count").textContent =
    `${rows.length} missions · * restricted cutoff, completion time undefined`;
}
function renderEvents() {
  const trace = activeTrace();
  if (!trace) return;
  const filter = $("event-filter").value;
  const rows = trace.sessions.filter(
    (e) =>
      filter === "all" ||
      (filter === "warning" && e.warning) ||
      (filter === "failed" && !e.radio) ||
      (filter === "commit" && e.committed),
  );
  $("events-body").innerHTML = rows
    .map(
      (e) =>
        `<tr class="clickable" data-session="${e.k}" tabindex="0" aria-label="Inspect exchange at ${e.t} seconds"><td>${fmt(e.t)}</td><td>${fmt(e.r, 1)}</td><td>${e.radio ? "Available" : "Unavailable"}</td><td>${e.warning ? "Warning + reserve" : e.committed ? "Allocate" : "No commit"}</td><td>${fmt(e.bytes_attempted)}</td></tr>`,
    )
    .join("");
  $("event-count").textContent =
    `${rows.length} shown / ${trace.sessions.length} exchanges · ${fmt(trace.event_counts.tick)} motion ticks`;
  $("event-json").textContent =
    "Select an exchange to inspect its exact serialized record, including payloads, reservations, local knowledge and counted work.";
}
function inspectEvent(row) {
  const session = activeTrace()?.sessions.find((e) => e.k === +row.dataset.session);
  if (!session) return;
  setPlaying(false);
  setTime(session.t);
  $("event-json").textContent = JSON.stringify(session, null, 2);
  document
    .querySelectorAll("#events-body tr")
    .forEach((e) => e.classList.toggle("selected", e === row));
}
function downloadBlob(content, type, filename) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function exportChart(id) {
  const svg = $(id).querySelector("svg");
  if (!svg) return;
  const copy = svg.cloneNode(true);
  copy.querySelectorAll(".time-cursor").forEach((e) => e.remove());
  const description = document.createElementNS("http://www.w3.org/2000/svg", "desc");
  const mission = ["coverage-chart", "signal-chart"].includes(id),
    r = activeTrace()?.result;
  description.textContent = `USV Research Lab; synthetic model; design ${state.catalog.design.sha256}; ${mission ? `scenario seed=${r?.seed}, slowdown=${r?.slowdown}, L=${r?.fade_length}, dataset=${activeTrace()?.dataset}` : `frozen study; condition slowdown=${$("study-slow").value}, L=${$("study-length").value}; pooled charts are explicitly labeled`}. See repository for definitions and source evidence.`;
  const filename = mission
    ? `${id}-seed${r?.seed}-slow${Number(r?.slowdown)}-L${r?.fade_length}.svg`
    : `${id}-slow${Number($("study-slow").value === "true")}-L${$("study-length").value}.svg`;
  copy.prepend(description);
  downloadBlob(new XMLSerializer().serializeToString(copy), "image/svg+xml", filename);
  toast("Chart exported as an editable SVG. Run bundles also include PNG and PDF figures.");
}
async function submit(action, selected = false) {
  try {
    if (!state.catalog) return;
    let req = {};
    if (action === "run") {
      if (!$("run-form").reportValidity()) return;
      req = request();
      req.policy = selected ? $("policy").value : "all";
    }
    const record = await api("/api/jobs", { action, request: req });
    state.currentJob = record.id;
    $("run-progress").hidden = false;
    $("run-status").textContent = `Queued ${record.action} · ${record.id}`;
    toast(
      `${action === "run" ? "Experiment" : "Workflow"} queued. Its evidence will be saved in a new bundle.`,
    );
    await refreshJobs();
  } catch (error) {
    toast(error.message, true);
  }
}
const handledJobs = new Set();
async function refreshJobs() {
  const jobs = await api("/api/jobs");
  state.jobs = jobs;
  $("job-count").textContent = jobs.length;
  $("jobs-list").innerHTML = jobs.length
    ? jobs
        .map(
          (j) =>
            `<div class="job-row" data-job="${j.id}" tabindex="0" role="button" aria-label="Inspect ${j.action} ${j.id}"><span class="job-state ${j.status}">${j.status === "passed" ? "✓" : ["failed", "interrupted"].includes(j.status) ? "!" : "↻"}</span><div><h3>${esc(j.action === "run" ? `${j.request.policy === "all" ? "Five-policy comparison" : j.request.policy} · seed ${j.request.seed}` : { tests: "Implementation tests", smoke: "Automated smoke workflow", full: "Full 900-mission reproduction" }[j.action])} <span class="outcome ${j.status === "failed" ? "timeout" : ""}">${esc(j.status)}</span></h3><p>${esc(j.message)}</p><p class="mono">${j.id}</p></div><time>${esc(new Date(j.created_utc).toLocaleString("en-GB"))}</time><button class="text-button">Inspect ↗</button></div>`,
        )
        .join("")
    : '<div class="empty">Your experiment history starts here. Run a mission or launch a verification workflow.</div>';
  const current = jobs.find((j) => j.id === state.currentJob);
  if (current) {
    $("run-status").textContent = `${current.status}: ${current.message}`;
    $("run-meter").max = current.total || 1;
    $("run-meter").value = current.done || 0;
    if (
      ["passed", "failed", "interrupted"].includes(current.status) &&
      !handledJobs.has(current.id)
    ) {
      handledJobs.add(current.id);
      if (current.status === "passed") {
        toast("Run complete. Raw logs verified; figures and evidence archive ready.");
        if (["run", "smoke", "full"].includes(current.action)) await openCompleted(current.id);
      } else toast(current.message, true);
    }
  }
  if (
    state.selectedJob &&
    jobs.some(
      (j) => j.id === state.selectedJob && ["running", "queued", "packaging"].includes(j.status),
    )
  )
    await inspectJob(state.selectedJob);
}
async function openCompleted(identity) {
  const job = await api(`/api/job?id=${identity}`);
  if (!job.runs.length) return;
  const r = job.runs[0],
    req =
      job.action === "run"
        ? job.request
        : {
            seed: r.seed,
            length: r.fade_length,
            slowdown: r.slowdown,
            exponent: r.path_exponent,
            timeout: 7200,
          };
  setSetup(req);
  state.dataset = identity;
  state.traces = {};
  state.t = 0;
  setPlaying(false);
  if (!job.runs.some((r) => r.policy === $("policy").value)) $("policy").value = job.runs[0].policy;
  await loadComparison(POLICIES.filter((p) => job.runs.some((r) => r.policy === p)));
}
async function inspectJob(identity) {
  state.selectedJob = identity;
  const job = await api(`/api/job?id=${identity}`);
  $("job-detail").hidden = false;
  $("job-title").textContent = `${job.action} · ${job.id}`;
  const link = (name, label) =>
    `<a class="text-button" href="/api/download?dataset=${identity}&name=${encodeURIComponent(name)}">${label} ↓</a>`;
  $("job-downloads").innerHTML = ["passed", "failed", "interrupted"].includes(job.status)
    ? link("evidence.zip", "Evidence ZIP") +
      link("provenance.json", "Provenance") +
      (job.runs.length && job.status === "passed"
        ? `<button class="text-button" data-open-job="${identity}">Replay ↗</button>`
        : "")
    : "";
  $("job-log").textContent =
    job.test_log ||
    JSON.stringify(
      {
        status: job.status,
        request: job.request,
        message: job.message,
        runs: job.runs.map((r) => ({
          policy: r.policy,
          complete: r.complete,
          coverage: r.coverage,
          restricted_s: r.restricted_s,
        })),
        provenance: job.provenance,
      },
      null,
      2,
    );
}
function renderSlide() {
  if (!state.catalog) return;
  const d = state.catalog,
    all = d.runs;
  const completed = (p) => all.filter((r) => r.policy === p && r.complete).length;
  const content = [
    () =>
      `<div class="eyebrow">01 · THE QUESTION</div><h2 class="slide-title">Can a short radio forecast improve a shared survey?</h2><p class="slide-lead">Two unmanned surface vehicles divide 240 observation cells. They must coordinate while the radio link fades and one boat can temporarily slow down.</p><div class="slide-facts"><div><strong>2</strong><span>simulated boats</span></div><div><strong>240</strong><span>cells · 400 × 240 m</span></div><div><strong>10 s</strong><span>between exchanges</span></div></div><div class="slide-callout">Controlled synthetic evidence: finite speed, turn costs, bounded messages, independent disturbance streams. No measured energy or physical survey accuracy.</div>`,
    () =>
      `<div class="eyebrow">02 · THE MECHANISM</div><h2 class="slide-title">Watch work continue when the link cannot.</h2><div class="slide-grid"><div><canvas id="slide-map" class="slide-map" aria-label="Active mission replay"></canvas><button id="slide-play" class="button primary">${state.playing ? "Pause mission" : "Play mission"}</button> <span class="mono">${esc(state.active)} · seed ${activeTrace()?.result.seed ?? "—"} · use Mission lab to seek</span></div><ul class="slide-list"><li><b>S2 · Short queue</b>Three unstarted tasks. Refill requires a successful atomic exchange.</li><li><b>S3 · Always long</b>Twelve tasks, testing whether queue capacity alone explains the effect.</li><li><b>S4-T / S4-P · Adaptive reserve</b>Use the same allocator; extend the queue when trend or persistence warns of an outage.</li></ul></div>`,
    () =>
      `<div class="eyebrow">03 · THE OBSERVED OUTCOME</div><h2 class="slide-title">Completion reveals the model’s limits.</h2><div id="slide-completion" class="chart"></div><p class="slide-lead">S1 finished ${completed("S1")}/180 missions; S2 finished ${completed("S2")}/180. Boats with empty queues can remain beyond radio range because this model has no reconnection controller.</p><div class="slide-callout">Trend reservations finished ${completed("S4-T")}/180 missions. Always-long queues finished ${completed("S3")}/180; persistence finished ${completed("S4-P")}/180. These pooled counts are descriptive. Use condition-specific paired intervals for comparisons.</div>`,
    () =>
      `<div class="eyebrow">04 · INTERPRETATION</div><h2 class="slide-title">Reserve capacity helps.<br>Forecast value remains unproven.</h2><div class="slide-grid"><div><p class="slide-lead">The reactive baseline stalls. Its large contrast with adaptive reservations cannot establish that a trend forecast is useful.</p><ul class="slide-list"><li><b>Compare against strong controls</b>Inspect S4-T − S3 and S4-T − S4-P within each condition.</li><li><b>Do not discard incomplete missions</b>Restricted time includes the 7200 s administrative cutoff.</li><li><b>Separate resource measures</b>Bytes, arithmetic counts, CPU time and memory describe different costs. They are not measured energy.</li></ul></div><div id="slide-warning" class="chart"></div></div>`,
    () =>
      `<div class="eyebrow">05 · REPRODUCIBILITY</div><h2 class="slide-title">Every figure has a path back to an event.</h2><div class="slide-facts"><div><strong>${fmt(all.length)}</strong><span>evaluation missions</span></div><div><strong>${fmt(d.verification.raw_runs_reconstructed)}</strong><span>logs reconstructed</span></div><div><strong>30</strong><span>paired seeds / condition</span></div></div><ul class="slide-list"><li><b>Freeze before evaluation</b>Pilot 0–9; evaluation 1000–1029; selected warning margins 4 dB.</li><li><b>Keep evidence together</b>Configuration, source snapshot, environment, raw logs, metrics, figures and SHA-256 inventory.</li><li><b>Run it again</b><code>python -m usv_sim.workflow --preset full --workers 4</code></li></ul><div class="slide-callout">Author reproduction and mentor review remain necessary. Next research decisions should follow the results and the agreed plan; the dashboard does not change the frozen protocol.</div>`,
  ];
  $("slide-number").textContent = `${String(state.slide + 1).padStart(2, "0")} / 05`;
  $("slide-content").innerHTML = content[state.slide]();
  $("slide-dots").innerHTML = content
    .map(
      (_, i) =>
        `<button class="${i === state.slide ? "active" : ""}" data-slide="${i}" aria-label="Scene ${i + 1}"></button>`,
    )
    .join("");
  $("previous-slide").disabled = state.slide === 0;
  $("next-slide").disabled = state.slide === 4;
  if (state.slide === 1) drawAll();
  if (state.slide === 2)
    barChart(
      "slide-completion",
      POLICIES.map((p) => ({ name: p, value: completed(p) })),
      {
        title: "Completed missions across all six equally sized conditions",
        unit: "Completed missions [of 180]",
        max: 200,
      },
    );
  if (state.slide === 3) $("slide-warning").innerHTML = $("warning-chart").innerHTML;
}

document.addEventListener("click", async (event) => {
  const nav = event.target.closest("[data-view]");
  if (nav) view(nav.dataset.view);
  const slow = event.target.closest("[data-slow]");
  if (slow) {
    setSetup({ ...request(), slowdown: slow.dataset.slow === "true" });
    setupChanged();
  }
  const policy = event.target.closest(".compare-card");
  if (policy) {
    $("policy").value = policy.dataset.policy;
    await loadSelected();
  }
  const session = event.target.closest("[data-session]");
  if (session) inspectEvent(session);
  const chart = event.target.closest(".chart-export");
  if (chart) exportChart(chart.dataset.chart);
  const action = event.target.closest("[data-action]");
  if (action) await submit(action.dataset.action);
  const job = event.target.closest("[data-job]");
  if (job) {
    try {
      await inspectJob(job.dataset.job);
    } catch (e) {
      toast(e.message, true);
    }
  }
  const open = event.target.closest("[data-open-job]");
  if (open) {
    await openCompleted(open.dataset.openJob);
    view("mission");
  }
  const replay = event.target.closest("[data-replay]");
  if (replay) {
    const parts = replay.dataset.replay.split("-");
    const p = parts.slice(3).join("-");
    setSetup({
      seed: +parts[0],
      slowdown: parts[1] === "1",
      length: +parts[2],
      exponent: 2,
      timeout: 7200,
    });
    state.dataset = "core";
    $("policy").value = p;
    await loadSelected(true);
    view("mission");
  }
  const slide = event.target.closest("[data-slide]");
  if (slide) {
    state.slide = +slide.dataset.slide;
    renderSlide();
  }
  if (event.target.closest("#slide-play")) {
    setPlaying(!state.playing);
    $("slide-play").textContent = state.playing ? "Pause mission" : "Play mission";
  }
});
document.addEventListener("keydown", (event) => {
  if (["INPUT", "SELECT", "TEXTAREA"].includes(event.target.tagName)) return;
  if (event.key === "Enter") {
    const row = event.target.closest("[data-session]");
    if (row) inspectEvent(row);
    const job = event.target.closest("[data-job]");
    if (job) inspectJob(job.dataset.job).catch((e) => toast(e.message, true));
  }
  if (event.key === "Escape" && state.presentationFocus) exitPresentationFocus();
  if (state.view === "presentation" && ["ArrowLeft", "ArrowRight"].includes(event.key)) {
    event.preventDefault();
    state.slide = Math.min(4, Math.max(0, state.slide + (event.key === "ArrowRight" ? 1 : -1)));
    renderSlide();
  }
});
function setupChanged() {
  state.dataset = "core";
  setPlaying(false);
  if (+$("exponent").value === 2 && +$("timeout").value === 7200) loadSelected(true);
  else
    toast(
      "Exploratory settings selected. Run a mission to apply them; the map retains its last recorded view.",
    );
}
$("policy").addEventListener("change", () => loadSelected());
for (const id of ["seed", "length", "exponent", "timeout"])
  $(id).addEventListener("change", setupChanged);
for (const id of ["show-trails", "show-queues", "knowledge"])
  $(id).addEventListener("change", drawAll);
$("timeline").addEventListener("input", () => {
  setPlaying(false);
  setTime(+$("timeline").value);
});
$("play").addEventListener("click", () => {
  if (state.t >= +$("timeline").max) state.t = 0;
  setPlaying(!state.playing);
});
$("restart").addEventListener("click", () => {
  setPlaying(false);
  setTime(0);
});
$("load-comparison").addEventListener("click", loadComparison);
$("run-form").addEventListener("submit", (event) => {
  event.preventDefault();
  submit("run");
});
$("run-one").addEventListener("click", () => submit("run", true));
$("event-filter").addEventListener("change", renderEvents);
for (const id of ["study-slow", "study-length"]) $(id).addEventListener("change", renderEvidence);
$("outcome-filter").addEventListener("change", renderRuns);
$("snapshot").addEventListener("click", () => {
  const canvas = $("map");
  if (!activeTrace()) return;
  const output = document.createElement("canvas");
  output.width = Math.max(canvas.width, 780);
  output.height = canvas.height + 110;
  const context = output.getContext("2d");
  context.fillStyle = "#f4f7f1";
  context.fillRect(0, 0, output.width, output.height);
  context.drawImage(canvas, (output.width - canvas.width) / 2, 0);
  context.fillStyle = "#315b4a";
  context.font = "14px Segoe UI";
  const trace = activeTrace();
  const snapshotTime = Math.min(state.t, trace.result.stop_s);
  context.fillText(
    `USV Research Lab · ${state.active} · seed ${trace.result.seed} · ${fmt(snapshotTime, 1)} s · synthetic model`,
    20,
    canvas.height + 28,
  );
  context.font = "12px Segoe UI";
  const c = trace.config;
  context.fillText(
    `${c.width * c.cell_m} × ${c.height * c.cell_m} m · ${c.cell_m} m cells · L=${trace.result.fade_length} exchanges · slowdown=${trace.result.slowdown} · n=${c.path_exponent}`,
    20,
    canvas.height + 48,
  );
  context.font = "11px Segoe UI";
  const layer = $("knowledge").value;
  context.fillText(
    `Green: ${layer === "global" ? "observed coverage" : `boat ${Number(layer) + 1} knowledge`} · orange: boat 1 · teal: boat 2 · outlines: queued tasks`,
    20,
    canvas.height + 68,
  );
  context.font = "10px Consolas";
  context.fillText(`raw SHA-256 ${trace.raw_sha256}`, 20, canvas.height + 89);
  const filename = `mission-${trace.name}-${snapshotTime.toFixed(1)}s.png`;
  output.toBlob((blob) => {
    if (blob) downloadBlob(blob, "image/png", filename);
    else
      toast("The browser could not encode this map. Try the figure export in a run bundle.", true);
  }, "image/png");
});
$("previous-slide").addEventListener("click", () => {
  state.slide = Math.max(0, state.slide - 1);
  renderSlide();
});
$("next-slide").addEventListener("click", () => {
  state.slide = Math.min(4, state.slide + 1);
  renderSlide();
});
function presentationFocus(on) {
  state.presentationFocus = on;
  document.body.classList.toggle("presentation-focus", on);
  $("exit-presentation").hidden = !on;
  drawAll();
}
function exitPresentationFocus() {
  presentationFocus(false);
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
}
$("fullscreen").addEventListener("click", () => {
  presentationFocus(true);
  // Embedded browsers may deny native fullscreen. Focused layout still works.
  document
    .querySelector(".presentation-shell")
    .requestFullscreen?.()
    .catch(() => {});
});
$("exit-presentation").addEventListener("click", exitPresentationFocus);
document.addEventListener("fullscreenchange", () => {
  if (document.fullscreenElement) state.nativeFullscreen = true;
  else if (state.nativeFullscreen) {
    state.nativeFullscreen = false;
    presentationFocus(false);
  }
});
$("refresh-jobs").addEventListener("click", () =>
  refreshJobs().catch((e) => toast(e.message, true)),
);
window.addEventListener("resize", drawAll);
async function init() {
  try {
    state.catalog = await api("/api/catalog");
    renderEvidence();
    await refreshJobs();
    view(location.hash.slice(1) || "mission");
    await loadSelected(true);
    requestAnimationFrame(animate);
    setInterval(() => {
      if (!document.hidden)
        refreshJobs().catch(() => {
          $("connection").textContent = "Engine disconnected";
        });
    }, 2500);
  } catch (error) {
    $("connection").textContent = "Engine unavailable";
    toast(error.message, true);
  }
}
init();
