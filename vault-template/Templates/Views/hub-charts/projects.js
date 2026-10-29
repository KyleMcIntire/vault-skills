// Project dashboard for the Project Hub.
// In the hub:  await dv.view("Templates/Views/hub-charts", { hub: "projects" })
// Reads notes under Projects/ with `type: project` (any case) and a `status`. Properties:
// status (🟢 Active, 🧪 Planning, 💡 Idea, ⏸️ Paused, ✅ Done), category, title, reviewed. Notes
// with `type: doc` (sub-items of a project, with `workstream`) get their own "Items" scope.
// Also reads every Tasks-plugin checkbox under Projects/, grouped by the project folder.

const { DateTime, fmt, open } = H;
const today = DateTime.now().startOf("day");
const STALE_DAYS = 30;

const STATUSES = ["🟢 Active", "🧪 Planning", "💡 Idea", "⏸️ Paused", "✅ Done"];
const OPEN = new Set(["🟢 Active", "🧪 Planning"]);

const pages = dv.pages('"Projects"').array();
const folderOf = p => p.file.path.split("/")[1]?.replace(/\.md$/, "") ?? "Projects";
const notes = pages
  .filter(p => ["project", "doc"].includes(String(p.type ?? "").toLowerCase()) && p.status)
  .map(p => ({
    path: p.file.path,
    title: String(p.title ?? p.file.name),
    item: String(p.type).toLowerCase() === "doc",
    status: String(p.status).trim(),
    group: String((String(p.type).toLowerCase() === "doc" ? p.workstream : p.category) ?? "").trim() || "(none)",
    folder: folderOf(p),
    reviewed: H.toDate(p.reviewed),
  }));
if (!notes.length) {
  dv.paragraph("No project notes with a `status` under `Projects/` yet.");
  return;
}
// Each folder's main note: its `type: project` note, else the first note in it.
const mainNote = new Map();
for (const n of notes) if (!n.item && !mainNote.has(n.folder)) mainNote.set(n.folder, n);
const tasks = pages.flatMap(p => (p.file.tasks.array ? p.file.tasks.array() : [...p.file.tasks]).map(t => ({ ...t, folder: folderOf(p), note: p.file.path })));
const done = tasks.filter(t => t.completed && t.completion).map(t => ({ ...t, when: H.toDate(t.completion) }));
const openTasks = tasks.filter(t => !t.checked);

const ctx = H.dashboard({ defaults: { range: "12", scope: "projects" } });
const { state } = ctx;
const scoped = () => notes.filter(n => n.item === (state.scope === "items"));
const ageOf = n => (n.reviewed ? Math.round(today.diff(n.reviewed.startOf("day"), "days").days) : null);

// ---------- tiles ----------
const projects = notes.filter(n => !n.item);
const stale = notes.filter(n => OPEN.has(n.status) && (ageOf(n) ?? Infinity) > STALE_DAYS);
const weekStart = today.startOf("week");
ctx.tiles(null, [
  { value: projects.filter(n => OPEN.has(n.status)).length, label: "Open projects", sub: `${projects.filter(n => n.status === "🟢 Active").length} active · ${projects.filter(n => n.status === "🧪 Planning").length} planning` },
  { value: notes.filter(n => n.item && OPEN.has(n.status)).length, label: "Open sub-items", tone: "2" },
  { value: openTasks.length, label: "Open tasks", sub: `${openTasks.filter(t => t.due && H.toDate(t.due) < today).length} overdue`, tone: "3" },
  { value: done.filter(t => t.when >= weekStart).length, label: "Tasks done this week", sub: `${done.filter(t => t.when >= weekStart.minus({ weeks: 1 }) && t.when < weekStart).length} last week`, tone: "live" },
  { value: stale.length, label: `Not reviewed in ${STALE_DAYS} days`, tone: stale.length ? "warn" : "idle",
    sub: stale.slice(0, 2).map(n => n.title).join(" · ") || "everything open is fresh",
    onClick: stale.length ? e => open(stale[0].path, e) : null },
  { value: projects.filter(n => n.status === "✅ Done").length, label: "Projects done", tone: "4" },
]);

ctx.controls([
  { label: "Range", key: "range", options: [["12", "12 weeks"], ["26", "26 weeks"], ["52", "1 year"]] },
  { label: "Notes", key: "scope", options: [["projects", "Projects"], ["items", "Items"]] },
]);

// Folders get fixed slots by all-time completed tasks.
const folderRank = [...done.reduce((m, t) => m.set(t.folder, (m.get(t.folder) ?? 0) + 1), new Map())]
  .sort((a, b) => b[1] - a[1]).map(([f]) => f);
