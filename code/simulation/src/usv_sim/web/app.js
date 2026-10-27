"use strict";
// USV·PAC research lab. The browser only draws: every value comes from the
// local Python engine (/api/*), which simulates, verifies and stores runs.
const $ = (id) => document.getElementById(id);
const t = (key, vars) => I18N.t(key, vars);
const CORE = ["S1", "S2", "S3", "S4-T", "S4-P"];
const EXTRA = ["S4-E", "S4-K", "S4-G", "S4-L", "S4-M", "S4-O"];
const ALL = [...CORE, ...EXTRA];
const VIEWS = ["map", "link", "log", "core", "extension", "runs", "guide", "presentation"];
const LEGACY_VIEWS = { mission: "map", evidence: "core", activity: "runs" };
const LENGTHS = [2, 5, 10];

const root = getComputedStyle(document.documentElement);
const token = (name) => root.getPropertyValue(`--${name}`).trim();
const COLORS = Object.fromEntries(ALL.map((p) => [p, token(`policy-${p}`)]));
const BOAT = [token("usv-1"), token("usv-2")];
const BOAT_SOFT = [token("usv-1-soft"), token("usv-2-soft")];
const INK = token("foreground"), MUTED = token("muted-foreground"), LINE = token("border");
const DANGER = token("danger"), WARNING = token("warning"), ACCENT = token("accent");
const LINK = { connected: token("link-connected"), fade: token("link-fade"), budget: token("link-budget"), range: token("link-range") };
const LINK_DASH = { connected: [], fade: [6, 4], budget: [2, 3, 8, 3], range: [1.5, 3.5] };
const UI_FONT = "Inter, 'Segoe UI', system-ui, sans-serif";

const state = {
  catalog: null, ext: null, traces: {}, active: "S4-T", dataset: "core", t: 0, playing: false,
  slowdown: true, view: "map", slide: 0, jobs: [], generation: 0, currentJob: null, selectedJob: null,
  motionPaused: false, tour: null,
};
const store = {
  get(key) { try { return localStorage.getItem(`usvpac.${key}`); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(`usvpac.${key}`, value); } catch { /* private mode */ } },
};
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const locale = () => (I18N.lang === "it" ? "it-IT" : "en-GB");
const fmt = (n, digits = 0) => (n == null || Number.isNaN(+n) ? "—" : Number(n).toLocaleString(locale(), { maximumFractionDigits: digits, minimumFractionDigits: digits }));
const clock = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const policyName = (p) => t(`policy.${p}`);
const activeTrace = () => state.traces[state.active];
const datasetPolicies = (dataset = state.dataset) => (dataset === "extension" ? ALL : CORE);
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const condLabel = (slow, length) => `${slow ? t("cond.slowdown") : t("cond.balanced")} · L=${length}`;

let toastTimer;
function toast(message, error = false) {
  $("toast").textContent = message;
  $("toast").classList.toggle("error", error);
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("toast").hidden = true), error ? 12000 : 5500);
}
async function api(url, body) {
  const options = body ? { method: "POST", headers: { "Content-Type": "application/json", "X-Lab-Token": state.catalog.token }, body: JSON.stringify(body) } : {};
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) throw Error(result.error || `Request failed (${response.status})`);
  return result;
}

/* ---------- navigation ---------- */
function view(name, { scroll = true } = {}) {
  name = LEGACY_VIEWS[name] || name;
  if (!VIEWS.includes(name)) name = "map";
  state.view = name;
  document.querySelectorAll(".view").forEach((e) => e.classList.toggle("active", e.id === `view-${name}`));
  document.querySelectorAll(".nav-item").forEach((e) => {
    const on = e.dataset.view === name;
    e.classList.toggle("active", on);
    if (on) e.setAttribute("aria-current", "page"); else e.removeAttribute("aria-current");
  });
  history.replaceState(null, "", `#${name}`);
  document.title = `${t(`nav.${name}`)} · USV·PAC`;
  closeMenu();
  if (name === "presentation") renderSlide();
  if (name === "extension") loadExtension();
  if (name === "core" && state.catalog) renderEvidence();
  if (name === "guide") renderGuide();
  if (["map", "link", "log"].includes(name)) { renderMissionCharts(); drawAll(); }
  syncFields();
  if (scroll) window.scrollTo({ top: 0, behavior: "instant" });
}
function closeMenu() {
  document.body.classList.remove("menu-open");
  $("menu-button").setAttribute("aria-expanded", "false");
  $("scrim").hidden = true;
}

/* ---------- setup & loading ---------- */
function request() {
  return { seed: +$("seed").value, length: +$("length").value, slowdown: state.slowdown, exponent: +$("exponent").value, timeout: +$("timeout").value, policy: "all" };
}
const nameFor = (policy, req = request()) => `${req.seed}-${Number(req.slowdown)}-${req.length}-${policy}`;
const urlForTrace = (policy, dataset = state.dataset, req = request()) => `/api/trace?dataset=${encodeURIComponent(dataset)}&run=${encodeURIComponent(nameFor(policy, req))}`;
function traceMatches(data, req, dataset) {
  return data && data.dataset === dataset && data.result.seed === req.seed && data.result.slowdown === req.slowdown &&
    data.result.fade_length === req.length && data.result.path_exponent === req.exponent && data.config.timeout_s === req.timeout;
}
function fillPolicySelect() {
  const current = state.active;
  const option = (p) => `<option value="${p}">${p} · ${esc(policyName(p))}</option>`;
  $("policy").innerHTML = state.dataset === "extension"
    ? `<optgroup label="${esc(t("setup.coreGroup"))}">${CORE.map(option).join("")}</optgroup><optgroup label="${esc(t("setup.extGroup"))}">${EXTRA.map(option).join("")}</optgroup>`
    : CORE.map(option).join("");
  $("policy").value = datasetPolicies().includes(current) ? current : "S4-T";
  $("run-all").querySelector("span").textContent = t("setup.runAll");
  $("run-all").disabled = $("run-one").disabled = state.dataset === "extension";
  $("run-all").title = state.dataset === "extension" ? t("setup.extNoRun") : "";
}
function setSetup(req) {
  $("seed").value = req.seed;
  $("length").value = req.length;
  $("exponent").value = req.exponent ?? 2;
  $("timeout").value = req.timeout ?? 7200;
  state.slowdown = req.slowdown;
  $("progress-description").textContent = state.slowdown ? t("setup.slowHint") : t("setup.balancedHint");
  document.querySelectorAll("[data-slow]").forEach((e) => e.setAttribute("aria-pressed", String((e.dataset.slow === "true") === state.slowdown)));
}
async function loadSelected(reset = false) {
  const generation = ++state.generation;
  const policy = $("policy").value;
  try {
    const req = request(), dataset = state.dataset;
    const trace = traceMatches(state.traces[policy], req, dataset) ? state.traces[policy] : await api(urlForTrace(policy));
    if (generation !== state.generation) return;
    if (Object.values(state.traces).some((d) => !traceMatches(d, req, dataset))) state.traces = {};
    state.traces[policy] = prepare(trace);
    state.active = policy;
    if (reset) state.t = 0;
    afterLoad();
  } catch (error) {
    if (generation === state.generation) toast(t("toast.loadFailed", { message: error.message }), true);
  }
}
function prepare(trace) {
  // Derived indexes over recorded events only: second-observation time per cell and session lookup.
  if (trace.secondSeen) return trace;
  const counts = new Array(trace.first_seen.length).fill(0);
  trace.secondSeen = new Array(trace.first_seen.length).fill(null);
  for (const [at, , cell] of trace.observations) if (++counts[cell] === 2) trace.secondSeen[cell] = at;
  trace.sessionAt = new Map(trace.sessions.map((s) => [s.t, s]));
  return trace;
}
function refreshHero() {
  // Hero facts read the loaded trace and extension; re-render them once those arrive.
  if (state.view !== "guide") return;
  $("guide-numbers").innerHTML = heroNumbers(studyFacts());
  rollNumbers($("guide-numbers"));
}
function afterLoad() {
  refreshHero();
  activateTrace();
  renderComparison();
  renderMissionCharts();
  renderEvents();
  drawAll();
}
function activateTrace() {
  const trace = activeTrace();
  if (!trace) return;
  const r = trace.result;
  $("active-policy").innerHTML = `<i class="policy-swatch" style="--c:${COLORS[trace.policy]}"></i>${esc(trace.policy)} <span>${esc(policyName(trace.policy))}</span>`;
  const maximum = Math.max(...Object.values(state.traces).map((d) => d.result.stop_s));
  $("timeline").max = maximum;
  $("duration-display").textContent = clock(maximum);
  state.t = Math.min(state.t, maximum);
  $("timeline").value = state.t;
  const source = { core: t("source.core"), extension: t("source.extension") }[trace.dataset] || t("source.bundle");
  $("source-label").textContent = t("source.label", { source, seed: r.seed, condition: condLabel(r.slowdown, r.fade_length), n: r.path_exponent });
  $("raw-download").href = `/api/raw?dataset=${encodeURIComponent(trace.dataset)}&run=${encodeURIComponent(trace.name)}`;
}

/* ---------- replay geometry ---------- */
function frameAt(trace, at) {
  const frames = trace.frames;
  let low = 0, high = frames.length - 1;
  while (low < high) { const mid = Math.ceil((low + high) / 2); if (frames[mid].t <= at) low = mid; else high = mid - 1; }
  return frames[low];
}
function sessionBefore(trace, at) {
  const list = trace.sessions;
  let low = 0, high = list.length - 1, found = null;
  while (low <= high) { const mid = (low + high) >> 1; if (list[mid].t <= at) { found = list[mid]; low = mid + 1; } else high = mid - 1; }
  return found;
}
function trackAt(trace, at) {
  const time = Math.min(Math.max(0, at), trace.result.stop_s);
  const a = trace.tracks[Math.floor(time)] || trace.tracks.at(-1);
  const b = trace.tracks[Math.ceil(time)] || a;
  const fraction = time - Math.floor(time);
  return [time, ...a.slice(1, 5).map((v, i) => v + fraction * (b[i + 1] - v)), a[5], a[6]];
}
function canvasContext(canvas) {
  const box = canvas.getBoundingClientRect();
  if (!box.width || !box.height) return null;
  const scale = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.round(box.width * scale), height = Math.round(box.height * scale);
  if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  return { ctx, width: box.width, height: box.height };
}
function localKnowledge(trace, frame, at, boat) {
  const known = new Set(frame.known?.[boat] || []);
  for (const [time, id, cell] of trace.observations) if (time > frame.t && time <= at && boat === id) known.add(cell);
  return known;
}
function taskStateAt(trace, at) {
  const states = trace.motion_states;
  if (states?.length) {
    let low = 0, high = states.length - 1;
    while (low < high) { const mid = Math.ceil((low + high) / 2); if (states[mid].t <= at) low = mid; else high = mid - 1; }
    return { ...states[low], exact: true };
  }
  return { ...frameAt(trace, at), exact: false };
}
function linkState(session) {
  if (!session) return null;
  if (session.budget_failure) return "budget";
  if (session.radio) return "connected";
  return session.distance_failure ? "range" : "fade";
}

