// Live chart dashboards for hub notes, styled by view.css. Needs the Dataview plugin with
// "Enable JavaScript Queries" turned on.
// Reads no note properties itself: it is the shared toolkit. Each dashboard (`<hub>.js` next
// to this file) lists the properties it reads in its own header.
// In a hub:  await dv.view("Templates/Views/hub-charts", { hub: "tasks" })
// If you rename the Templates folder (folders.templates in .vault-skills.yaml), change BASE
// below and the path in each hub note's dv.view call.
// This file is the shared toolkit (tiles, controls, stacked bars, line, calendar heatmap,
// ranked bars, tooltips, table views). Each dashboard is `<hub>.js` next to it and runs as
// an async function of (dv, input, H). Dataview re-runs the block when indexed notes change,
// so every dashboard stays current without a refresh.

const app = dv.app;
const { DateTime } = dv.luxon;
const BASE = "Templates/Views/hub-charts";
const NS = "http://www.w3.org/2000/svg";
const hubName = String(input?.hub ?? "").replace(/[^\w-]/g, "");
if (!hubName) {
  dv.paragraph("hub-charts: pass `{ hub: \"<name>\" }` to pick a dashboard.");
  return;
}

// ---------- helpers ----------
const num = v => (typeof v === "number" && isFinite(v) ? v : Number(v) || 0);
const toDate = v => {
  if (!v) return null;
  if (dv.value.isDate(v)) return v.toLocal();
  const d = DateTime.fromISO(String(v));
  return d.isValid ? d.toLocal() : null;
};
const el = (parent, tag, cls, text) => parent.createEl(tag, { cls, text });
const svg = (parent, tag, attrs = {}) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  parent.appendChild(e);
  return e;
};
const fmt = {
  int: n => Math.round(n).toLocaleString(),
  compact: n =>
    n >= 1e9 ? `${(n / 1e9).toFixed(1)}B` : n >= 1e6 ? `${(n / 1e6).toFixed(1)}M`
    : n >= 1e4 ? `${Math.round(n / 1e3)}k` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}k`
    : Number.isInteger(n) ? `${n}` : n.toFixed(1),
  money: n => (n >= 100 ? `$${Math.round(n).toLocaleString()}` : `$${n.toFixed(2)}`),
  pct: (a, b) => (b ? `${((100 * a) / b).toFixed(1)}%` : "–"),
  share: v => `${Math.round(v * 100)}%`,
  hours: m => (m >= 60 ? `${(m / 60).toFixed(m >= 600 ? 0 : 1)} h` : `${Math.round(m)} min`),
  ago: d => {
    if (!d) return "never";
    const m = Math.round(DateTime.now().diff(d, "minutes").minutes);
    return m < 1 ? "just now" : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago`
      : `${Math.round(m / 1440)} days ago`;
  },
};
const open = (path, e) => app.workspace.openLinkText(path, dv.currentFilePath, !!(e && (e.metaKey || e.ctrlKey)));
// Axis top for four gridlines: a round tick step times four, whole steps for whole-number data.
const niceMax = (v, integer = false) => {
  if (v <= 0) return integer ? 4 : 1;
  const raw = v / 4, p = 10 ** Math.floor(Math.log10(raw)), f = raw / p;
  let step = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find(x => f <= x) * p;
  if (integer) step = Math.max(1, Math.ceil(step));
  return step * 4;
};
// Bar with 4px rounded top, square at the baseline.
const barPath = (x, y, w, h, r = 4) => {
  r = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
};

// Periods from `start` to `end` (inclusive), one per `unit` ("day", "week", "month", "year").
const periods = (start, end, unit) => {
  const out = [];
  for (let d = start.startOf(unit); d <= end; d = d.plus({ [`${unit}s`]: 1 })) out.push(d);
  return out;
};
// Buckets keyed by period start; `add(bucket, item)` folds each item in.
const bucket = (items, dateOf, unit, start, end, init = () => ({}), add = (b, x) => b.items.push(x)) => {
  const list = periods(start, end, unit).map(d => ({ start: d, items: [], ...init() }));
  const index = new Map(list.map(b => [b.start.toISODate(), b]));
  for (const x of items) {
    const d = dateOf(x);
    const b = d && index.get(d.startOf(unit).toISODate());
    if (b) add(b, x);
  }
  return list;
};
const periodLabel = (d, unit) =>
  unit === "day" ? d.toFormat("ccc d LLL yyyy") : unit === "week" ? `Week of ${d.toFormat("d LLL yyyy")}`
  : unit === "month" ? d.toFormat("LLLL yyyy") : d.toFormat("yyyy");
