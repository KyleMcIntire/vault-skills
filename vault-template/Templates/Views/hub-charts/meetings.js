// Meeting dashboard for the Meeting Hub.
// In the hub:  await dv.view("Templates/Views/hub-charts", { hub: "meetings" })
// Reads `type: meeting` notes under Meetings/. Properties: date, title, meeting type
// (standup, planning, review, other), project, duration (minutes), status (a status containing
// "Waiting" counts as waiting on others). Also reads the Tasks-plugin checkboxes in them.

const { DateTime, num, fmt, open } = H;
const today = DateTime.now().startOf("day");

const meetings = dv.pages('"Meetings"')
  .where(p => ["meeting", "meeting-transcript"].includes(String(p.type ?? "")) && p.date)
  .array()
  .map(p => ({
    path: p.file.path,
    title: String(p.title ?? p.file.name),
    date: H.toDate(p.date)?.startOf("day"),
    kind: String(p["meeting type"] ?? "").trim() || "other",
    project: String(p.project ?? "").trim() || "(none)",
    minutes: num(p.duration),
    status: String(p.status ?? "").trim(),
    tasks: p.file.tasks.array ? p.file.tasks.array() : [...p.file.tasks],
  }))
  .filter(m => m.date?.isValid);
if (!meetings.length) {
  dv.paragraph("No dated `type: meeting` notes under `Meetings/` yet.");
  return;
}

const KINDS = [
  { key: "standup", label: "Standup", slot: 1 },
  { key: "planning", label: "Planning", slot: 2 },
  { key: "review", label: "Review", slot: 3 },
  { key: "other", label: "Other", slot: 4 },
];
const kindKey = k => (KINDS.some(x => x.key === k) ? k : "other");

const ctx = H.dashboard({ defaults: { range: "30", measure: "count" } });
const { state } = ctx;
const unit = () => (state.range === "30" ? "day" : "week");
const rangeStart = () => state.range === "all"
  ? meetings.reduce((m, x) => (x.date < m ? x.date : m), today).startOf("week")
  : today.minus({ days: Number(state.range) - 1 }).startOf(unit());
const measure = m => (state.measure === "minutes" ? m.minutes : 1);
const measureFmt = v => (state.measure === "minutes" ? fmt.hours(v) : fmt.int(v));
const inRange = () => meetings.filter(m => m.date >= rangeStart() && m.date <= today);

// ---------- tiles ----------
const weekStart = today.startOf("week");
const thisWeek = meetings.filter(m => m.date >= weekStart && m.date <= today);
const waiting = meetings.filter(m => m.status.includes("Waiting")).sort((a, b) => a.date - b.date);
const actions = meetings.flatMap(m => m.tasks);
const timed = meetings.filter(m => m.minutes);
ctx.tiles(null, [
  { value: thisWeek.length, label: "Meetings this week", sub: `${meetings.filter(m => m.date >= weekStart.minus({ weeks: 1 }) && m.date < weekStart).length} last week` },
  { value: fmt.hours(thisWeek.reduce((a, m) => a + m.minutes, 0)), label: "In meetings this week", tone: "2" },
  { value: waiting.length, label: "Waiting on others", tone: waiting.length ? "4" : "idle",
    sub: waiting.slice(0, 2).map(m => m.title).join(" · ") || "nothing outstanding",
    onClick: waiting.length ? e => open(waiting[0].path, e) : null },
  { value: actions.filter(t => !t.checked).length, label: "Open action items", sub: `${actions.filter(t => t.completed).length} done`, tone: "3" },
  timed.length ? { value: fmt.hours(timed.reduce((a, m) => a + m.minutes, 0) / timed.length), label: "Average length", sub: `${timed.length} timed meetings` } : null,
]);

ctx.controls([
  { label: "Range", key: "range", options: [["30", "30 days"], ["90", "90 days"], ["all", "All time"]] },
  { label: "Measure", key: "measure", options: [["count", "Meetings"], ["minutes", "Time"]] },
]);

