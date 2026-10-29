// Vault stats dashboard for Home.
// Properties read: none. It uses file metadata (path, last-modified time) and Tasks-plugin checkboxes
// (✅ completion dates, 📅 due dates) from every note except those under Templates/.
// In the note:  await dv.view("Templates/Views/hub-charts", { hub: "home" })
// Counts every note Dataview indexes, by top-level folder ("area"), with edits by each
// note's last-modified time and tasks by their ✅ date, so an older edit to a note that
// was changed again later isn't counted.

const { DateTime, fmt, open } = H;
const today = DateTime.now().startOf("day");

const pages = dv.pages('""').array();
const areaOf = p => (p.file.path.includes("/") ? p.file.path.split("/")[0] : "Root");
const notes = pages.map(p => ({ path: p.file.path, name: p.file.name, area: areaOf(p), mtime: p.file.mtime }));
const tasks = pages.flatMap(p => (p.file.tasks.array ? p.file.tasks.array() : [...p.file.tasks])
  .filter(t => !p.file.path.startsWith("Templates/")).map(t => ({ ...t, area: areaOf(p) })));
const done = tasks.filter(t => t.completed && t.completion).map(t => ({ ...t, when: H.toDate(t.completion) }));

const ctx = H.dashboard({ defaults: { range: "14" } });
const { state } = ctx;

// Areas get fixed slots by note count, so an area keeps its colour across charts and ranges.
const areaRank = [...notes.reduce((m, n) => m.set(n.area, (m.get(n.area) ?? 0) + 1), new Map())].sort((a, b) => b[1] - a[1]);
const TOP = areaRank.slice(0, 5).map(([a]) => a);
const AREAS = [...TOP.map((a, i) => ({ key: a, label: a, slot: i + 1 })), { key: "Other", label: "Other", slot: 6 }];
const areaKey = a => (TOP.includes(a) ? a : "Other");

// ---------- tiles ----------
const editedSince = d => notes.filter(n => n.mtime >= d);
const openTasks = tasks.filter(t => !t.checked);
const overdue = openTasks.filter(t => t.due && H.toDate(t.due) < today);
const weekStart = today.startOf("week");
ctx.tiles(null, [
  { value: fmt.int(notes.length), label: "Notes", sub: `${areaRank.length} areas` },
  { value: editedSince(today).length, label: "Edited today", sub: `${editedSince(today.minus({ days: 6 })).length} in the last 7 days`, tone: "live" },
  { value: fmt.int(openTasks.length), label: "Open tasks", sub: `${overdue.length} overdue`, tone: overdue.length ? "warn" : "3" },
  { value: done.filter(t => t.when >= today).length, label: "Tasks done today", sub: `${done.filter(t => t.when >= weekStart).length} this week`, tone: "2" },
]);

ctx.controls([{ label: "Range", key: "range", options: [["14", "14 days"], ["30", "30 days"], ["90", "90 days"]] }]);

const grid1 = ctx.grid();
// ---------- notes by area ----------
ctx.chart(grid1, card => {
  H.head(card, "Notes by area", "Top-level folders; the five biggest keep their colours in the other charts.");
  H.ranked(ctx, card, {
    rows: areaRank.map(([a, value]) => ({ label: a, value, name: "Notes", slot: AREAS.find(x => x.key === areaKey(a)).slot })),
    limit: 10,
  });
});

// ---------- notes edited per day ----------
ctx.chart(grid1, card => {
  H.head(card, "Notes edited per day", "By each note's last-modified time, split by area. Click a day to open its latest edit.");
  const unit = state.range === "90" ? "week" : "day";
  const buckets = H.bucket(notes, n => n.mtime, unit, today.minus({ days: Number(state.range) - 1 }), DateTime.now(),
    () => ({ values: Object.fromEntries(AREAS.map(a => [a.key, 0])) }),
    (b, n) => { b.items.push(n); b.values[areaKey(n.area)] += 1; })
    .map(b => ({ ...b, label: H.tickLabel(b.start, unit), title: H.periodLabel(b.start, unit) }));
  H.bars(ctx, card, {
    buckets, series: AREAS, format: fmt.int, height: 200,
    onClick: b => {
      const last = b.items.slice().sort((x, y) => y.mtime - x.mtime)[0];
      return last ? e => open(last.path, e) : null;
    },
  });
});

// ---------- tasks done per week ----------
ctx.chart(null, card => {
  H.head(card, "Tasks done per week", "Every checkbox in the vault by its ✅ date (templates excluded), split by area.");
  const weeks = Math.max(8, Math.ceil(Number(state.range) / 7));
  const buckets = H.bucket(done, t => t.when, "week", today.startOf("week").minus({ weeks: weeks - 1 }), today,
    () => ({ values: Object.fromEntries(AREAS.map(a => [a.key, 0])) }),
    (b, t) => { b.values[areaKey(t.area)] += 1; })
    .map(b => ({ ...b, label: b.start.toFormat("d LLL"), title: H.periodLabel(b.start, "week") }));
  H.bars(ctx, card, { buckets, series: AREAS, format: fmt.int, height: 190 });
  H.table(card, ["Week", ...AREAS.map(a => a.label)],
    buckets.slice().reverse().map(b => [b.start.toISODate(), ...AREAS.map(a => b.values[a.key])]));
}, { wide: true });

ctx.start();