const tickLabel = (d, unit) =>
  unit === "year" ? d.toFormat("yyyy") : unit === "month" ? d.toFormat("LLL yy") : d.toFormat("d LLL");

// ---------- dashboard ----------
const dashboard = ({ key, defaults = {} } = {}) => {
  const stateKey = `hub-charts:${key ?? hubName}:${dv.currentFilePath}`;
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(stateKey)) ?? {}; } catch { /* first run */ }
  const state = { ...defaults, ...saved };
  const root = el(dv.container, "div", "hc-root");
  const tipEl = el(root, "div", "hc-tip");
  const charts = [];
  const timers = [];

  const tip = {
    show(e, lines) {
      tipEl.empty();
      for (const line of lines) {
        if (!line) continue;
        const row = el(tipEl, "div", line.cls ?? "hc-tip-row");
        if (line.slot) el(row, "span", `hc-swatch hc-s${line.slot}`);
        el(row, "span", "hc-tip-label", line.label);
        if (line.value != null) el(row, "span", "hc-tip-value", String(line.value));
      }
      tipEl.addClass("is-visible");
      const r = root.getBoundingClientRect();
      const x = e.clientX - r.left, y = e.clientY - r.top;
      tipEl.style.left = `${Math.max(4, Math.min(x + 14, r.width - tipEl.offsetWidth - 4))}px`;
      tipEl.style.top = `${y + 16}px`;
    },
    hide() { tipEl.removeClass("is-visible"); },
  };
  const bindTip = (node, lines, onClick) => {
    node.addEventListener("mousemove", e => tip.show(e, typeof lines === "function" ? lines() : lines));
    node.addEventListener("mouseleave", tip.hide);
    if (onClick) {
      node.classList.add("is-clickable");
      node.addEventListener("click", onClick);
    }
  };

  const ctx = {
    root, state, tip, bindTip,
    save() { localStorage.setItem(stateKey, JSON.stringify(state)); },
    redraw() { tip.hide(); for (const c of charts) c(); },
    grid(parent = root) { return el(parent, "div", "hc-grid"); },
    // A card whose body `draw(card)` rebuilds on every control change or resize.
    chart(parent, draw, { wide = false } = {}) {
      const card = el(parent ?? root, "div", `hc-card${wide ? " hc-wide" : ""}`);
      const run = () => {
        card.empty();
        try { draw(card); } catch (err) { el(card, "div", "hc-empty", `Chart failed: ${err.message}`); console.error(err); }
      };
      charts.push(run);
      return card;
    },
    // A block refreshed every `seconds` (for "x min ago" and live counts) as well as on redraw.
    live(parent, draw, seconds = 30) {
      const box = el(parent ?? root, "div");
      const run = () => { box.empty(); draw(box); };
      charts.push(run);
      timers.push(window.setInterval(run, seconds * 1000));
      return box;
    },
    header(parent, text, isLive = false) {
      const h = el(parent ?? root, "div", "hc-header");
      el(h, "span", `hc-pulse${isLive ? " is-live" : ""}`);
      el(h, "span", "hc-header-text", text);
      return h;
    },
    tiles(parent, list) {
      const box = el(parent ?? root, "div", "hc-tiles");
      for (const t of list) {
        if (!t) continue;
        const tile = el(box, "div", `hc-tile${t.tone ? ` hc-tone-${t.tone}` : ""}`);
        el(tile, "div", "hc-tile-value", String(t.value));
        el(tile, "div", "hc-tile-label", t.label);
        if (t.sub) el(tile, "div", "hc-tile-sub", t.sub);
        if (t.onClick) { tile.addClass("is-clickable"); tile.addEventListener("click", t.onClick); }
        if (t.title) tile.setAttr("title", t.title);
      }
      return box;
    },
    controls(groups, parent = root) {
      const bar = el(parent, "div", "hc-controls");
      for (const g of groups) {
        const group = el(bar, "div", "hc-seg");
        el(group, "span", "hc-seg-label", g.label);
        const buttons = g.options.map(([value, text]) => {
          const b = el(group, "button", "hc-seg-btn", text);
          b.toggleClass("is-active", state[g.key] === value);
          b.addEventListener("click", () => {
            state[g.key] = value;
            ctx.save();
            for (const x of buttons) x.toggleClass("is-active", x === b);
            ctx.redraw();
          });
          return b;
        });
      }
      return bar;
    },
    start() {
      ctx.redraw();
      let lastWidth = root.clientWidth;
      const ro = new ResizeObserver(() => {
        if (Math.abs(root.clientWidth - lastWidth) < 24) return;
        lastWidth = root.clientWidth;
        ctx.redraw();
      });
      ro.observe(root);
      dv.component.register(() => { for (const t of timers) window.clearInterval(t); ro.disconnect(); });
    },
  };
  return ctx;
};