/* ---------- map ---------- */
function drawMap(canvas, trace, time, { mini = false, paper = false } = {}) {
  const surface = canvasContext(canvas);
  if (!surface || !trace) return;
  const { ctx, width, height } = surface;
  const c = trace.config;
  const at = Math.min(time, trace.result.stop_s);
  const frame = frameAt(trace, at), track = trackAt(trace, at), tasks = taskStateAt(trace, at);
  const padX = mini ? 6 : width < 420 ? 34 : 50, padY = mini ? 6 : 34;
  const cell = Math.min((width - 2 * padX) / c.width, (height - 2 * padY) / c.height);
  const ox = (width - c.width * cell) / 2, oy = (height - c.height * cell) / 2;
  const project = (x, y) => [ox + (x / c.cell_m) * cell, oy + (c.height - y / c.cell_m) * cell];
  const cellXY = (id) => [ox + (id % c.width) * cell, oy + (c.height - 1 - Math.floor(id / c.width)) * cell];
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  const layer = mini ? "global" : $("knowledge").value;
  const known = layer === "global" ? null : localKnowledge(trace, frame, at, +layer);
  const showRepeats = !mini && $("show-redundant").checked && layer === "global";
  for (let id = 0; id < c.width * c.height; id++) {
    const seen = known ? known.has(id) : trace.first_seen[id] != null && trace.first_seen[id] <= at;
    const [x, y] = cellXY(id);
    ctx.fillStyle = seen ? token("cell-observed") : token("cell-unobserved");
    ctx.fillRect(x, y, cell, cell);
    ctx.strokeStyle = token("cell-line");
    ctx.lineWidth = 0.6;
    ctx.strokeRect(x + 0.3, y + 0.3, cell - 0.6, cell - 0.6);
    if (seen && !mini) {
      ctx.fillStyle = token("cell-observed-dot");
      ctx.beginPath(); ctx.arc(x + cell / 2, y + cell / 2, Math.max(0.9, cell * 0.05), 0, Math.PI * 2); ctx.fill();
    }
    if (showRepeats && trace.secondSeen[id] != null && trace.secondSeen[id] <= at) {
      ctx.save(); ctx.beginPath(); ctx.rect(x, y, cell, cell); ctx.clip();
      ctx.strokeStyle = token("cell-redundant"); ctx.lineWidth = 1;
      for (let k = -cell; k < cell; k += 5) { ctx.beginPath(); ctx.moveTo(x + k, y + cell); ctx.lineTo(x + k + cell, y); ctx.stroke(); }
      ctx.restore();
    }
  }
  if ((mini || $("show-queues").checked) && tasks.queues)
    tasks.queues.forEach((queue, boat) => {
      ctx.setLineDash(tasks.exact ? [] : [3, 2]);
      for (const [index, id] of queue.entries()) {
        const [x, y] = cellXY(id);
        ctx.fillStyle = BOAT_SOFT[boat];
        ctx.fillRect(x + cell * 0.14, y + cell * 0.14, cell * 0.72, cell * 0.72);
        ctx.strokeStyle = BOAT[boat]; ctx.lineWidth = mini ? 0.8 : 1.4;
        ctx.strokeRect(x + cell * 0.14, y + cell * 0.14, cell * 0.72, cell * 0.72);
        if (!mini && cell >= 17) {
          ctx.fillStyle = BOAT[boat]; ctx.font = `600 ${Math.min(10, cell * 0.42)}px ${UI_FONT}`; ctx.textAlign = "center";
          ctx.fillText(index + 1, x + cell / 2, y + cell * 0.66); ctx.textAlign = "left";
        }
      }
      ctx.setLineDash([]);
      if (tasks.targets?.[boat] != null) {
        const [x, y] = cellXY(tasks.targets[boat]);
        ctx.strokeStyle = BOAT[boat]; ctx.lineWidth = mini ? 1 : 1.8;
        ctx.strokeRect(x + 1.5, y + 1.5, cell - 3, cell - 3);
        ctx.beginPath();
        ctx.moveTo(x + cell * 0.3, y + cell * 0.3); ctx.lineTo(x + cell * 0.7, y + cell * 0.7);
        ctx.moveTo(x + cell * 0.7, y + cell * 0.3); ctx.lineTo(x + cell * 0.3, y + cell * 0.7);
        ctx.stroke();
      }
    });
  if (mini || $("show-trails").checked)
    for (let boat = 0; boat < 2; boat++) {
      ctx.beginPath(); ctx.strokeStyle = BOAT[boat]; ctx.globalAlpha = mini ? 0.45 : 0.7; ctx.lineWidth = mini ? 1 : 1.5;
      let previous = null;
      // Keep every recorded turn; decimating the polyline would cut corners.
      for (let i = 0; i <= Math.floor(at) && i < trace.tracks.length; i++) {
        const point = project(trace.tracks[i][1 + boat * 2], trace.tracks[i][2 + boat * 2]);
        if (!previous) ctx.moveTo(...point); else if (point[0] !== previous[0] || point[1] !== previous[1]) ctx.lineTo(...point);
        previous = point;
      }
      ctx.lineTo(...project(track[1 + boat * 2], track[2 + boat * 2]));
      ctx.stroke(); ctx.globalAlpha = 1;
    }
  const points = [project(track[1], track[2]), project(track[3], track[4])];
  const session = frame.terminal ? null : trace.sessionAt.get(frame.t);
  const status = linkState(session);
  if (status) {
    // The channel is evaluated only at exchanges: anchor the link to the sampled positions.
    const radioPoints = frame.xy?.map((xy) => project(...xy)) || points;
    ctx.beginPath(); ctx.strokeStyle = LINK[status]; ctx.lineWidth = mini ? 0.9 : 1.6; ctx.setLineDash(LINK_DASH[status]);
    ctx.moveTo(...radioPoints[0]); ctx.lineTo(...radioPoints[1]); ctx.stroke(); ctx.setLineDash([]);
    if (!mini) radioPoints.forEach(([x, y]) => { ctx.lineWidth = 1; ctx.strokeRect(x - 3, y - 3, 6, 6); });
  }
  points.forEach(([x, y], boat) => {
    ctx.beginPath(); ctx.fillStyle = BOAT[boat]; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = mini ? 1 : 2;
    ctx.arc(x, y, mini ? 4.2 : 9, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    if (!mini) { ctx.fillStyle = "#ffffff"; ctx.font = `700 10px ${UI_FONT}`; ctx.textAlign = "center"; ctx.fillText(boat + 1, x, y + 3.5); ctx.textAlign = "left"; }
  });
  if (!mini) {
    ctx.font = `11px ${UI_FONT}`; ctx.fillStyle = paper ? "#000" : MUTED; ctx.textAlign = "center";
    for (let x = 0; x <= c.width; x += 5) ctx.fillText(`${x * c.cell_m}`, ox + x * cell, oy + c.height * cell + 16);
    ctx.textAlign = "right";
    for (let y = 0; y <= c.height; y += 4) ctx.fillText(`${y * c.cell_m}`, ox - 8, oy + (c.height - y) * cell + 3);
    ctx.font = `600 10px ${UI_FONT}`; ctx.textAlign = "left"; ctx.fillText("y [m]", 6, oy - 12);
    ctx.textAlign = "right"; ctx.fillText("x [m]", ox + c.width * cell, oy + c.height * cell + 29); ctx.textAlign = "left";
  }
}

/* ---------- per-frame updates ---------- */
function drawAll() {
  const trace = activeTrace();
  if (!trace) return;
  const at = Math.min(state.t, trace.result.stop_s), frame = frameAt(trace, at);
  if (state.view === "map" || state.view === "presentation") {
    drawMap($("map"), trace, state.t);
    document.querySelectorAll(".compare-card").forEach((card) => {
      const data = state.traces[card.dataset.policy];
      drawMap(card.querySelector("canvas"), data, state.t, { mini: true });
      const seen = data.first_seen.filter((v) => v != null && v <= Math.min(state.t, data.result.stop_s)).length;
      card.querySelector(".compare-coverage").textContent = `${fmt((100 * seen) / data.first_seen.length, 1)}%`;
      card.querySelector(".compare-clock").textContent = state.t >= data.result.stop_s ? t("cmp.final", { time: clock(data.result.stop_s) }) : t("cmp.at", { time: clock(state.t) });
    });
  }
  const observed = trace.first_seen.filter((v) => v != null && v <= at).length;
  $("map-clock").textContent = `${clock(at)}${at >= trace.result.stop_s ? ` · ${t("map.end")}` : ""}`;
  $("time-display").textContent = clock(state.t);
  $("timeline").value = state.t;
  updateHeader(trace, at);
  renderKpis(trace, at, observed);
  renderStateContext(trace, at, frame, observed);
  if (state.view === "link" || state.view === "presentation") { renderForecast(trace, at); renderBudgetNow(trace, at); }
  document.querySelectorAll(".time-cursor").forEach((line) => {
    const x = +line.dataset.left + ((+line.dataset.right - +line.dataset.left) * state.t) / +line.dataset.duration;
    const clamped = Math.min(+line.dataset.right, x);
    line.setAttribute("x1", clamped); line.setAttribute("x2", clamped);
  });
  const slideMap = $("slide-map");
  if (slideMap) drawMap(slideMap, trace, state.t);
}
function updateHeader(trace, at) {
  const r = trace.result, timeout = trace.config.timeout_s;
  $("hdr-dataset").textContent = { core: t("hdr.core"), extension: t("hdr.extension") }[trace.dataset] || t("hdr.bundle");
  const chip = $("hdr-policy");
  chip.style.setProperty("--c", COLORS[trace.policy]);
  chip.querySelector("b").textContent = `${trace.policy} · ${policyName(trace.policy)}`;
  $("hdr-seed").textContent = r.seed;
  $("hdr-condition").textContent = condLabel(r.slowdown, r.fade_length);
  $("hdr-elapsed").textContent = clock(at);
  $("hdr-timeout").textContent = clock(timeout);
  $("hdr-progress").setAttribute("aria-valuenow", Math.round(at));
  $("hdr-progress").setAttribute("aria-valuemax", timeout);
  $("hdr-progress-fill").style.width = `${(100 * at) / timeout}%`;
  $("hdr-progress-end").style.left = `${(100 * r.stop_s) / timeout}%`;
  const ended = at >= r.stop_s, out = $("hdr-outcome");
  out.hidden = !ended;
  out.className = `chip outcome-chip ${r.complete ? "ok" : "censored"}`;
  out.textContent = r.complete ? t("outcome.complete") : t("outcome.censored", { s: fmt(timeout) });
}
function sumWork(result, key) {
  return Object.values(result.work || {}).reduce((total, w) => total + (w[key] || 0), 0);
}
function kpi(label, value, unit, note, cls = "") {
  return `<article class="kpi ${cls}"><span class="kpi-label">${esc(label)}</span><strong class="num">${value}${unit ? `<em>${esc(unit)}</em>` : ""}</strong><small>${note}</small></article>`;
}
function renderKpis(trace, at, observed) {
  const r = trace.result, c = trace.config, done = at >= r.stop_s;
  const sessions = trace.sessions.filter((s) => s.t <= at);
  const attempted = sessions.reduce((a, s) => a + (s.attempted || 0), 0), delivered = sessions.reduce((a, s) => a + (s.delivered || 0), 0);
  const bytes = sessions.reduce((a, s) => a + (s.bytes_attempted || 0), 0);
  const repeats = trace.secondSeen ? trace.observations.filter(([time]) => time <= at).length - observed : null;
  const last = sessions.at(-1);
  const condition = `${t("kpi.seed")} ${r.seed} · ${condLabel(r.slowdown, r.fade_length)}`;
  const completion = r.complete
    ? kpi(t("kpi.completion"), roll("kpi-completion", r.completion_s), "s", done ? condition : t("kpi.finalOutcome"), "ok")
    : kpi(t("kpi.completion"), t("kpi.censored"), "", t("kpi.censoredNote", { s: fmt(c.timeout_s) }), "censored");
  $("kpis").innerHTML = [
    kpi(t("kpi.coverage"), roll("kpi-coverage", (100 * observed) / trace.first_seen.length, 1), "%", t("kpi.cells", { n: observed, total: trace.first_seen.length }) + `<span class="meter"><i style="width:${(100 * observed) / trace.first_seen.length}%"></i></span>`),
    completion,
    kpi(t("kpi.redundant"), roll("kpi-redundant", repeats), t("kpi.obs"), t("kpi.redundantNote", { final: r.redundant })),
    kpi(t("kpi.messages"), roll("kpi-messages", attempted), t("kpi.datagrams"), t("kpi.delivered", { n: fmt(delivered) })),
    kpi(t("kpi.bytes"), roll("kpi-bytes", bytes / 1000, 1), "kB", t("kpi.bytesNote")),
    kpi(t("kpi.missing"), last?.missing ? roll("kpi-missing", 100 * Math.max(...last.missing), 1) : "—", "%", t("kpi.missingNote", { mean: r.missing_mean?.[0] == null ? "—" : fmt(50 * (r.missing_mean[0] + r.missing_mean[1]), 1) })),
    kpi(t("kpi.cpu"), roll("kpi-cpu", sumWork(r, "cpu_ns") / 1e6, 2), "ms", t("kpi.cpuNote")),
    kpi(t("kpi.ops"), roll("kpi-ops", sumWork(r, "arithmetic") / 1000, 1), t("kpi.thousand"), t("kpi.opsNote")),
    kpi(t("kpi.ram"), t("kpi.notRecorded"), "", t("kpi.ramNote"), "na"),
  ].join("");
  rollNumbers($("kpis"));
}
function renderStateContext(trace, at, frame, observed) {
  const c = trace.config, tasks = taskStateAt(trace, at), track = trackAt(trace, at), layer = $("knowledge").value;
  const session = frame.terminal ? null : trace.sessionAt.get(frame.t), status = linkState(session);
  $("map-layer").innerHTML = `${esc(layer === "global" ? t("map.layerObserver") : t("map.layerBoat", { n: +layer + 1 }))}${status ? ` · <span class="link-pill ${status}">${esc(t(`link.${status}`))}</span>` : ""}`;
  const onset = trace.scenario.onset_s, end = onset + c.slowdown_s, slow = trace.scenario.slowdown;
  const phase = !slow ? t("phase.balanced") : at < onset ? t("phase.scheduled", { a: fmt(onset), b: fmt(end) })
    : at < end ? t("phase.active", { v: fmt(c.speed_mps * c.slowdown_factor, 1), b: fmt(end) }) : t("phase.ended", { b: fmt(end) });
  $("slowdown-note").textContent = phase + (slow && trace.result.stop_s < onset ? ` · ${t("phase.before")}` : "");
  $("slowdown-note").classList.toggle("active", slow && at >= onset && at < end);
  $("jump-slowdown").hidden = !slow || onset > trace.result.stop_s;
  const key = `${trace.raw_sha256}:${Math.floor(at)}:${layer}:${I18N.lang}`;
  if ($("boat-states").dataset.key === key) return;
  $("boat-states").dataset.key = key;
  $("boat-states").innerHTML = [0, 1].map((boat) => {
    const known = localKnowledge(trace, frame, at, boat), gap = observed - known.size;
    const queue = tasks.queues?.[boat], target = tasks.targets?.[boat], mode = tasks.modes?.[boat]?.replaceAll("_", " ");
    const rows = [
      [t("boat.known"), `${known.size} / ${c.width * c.height}`],
      [t("boat.gap"), `${gap} <small>(${fmt((100 * gap) / (c.width * c.height), 1)}%)</small>`],
      [tasks.exact ? t("boat.target") : t("boat.sampledTarget"), target == null ? (queue == null ? t("boat.unavailable") : t("boat.none")) : t("boat.cell", { id: target })],
      [t("boat.queue"), queue == null ? t("boat.unavailable") : queue.length],
      ...(mode ? [[t("boat.activity"), esc(mode)], [t("boat.speed"), `${fmt(tasks.speed_mps[boat], 1)} m/s`]] : []),
    ];
    return `<article class="boat-card" style="--c:${BOAT[boat]}"><div class="boat-head"><span class="boat-badge">${boat + 1}</span><b>USV ${boat + 1}</b><span class="mono num">(${fmt(track[1 + boat * 2], 1)}, ${fmt(track[2 + boat * 2], 1)}) m</span></div><dl>${rows.map(([k, v]) => `<div><dt>${k}</dt><dd class="num">${v}</dd></div>`).join("")}</dl></article>`;
  }).join("");
}

/* ---------- comparison ---------- */
function renderComparison() {
  const entries = datasetPolicies().filter((p) => state.traces[p]);
  if (!entries.length) return;
  $("comparison").innerHTML = entries.map((p) => {
    const r = state.traces[p].result;
    return `<button class="compare-card ${p === state.active ? "selected" : ""}" data-policy="${p}" style="--c:${COLORS[p]}" aria-pressed="${p === state.active}" aria-label="${esc(t("cmp.inspect", { p, name: policyName(p) }))}">
      <span class="compare-top"><b><i class="policy-swatch"></i>${p}</b><span class="badge ${r.complete ? "ok" : "censored"}">${r.complete ? t("outcome.complete") : t("outcome.censoredShort")}</span></span>
      <span class="compare-name">${esc(policyName(p))}</span><canvas aria-hidden="true"></canvas>
      <span class="compare-bottom"><strong class="compare-coverage num">0%</strong><span class="compare-clock num"></span></span>
      <span class="compare-final num">${esc(t("cmp.finalLine", { cov: fmt(100 * r.coverage, 1), s: fmt(r.stop_s), end: r.complete ? t("cmp.toFinish") : t("cmp.cutoff") }))}</span></button>`;
  }).join("");
}
async function loadComparison(policies) {
  if (!Array.isArray(policies)) policies = datasetPolicies();
  const generation = ++state.generation, dataset = state.dataset, req = request();
  $("load-comparison").disabled = true;
  const settled = await Promise.allSettled(policies.map((p) => api(urlForTrace(p, dataset, req))));
  $("load-comparison").disabled = false;
  if (generation !== state.generation) return;
  let missing = 0;
  if (settled.some((r) => r.status === "fulfilled") && Object.values(state.traces).some((d) => !traceMatches(d, req, dataset))) state.traces = {};
  settled.forEach((r, i) => { if (r.status === "fulfilled") state.traces[policies[i]] = prepare(r.value); else missing++; });
  if (missing) toast(t("toast.missingTraces", { n: missing }), true);
  if (!activeTrace()) state.active = datasetPolicies().find((p) => state.traces[p]) || state.active;
  $("policy").value = state.active;
  afterLoad();
}
function setTime(at) { state.t = Math.min(Math.max(0, at), +$("timeline").max); drawAll(); }
function setPlaying(on) {
  state.playing = on;
  $("play").classList.toggle("playing", on);
  $("play").setAttribute("aria-label", on ? t("play.pause") : t("play.play"));
  $("play").innerHTML = `<svg><use href="#i-${on ? "pause" : "play"}"/></svg>`;
  const slide = $("slide-play");
  if (slide) slide.textContent = on ? t("pres.pauseMission") : t("pres.playMission");
}
let lastFrame = 0, renderAt = 0;
function animate(timestamp) {
  const elapsed = Math.min((timestamp - lastFrame) / 1000, 0.1);
  lastFrame = timestamp;
  if (state.playing && !document.hidden) {
    state.t = Math.min(+$("timeline").max, state.t + elapsed * +$("speed").value);
    if (timestamp - renderAt > 40) { drawAll(); renderAt = timestamp; }
    if (state.t >= +$("timeline").max) setPlaying(false);
  }
  requestAnimationFrame(animate);
}

/* ---------- SVG charts (recorded numbers only) ---------- */
const W = 520;
// Full-width charts follow their container (520–1000 units) so text keeps a readable size.
const widthOf = (id) => ($(id).classList.contains("wide") ? Math.round(Math.min(1000, Math.max(W, $(id).clientWidth || W))) : W);
function text(x, y, value, cls = "lbl", anchor = "start", extra = "") {
  return `<text x="${x}" y="${y}" class="${cls}" text-anchor="${anchor}" ${extra}>${esc(value)}</text>`;
}
function chartShell(title, content, height = 250, width = W) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(title)}"><title>${esc(title)}</title><defs><pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="#fff"/><line x1="0" y1="0" x2="0" y2="5" stroke="currentColor" stroke-width="2"/></pattern></defs><style>text{font-family:${UI_FONT};font-variant-numeric:tabular-nums}.lbl{font-size:11px;fill:${MUTED}}.val{font-size:11px;fill:${INK};font-weight:600}.leg{font-size:10.5px;fill:${INK}}.axis{font-size:11px;fill:${INK};font-weight:600}.grid{stroke:${LINE};stroke-width:1}.time-cursor{stroke:${ACCENT};stroke-width:1.2;stroke-dasharray:3 3}</style>${content}</svg>`;
}
function yAxis(left, right, y, ticks, digits = 0) {
  return ticks.map((v) => `<line x1="${left}" x2="${right}" y1="${y(v)}" y2="${y(v)}" class="grid"/>${text(left - 8, y(v) + 4, fmt(v, digits), "lbl", "end")}`).join("");
}
function niceTicks(max, count = 4) {
  const raw = max / count, step = 10 ** Math.floor(Math.log10(raw)), nice = [1, 2, 2.5, 5, 10].find((m) => m * step >= raw) * step;
  // The last tick always reaches the maximum, so no mark is drawn outside the axis.
  const ticks = [0];
  while (ticks.at(-1) < max - 1e-9) ticks.push(+(ticks.at(-1) + nice).toFixed(10));
  return ticks;
}
function cursorLine(left, right, top, bottom, duration) {
  return `<line class="time-cursor" data-left="${left}" data-right="${right}" data-duration="${duration}" x1="${left}" x2="${left}" y1="${top}" y2="${bottom}"/>`;
}
function attachSeek(id, left, right, duration, width = W) {
  $(id).querySelector("svg").addEventListener("click", (event) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setPlaying(false);
    setTime(((((event.clientX - rect.left) / rect.width) * width - left) / (right - left)) * duration);
  });
}
function renderMissionCharts() {
  const entries = datasetPolicies().filter((p) => state.traces[p]);
  const trace = activeTrace();
  if (!entries.length || !trace) return;
  const duration = Math.max(...entries.map((p) => state.traces[p].result.stop_s));
  // Coverage over time.
  const width = widthOf("coverage-chart"), left = 50, right = width - 20, top = 18, bottom = 188;
  const x = (at) => left + ((right - left) * at) / duration, y = (v) => bottom - ((bottom - top) * v) / 100;
  let content = yAxis(left, right, y, [0, 25, 50, 75, 100]) + text(left, 10, t("chart.coverage"), "axis");
  for (let i = 0; i <= 4; i++) content += text(x((duration * i) / 4), 206, fmt(((duration / 60) * i) / 4), "lbl", "middle");
  content += text(right, 222, t("chart.timeMin"), "lbl", "end");
  entries.forEach((p, i) => {
    const d = state.traces[p], first = d.first_seen.filter((v) => v != null).sort((a, b) => a - b);
    const pts = [[0, 0]];
    first.forEach((at, j) => pts.push([at, (j / d.first_seen.length) * 100], [at, ((j + 1) / d.first_seen.length) * 100]));
    pts.push([d.result.stop_s, d.result.coverage * 100]);
    content += `<path d="${pts.map(([a, v], j) => `${j ? "L" : "M"}${x(a).toFixed(1)},${y(v).toFixed(1)}`).join("")}" fill="none" stroke="${COLORS[p]}" stroke-width="${p === state.active ? 2.2 : 1.4}"><title>${esc(p)}</title></path>`;
    if (!d.result.complete) content += `<circle cx="${x(d.result.stop_s)}" cy="${y(d.result.coverage * 100)}" r="3.5" fill="#fff" stroke="${COLORS[p]}" stroke-width="1.6"><title>${esc(t("chart.censoredAt", { p }))}</title></circle>`;
    const lx = left + i * 80, ly = 238;
    content += `<line x1="${lx}" x2="${lx + 12}" y1="${ly - 4}" y2="${ly - 4}" stroke="${COLORS[p]}" stroke-width="2"/>${text(lx + 16, ly, p, "leg")}`;
  });
  content += cursorLine(left, right, top, bottom, duration);
  $("coverage-chart").innerHTML = chartShell(t("chart.coverageTitle"), content, 250, width);
  attachSeek("coverage-chart", left, right, duration, width);
  signalChart(trace, duration);
  budgetChart(trace, duration);
  renderLinkStates(trace);
  renderWarningKpis();
}
function signalChart(trace, duration) {
  const width = widthOf("signal-chart"), left = 50, right = width - 20, top = 18, bottom = 196;
  const sessions = trace.sessions, values = sessions.map((s) => s.r);
  const min = Math.floor(Math.min(trace.config.threshold_dbm - 10, ...values) / 10) * 10, max = Math.ceil(Math.max(-60, ...values) / 10) * 10;
  const x = (at) => left + ((right - left) * at) / duration, y = (v) => bottom - ((bottom - top) * (v - min)) / (max - min);
  let content = "";
  // Shade contiguous fade episodes (pre-generated scenario state, recorded per exchange).
  const step = trace.config.exchange_s;
  let start = null;
  sessions.forEach((s, i) => {
    if (s.fade && start == null) start = s.t;
    const next = sessions[i + 1];
    if (start != null && (!next || !next.fade)) {
      content += `<rect x="${x(start - step / 2)}" y="${top}" width="${Math.max(1, x(s.t + step / 2) - x(start - step / 2))}" height="${bottom - top}" fill="${token("muted")}"/>`;
      start = null;
    }
  });
  const ticks = []; for (let v = min; v <= max; v += 10) ticks.push(v);
  content += yAxis(left, right, y, ticks) + text(left, 10, t("chart.signal"), "axis");
  for (let i = 0; i <= 4; i++) content += text(x((duration * i) / 4), 214, fmt(((duration / 60) * i) / 4), "lbl", "middle");
  content += text(right, 230, t("chart.timeMin"), "lbl", "end");
  content += `<line x1="${left}" x2="${right}" y1="${y(trace.config.threshold_dbm)}" y2="${y(trace.config.threshold_dbm)}" stroke="${DANGER}" stroke-width="1.2" stroke-dasharray="5 3"/>${text(right - 2, y(trace.config.threshold_dbm) - 5, `${trace.config.threshold_dbm} dBm`, "lbl", "end")}`;
  for (const s of sessions) {
    const status = linkState(s);
    content += status === "connected"
      ? `<circle cx="${x(s.t)}" cy="${y(s.r)}" r="1.9" fill="${COLORS[trace.policy]}"><title>${s.t} s · ${fmt(s.r, 1)} dBm · ${esc(t(`link.${status}`))}</title></circle>`
      : `<circle cx="${x(s.t)}" cy="${y(s.r)}" r="2" fill="#fff" stroke="${COLORS[trace.policy]}" stroke-width="1"><title>${s.t} s · ${fmt(s.r, 1)} dBm · ${esc(t(`link.${status}`))}</title></circle>`;
  }
  for (const s of sessions.filter((e) => e.warning))
    content += `<path d="M${x(s.t)},${top + 2} l4,7 h-8z" fill="${WARNING}"><title>${esc(t("chart.warningAt", { t: s.t }))}</title></path>`;
  content += cursorLine(left, right, top, bottom, duration);
  $("signal-chart").innerHTML = chartShell(t("chart.signalTitle", { p: trace.policy }), content, 240, width);
  attachSeek("signal-chart", left, right, duration, width);
}
function budgetChart(trace, duration) {
  const left = 50, right = 500, top = 18, bottom = 170, c = trace.config;
  const x = (at) => left + ((right - left) * at) / duration, y = (v) => bottom - ((bottom - top) * v) / 100;
  let content = yAxis(left, right, y, [0, 25, 50, 75, 100]) + text(left, 10, t("chart.budget"), "axis");
  for (let i = 0; i <= 4; i++) content += text(x((duration * i) / 4), 188, fmt(((duration / 60) * i) / 4), "lbl", "middle");
  content += text(right, 204, t("chart.timeMin"), "lbl", "end");
  for (const s of trace.sessions) {
    if (s.budget_failure) content += `<rect x="${x(s.t) - 1}" y="${top}" width="2" height="${bottom - top}" fill="${LINK.budget}" opacity=".5"/>`;
    const bytes = (100 * (s.bytes_attempted || 0)) / c.max_bytes, grams = (100 * (s.attempted || 0)) / c.max_datagrams;
    if (s.attempted) content += `<circle cx="${x(s.t)}" cy="${y(grams)}" r="1.8" fill="${INK}"><title>${s.t} s · ${s.attempted}/${c.max_datagrams} ${esc(t("chart.datagrams"))}</title></circle><rect x="${x(s.t) - 1.6}" y="${y(bytes) - 1.6}" width="3.2" height="3.2" fill="${ACCENT}"><title>${s.t} s · ${s.bytes_attempted}/${c.max_bytes} B</title></rect>`;
  }
  content += `<circle cx="${left + 4}" cy="226" r="2.5" fill="${INK}"/>${text(left + 12, 230, t("chart.datagramShare", { n: c.max_datagrams }), "leg")}<rect x="${left + 170}" y="223" width="6" height="6" fill="${ACCENT}"/>${text(left + 182, 230, t("chart.byteShare", { n: c.max_bytes }), "leg")}<rect x="${left + 330}" y="222" width="3" height="10" fill="${LINK.budget}" opacity=".5"/>${text(left + 338, 230, t("link.budget"), "leg")}`;
  content += cursorLine(left, right, top, bottom, duration);
  $("budget-chart").innerHTML = chartShell(t("chart.budgetTitle"), content, 240);
  attachSeek("budget-chart", left, right, duration);
}
function renderBudgetNow(trace, at) {
  const s = sessionBefore(trace, at), c = trace.config;
  if (!s) { $("budget-now").innerHTML = `<p class="muted">${esc(t("budget.none"))}</p>`; return; }
  const status = linkState(s);
  const offeredBytes = s.offered_bytes ?? s.bytes_attempted ?? 0, offeredGrams = s.offered_datagrams ?? s.attempted ?? 0;
  const meter = (label, value, max) => `<div class="budget-meter"><span>${esc(label)}</span><span class="meter ${value > max ? "over" : ""}"><i style="width:${Math.min(100, (100 * value) / max)}%"></i></span><b class="num">${fmt(value)} / ${fmt(max)}</b></div>`;
  $("budget-now").innerHTML = `<p><span class="link-pill ${status}">${esc(t(`link.${status}`))}</span> <span class="muted num">${esc(t("budget.at", { t: fmt(s.t) }))}</span></p>${meter(t("budget.datagrams"), offeredGrams, c.max_datagrams)}${meter(t("budget.bytes"), offeredBytes, c.max_bytes)}`;
}
function renderLinkStates(trace) {
  const counts = { connected: 0, fade: 0, budget: 0, range: 0 };
  trace.sessions.forEach((s) => counts[linkState(s)]++);
  const total = trace.sessions.length || 1;
  $("link-states").innerHTML = Object.entries(counts).map(([k, n]) => `<div class="link-state ${k}"><span class="link-pill ${k}">${esc(t(`link.${k}`))}</span><strong class="num">${roll(`link-${k}`, n)}</strong><small class="num">${fmt((100 * n) / total, 1)}% · ${esc(t(`link.${k}Note`))}</small></div>`).join("");
}
function renderWarningKpis() {
  if (!state.catalog) return;
  const rows = state.catalog.warnings || [];
  $("warning-kpis").innerHTML = rows.length ? rows.map((r) => {
    const lead = r.lead_s?.length ? r.lead_s.reduce((a, b) => a + b, 0) / r.lead_s.length : null;
    const p = r.method === "trend" ? "S4-T" : "S4-P";
    return `<article class="kpi" style="--c:${COLORS[p]}"><span class="kpi-label"><i class="policy-swatch"></i>${p} · ${esc(t(`method.${r.method}`))}</span><div class="kpi-row"><span>${esc(t("wq.precision"))}<b class="num">${roll(`wq-${p}-p`, r.precision, 3)}</b></span><span>${esc(t("wq.recall"))}<b class="num">${roll(`wq-${p}-r`, r.recall, 3)}</b></span><span>F1<b class="num">${roll(`wq-${p}-f`, r.f1, 3)}</b></span><span>${esc(t("wq.lead"))}<b class="num">${roll(`wq-${p}-l`, lead, 1)} s</b></span></div><small class="num">${esc(t("wq.counts", { tp: r.true_positives, fp: r.false_positives, fn: r.false_negatives }))}</small></article>`;
  }).join("") : `<p class="muted">${esc(t("kpi.notRecorded"))}</p>`;
}
function renderForecast(trace, at) {
  const session = trace.sessions.findLast((s) => s.t <= at && s.committed && s.projected?.length);
  if (session) {
    const count = trace.sessions.filter((s) => s.t <= session.t && s.committed).length;
    const method = trace.policy === "S4-T" && count >= trace.config.window ? t("fc.trend") : t("fc.persistence");
    $("forecast-description").textContent = t("fc.description", { method, issued: fmt(session.t), ago: fmt(at - session.t, 1), n: Math.min(count, trace.config.window), reserve: session.warning ? t("fc.long") : t("fc.short") });
  }
  const key = `${trace.raw_sha256}:${session?.k ?? "none"}:${I18N.lang}`;
  if ($("forecast-chart").dataset.key === key) return;
  $("forecast-chart").dataset.key = key;
  const statusEl = $("forecast-status");
  if (!session) {
    const usesForecast = trace.policy.startsWith("S4");
    $("forecast-chart").innerHTML = `<div class="empty small"><strong>${esc(usesForecast ? t("fc.noneYet") : t("fc.notUsed"))}</strong><p>${esc(usesForecast ? t("fc.noneYetHint") : t("fc.notUsedHint"))}</p></div>`;
    statusEl.textContent = t("fc.noForecast"); statusEl.className = "badge";
    $("forecast-description").textContent = t("fc.noFuture");
    return;
  }
  const c = trace.config, issued = session.t, delta = c.exchange_s;
  const history = trace.sessions.filter((s) => s.t <= issued && s.committed).slice(-c.window);
  const margin = trace.margins?.[trace.policy === "S4-P" ? "persistence" : "trend"] ?? 0;
  const lower = Math.floor(Math.min(c.threshold_dbm - 5, ...history.map((s) => s.r), ...session.projected) / 5) * 5;
  const upper = Math.ceil(Math.max(c.threshold_dbm + 10, ...history.map((s) => s.r), ...session.projected) / 5) * 5;
  const earliest = history[0]?.t ?? issued, latest = issued + (c.horizon + 1) * delta;
  const left = 52, right = 500, top = 22, bottom = 178;
  const x = (at2) => left + ((right - left) * (at2 - earliest)) / (latest - earliest), y = (r) => bottom - ((bottom - top) * (r - lower)) / (upper - lower);
  let content = `<rect x="${x(issued)}" y="${top}" width="${right - x(issued)}" height="${bottom - top}" fill="${token("accent-soft")}"/>`;
  const ticks = []; for (let v = lower; v <= upper; v += 5) ticks.push(v);
  content += yAxis(left, right, y, ticks) + text(left, 12, t("chart.signal"), "axis");
  content += `<line x1="${left}" x2="${right}" y1="${y(c.threshold_dbm)}" y2="${y(c.threshold_dbm)}" stroke="${DANGER}" stroke-dasharray="5 3"/>`;
  content += `<line x1="${x(issued)}" x2="${right}" y1="${y(c.threshold_dbm + margin)}" y2="${y(c.threshold_dbm + margin)}" stroke="${WARNING}" stroke-dasharray="2 3"/>`;
  for (const h of history) content += `<circle cx="${x(h.t)}" cy="${y(h.r)}" r="3.3" fill="${COLORS[trace.policy]}"><title>${h.t} s: ${fmt(h.r, 1)} dBm</title></circle>`;
  const forecasts = [[issued, session.r], ...session.projected.map((r, i) => [issued + delta * (i + 1), r])];
  content += `<path d="${forecasts.map(([a, r], i) => `${i ? "L" : "M"}${x(a)},${y(r)}`).join(" ")}" stroke="${COLORS[trace.policy]}" stroke-width="2" stroke-dasharray="5 4" fill="none"/>`;
  session.projected.forEach((r, i) => {
    const a = issued + delta * (i + 1);
    content += `<circle cx="${x(a)}" cy="${y(r)}" r="3.8" fill="#fff" stroke="${COLORS[trace.policy]}" stroke-width="1.7"><title>+${delta * (i + 1)} s: ${fmt(r, 2)} dBm</title></circle>${text(x(a), 196, `+${delta * (i + 1)} s`, "lbl", "middle")}`;
  });
  content += `<line x1="${x(issued)}" x2="${x(issued)}" y1="${top}" y2="${bottom}" stroke="${MUTED}"/>${text(x(issued), 212, t("fc.issued", { t: issued }), "lbl", "middle")}`;
  content += text(left, 236, t("fc.legend"), "leg") + text(right, 236, t("fc.cutoff", { c: c.threshold_dbm, m: margin }), "leg", "end");
  $("forecast-chart").innerHTML = chartShell(t("fc.chartTitle", { p: trace.policy, t: issued }), content, 246);
  statusEl.textContent = session.warning ? t("fc.positive") : t("fc.negative");
  statusEl.className = `badge ${session.warning ? "warn" : ""}`;
}