const TOP = folderRank.slice(0, 4);
const FOLDERS = [...TOP.map((f, i) => ({ key: f, label: f, slot: i + 1 })), { key: "Other", label: "Other", slot: 5 }];
const folderKey = f => (TOP.includes(f) ? f : "Other");

// ---------- tasks done per week ----------
ctx.chart(null, card => {
  H.head(card, "Tasks done per week", "Checkboxes anywhere under Projects/ by their ✅ date, split by project folder. Click a week to open its busiest project.");
  const start = today.startOf("week").minus({ weeks: Number(state.range) - 1 });
  const buckets = H.bucket(done, t => t.when, "week", start, today,
    () => ({ values: Object.fromEntries(FOLDERS.map(f => [f.key, 0])) }),
    (b, t) => { b.items.push(t); b.values[folderKey(t.folder)] += 1; })
    .map(b => ({ ...b, label: b.start.toFormat("d LLL"), title: H.periodLabel(b.start, "week") }));
  const busiest = b => [...b.items.reduce((m, t) => m.set(t.folder, (m.get(t.folder) ?? 0) + 1), new Map())].sort((x, y) => y[1] - x[1])[0];
  H.bars(ctx, card, {
    buckets, series: FOLDERS, format: fmt.int, height: 200,
    tip: b => { const top = busiest(b); return top ? [{ cls: "hc-tip-muted", label: `Most: ${top[0]} (${top[1]})` }] : []; },
    onClick: b => { const top = busiest(b); const n = top && mainNote.get(top[0]); return n ? e => open(n.path, e) : null; },
  });
  H.table(card, ["Week", ...FOLDERS.map(f => f.label)],
    buckets.slice().reverse().filter(b => b.items.length).map(b => [b.start.toISODate(), ...FOLDERS.map(f => b.values[f.key])]));
}, { wide: true });

const grid1 = ctx.grid();
// ---------- status ----------
ctx.chart(grid1, card => {
  const items = state.scope === "items";
  H.head(card, items ? "Items by status" : "Projects by status", "Hover for the names.");
  const list = scoped();
  const rows = STATUSES.map(s => {
    const withIt = list.filter(n => n.status === s);
    return { label: s, value: withIt.length, name: items ? "Items" : "Projects",
      tip: withIt.slice(0, 5).map(n => ({ cls: "hc-tip-muted", label: n.title })),
      onClick: withIt.length ? e => open(withIt[0].path, e) : null };
  });
  H.ranked(ctx, card, { rows, sort: false, limit: 0 });
});

// ---------- category or workstream ----------
ctx.chart(grid1, card => {
  const items = state.scope === "items";
  H.head(card, items ? "Items by workstream" : "Projects by category", items ? "`workstream` on items." : "`category` on project notes.");
  const counts = new Map();
  for (const n of scoped()) counts.set(n.group, (counts.get(n.group) ?? 0) + 1);
  H.ranked(ctx, card, { rows: [...counts].map(([label, value]) => ({ label, value, name: "Notes" })) });
});

const grid2 = ctx.grid();
// ---------- open tasks by project ----------
ctx.chart(grid2, card => {
  H.head(card, "Open tasks by project", "Unticked checkboxes per project folder. Click to open the project.");
  const counts = new Map();
  for (const t of openTasks) counts.set(t.folder, (counts.get(t.folder) ?? 0) + 1);
  H.ranked(ctx, card, {
    rows: [...counts].map(([f, value]) => {
      const n = mainNote.get(f);
      return { label: f, value, name: "Open tasks", slot: FOLDERS.find(x => x.key === folderKey(f)).slot,
        tip: n ? [{ label: "Status", value: n.status }] : [], onClick: n ? e => open(n.path, e) : null };
    }),
  });
});

// ---------- review freshness ----------
ctx.chart(grid2, card => {
  H.head(card, "Days since review", `Open ${state.scope === "items" ? "items" : "projects"}, stalest first; over ${STALE_DAYS} days is due a look.`);
  const rows = scoped().filter(n => OPEN.has(n.status)).map(n => {
    const age = ageOf(n);
    return { label: n.title, value: age ?? 999, name: "Days",
      tip: [{ label: "Status", value: n.status }, { label: "Reviewed", value: n.reviewed ? n.reviewed.toISODate() : "never" }],
      onClick: e => open(n.path, e) };
  });
  // Reviewed today is still worth listing; give it a sliver.
  for (const r of rows) if (r.value === 0) r.value = 0.4;
  H.ranked(ctx, card, { rows, format: v => (v >= 999 ? "never ⚠" : `${Math.round(v)} d${v > STALE_DAYS ? " ⚠" : ""}`), limit: 10 });
});

ctx.start();