// ---------- card pieces ----------
const head = (card, title, note) => {
  const h = el(card, "div", "hc-card-head");
  el(h, "div", "hc-card-title", title);
  if (note) el(h, "div", "hc-card-note", note);
  return h;
};
const legend = (card, series) => {
  if (series.length < 2) return;
  const l = el(card, "div", "hc-legend");
  for (const s of series) {
    const i = el(l, "span", "hc-legend-item");
    el(i, "span", `hc-swatch hc-s${s.slot}`);
    i.appendText(s.label);
  }
};
const empty = (card, text) => el(card, "div", "hc-empty", text);
const table = (card, headers, rows) => {
  if (!rows.length) return;
  const d = el(card, "details", "hc-table");
  el(d, "summary", null, "Table");
  const t = el(d, "table");
  const hr = el(el(t, "thead"), "tr");
  for (const h of headers) el(hr, "th", null, h);
  const body = el(t, "tbody");
  for (const r of rows) {
    const tr = el(body, "tr");
    for (const c of r) el(tr, "td", null, String(c));
  }
};
const plotArea = (card, height) => {
  const host = el(card, "div", "hc-plot");
  const width = Math.max(260, host.clientWidth || card.clientWidth || 640);
  const s = svg(host, "svg", { width, height, viewBox: `0 0 ${width} ${height}`, class: "hc-svg", role: "img" });
  return { s, width, height };
};
const yAxis = (s, pad, width, height, lo, hi, format) => {
  for (let i = 0; i <= 4; i++) {
    const v = lo + ((hi - lo) * i) / 4, y = height - pad.b - ((height - pad.t - pad.b) * i) / 4;
    svg(s, "line", { x1: pad.l, x2: width - pad.r, y1: y, y2: y, class: i ? "hc-grid-line" : "hc-base-line" });
    svg(s, "text", { x: pad.l - 6, y: y + 4, class: "hc-axis", "text-anchor": "end" }).textContent = format(v);
  }
};

// Stacked (or single-series) vertical bars.
// buckets: [{ label, values: { key: n }, tip?: lines[], onClick?: fn }]; series: [{ key, label, slot }]
const bars = (ctx, card, { buckets, series, format = fmt.compact, height = 200, tick, tip, onClick, total = true }) => {
  legend(card, series);
  if (!buckets.length) return empty(card, "Nothing in this range.");
  const { s, width } = plotArea(card, height);
  const pad = { t: 10, r: 8, b: 24, l: 48 };
  const totals = buckets.map(b => series.reduce((a, x) => a + num(b.values[x.key]), 0));
  const max = niceMax(Math.max(...totals), totals.every(Number.isInteger));
  yAxis(s, pad, width, height, 0, max, format);
  const plotW = width - pad.l - pad.r, plotH = height - pad.t - pad.b;
  const slotW = plotW / buckets.length, barW = Math.max(2, Math.min(28, slotW - 2));
  const labelEvery = Math.ceil(buckets.length / Math.max(2, Math.floor(plotW / 64)));
  buckets.forEach((b, i) => {
    const x = pad.l + i * slotW + (slotW - barW) / 2;
    let base = height - pad.b;
    const visible = series.filter(ser => num(b.values[ser.key]) > 0);
    visible.forEach((ser, j) => {
      const gap = j > 0 ? 2 : 0;
      const segH = Math.max(0, (num(b.values[ser.key]) / max) * plotH - gap);
      const top = base - gap - segH;
      if (segH > 0) svg(s, "path", {
        d: j === visible.length - 1 ? barPath(x, top, barW, segH) : `M${x},${top}h${barW}v${segH}h${-barW}Z`,
        class: `hc-fill-s${ser.slot}`,
      });
      base = top;
    });
    if (i % labelEvery === 0) {
      svg(s, "text", { x: x + barW / 2, y: height - 6, class: "hc-axis", "text-anchor": "middle" })
        .textContent = tick ? tick(b, i) : b.label;
    }
    const hit = svg(s, "rect", { x: pad.l + i * slotW, y: pad.t, width: slotW, height: plotH, class: "hc-hit" });
    ctx.bindTip(hit, () => [
      { cls: "hc-tip-title", label: b.title ?? b.label },
      ...series.slice().reverse().map(x => ({ slot: series.length > 1 ? x.slot : null, label: x.label, value: format(num(b.values[x.key])) })),
      series.length > 1 && total ? { cls: "hc-tip-total", label: "Total", value: format(totals[i]) } : null,
      ...(tip ? tip(b) : []),
    ], onClick ? onClick(b) : null);
  });
};