/* ---------- bar / contrast charts for studies ---------- */
function barChart(id, data, { title, unit = "", max, digits = 0, ticks, secondary = false, labels = true }) {
  const left = 50, right = 505, top = 22, bottom = 186;
  ticks = ticks || niceTicks(max ?? Math.max(1, ...data.map((d) => d.hi ?? Math.max(d.value, d.other || 0))) * 1.12);
  max = max ?? ticks.at(-1);
  const y = (v) => bottom - ((bottom - top) * v) / max, spacing = (right - left) / data.length;
  let content = text(left, 11, unit, "axis") + yAxis(left, right, y, ticks, max <= 1 ? 2 : 0);
  data.forEach((d, i) => {
    const center = left + spacing * (i + 0.5), width = Math.min(40, spacing * 0.56), color = d.color || COLORS[d.name] || ACCENT;
    const w = secondary ? width * 0.48 : width, x0 = secondary ? center - w - 1 : center - w / 2;
    const fill = d.censored ? "url(#hatch)" : color;
    content += `<rect x="${x0}" y="${y(d.value)}" width="${w}" height="${Math.max(0, bottom - y(d.value))}" rx="1.5" fill="${fill}" stroke="${color}" stroke-width="${d.censored ? 1.2 : 0}" style="color:${color}"><title>${esc(d.name)}: ${fmt(d.value, digits)} ${esc(unit)}</title></rect>`;
    if (secondary) content += `<rect x="${center + 1}" y="${y(d.other)}" width="${w}" height="${Math.max(0, bottom - y(d.other))}" rx="1.5" fill="${color}" opacity=".35"><title>${esc(d.name)} · ${esc(t("chart.delivered"))}: ${fmt(d.other, digits)}</title></rect>`;
    if (d.lo != null) content += `<path d="M${center},${y(d.lo)}V${y(d.hi)}M${center - 4},${y(d.lo)}H${center + 4}M${center - 4},${y(d.hi)}H${center + 4}" stroke="${INK}" stroke-width="1.1" fill="none"/>`;
    if (labels) content += text(center, Math.max(16, y(d.hi ?? Math.max(d.value, d.other || 0)) - 6), d.label ?? fmt(d.value, digits), "val", "middle");
    content += text(center, 202, d.name, "lbl", "middle");
  });
  if (data.some((d) => d.censored)) content += `<rect x="${left}" y="216" width="10" height="10" fill="url(#hatch)" stroke="${MUTED}" style="color:${MUTED}"/>${text(left + 15, 225, t("chart.censoredLegend"), "leg")}`;
  if (secondary) content += `<rect x="${left}" y="232" width="8" height="8" fill="${MUTED}"/>${text(left + 12, 240, t("chart.attempted"), "leg")}<rect x="${left + 110}" y="232" width="8" height="8" fill="${MUTED}" opacity=".35"/>${text(left + 122, 240, t("chart.delivered"), "leg")}`;
  $(id).innerHTML = chartShell(title, content, 248);
}
function contrastChart(id, rows, title, bound) {
  const width = widthOf(id), left = 150, right = width - 20, rowH = 34, top = 30, height = top + rows.length * rowH + 50;
  bound = bound ?? Math.max(1, ...rows.map((r) => Math.max(Math.abs(r.ci_low_s), Math.abs(r.ci_high_s)))) * 1.12;
  const x = (v) => left + ((right - left) * (v + bound)) / (2 * bound), bottom = top + rows.length * rowH;
  let content = text(left, 14, t("chart.contrastAxis"), "axis");
  for (const v of [-bound, -bound / 2, 0, bound / 2, bound]) content += `<line x1="${x(v)}" x2="${x(v)}" y1="${top - 6}" y2="${bottom}" class="grid"/>${text(x(v), bottom + 16, fmt(v), "lbl", "middle")}`;
  content += `<line x1="${x(0)}" x2="${x(0)}" y1="${top - 6}" y2="${bottom}" stroke="${INK}"/>`;
  rows.forEach((r, i) => {
    const yy = top + rowH * (i + 0.5), first = r.comparison.split(" minus ")[0], color = COLORS[first] || INK;
    content += text(8, yy + 4, r.comparison.replace(" minus ", " − "), "leg");
    content += `<path d="M${x(r.ci_low_s)},${yy}H${x(r.ci_high_s)}M${x(r.ci_low_s)},${yy - 5}V${yy + 5}M${x(r.ci_high_s)},${yy - 5}V${yy + 5}" stroke="${color}" stroke-width="1.5"/><circle cx="${x(r.mean_difference_s)}" cy="${yy}" r="4" fill="${color}"><title>${fmt(r.mean_difference_s, 1)} s [${fmt(r.ci_low_s, 1)}, ${fmt(r.ci_high_s, 1)}]</title></circle>`;
  });
  content += text(left, bottom + 34, t("chart.favoursFirst"), "leg") + text(right, bottom + 34, t("chart.favoursSecond"), "leg", "end");
  $(id).innerHTML = chartShell(title, content, height, width);
}