// ---------- meetings over time ----------
ctx.chart(null, card => {
  H.head(card, `${state.measure === "minutes" ? "Time in meetings" : "Meetings"} per ${unit()}`, "By `meeting type`. Click a bar to open its longest meeting.");
  const buckets = H.bucket(meetings, m => m.date, unit(), rangeStart(), today,
    () => ({ values: Object.fromEntries(KINDS.map(k => [k.key, 0])) }),
    (b, m) => { b.items.push(m); b.values[kindKey(m.kind)] += measure(m); })
    .map(b => ({ ...b, label: H.tickLabel(b.start, unit()), title: H.periodLabel(b.start, unit()) }));
  H.bars(ctx, card, {
    buckets, series: KINDS, format: measureFmt, height: 200,
    tip: b => b.items.slice(0, 4).map(m => ({ cls: "hc-tip-muted", label: `${m.title}${m.minutes ? ` (${m.minutes} min)` : ""}` })),
    onClick: b => {
      const top = b.items.slice().sort((x, y) => y.minutes - x.minutes)[0];
      return top ? e => open(top.path, e) : null;
    },
  });
  H.table(card, [unit() === "day" ? "Day" : "Week", ...KINDS.map(k => k.label)],
    buckets.slice().reverse().filter(b => b.items.length).map(b => [b.start.toISODate(), ...KINDS.map(k => measureFmt(b.values[k.key]))]));
}, { wide: true });

const grid1 = ctx.grid();
// ---------- by type ----------
ctx.chart(grid1, card => {
  H.head(card, "By meeting type", `${state.range === "all" ? "All time" : `Last ${state.range} days`}; every \`meeting type\` value.`);
  const totals = new Map();
  for (const m of inRange()) totals.set(m.kind, (totals.get(m.kind) ?? 0) + measure(m));
  H.ranked(ctx, card, {
    rows: [...totals].map(([k, value]) => ({ label: k, value, slot: KINDS.find(x => x.key === kindKey(k)).slot,
      name: state.measure === "minutes" ? "Time" : "Meetings" })),
    format: measureFmt,
  });
});

// ---------- by project ----------
ctx.chart(grid1, card => {
  H.head(card, "By project", "`project` on the meeting note.");
  const totals = new Map();
  for (const m of inRange()) totals.set(m.project, (totals.get(m.project) ?? 0) + measure(m));
  H.ranked(ctx, card, { rows: [...totals].map(([label, value]) => ({ label, value, name: state.measure === "minutes" ? "Time" : "Meetings" })), format: measureFmt });
});

const grid2 = ctx.grid();
// ---------- waiting on others ----------
ctx.chart(grid2, card => {
  H.head(card, "Waiting on others", "Meetings still marked ⌛, oldest first, by days since the meeting. Click to open.");
  H.ranked(ctx, card, {
    rows: waiting.map(m => ({ label: m.title, value: Math.max(0.4, today.diff(m.date, "days").days), name: "Days waiting",
      tip: [{ label: "Met", value: m.date.toISODate() }, { label: "Project", value: m.project }], onClick: e => open(m.path, e) })),
    format: v => `${Math.round(v)} d`, sort: false, limit: 0,
  });
});

// ---------- action items ----------
ctx.chart(grid2, card => {
  H.head(card, "Action items done per week", "Checkboxes in meeting notes by their ✅ date.");
  const done = actions.filter(t => t.completed && t.completion).map(t => ({ when: H.toDate(t.completion) }));
  const start = state.range === "30" ? today.startOf("week").minus({ weeks: 7 }) : rangeStart().startOf("week");
  const buckets = H.bucket(done, t => t.when, "week", start, today, () => ({ values: { n: 0 } }), (b) => { b.values.n += 1; })
    .map(b => ({ ...b, label: b.start.toFormat("d LLL"), title: H.periodLabel(b.start, "week") }));
  H.bars(ctx, card, { buckets, series: [{ key: "n", label: "Action items done", slot: 3 }], format: fmt.int, height: 170 });
});

ctx.start();