// One line over ordered points: [{ label, title, value, tip?: lines[] }]; value domain [lo, hi].
const line = (ctx, card, { points, format = fmt.compact, height = 180, lo, hi, slot = 1 }) => {
  if (points.length < 2) return empty(card, "Needs at least two points; try a longer range.");
  const { s, width } = plotArea(card, height);
  const pad = { t: 12, r: 12, b: 24, l: 44 };
  const vals = points.map(p => p.value);
  lo = lo ?? Math.min(0, ...vals);
  hi = hi ?? niceMax(Math.max(...vals));
  if (hi <= lo) hi = lo + 1;
  const scale = v => height - pad.b - ((v - lo) / (hi - lo)) * (height - pad.t - pad.b);
  yAxis(s, pad, width, height, lo, hi, format);
  const plotW = width - pad.l - pad.r;
  const xs = points.map((_, i) => pad.l + (i * plotW) / (points.length - 1));
  svg(s, "path", { d: points.map((p, i) => `${i ? "L" : "M"}${xs[i]},${scale(p.value)}`).join(""), class: `hc-line hc-stroke-s${slot}` });
  const labelEvery = Math.ceil(points.length / Math.max(2, Math.floor(plotW / 64)));
  points.forEach((p, i) => {
    if (i % labelEvery === 0)
      svg(s, "text", { x: xs[i], y: height - 6, class: "hc-axis", "text-anchor": "middle" }).textContent = p.label;
  });
  const cross = svg(s, "line", { y1: pad.t, y2: height - pad.b, class: "hc-crosshair" });
  const dot = svg(s, "circle", { r: 4.5, class: `hc-dot hc-fill-s${slot}` });
  cross.style.display = dot.style.display = "none";
  const hit = svg(s, "rect", { x: pad.l, y: pad.t, width: plotW, height: height - pad.t - pad.b, class: "hc-hit" });
  hit.addEventListener("mousemove", e => {
    const r = s.getBoundingClientRect();
    const mx = ((e.clientX - r.left) / r.width) * width;
    let i = 0;
    xs.forEach((x, j) => { if (Math.abs(x - mx) < Math.abs(xs[i] - mx)) i = j; });
    const p = points[i];
    cross.setAttribute("x1", xs[i]); cross.setAttribute("x2", xs[i]);
    dot.setAttribute("cx", xs[i]); dot.setAttribute("cy", scale(p.value));
    cross.style.display = dot.style.display = "";
    ctx.tip.show(e, [{ cls: "hc-tip-title", label: p.title ?? p.label }, { label: p.name ?? "Value", value: format(p.value) }, ...(p.tip ?? [])]);
  });
  hit.addEventListener("mouseleave", () => { cross.style.display = dot.style.display = "none"; ctx.tip.hide(); });
};