/* ---------- core study ---------- */
// One headline cell per policy: completed / runs and restricted mean time, both rolling.
function headlineCell(policy, key, done, total, mean) {
  return `<div class="headline-cell ${done < total ? "censored" : ""}" style="--c:${COLORS[policy]}"><span class="policy-tag"><i class="policy-swatch"></i>${policy}</span><strong>${roll(`${key}-done`, done)}<em>/ ${total}</em></strong><small>${esc(done < total ? t("headline.censored", { n: total - done }) : t("headline.complete"))}</small><span class="headline-time num">${roll(`${key}-mean`, mean)} s</span></div>`;
}
const truthy = (v) => v === true || String(v).toLowerCase() === "true";
function conditionRows() {
  return state.catalog.runs.filter((r) => r.slowdown === ($("study-slow").value === "true") && r.fade_length === +$("study-length").value);
}
function renderEvidence() {
  const c = state.catalog;
  if (!c) return;
  const slow = $("study-slow").value === "true", length = +$("study-length").value;
  const match = (r) => truthy(r.slowdown) === slow && +r.fade_length === length;
  const summaries = (c.tables["condition-summary"] || []).filter(match).sort((a, b) => CORE.indexOf(a.policy) - CORE.indexOf(b.policy));
  const rows = conditionRows();
  $("condition-label").textContent = t("core.runsInCondition", { n: rows.length });
  const completed = (p) => rows.filter((r) => r.policy === p && r.complete).length, perPolicy = (p) => rows.filter((r) => r.policy === p).length;
  $("core-headline").innerHTML = summaries.map((r) => headlineCell(r.policy, `core-${r.policy}`, completed(r.policy), perPolicy(r.policy), +r.restricted_mean_s)).join("");
  rollNumbers($("core-headline"));
  barChart("time-chart", summaries.map((r) => ({ name: r.policy, value: +r.restricted_mean_s, lo: +r.ci_low_s, hi: +r.ci_high_s, censored: completed(r.policy) < perPolicy(r.policy), label: `${completed(r.policy)}/${perPolicy(r.policy)}` })),
    { title: t("ct.chartTitle"), unit: t("chart.restricted"), max: 8000, ticks: [0, 2000, 4000, 6000, 8000] });
  barChart("completion-chart", CORE.map((p) => ({ name: p, value: completed(p) })), { title: t("cc.chartTitle"), unit: t("chart.completedOf", { n: 30 }), max: 33, ticks: [0, 10, 20, 30] });
  contrastChart("contrast-chart", (c.tables["paired-contrasts"] || []).filter(match).map((r) => ({ ...r, ci_low_s: +r.ci_low_s, ci_high_s: +r.ci_high_s, mean_difference_s: +r.mean_difference_s })), t("pc.chartTitle"));
  barChart("bytes-chart", summaries.map((r) => ({ name: r.policy, value: +r.attempted_bytes / 1000, other: +r.delivered_bytes / 1000 })), { title: t("cb.chartTitle"), unit: t("chart.payload"), secondary: true, digits: 1 });
  warningChart();
  workChart();
  renderRuns();
  document.querySelectorAll("#view-core .figure-link").forEach((a) => (a.href = `/api/figure?name=${a.dataset.figure}&slowdown=${slow}&length=${length}`));
  $("verified-count").textContent = t("core.verified", { n: fmt(c.verification.raw_runs_reconstructed) });
  $("design-hash").textContent = c.design.sha256;
  $("provenance-json").textContent = JSON.stringify({ evaluation: c.evaluation, analysis: c.analysis, verification: c.verification, environment: c.environment }, null, 2);
  const timings = c.benchmark.timings || {}, memory = c.benchmark.process_memory || [];
  const cards = [["trend", "S4-T"], ["persistence", "S4-P"], ["allocation", null]].map(([k]) =>
    kpi(t(`hb.${k}`), fmt(timings[k]?.median_cpu_ns / 1000, 1), "µs", t("hb.perDecision")));
  cards.push(kpi(t("hb.peak"), memory.length ? `${fmt(Math.min(...memory.map((r) => r.peak_process_rss_bytes)) / 1048576, 1)}–${fmt(Math.max(...memory.map((r) => r.peak_process_rss_bytes)) / 1048576, 1)}` : t("kpi.notRecorded"), memory.length ? "MiB" : "", t("hb.peakNote")));
  $("host-metrics").innerHTML = cards.join("");
}
function warningChart() {
  const rows = state.catalog.warnings || [], metrics = ["precision", "recall", "f1"];
  const top = 22, bottom = 186, y = (v) => bottom - (bottom - top) * v;
  let content = text(50, 11, t("chart.score"), "axis") + yAxis(50, 505, y, [0, 0.25, 0.5, 0.75, 1], 2);
  rows.forEach((row, j) => metrics.forEach((m, i) => {
    const value = row[m], x0 = 110 + i * 140 + j * 32, p = row.method === "trend" ? "S4-T" : "S4-P";
    if (value != null) content += `<rect x="${x0}" y="${y(value)}" width="26" height="${bottom - y(value)}" fill="${COLORS[p]}" rx="1.5"><title>${p} ${m}: ${fmt(value, 3)}</title></rect>${text(x0 + 13, y(value) - 6, fmt(value, 2), "val", "middle")}`;
  }));
  metrics.forEach((m, i) => (content += text(139 + i * 140, 202, t(`wq.${m}`), "lbl", "middle")));
  content += `<rect x="150" y="220" width="8" height="8" fill="${COLORS["S4-T"]}"/>${text(162, 228, `S4-T · ${t("method.trend")}`, "leg")}<rect x="290" y="220" width="8" height="8" fill="${COLORS["S4-P"]}"/>${text(302, 228, `S4-P · ${t("method.persistence")}`, "leg")}`;
  $("warning-chart").innerHTML = chartShell(t("cw.chartTitle"), content, 244);
}
function workChart() {
  const resources = state.catalog.tables["component-resources"] || [], components = ["allocation", "forecast", "resync"];
  const shades = [INK, MUTED, LINE];
  const totals = CORE.map((p) => components.map((c) => +(resources.find((r) => r.policy === p && r.component === c)?.mean_arithmetic || 0) / 1000));
  const ticks = niceTicks(Math.max(1, ...totals.map((v) => v.reduce((a, b) => a + b, 0))) * 1.08), maximum = ticks.at(-1);
  const y = (v) => 186 - (164 * v) / maximum;
  let content = text(50, 11, t("chart.arith"), "axis") + yAxis(50, 505, y, ticks);
  totals.forEach((values, i) => {
    let acc = 0;
    values.forEach((v, j) => {
      content += `<rect x="${80 + i * 88}" y="${y(acc + v)}" width="38" height="${(164 * v) / maximum}" fill="${shades[j]}" stroke="#fff" stroke-width=".5"><title>${CORE[i]} ${components[j]}: ${fmt(v * 1000)}</title></rect>`;
      acc += v;
    });
    content += text(99 + i * 88, 202, CORE[i], "lbl", "middle");
  });
  components.forEach((c, i) => (content += `<rect x="${90 + i * 120}" y="220" width="8" height="8" fill="${shades[i]}" stroke="${MUTED}" stroke-width=".5"/>${text(102 + i * 120, 228, t(`work.${c}`), "leg")}`));
  $("work-chart").innerHTML = chartShell(t("ck.chartTitle"), content, 244);
}
function runRow(r, dataset, extra) {
  const name = nameFor(r.policy, { seed: r.seed, slowdown: r.slowdown, length: r.fade_length });
  return `<tr><td class="num">${r.seed}</td><td><span class="policy-tag" style="--c:${COLORS[r.policy]}"><i class="policy-swatch"></i>${r.policy}</span></td><td><span class="badge ${r.complete ? "ok" : "censored"}">${r.complete ? t("outcome.complete") : t("outcome.censoredShort")}</span></td><td class="num">${fmt(r.restricted_s)}${r.complete ? "" : " *"}</td><td class="num">${extra(r)}</td><td class="num">${r.redundant}</td><td class="num">${fmt(r.attempted_bytes / 1000, 1)}</td><td><button class="text-button" data-replay="${name}" data-dataset="${dataset}">${esc(t("re.replay"))} ↗</button></td></tr>`;
}
function renderRuns() {
  const outcome = $("outcome-filter").value;
  const rows = conditionRows().filter((r) => outcome === "all" || r.complete === (outcome === "complete"));
  $("runs-body").innerHTML = rows.map((r) => runRow(r, "core", (x) => `${fmt(100 * x.coverage, 1)}%`)).join("");
  $("runs-count").textContent = t("re.count", { n: rows.length });
}

/* ---------- extension ---------- */
async function loadExtension() {
  if (state.ext || !state.catalog) { if (state.ext) renderExtension(); return; }
  if (!state.catalog.extension_available) { $("ext-missing").hidden = false; $("ext-content").hidden = true; return; }
  try {
    state.ext = await api("/api/extension");
    const profiles = [...new Set(state.ext.hardware.map((r) => r.profile))];
    $("ext-profile").innerHTML = profiles.map((p) => `<option value="${p}">${esc(p.toUpperCase())}</option>`).join("");
    renderExtension();
    refreshHero();
  } catch (error) {
    $("ext-missing").hidden = false; $("ext-missing").textContent = error.message; $("ext-content").hidden = true;
  }
}
function renderExtension() {
  const e = state.ext;
  if (!e) return;
  const slow = $("ext-slow").value === "true", length = +$("ext-length").value;
  const match = (r) => r.slowdown === slow && r.fade_length === length;
  const policies = e.design.policies;
  const summary = policies.map((p) => e.summary.find((r) => match(r) && r.policy === p)).filter(Boolean);
  const runs = e.runs.filter(match);
  $("ext-condition-label").textContent = t("core.runsInCondition", { n: runs.length });
  barChart("ext-time-chart", summary.map((r) => {
    const done = Math.round(r.completion_proportion * r.n);
    return { name: r.policy, value: r.restricted_mean_s, lo: r.ci_low_s, hi: r.ci_high_s, censored: done < r.n, label: `${done}/${r.n}` };
  }), { title: t("ext.timeTitle"), unit: t("chart.restricted"), max: 8000, ticks: [0, 2000, 4000, 6000, 8000], labels: true });
  // Recovery trips (bars) and idle seconds (dots, right scale).
  {
    const left = 50, right = 470, top = 22, bottom = 186, spacing = (right - left) / summary.length;
    const tripTicks = niceTicks(Math.max(1, ...summary.map((r) => r.recovery_trips)) * 1.1), idleTicks = niceTicks(Math.max(1, ...summary.map((r) => r.idle_s)) * 1.1);
    const tripMax = tripTicks.at(-1), idleMax = idleTicks.at(-1);
    const y = (v) => bottom - ((bottom - top) * v) / tripMax, yi = (v) => bottom - ((bottom - top) * v) / idleMax;
    let content = text(left, 11, t("ext.trips"), "axis") + yAxis(left, right, y, tripTicks, tripMax < 5 ? 1 : 0) + text(505, 11, t("ext.idle"), "axis", "end");
    idleTicks.forEach((v) => (content += text(right + 8, yi(v) + 4, fmt(v), "lbl")));
    summary.forEach((r, i) => {
      const cx = left + spacing * (i + 0.5);
      content += `<rect x="${cx - 12}" y="${y(r.recovery_trips)}" width="24" height="${bottom - y(r.recovery_trips)}" fill="${COLORS[r.policy]}" rx="1.5"><title>${r.policy}: ${fmt(r.recovery_trips, 2)}</title></rect><circle cx="${cx}" cy="${yi(r.idle_s)}" r="3.5" fill="#fff" stroke="${INK}" stroke-width="1.4"><title>${r.policy} idle: ${fmt(r.idle_s)} s</title></circle>${text(cx, 202, r.policy, "lbl", "middle")}`;
    });
    content += `<rect x="${left}" y="220" width="8" height="8" fill="${MUTED}"/>${text(left + 12, 228, t("ext.tripsLegend"), "leg")}<circle cx="${left + 184}" cy="224" r="3.5" fill="#fff" stroke="${INK}" stroke-width="1.4"/>${text(left + 192, 228, t("ext.idleLegend"), "leg")}`;
    $("ext-recovery-chart").innerHTML = chartShell(t("ext.recTitle"), content, 244);
  }
  const contrasts = e.contrasts.filter((r) => match(r) && r.role !== "predictor");
  $("ext-headline").innerHTML = summary.map((r) => headlineCell(r.policy, `ext-${r.policy}`, Math.round(r.completion_proportion * r.n), r.n, r.restricted_mean_s)).join("");
  rollNumbers($("ext-headline"));
  contrastChart("ext-contrast-chart", contrasts, t("ext.contrastTitle"));
  document.querySelectorAll("#view-extension .figure-link").forEach((a) => (a.href = `/api/figure?name=${a.dataset.figure}&slowdown=${slow}&length=${length}`));
  renderPredictors();
  renderHardware();
  renderMapAccuracy(slow, length);
  renderExtRuns(runs);
}
const predictorPolicy = (predictor) => Object.entries(state.ext.design.policy_predictors).find(([, v]) => v === predictor)?.[0];
function renderPredictors() {
  const e = state.ext, rows = e.warning.filter((w) => w.split === "extension-2000");
  const left = 50, right = 500, top = 18, bottom = 186;
  const costs = rows.map((r) => r.arithmetic_per_decision + r.transcendental_per_decision);
  const lo = Math.floor(Math.log10(Math.max(0.5, Math.min(...costs)))), hi = Math.ceil(Math.log10(Math.max(...costs)));
  const x = (v) => left + ((right - left) * (Math.log10(Math.max(v, 10 ** lo)) - lo)) / (hi - lo || 1), y = (v) => bottom - (bottom - top) * v;
  let content = text(left, 11, t("ext.f1"), "axis") + yAxis(left, right, y, [0, 0.25, 0.5, 0.75, 1], 2);
  for (let d = lo; d <= hi; d++) content += `<line x1="${x(10 ** d)}" x2="${x(10 ** d)}" y1="${top}" y2="${bottom}" class="grid"/>${text(x(10 ** d), 202, fmt(10 ** d), "lbl", "middle")}`;
  content += text(right, 218, t("ext.opsAxis"), "lbl", "end");
  rows.forEach((r) => {
    const p = predictorPolicy(r.predictor), cx = x(r.arithmetic_per_decision + r.transcendental_per_decision), cy = y(r.f1);
    content += r.predictor === "fade-oracle"
      ? `<path d="M${cx - 5},${cy - 5}L${cx + 5},${cy + 5}M${cx + 5},${cy - 5}L${cx - 5},${cy + 5}" stroke="${COLORS[p]}" stroke-width="2"><title>${p} ${esc(r.label)}</title></path>${text(cx + 8, cy + 4, `${p} · ${t("ext.bound")}`, "leg")}`
      : `<circle cx="${cx}" cy="${cy}" r="4.5" fill="${COLORS[p]}"><title>${p} ${esc(r.label)}: F1 ${fmt(r.f1, 3)}</title></circle>`;
  });
  const legend = rows.filter((r) => r.predictor !== "fade-oracle");
  legend.forEach((r, i) => { const p = predictorPolicy(r.predictor), lx = left + (i % 4) * 112, ly = 236 + Math.floor(i / 4) * 14; content += `<circle cx="${lx + 4}" cy="${ly - 4}" r="3.5" fill="${COLORS[p]}"/>${text(lx + 11, ly, p, "leg")}`; });
  $("ext-pq-chart").innerHTML = chartShell(t("ext.pqTitle"), content, 236 + Math.ceil(legend.length / 4) * 14);
  const split = $("ext-split").value;
  const table = e.warning.filter((w) => w.split === split);
  $("ext-predictor-table").innerHTML = `<thead><tr><th>${esc(t("ext.c.policy"))}</th><th>${esc(t("wq.precision"))}</th><th>${esc(t("wq.recall"))}</th><th>F1</th><th>${esc(t("wq.lead"))} [s]</th><th>${esc(t("ext.c.memory"))} [B]</th><th>${esc(t("ext.c.ops"))}</th><th>CPU [µs]</th></tr></thead><tbody>${table.map((r) => {
    const p = predictorPolicy(r.predictor);
    return `<tr><td><span class="policy-tag" style="--c:${COLORS[p]}"><i class="policy-swatch"></i>${p}</span> ${esc(r.label.replace(" (bound)", ""))}${r.predictor === "fade-oracle" ? ` <span class="badge warn">${esc(t("ext.boundBadge"))}</span>` : ""}</td><td>${fmt(r.precision, 3)}</td><td>${fmt(r.recall, 3)}</td><td>${fmt(r.f1, 3)}</td><td>${fmt(r.mean_lead_s, 1)}</td><td>${fmt(r.memory_bytes)}</td><td>${fmt(r.arithmetic_per_decision + r.transcendental_per_decision, 1)}</td><td>${fmt(r.cpu_us_per_decision, 2)}</td></tr>`;
  }).join("")}</tbody>`;
}
function renderHardware() {
  const profile = $("ext-profile").value, rows = state.ext.hardware.filter((r) => r.profile === profile);
  $("ext-hardware-table").innerHTML = `<thead><tr><th>${esc(t("ext.c.policy"))}</th><th>${esc(t("ext.c.cycles"))}</th><th>${esc(t("ext.c.latency"))} [µs]</th><th>${esc(t("ext.c.duty"))} [%]</th><th>${esc(t("ext.c.memfrac"))} [%]</th><th>${esc(t("ext.c.energy"))} [µJ]</th></tr></thead><tbody>${rows.map((r) => {
    const p = predictorPolicy(r.predictor);
    return `<tr><td><span class="policy-tag" style="--c:${COLORS[p]}"><i class="policy-swatch"></i>${p}</span></td><td>${fmt(r.cycles_low)}–${fmt(r.cycles_high)}</td><td>${fmt(r.latency_us_low, 1)}–${fmt(r.latency_us_high, 1)}</td><td>${fmt(r.duty_cycle_percent_high, 5)}</td><td>${fmt(r.memory_fraction_percent, 3)}</td><td>${fmt(r.projected_energy_uj_low, 2)}–${fmt(r.projected_energy_uj_high, 2)}</td></tr>`;
  }).join("")}</tbody>`;
}
function renderMapAccuracy(slow, length) {
  const curves = state.ext.map_curves.filter((c) => c.slowdown === slow && c.fade_length === length);
  const ticks = niceTicks(Math.max(0.5, ...curves.flatMap((c) => c.rmse_m)) * 1.05);
  const draw = (id, study, policies) => {
    const left = 46, right = 500, top = 16, bottom = 180, x = (v) => left + ((right - left) * v) / 4000, y = (v) => bottom - ((bottom - top) * v) / ticks.at(-1);
    let content = text(left, 10, t("ext.rmse"), "axis") + yAxis(left, right, y, ticks, 1);
    for (const v of [0, 1000, 2000, 3000, 4000]) content += text(x(v), 196, fmt(v), "lbl", "middle");
    content += text(right, 211, t("chart.timeS"), "lbl", "end");
    content += `<line x1="${left}" x2="${right}" y1="${y(0.5)}" y2="${y(0.5)}" stroke="${MUTED}" stroke-dasharray="2 3"/>`;
    policies.forEach((p, i) => {
      const c = curves.find((k) => k.study === study && k.policy === p);
      if (!c) return;
      const pts = c.t.map((at, j) => [at, c.rmse_m[j]]).filter(([at]) => at <= 4000);
      content += `<path d="${pts.map(([a, v], j) => `${j ? "L" : "M"}${x(a).toFixed(1)},${y(v).toFixed(1)}`).join("")}" fill="none" stroke="${COLORS[p]}" stroke-width="1.6"${p === "S4-O" ? ' stroke-dasharray="4 3"' : ""}><title>${p}</title></path>`;
      const lx = left + (i % 6) * 76, ly = 228 + Math.floor(i / 6) * 14;
      content += `<line x1="${lx}" x2="${lx + 12}" y1="${ly - 4}" y2="${ly - 4}" stroke="${COLORS[p]}" stroke-width="2"${p === "S4-O" ? ' stroke-dasharray="4 3"' : ""}/>${text(lx + 16, ly, p, "leg")}`;
    });
    $(id).innerHTML = chartShell(`${t("ext.mapTitle")} · ${study}`, content, 234 + Math.floor((policies.length - 1) / 6) * 14);
  };
  draw("ext-map-core", "core", CORE);
  draw("ext-map-ext", "extension", state.ext.design.policies);
  const rows = state.ext.maps;
  $("ext-map-table").innerHTML = `<thead><tr><th>${esc(t("ext.c.study"))}</th><th>${esc(t("ext.c.policy"))}</th><th>${esc(t("ext.c.finalRmse"))} [m]</th><th>RMSE 900 s [m]</th><th>RMSE 1800 s [m]</th><th>${esc(t("ext.c.reached"))}</th><th>${esc(t("ext.c.median"))} [s]</th></tr></thead><tbody>${rows.map((r) => `<tr><td>${esc(r.study === "core" ? t("ext.studyCore") : t("ext.studyExt"))}</td><td><span class="policy-tag" style="--c:${COLORS[r.policy]}"><i class="policy-swatch"></i>${r.policy}</span></td><td>${fmt(r.final_rmse_m, 3)}</td><td>${fmt(r.rmse_900_m, 3)}</td><td>${fmt(r.rmse_1800_m, 3)}</td><td>${r.reached_0_5_m} / ${r.runs}</td><td>${r.median_time_to_0_5_m_s == null ? esc(t("ext.never")) : fmt(r.median_time_to_0_5_m_s)}</td></tr>`).join("")}</tbody>`;
}
function renderExtRuns(runs) {
  const select = $("ext-run-policy");
  if (!select.options.length) select.innerHTML = state.ext.design.policies.map((p) => `<option value="${p}">${p} · ${esc(policyName(p))}</option>`).join("");
  const rows = runs.filter((r) => r.policy === select.value);
  $("ext-runs-body").innerHTML = rows.map((r) => runRow(r, "extension", (x) => fmt(x.recovery_trips))).join("");
}