// GitHub-style calendar, Monday rows, `weeks` columns ending this week.
// cells: Map(isoDate -> { level: 0..4, tip: lines[], onClick?: fn }); days without a cell are blank.
const heatmap = (ctx, card, { cells, weeks = 26, low = "Less", high = "More", end = DateTime.now().startOf("day") }) => {
  const start = end.startOf("week").minus({ weeks: weeks - 1 });
  const host = el(card, "div", "hc-plot");
  const avail = Math.max(260, host.clientWidth || card.clientWidth || 400);
  const left = 26, gap = 2, cell = Math.max(8, Math.min(16, Math.floor((avail - left) / weeks) - gap));
  const width = left + weeks * (cell + gap), height = 16 + 7 * (cell + gap);
  const s = svg(host, "svg", { width, height, viewBox: `0 0 ${width} ${height}`, class: "hc-svg", role: "img" });
  ["Mon", "", "Wed", "", "Fri", "", ""].forEach((d, i) => {
    if (d) svg(s, "text", { x: 0, y: 16 + i * (cell + gap) + cell - 1, class: "hc-axis" }).textContent = d;
  });
  let lastMonth = null;
  for (let w = 0; w < weeks; w++) {
    const weekStart = start.plus({ weeks: w });
    if (weekStart.month !== lastMonth) {
      svg(s, "text", { x: left + w * (cell + gap), y: 10, class: "hc-axis" }).textContent = weekStart.toFormat("LLL");
      lastMonth = weekStart.month;
    }
    for (let d = 0; d < 7; d++) {
      const day = weekStart.plus({ days: d });
      if (day > end) continue;
      const info = cells.get(day.toISODate());
      const r = svg(s, "rect", {
        x: left + w * (cell + gap), y: 16 + d * (cell + gap), width: cell, height: cell, rx: 2,
        class: `hc-heat hc-heat-${info ? info.level : "none"}${day.hasSame(end, "day") ? " is-today" : ""}`,
      });
      ctx.bindTip(r, [{ cls: "hc-tip-title", label: day.toFormat("ccc d LLL yyyy") }, ...(info?.tip ?? [{ cls: "hc-tip-muted", label: "No data" }])],
        info?.onClick ?? null);
    }
  }
  const l = el(card, "div", "hc-legend hc-heat-legend");
  l.appendText(low);
  for (let i = 0; i <= 4; i++) el(l, "span", `hc-heat-key hc-heat-${i}`);
  l.appendText(high);
};
// Map a value to heat levels 0..4 against `peak` (0 stays 0).
const level = (v, peak) => (v <= 0 || peak <= 0 ? 0 : Math.min(4, Math.max(1, Math.ceil((4 * v) / peak))));

// Ranked horizontal bars: rows [{ label, value, title?, tip?: lines[], onClick?: fn, slot? }].
// `sort: false` keeps the given order (for ordinal categories); `limit: 0` shows every row.
const ranked = (ctx, card, { rows, format = fmt.int, slot = 1, limit = 8, other = "Other", sort = true }) => {
  rows = rows.filter(r => r.value > 0);
  if (sort) rows.sort((a, b) => b.value - a.value);
  if (limit && rows.length > limit) {
    const rest = rows.slice(limit);
    rows = [...rows.slice(0, limit), { label: other, value: rest.reduce((a, r) => a + r.value, 0), tip: [{ cls: "hc-tip-muted", label: `${rest.length} more` }] }];
  }
  if (!rows.length) return empty(card, "Nothing in this range.");
  const max = Math.max(...rows.map(r => r.value));
  const sum = rows.reduce((a, r) => a + r.value, 0);
  const list = el(card, "div", "hc-hbars");
  for (const r of rows) {
    const row = el(list, "div", "hc-hbar");
    el(row, "div", "hc-hbar-label", r.label).setAttr("title", r.title ?? r.label);
    const fill = el(el(row, "div", "hc-hbar-track"), "div", `hc-hbar-fill hc-s${r.slot ?? slot}`);
    fill.style.width = `${Math.max(1.5, (100 * r.value) / max)}%`;
    el(row, "div", "hc-hbar-value", format(r.value));
    ctx.bindTip(row, [
      { cls: "hc-tip-title", label: r.title ?? r.label },
      { label: r.name ?? "Value", value: format(r.value) },
      { cls: "hc-tip-muted", label: `${fmt.pct(r.value, sum)} of the total` },
      ...(r.tip ?? []),
    ], r.onClick ?? null);
  }
};

// ---------- run the hub's dashboard ----------
const H = {
  DateTime, num, toDate, el, svg, fmt, open, periods, bucket, periodLabel, tickLabel, level,
  dashboard, head, legend, empty, table, bars, line, heatmap, ranked,
};
let code;
try {
  code = await app.vault.adapter.read(`${BASE}/${hubName}.js`);
} catch {
  dv.paragraph(`hub-charts: no dashboard at \`${BASE}/${hubName}.js\`.`);
  return;
}
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
try {
  await new AsyncFunction("dv", "input", "H", code)(dv, input, H);
} catch (err) {
  console.error(`hub-charts/${hubName}`, err);
  dv.paragraph(`hub-charts: the \`${hubName}\` dashboard failed: ${err.message}`);
}