/* ---------- export ---------- */
function downloadBlob(content, type, filename) {
  const url = URL.createObjectURL(content instanceof Blob ? content : new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function exportChart(id) {
  // Paper theme: white background, black text, serif type, 3x raster.
  const svg = $(id)?.querySelector("svg");
  if (!svg) return;
  const copy = svg.cloneNode(true);
  copy.querySelectorAll(".time-cursor").forEach((e) => e.remove());
  const [, , w, h] = copy.getAttribute("viewBox").split(" ").map(Number);
  copy.setAttribute("width", w); copy.setAttribute("height", h);
  const style = document.createElementNS("http://www.w3.org/2000/svg", "style");
  style.textContent = "text{font-family:'Times New Roman',Times,serif!important;fill:#000!important}.grid{stroke:#d9d9d9!important}";
  copy.append(style);
  const background = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  background.setAttribute("width", "100%"); background.setAttribute("height", "100%"); background.setAttribute("fill", "#fff");
  copy.prepend(background);
  const trace = activeTrace(), r = trace?.result;
  const mission = ["coverage-chart", "signal-chart", "budget-chart", "forecast-chart"].includes(id);
  const filename = mission ? `${id}-${trace?.dataset}-seed${r?.seed}-slow${Number(r?.slowdown)}-L${r?.fade_length}.png` : `${id}.png`;
  const image = new Image(), scale = 3;
  image.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = w * scale; canvas.height = h * scale;
    const ctx = canvas.getContext("2d");
    ctx.scale(scale, scale); ctx.drawImage(image, 0, 0);
    canvas.toBlob((blob) => (blob ? downloadBlob(blob, "image/png", filename) : toast(t("toast.exportFailed"), true)), "image/png");
    URL.revokeObjectURL(image.src);
  };
  image.onerror = () => toast(t("toast.exportFailed"), true);
  image.src = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(copy)], { type: "image/svg+xml" }));
  toast(t("toast.exported"));
}
function saveMap() {
  const trace = activeTrace();
  if (!trace) return;
  const canvas = $("map"), output = document.createElement("canvas"), scale = canvas.width / canvas.getBoundingClientRect().width;
  output.width = Math.max(canvas.width, 900); output.height = canvas.height + 120 * scale;
  const ctx = output.getContext("2d");
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, output.width, output.height);
  ctx.drawImage(canvas, (output.width - canvas.width) / 2, 0);
  const at = Math.min(state.t, trace.result.stop_s), c = trace.config;
  ctx.fillStyle = "#000"; ctx.font = `${14 * scale}px 'Times New Roman', serif`;
  ctx.fillText(`USV·PAC · ${trace.policy} ${policyName(trace.policy)} · ${t("kpi.seed")} ${trace.result.seed} · ${condLabel(trace.result.slowdown, trace.result.fade_length)} · t = ${fmt(at, 1)} s`, 20 * scale, canvas.height + 28 * scale);
  ctx.font = `${12 * scale}px 'Times New Roman', serif`;
  ctx.fillText(`${c.width * c.cell_m} × ${c.height * c.cell_m} m · ${c.cell_m} m ${t("map.cells")} · n = ${c.path_exponent} · ${t("map.snapshotLegend")}`, 20 * scale, canvas.height + 50 * scale);
  ctx.font = `${10 * scale}px Consolas, monospace`;
  ctx.fillText(`raw SHA-256 ${trace.raw_sha256}`, 20 * scale, canvas.height + 72 * scale);
  output.toBlob((blob) => (blob ? downloadBlob(blob, "image/png", `map-${trace.dataset}-${trace.name}-${at.toFixed(0)}s.png`) : toast(t("toast.exportFailed"), true)), "image/png");
}

/* ---------- jobs ---------- */
async function submit(action, selected = false) {
  try {
    if (!state.catalog) return;
    let req = {};
    if (action === "run") {
      if (!$("run-form").reportValidity()) return;
      req = request(); req.policy = selected ? $("policy").value : "all";
    }
    const record = await api("/api/jobs", { action, request: req });
    state.currentJob = record.id;
    $("run-progress").hidden = false;
    $("run-status").textContent = t("job.queued", { action: t(`job.action.${record.action}`), id: record.id });
    toast(action === "run" ? t("toast.runQueued") : t("toast.workflowQueued"));
    await refreshJobs();
  } catch (error) { toast(error.message, true); }
}
const handledJobs = new Set();
function jobTitle(j) {
  return j.action === "run" ? `${j.request.policy === "all" ? t("job.allPolicies") : j.request.policy} · ${t("kpi.seed")} ${j.request.seed} · ${condLabel(j.request.slowdown, j.request.length)}` : t(`job.action.${j.action}`);
}
async function refreshJobs() {
  const jobs = await api("/api/jobs");
  state.jobs = jobs;
  $("job-count").textContent = jobs.length;
  $("jobs-list").innerHTML = jobs.length ? jobs.map((j) => {
    const icon = j.status === "passed" ? "✓" : ["failed", "interrupted"].includes(j.status) ? "!" : "↻";
    return `<div class="job-row ${j.status}" data-job="${j.id}" tabindex="0" role="button" aria-label="${esc(t("job.inspect", { id: j.id }))}"><span class="job-state" aria-hidden="true">${icon}</span><div><h3>${esc(jobTitle(j))} <span class="badge ${j.status === "passed" ? "ok" : ["failed", "interrupted"].includes(j.status) ? "censored" : ""}">${esc(t(`job.status.${j.status}`))}</span></h3><p>${esc(j.message)}</p>${["running", "queued", "packaging"].includes(j.status) ? `<progress value="${j.done || 0}" max="${j.total || 1}"></progress>` : ""}<p class="mono small">${j.id}</p></div><time class="num">${esc(new Date(j.created_utc).toLocaleString(locale()))}</time></div>`;
  }).join("") : `<div class="empty">${esc(t("job.empty"))}</div>`;
  const current = jobs.find((j) => j.id === state.currentJob);
  if (current) {
    $("run-status").textContent = `${t(`job.status.${current.status}`)} · ${current.message}`;
    $("run-meter").max = current.total || 1; $("run-meter").value = current.done || 0;
    if (["passed", "failed", "interrupted"].includes(current.status) && !handledJobs.has(current.id)) {
      handledJobs.add(current.id);
      if (current.status === "passed") {
        toast(t("toast.runDone"));
        if (["run", "smoke", "full"].includes(current.action)) await openCompleted(current.id);
      } else toast(current.message, true);
    }
  }
  if (state.selectedJob && jobs.some((j) => j.id === state.selectedJob && ["running", "queued", "packaging"].includes(j.status))) await inspectJob(state.selectedJob);
}
async function openCompleted(identity) {
  const job = await api(`/api/job?id=${identity}`);
  if (!job.runs.length) return;
  const r = job.runs[0];
  const req = job.action === "run" ? job.request : { seed: r.seed, length: r.fade_length, slowdown: r.slowdown, exponent: r.path_exponent, timeout: 7200 };
  state.dataset = identity;
  fillPolicySelect();
  setSetup(req);
  state.traces = {}; state.t = 0; setPlaying(false);
  if (!job.runs.some((x) => x.policy === $("policy").value)) $("policy").value = job.runs[0].policy;
  state.active = $("policy").value;
  await loadComparison(CORE.filter((p) => job.runs.some((x) => x.policy === p)));
}
async function inspectJob(identity) {
  state.selectedJob = identity;
  const job = await api(`/api/job?id=${identity}`);
  $("job-detail").hidden = false;
  $("job-title").textContent = `${jobTitle(job)} · ${job.id}`;
  const link = (name, label) => `<a class="button secondary small" href="/api/download?dataset=${identity}&name=${encodeURIComponent(name)}"><svg><use href="#i-download"/></svg>${esc(label)}</a>`;
  $("job-downloads").innerHTML = ["passed", "failed", "interrupted"].includes(job.status)
    ? link("evidence.zip", t("job.zip")) + link("provenance.json", t("job.provenance")) +
      (job.runs.length && job.status === "passed" ? link("figures/paired-mission.png", t("job.figure")) + `<button class="button primary small" data-open-job="${identity}">${esc(t("job.replay"))} ↗</button>` : "")
    : "";
  $("job-log").textContent = job.test_log || JSON.stringify({ status: job.status, request: job.request, message: job.message, runs: job.runs.map((r) => ({ policy: r.policy, complete: r.complete, coverage: r.coverage, restricted_s: r.restricted_s })), provenance: job.provenance }, null, 2);
}

/* ---------- events ---------- */
function renderEvents() {
  const trace = activeTrace();
  if (!trace) return;
  const filter = $("event-filter").value;
  const rows = trace.sessions.filter((e) => filter === "all" || (filter === "warning" && e.warning) || (filter === "failed" && !e.radio) || (filter === "budget" && e.budget_failure) || (filter === "commit" && e.committed));
  $("events-body").innerHTML = rows.map((e) => {
    const status = linkState(e);
    const decision = e.warning ? t("log.d.warning") : e.committed ? t("log.d.allocate") : t("log.d.none");
    return `<tr class="clickable" data-session="${e.k}" tabindex="0" aria-label="${esc(t("log.rowLabel", { t: e.t }))}"><td class="num">${fmt(e.t)}</td><td class="num">${fmt(e.r, 1)}</td><td><span class="link-pill ${status}">${esc(t(`link.${status}`))}</span></td><td>${e.warning ? `<span class="warn-mark" aria-hidden="true">▲</span> ` : ""}${esc(decision)}</td><td class="num">${fmt(e.bytes_attempted)}</td></tr>`;
  }).join("");
  $("event-count").textContent = t("log.count", { shown: rows.length, total: trace.sessions.length, ticks: fmt(trace.event_counts.tick) });
  $("event-json").textContent = t("log.hint");
}
function inspectEvent(row) {
  const session = activeTrace()?.sessions.find((e) => e.k === +row.dataset.session);
  if (!session) return;
  setPlaying(false); setTime(session.t);
  $("event-json").textContent = JSON.stringify(session, null, 2);
  document.querySelectorAll("#events-body tr").forEach((e) => e.classList.toggle("selected", e === row));
}

/* ---------- guide, architecture, reference ---------- */
const ARCH = [
  ["browser", "arch.browser", "arch.browserSub"],
  ["post", "arch.post", "arch.postSub"],
  ["queue", "arch.queue", "arch.queueSub"],
  ["workflow", "arch.workflow", "arch.workflowSub"],
  ["model", "arch.model", "arch.modelSub"],
  ["results", "arch.results", "arch.resultsSub"],
  ["replay", "arch.replay", "arch.replaySub"],
];
function renderGuide() {
  // Architecture: two lanes (browser / Python on this PC), seven numbered steps.
  const boxW = 156, boxH = 66, xs = [20, 196, 372, 548, 724];
  const pos = [[xs[0], 36], [xs[0], 176], [xs[1], 176], [xs[2], 176], [xs[3], 176], [xs[4], 176], [xs[4], 36]];
  const mid = (i) => pos[i][0] + boxW / 2;
  let svg = `<svg viewBox="0 0 900 262" xmlns="http://www.w3.org/2000/svg"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10z" fill="${MUTED}"/></marker></defs>`;
  svg += `<rect x="6" y="8" width="888" height="108" rx="8" fill="${token("accent-soft")}" stroke="${LINE}"/><text x="18" y="25" class="lane">${esc(t("arch.laneBrowser"))}</text>`;
  svg += `<rect x="6" y="146" width="888" height="110" rx="8" fill="${token("muted")}" stroke="${LINE}"/><text x="18" y="163" class="lane">${esc(t("arch.lanePython"))}</text>`;
  const arrow = (d, dashed = false) => `<path d="${d}" fill="none" stroke="${MUTED}" stroke-width="1.3"${dashed ? ' stroke-dasharray="4 3"' : ""} marker-end="url(#arrow)"/>`;
  svg += arrow(`M${mid(0)},${pos[0][1] + boxH} V${pos[1][1] - 2}`);
  for (const i of [1, 2, 3, 4]) svg += arrow(`M${pos[i][0] + boxW},${pos[i][1] + boxH / 2} H${pos[i + 1][0] - 2}`);
  svg += arrow(`M${mid(5)},${pos[5][1]} V${pos[6][1] + boxH + 2}`);
  svg += arrow(`M${pos[6][0]},${pos[6][1] + boxH / 2} H${pos[0][0] + boxW + 2}`, true);
  ARCH.forEach(([id, title, sub], i) => {
    const [x, y] = pos[i], python = i > 0 && i < 6;
    svg += `<g><rect x="${x}" y="${y}" width="${boxW}" height="${boxH}" rx="6" fill="#fff" stroke="${python ? INK : ACCENT}" stroke-width="${python ? 1 : 1.4}"/><circle cx="${x + 15}" cy="${y + 16}" r="9" fill="${python ? INK : ACCENT}"/><text x="${x + 15}" y="${y + 20}" text-anchor="middle" class="n">${i + 1}</text><text x="${x + 30}" y="${y + 21}" class="h">${esc(t(title))}</text><text x="${x + 10}" y="${y + 40}" class="s">${esc(t(sub))}</text><text x="${x + 10}" y="${y + 55}" class="m">${esc(t(`arch.${id}Code`))}</text></g>`;
  });
  svg += `<style>text{font-family:${UI_FONT}}.lane{font-size:10px;letter-spacing:.08em;fill:${MUTED};font-weight:600;text-transform:uppercase}.h{font-size:12px;font-weight:700;fill:${INK}}.s{font-size:9.5px;fill:${MUTED}}.m{font-size:9.5px;fill:${INK};font-family:'DM Mono','Cascadia Mono',Consolas,monospace}.n{font-size:10px;fill:#fff;font-weight:700}</style></svg>`;
  $("architecture").innerHTML = svg;
  $("arch-steps").innerHTML = ARCH.map(([id], i) => `<li><b>${i + 1}. ${esc(t(`arch.${id}`))}</b> ${esc(t(`arch.${id}Long`))}</li>`).join("");
  $("guide-numbers").innerHTML = heroNumbers(studyFacts());
  $("first-steps").innerHTML = FIRST_RUN.map((key, i) => `<li data-step="${i}"><span class="mono step-no">${String(i + 1).padStart(2, "0")}</span><div><b>${esc(t(`tourstep.${key}.t`))}</b><p>${esc(t(`tourstep.${key}.b`))}</p><button class="text-button" data-tour-start="first" data-tour-index="${i}">${esc(t("guide.show"))} ↗</button></div></li>`).join("");
  $("policy-concepts").innerHTML = ALL.map((p) => `<div><dt><span class="policy-tag" style="--c:${COLORS[p]}"><i class="policy-swatch"></i>${p}</span> ${esc(policyName(p))}</dt><dd>${esc(t(`policyLong.${p}`))}</dd></div>`).join("");
  const groups = {};
  for (const step of TOUR_FULL) (groups[step.view] ||= []).push(step);
  $("feature-reference").innerHTML = Object.entries(groups).map(([v, steps]) => `<section><h3><button class="text-button" data-view="${v}">${esc(t(`nav.${v}`))} ↗</button></h3><dl>${steps.map((s) => `<div><dt>${esc(t(`tourstep.${s.key}.t`))}</dt><dd>${esc(t(`tourstep.${s.key}.b`))}</dd></div>`).join("")}</dl></section>`).join("");
  setStep(0);
  if (stepObserver) document.querySelectorAll("#first-steps li").forEach((li) => stepObserver.observe(li));
  observeReveal($("view-guide"));
  startField($("guide-field"));
}

// Scroll timeline: the big serif step number follows the step in the middle of the screen.
function setStep(index) {
  const key = FIRST_RUN[index];
  $("step-big").innerHTML = roll("step", index + 1, 0);
  $("step-title").textContent = t(`tourstep.${key}.t`);
  document.querySelectorAll("#first-steps li").forEach((li) => li.classList.toggle("active", +li.dataset.step === index));
  rollNumbers($("step-big"));
}
const stepObserver = "IntersectionObserver" in window ? new IntersectionObserver((entries) => {
  for (const entry of entries) if (entry.isIntersecting) setStep(+entry.target.dataset.step);
}, { rootMargin: "-45% 0px -45% 0px" }) : null;

/* ---------- tour ---------- */
const TOUR_FULL = [
  { view: "guide", key: "welcome", sel: ".guide-hero" },
  { view: "map", key: "status", sel: '[data-tour="run-status"]' },
  { view: "map", key: "setup", sel: '[data-tour="setup"]' },
  { view: "map", key: "condition", sel: '[data-tour="condition"]' },
  { view: "map", key: "run", sel: '[data-tour="run"]' },
  { view: "map", key: "map", sel: '[data-tour="map"]' },
  { view: "map", key: "mapTools", sel: '[data-tour="map-tools"]' },
  { view: "map", key: "legend", sel: '[data-tour="legend"]' },
  { view: "map", key: "playback", sel: '[data-tour="playback"]' },
  { view: "map", key: "kpis", sel: '[data-tour="kpis"]' },
  { view: "map", key: "compare", sel: '[data-tour="compare"]' },
  { view: "map", key: "snapshot", sel: '[data-tour="snapshot"]' },
  { view: "link", key: "signal", sel: '[data-tour="signal"]' },
  { view: "link", key: "budget", sel: '[data-tour="budget"]' },
  { view: "link", key: "forecast", sel: '[data-tour="forecast"]' },
  { view: "link", key: "warningQuality", sel: '[data-tour="warning-quality"]' },
  { view: "log", key: "log", sel: '[data-tour="log"]' },
  { view: "core", key: "coreFilter", sel: '[data-tour="core-filter"]' },
  { view: "core", key: "coreTime", sel: '[data-tour="core-time"]' },
  { view: "extension", key: "extFilter", sel: '[data-tour="ext-filter"]' },
  { view: "extension", key: "extTime", sel: '[data-tour="ext-time"]' },
  { view: "extension", key: "extPredictors", sel: '[data-tour="ext-predictors"]' },
  { view: "extension", key: "extMap", sel: '[data-tour="ext-map"]' },
  { view: "runs", key: "workflows", sel: '[data-tour="workflows"]' },
  { view: "runs", key: "jobs", sel: '[data-tour="jobs"]' },
  { view: "presentation", key: "deck", sel: "#deck" },
  { view: "map", key: "lang", sel: '[data-tour="lang"]' },
  { view: "map", key: "tourButton", sel: '[data-tour="tour-button"]' },
];
const FIRST_RUN = ["setup", "condition", "run", "jobs", "playback", "map", "kpis", "compare", "signal", "log", "coreTime", "snapshot"];
function tourSteps(kind) {
  return kind === "first" ? FIRST_RUN.map((key) => TOUR_FULL.find((s) => s.key === key)) : TOUR_FULL;
}
function startTour(kind = "full", index = 0) {
  state.tour = { kind, index, opener: document.activeElement };
  $("tour").hidden = false;
  document.body.classList.add("touring");
  showTourStep();
}
function endTour() {
  if (!state.tour) return;
  const opener = state.tour.opener;
  state.tour = null;
  $("tour").hidden = true;
  document.body.classList.remove("touring");
  store.set("toured", "1");
  opener?.focus?.();
}
function showTourStep() {
  const steps = tourSteps(state.tour.kind), step = steps[state.tour.index];
  if (state.view !== step.view) view(step.view, { scroll: false });
  const target = document.querySelector(step.sel);
  target?.scrollIntoView({ block: "center", behavior: reduced() || state.motionPaused ? "instant" : "smooth" });
  $("tour-meta").textContent = `${t(state.tour.kind === "first" ? "tour.firstRun" : "tour.full")} · ${String(state.tour.index + 1).padStart(2, "0")} / ${String(steps.length).padStart(2, "0")}`;
  $("tour-title").textContent = t(`tourstep.${step.key}.t`);
  $("tour-body").textContent = t(`tourstep.${step.key}.b`);
  $("tour-prev").disabled = state.tour.index === 0;
  $("tour-next").textContent = state.tour.index === steps.length - 1 ? t("tour.finish") : t("tour.next");
  setTimeout(() => placeTour(target), reduced() || state.motionPaused ? 0 : 260);
  $("tour-next").focus({ preventScroll: true });
}
function placeTour(target) {
  if (!state.tour) return;
  const spot = $("tour-spot"), card = $("tour-card"), pad = 6;
  const rect = target?.getBoundingClientRect();
  if (!rect || !rect.width) { spot.style.cssText = "left:50%;top:50%;width:0;height:0"; } else {
    spot.style.left = `${rect.left - pad}px`; spot.style.top = `${rect.top - pad}px`;
    spot.style.width = `${rect.width + 2 * pad}px`; spot.style.height = `${rect.height + 2 * pad}px`;
  }
  if (innerWidth < 640) { card.style.left = "12px"; card.style.right = "12px"; card.style.top = "auto"; card.style.bottom = "12px"; return; }
  const cw = card.offsetWidth, ch = card.offsetHeight;
  let top = rect ? rect.bottom + 14 : innerHeight / 2 - ch / 2;
  if (rect && top + ch > innerHeight - 12) top = Math.max(12, rect.top - ch - 14);
  if (rect && top < 12) top = Math.min(innerHeight - ch - 12, Math.max(12, rect.top + 12));
  const left = Math.min(innerWidth - cw - 12, Math.max(12, rect ? rect.left : innerWidth / 2 - cw / 2));
  card.style.right = card.style.bottom = "auto";
  card.style.left = `${left}px`; card.style.top = `${top}px`;
}
function tourMove(delta) {
  const steps = tourSteps(state.tour.kind), next = state.tour.index + delta;
  if (next >= steps.length) return endTour();
  state.tour.index = Math.max(0, next);
  showTourStep();
}

/* ---------- rolling numbers ---------- */
// Elements with data-roll="key" data-v="value" data-d="decimals" animate from their
// previous value to the new one. The final text is always fmt(value) exactly; values are
// interpolated monotonically (no overshoot). Reduced motion, the motion pause and live
// playback (values already change every frame) switch instantly.
const ROLLED = new Map(), ROLLING = new Map(), ROLL_TIMERS = new Map();
const ROLL_MS = 450;
const easeOut = (p) => 1 - (1 - p) ** 3;
function rollValue(from, to, progress) {
  return progress >= 1 ? to : from + (to - from) * easeOut(Math.max(0, progress));
}
function rollNumbers(rootNode, { from } = {}) {
  rootNode?.querySelectorAll("[data-roll]").forEach((el) => {
    const key = el.dataset.roll, target = +el.dataset.v, digits = +el.dataset.d || 0;
    const final = `${el.dataset.prefix || ""}${fmt(target, digits)}`;
    const start = from ?? ROLLED.get(key);
    ROLLED.set(key, target);
    cancelAnimationFrame(ROLLING.get(key));
    clearTimeout(ROLL_TIMERS.get(key));
    if (start == null || start === target || !Number.isFinite(start) || reduced() || state.motionPaused || state.playing) {
      el.textContent = final;
      return;
    }
    const began = performance.now();
    el.classList.add("rolling");
    let done = false;
    const finish = () => { done = true; el.textContent = final; el.classList.remove("rolling"); };
    // Hidden tabs pause animation frames; this timer still lands on the exact value.
    ROLL_TIMERS.set(key, setTimeout(finish, ROLL_MS + 60));
    const step = (now) => {
      if (done) return;
      const p = (now - began) / ROLL_MS;
      if (p >= 1 || !el.isConnected) return finish();
      el.textContent = `${el.dataset.prefix || ""}${fmt(rollValue(start, target, p), digits)}`;
      ROLLING.set(key, requestAnimationFrame(step));
    };
    ROLLING.set(key, requestAnimationFrame(step));
  });
}
const roll = (key, value, digits = 0, prefix = "") =>
  value == null || !Number.isFinite(+value) ? "—" : `<span data-roll="${key}" data-v="${value}" data-d="${digits}"${prefix ? ` data-prefix="${prefix}"` : ""}>${prefix}${fmt(value, digits)}</span>`;

/* ---------- USV digit field (guide & title slide) ---------- */
// A grid of monospace digits taken only from received-signal values [−dBm] recorded in the
// replayed mission. Darker digits draw a survey boat, pulsing radio rings and a moving sea
// line; digits near the pointer re-read the log faster. Without a trace the field stays empty.
const fields = new Map();
function signalDigits() {
  const sessions = activeTrace()?.sessions || [];
  return sessions.map((s) => String(Math.round(Math.abs(s.r)))).join("");
}
function startField(canvas) {
  if (!canvas || fields.has(canvas)) return;
  const box = canvas.getBoundingClientRect();
  if (!box.width) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2), w = box.width, h = box.height;
  canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const cw = 11, ch = 15, cols = Math.floor(w / cw), rows = Math.floor(h / ch);
  // Boat silhouette rasterised once at pixel resolution, then sampled per cell.
  const off = document.createElement("canvas");
  off.width = Math.ceil(w); off.height = Math.ceil(h);
  const o = off.getContext("2d");
  o.fillStyle = "#000";
  o.beginPath(); o.moveTo(0.2 * w, 0.6 * h); o.lineTo(0.8 * w, 0.6 * h); o.lineTo(0.7 * w, 0.73 * h); o.lineTo(0.3 * w, 0.73 * h); o.closePath(); o.fill();
  o.fillRect(0.4 * w, 0.48 * h, 0.2 * w, 0.12 * h);
  o.fillRect(0.485 * w, 0.26 * h, Math.max(cw, 0.03 * w), 0.22 * h);
  const mask = o.getImageData(0, 0, off.width, off.height).data;
  const mast = [0.5 * w, 0.26 * h];
  const cells = [];
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const x = c * cw + cw / 2, y = r * ch + ch / 2;
    const hull = mask[(Math.floor(y) * off.width + Math.floor(x)) * 4 + 3] > 100;
    cells.push({ x, y, hull, i: (r * cols + c) * 7, next: 0 });
  }
  let pointer = null, elapsed = 0, previous = 0;
  canvas.addEventListener("pointermove", (e) => { const b = canvas.getBoundingClientRect(); pointer = [e.clientX - b.left, e.clientY - b.top]; });
  canvas.addEventListener("pointerleave", () => (pointer = null));
  const draw = (time) => {
    const digits = signalDigits(), still = reduced() || state.motionPaused;
    if (!still && previous) elapsed += Math.min(time - previous, 50);
    previous = time;
    const s = elapsed / 1000;
    ctx.clearRect(0, 0, w, h);
    ctx.font = `500 11px ${root.getPropertyValue("--font-mono")}`;
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    if (digits.length) for (const cell of cells) {
      const near = pointer && Math.hypot(cell.x - pointer[0], cell.y - pointer[1]) < 64;
      if (!still && (near || s > cell.next)) { cell.i += near ? 1 : 3; cell.next = s + 1.5 + ((cell.i * 7919) % 400) / 100; }
      const d = Math.hypot(cell.x - mast[0], cell.y - mast[1]), angle = Math.abs(Math.atan2(cell.y - mast[1], Math.abs(cell.x - mast[0])));
      let ring = 0;
      for (let k = 0; k < 3; k++) {
        const radius = (0.07 + 0.055 * k) * w, pulse = still ? 1 : (Math.sin(s * 2.2 - k * 1.1) + 1) / 2;
        if (Math.abs(d - radius) < 6 && angle < 0.95 && cell.y < mast[1] + 0.06 * h && Math.abs(cell.x - mast[0]) > 0.03 * w) ring = Math.max(ring, 0.25 + 0.7 * pulse);
      }
      const sea = 0.84 * h + 0.025 * h * Math.sin(cell.x / (0.09 * w) + (still ? 0 : s * 1.1));
      const wave = Math.abs(cell.y - sea) < ch * 0.55;
      ctx.fillStyle = near ? ACCENT : cell.hull ? ACCENT : ring ? BOAT[1] : wave ? ACCENT : INK;
      ctx.globalAlpha = near ? 0.95 : cell.hull ? 0.92 : ring ? ring : wave ? 0.55 : 0.08;
      ctx.fillText(digits[cell.i % digits.length], cell.x, cell.y);
    }
    ctx.globalAlpha = 1;
    if (canvas.isConnected && canvas.offsetParent) fields.set(canvas, requestAnimationFrame(draw));
    else fields.delete(canvas);
  };
  fields.set(canvas, requestAnimationFrame(draw));
}

/* ---------- scroll reveal and hero numbers ---------- */
const revealObserver = "IntersectionObserver" in window ? new IntersectionObserver((entries) => {
  for (const entry of entries) if (entry.isIntersecting) {
    entry.target.classList.add("in");
    // Hero numbers count up from zero each time they enter the view.
    if (entry.target.matches(".hero-numbers")) rollNumbers(entry.target, { from: 0 });
    revealObserver.unobserve(entry.target);
  }
}, { threshold: 0.2 }) : null;
function observeReveal(rootNode) {
  rootNode.querySelectorAll(".scroll-reveal:not(.in), .hero-numbers").forEach((e) => {
    if (revealObserver && !reduced() && !state.motionPaused) revealObserver.observe(e);
    else { e.classList.add("in"); if (e.matches(".hero-numbers")) rollNumbers(e); }
  });
}
function heroNumbers(items) {
  return `<div class="hero-numbers">${items.map(([key, value, unit, label, prefix]) => `<div class="hero-num"><strong>${roll(`hero-${key}`, value, 0, prefix)}<em>${esc(unit)}</em></strong><span>${esc(label)}</span></div>`).join("")}</div>`;
}
function studyFacts() {
  const c = state.catalog;
  const trace = activeTrace();
  return [
    ["cells", trace ? trace.first_seen.length : null, t("hero.cellsUnit"), t("hero.cells")],
    ["core", c?.runs.length, t("hero.runsUnit"), t("hero.core")],
    ["ext", state.ext?.runs.length, t("hero.runsUnit"), t("hero.ext")],
    ["policies", state.ext ? state.ext.design.policies.length : CORE.length, "", t("hero.policies")],
    ["dbm", trace ? -trace.config.threshold_dbm : null, "dBm", t("hero.threshold"), "−"],
  ].filter((item) => item[1] != null);
}

/* ---------- presentation ---------- */
const SLIDES = ["title", "question", "mechanism", "link", "outcome", "extension", "reproduce"];
function renderSlide() {
  if (!state.catalog) return;
  const d = state.catalog, all = d.runs, completed = (p) => all.filter((r) => r.policy === p && r.complete).length;
  const key = SLIDES[state.slide], ext = state.ext;
  const clone = (id) => $(id)?.innerHTML || `<div class="empty small">${esc(t("pres.openView"))}</div>`;
  const body = {
    title: () => `<div class="slide-title-grid"><div class="reveal"><p class="slide-kicker">${esc(t("pres.s1.kicker"))}</p><h2 class="slide-hero">${t("pres.s1.title")}</h2><p class="slide-lead">${esc(t("pres.s1.lead"))}</p><p class="slide-authors">Andrea Lo Iacono · Ettore Mugisha Cirillo</p><p class="slide-note">${esc(t("pres.s1.note"))}</p></div><div class="digit-field slide-field" aria-hidden="true"><canvas id="slide-field"></canvas><span class="field-caption mono">${esc(t("field.caption"))}</span></div></div>${heroNumbers(studyFacts())}`,
    question: () => `<h2 class="slide-h reveal">${esc(t("pres.s2.title"))}</h2><div class="slide-facts reveal"><div><strong class="num">${roll("s2-boats", 2)}</strong><span>${esc(t("pres.s2.boats"))}</span></div><div><strong class="num">${roll("s2-cells", 240)}</strong><span>${esc(t("pres.s2.cells"))}</span></div><div><strong class="num">${roll("s2-ex", 10)} s</strong><span>${esc(t("pres.s2.exchange"))}</span></div><div><strong class="num">${roll("s2-dbm", 90, 0, "−")} dBm</strong><span>${esc(t("pres.s2.threshold"))}</span></div></div><div class="slide-cols reveal">${CORE.map((p) => `<div class="slide-policy" style="--c:${COLORS[p]}"><span class="mono">${p}</span><b>${esc(policyName(p))}</b><small>${esc(t(`policyLong.${p}`))}</small></div>`).join("")}</div>`,
    mechanism: () => `<h2 class="slide-h reveal">${esc(t("pres.s3.title"))}</h2><div class="slide-split reveal"><div><canvas id="slide-map" class="slide-map" aria-label="${esc(t("map.canvas"))}"></canvas><p class="slide-caption"><button id="slide-play" class="button primary small">${esc(state.playing ? t("pres.pauseMission") : t("pres.playMission"))}</button> <span class="mono">${esc(state.active)} · ${esc(t("kpi.seed"))} ${activeTrace()?.result.seed ?? "—"}</span></p></div><ul class="slide-list">${["S2", "S3", "S4-T"].map((p) => `<li style="--c:${COLORS[p]}"><b><i class="policy-swatch"></i>${p} · ${esc(policyName(p))}</b>${esc(t(`policyLong.${p}`))}</li>`).join("")}</ul></div>`,
    link: () => `<h2 class="slide-h reveal">${esc(t("pres.s4.title"))}</h2><div class="slide-chart reveal">${clone("signal-chart")}</div><p class="slide-lead reveal">${esc(t("pres.s4.lead"))}</p>`,
    outcome: () => `<h2 class="slide-h reveal">${esc(t("pres.s5.title"))}</h2><div class="slide-split reveal"><div id="slide-completion" class="slide-chart"></div><div><div class="slide-chart">${clone("contrast-chart")}</div><p class="slide-lead">${esc(t("pres.s5.lead", { s1: completed("S1"), s2: completed("S2"), s3: completed("S3"), t4: completed("S4-T"), p4: completed("S4-P") }))}</p></div></div>`,
    extension: () => ext ? `<h2 class="slide-h reveal">${esc(t("pres.s6.title"))}</h2><div class="slide-split reveal"><div class="slide-chart">${clone("ext-time-chart")}</div><div class="slide-chart">${clone("ext-pq-chart")}</div></div><p class="slide-lead reveal">${esc(t("pres.s6.lead"))}</p>` : `<h2 class="slide-h">${esc(t("pres.s6.title"))}</h2><div class="empty">${esc(t("pres.s6.loading"))}</div>`,
    reproduce: () => `<h2 class="slide-h reveal">${esc(t("pres.s7.title"))}</h2><div class="slide-facts reveal"><div><strong class="num">${roll("s7-runs", all.length)}</strong><span>${esc(t("pres.s7.runs"))}</span></div><div><strong class="num">${roll("s7-logs", d.verification.raw_runs_reconstructed)}</strong><span>${esc(t("pres.s7.logs"))}</span></div><div><strong class="num">${ext ? roll("s7-ext", ext.runs.length) : "—"}</strong><span>${esc(t("pres.s7.ext"))}</span></div></div><ul class="slide-list reveal"><li><b>${esc(t("pres.s7.freeze"))}</b>${esc(t("pres.s7.freezeText"))}</li><li><b>${esc(t("pres.s7.bundle"))}</b>${esc(t("pres.s7.bundleText"))}</li><li><b>${esc(t("pres.s7.again"))}</b><code>python -m usv_sim.workflow --preset full --workers 4</code></li></ul>`,
  }[key];
  $("slide-number").textContent = `${String(state.slide + 1).padStart(2, "0")} / ${String(SLIDES.length).padStart(2, "0")}`;
  $("deck-section").textContent = t(`pres.section.${key}`);
  $("deck-progress").style.width = `${(100 * (state.slide + 1)) / SLIDES.length}%`;
  $("slide-content").innerHTML = body();
  $("slide-content").querySelectorAll(".reveal").forEach((e, i) => e.style.setProperty("--i", i));
  rollNumbers($("slide-content"), { from: 0 });
  $("slide-dots").innerHTML = SLIDES.map((s, i) => `<button class="${i === state.slide ? "active" : ""}" data-slide="${i}" aria-label="${esc(t("pres.goto", { n: i + 1, name: t(`pres.section.${s}`) }))}" aria-current="${i === state.slide}"></button>`).join("");
  $("previous-slide").disabled = state.slide === 0;
  $("next-slide").disabled = state.slide === SLIDES.length - 1;
  if (key === "title") startField($("slide-field"));
  if (key === "mechanism") drawAll();
  if (key === "outcome") barChart("slide-completion", CORE.map((p) => ({ name: p, value: completed(p) })), { title: t("pres.s5.chart"), unit: t("chart.completedOf", { n: 180 }), max: 200, ticks: [0, 60, 120, 180] });
  if (key === "extension" && !ext) loadExtension().then(() => state.view === "presentation" && SLIDES[state.slide] === "extension" && renderSlide());
}
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

/* ---------- language & motion ---------- */
function setLang(lang) {
  I18N.set(lang);
  store.set("lang", lang);
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  I18N.apply(document);
  fillPolicySelect();
  setSetup(request());
  setPlaying(state.playing);
  if (state.catalog) { renderEvidence(); refreshJobs().catch(() => {}); $("connection").textContent = t("engine.connected"); }
  $("ext-run-policy").innerHTML = "";
  if (state.ext) renderExtension();
  if (activeTrace()) { $("boat-states").dataset.key = ""; $("forecast-chart").dataset.key = ""; afterLoad(); }
  if (state.view === "guide") renderGuide();
  if (state.view === "presentation") renderSlide();
  if (state.tour) showTourStep();
  document.title = `${t(`nav.${state.view}`)} · USV·PAC`;
}
function setMotion(paused) {
  state.motionPaused = paused;
  store.set("motion", paused ? "paused" : "on");
  document.body.classList.toggle("motion-paused", paused);
  $("motion-toggle").setAttribute("aria-pressed", String(paused));
  $("motion-toggle").setAttribute("aria-label", paused ? t("motion.resume") : t("motion.pause"));
  $("motion-toggle").title = paused ? t("motion.resume") : t("motion.pause");
}
function syncFields() {
  if (state.view === "guide") startField($("guide-field"));
  if (state.view === "presentation") startField($("slide-field"));
}

/* ---------- events ---------- */
document.addEventListener("click", async (event) => {
  const nav = event.target.closest("[data-view]");
  if (nav) view(nav.dataset.view);
  const lang = event.target.closest("[data-lang]");
  if (lang) setLang(lang.dataset.lang);
  const slow = event.target.closest("[data-slow]");
  if (slow) { setSetup({ ...request(), slowdown: slow.dataset.slow === "true" }); setupChanged(); }
  const card = event.target.closest(".compare-card");
  if (card) { $("policy").value = card.dataset.policy; await loadSelected(); }
  const session = event.target.closest("[data-session]");
  if (session) inspectEvent(session);
  const chart = event.target.closest(".chart-export");
  if (chart) exportChart(chart.dataset.chart);
  const action = event.target.closest("[data-action]");
  if (action) await submit(action.dataset.action);
  const job = event.target.closest("[data-job]");
  if (job) inspectJob(job.dataset.job).catch((e) => toast(e.message, true));
  const open = event.target.closest("[data-open-job]");
  if (open) { await openCompleted(open.dataset.openJob); view("map"); }
  const replay = event.target.closest("[data-replay]");
  if (replay) {
    const parts = replay.dataset.replay.split("-");
    state.dataset = replay.dataset.dataset || "core";
    fillPolicySelect();
    setSetup({ seed: +parts[0], slowdown: parts[1] === "1", length: +parts[2], exponent: 2, timeout: 7200 });
    $("policy").value = parts.slice(3).join("-");
    state.traces = {};
    await loadSelected(true);
    view("map");
  }
  const slide = event.target.closest("[data-slide]");
  if (slide) { state.slide = +slide.dataset.slide; renderSlide(); }
  if (event.target.closest("#slide-play")) setPlaying(!state.playing);
  const tourStart = event.target.closest("[data-tour-start]");
  if (tourStart) startTour(tourStart.dataset.tourStart, +tourStart.dataset.tourIndex || 0);
});
document.addEventListener("keydown", (event) => {
  if (state.tour) {
    if (event.key === "Escape") endTour();
    else if (event.key === "ArrowRight") tourMove(1);
    else if (event.key === "ArrowLeft") tourMove(-1);
    else if (event.key === "Tab") {
      const focusable = [...$("tour-card").querySelectorAll("button:not([disabled])")];
      const index = focusable.indexOf(document.activeElement);
      event.preventDefault();
      focusable[(index + (event.shiftKey ? -1 : 1) + focusable.length) % focusable.length].focus();
    }
    return;
  }
  if (event.key === "Escape" && document.body.classList.contains("menu-open")) closeMenu();
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
    state.slide = Math.min(SLIDES.length - 1, Math.max(0, state.slide + (event.key === "ArrowRight" ? 1 : -1)));
    renderSlide();
  }
});
function setupChanged() {
  // A run bundle holds one scenario only; other settings come from the retained studies.
  if (!["core", "extension"].includes(state.dataset)) { state.dataset = "core"; fillPolicySelect(); }
  setPlaying(false);
  if (+$("exponent").value === 2 && +$("timeout").value === 7200) loadSelected(true);
  else toast(t("toast.exploratory"));
}
$("policy").addEventListener("change", () => loadSelected());
for (const id of ["seed", "length", "exponent", "timeout"]) $(id).addEventListener("change", setupChanged);
for (const id of ["show-trails", "show-queues", "show-redundant", "knowledge"]) $(id).addEventListener("change", drawAll);
$("timeline").addEventListener("input", () => { setPlaying(false); setTime(+$("timeline").value); });
$("play").addEventListener("click", () => { if (state.t >= +$("timeline").max) state.t = 0; setPlaying(!state.playing); });
$("restart").addEventListener("click", () => { setPlaying(false); setTime(0); });
$("jump-slowdown").addEventListener("click", () => { const tr = activeTrace(); if (tr) { setPlaying(false); setTime(tr.scenario.onset_s); } });
$("jump-end").addEventListener("click", () => { const tr = activeTrace(); if (tr) { setPlaying(false); setTime(tr.result.stop_s); } });
$("load-comparison").addEventListener("click", () => loadComparison());
$("run-form").addEventListener("submit", (event) => { event.preventDefault(); submit("run"); });
$("run-one").addEventListener("click", () => submit("run", true));
$("event-filter").addEventListener("change", renderEvents);
$("event-search").addEventListener("change", () => {
  const target = +$("event-search").value;
  const rows = [...document.querySelectorAll("#events-body tr")];
  const trace = activeTrace();
  if (!rows.length || !trace) return;
  const best = rows.reduce((a, b) => (Math.abs(trace.sessions.find((s) => s.k === +b.dataset.session).t - target) < Math.abs(trace.sessions.find((s) => s.k === +a.dataset.session).t - target) ? b : a));
  best.scrollIntoView({ block: "center" }); best.focus(); inspectEvent(best);
});
for (const id of ["study-slow", "study-length"]) $(id).addEventListener("change", renderEvidence);
for (const id of ["ext-slow", "ext-length"]) $(id).addEventListener("change", renderExtension);
$("ext-split").addEventListener("change", renderPredictors);
$("ext-profile").addEventListener("change", renderHardware);
$("ext-run-policy").addEventListener("change", () => renderExtension());
$("outcome-filter").addEventListener("change", renderRuns);
$("snapshot").addEventListener("click", saveMap);
$("previous-slide").addEventListener("click", () => { state.slide = Math.max(0, state.slide - 1); renderSlide(); });
$("next-slide").addEventListener("click", () => { state.slide = Math.min(SLIDES.length - 1, state.slide + 1); renderSlide(); });
$("fullscreen").addEventListener("click", () => {
  presentationFocus(true);
  // Embedded browsers may deny native fullscreen; the focused layout still works.
  $("deck").requestFullscreen?.().catch(() => {});
});
$("exit-presentation").addEventListener("click", exitPresentationFocus);
document.addEventListener("fullscreenchange", () => {
  if (document.fullscreenElement) state.nativeFullscreen = true;
  else if (state.nativeFullscreen) { state.nativeFullscreen = false; presentationFocus(false); }
});
$("refresh-jobs").addEventListener("click", () => refreshJobs().catch((e) => toast(e.message, true)));
$("menu-button").addEventListener("click", () => {
  const open = !document.body.classList.contains("menu-open");
  document.body.classList.toggle("menu-open", open);
  $("menu-button").setAttribute("aria-expanded", String(open));
  $("scrim").hidden = !open;
});
$("scrim").addEventListener("click", closeMenu);
$("motion-toggle").addEventListener("click", () => setMotion(!state.motionPaused));
$("tour-button").addEventListener("click", () => startTour("full"));
$("start-tour").addEventListener("click", () => startTour("full"));
$("start-first-run").addEventListener("click", () => startTour("first"));
$("tour-next").addEventListener("click", () => tourMove(1));
$("tour-prev").addEventListener("click", () => tourMove(-1));
$("tour-close").addEventListener("click", endTour);
window.addEventListener("hashchange", () => { const name = location.hash.slice(1); if (name && name !== state.view) view(name); });
let resizeTimer;
window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { renderMissionCharts(); if (state.catalog) renderEvidence(); if (state.ext) renderExtension(); drawAll(); if (state.tour) placeTour(document.querySelector(tourSteps(state.tour.kind)[state.tour.index].sel)); }, 80); });
window.addEventListener("scroll", () => { if (state.tour) placeTour(document.querySelector(tourSteps(state.tour.kind)[state.tour.index].sel)); }, { passive: true });

async function init() {
  const saved = new URLSearchParams(location.search).get("lang") || store.get("lang");
  setLang(saved ||((navigator.language || "en").toLowerCase().startsWith("it") ? "it" : "en"));
  setMotion(store.get("motion") === "paused");
  try {
    state.catalog = await api("/api/catalog");
    $("connection").textContent = t("engine.connected");
    $("engine-dot").classList.add("on");
    renderEvidence();
    await refreshJobs();
    const first = location.hash.slice(1) || (store.get("visited") ? "map" : "guide");
    store.set("visited", "1");
    view(first);
    await loadSelected(true);
    requestAnimationFrame(animate);
    setInterval(() => { if (!document.hidden) refreshJobs().catch(() => { $("connection").textContent = t("engine.disconnected"); $("engine-dot").classList.remove("on"); }); }, 2500);
    if (state.catalog.extension_available) loadExtension();
  } catch (error) {
    $("connection").textContent = t("engine.unavailable");
    toast(error.message, true);
  }
}
init();
