// Task dashboard for the Task Hub.
// In the hub:  await dv.view("Templates/Views/hub-charts", { hub: "tasks" })
// Reads `type: task` notes under Tasks/. Properties: status (To Do, In Progress, Done, Won't Do;
// an emoji prefix is fine), project, story points, dateModified. Also reads the Tasks-plugin
// checkboxes in those notes: ✅ dates give completed subtasks, 📅 dates give what's due.

const { DateTime, num, fmt, open } = H;
const today = DateTime.now().startOf("day");

// `match` is compared after dropping everything but letters, so "To Do", "to-do" and "📋 To do" all match.
const STATUSES = [
  { match: "inprogress", label: "🚧 In Progress", slot: 1 },
  { match: "todo", label: "📋 To Do", slot: 2 },
  { match: "done", label: "✅ Done", slot: 3 },
  { match: "wontdo", label: "🚫 Won't Do", slot: 4 },
];
const norm = s => String(s ?? "").toLowerCase().replace(/[^a-z]/g, "");
const statusOf = s => STATUSES.find(x => norm(s) === x.match) ?? null;

const tickets = dv.pages('"Tasks"')
  .where(p => String(p.type ?? "").toLowerCase() === "task")
  .array()
  .map(p => {
    const tasks = p.file.tasks.array ? p.file.tasks.array() : [...p.file.tasks];
    return {
      path: p.file.path,
      name: p.file.name,
      status: statusOf(p.status),
      project: String(p.project ?? "").trim() || "(none)",
      points: num(p["story points"]),
      modified: H.toDate(p.dateModified) ?? p.file.mtime,
      tasks: tasks.map(t => ({ ...t, ticket: p.file.path, ticketName: p.file.name, project: String(p.project ?? "").trim() || "(none)" })),
    };
  });
if (!tickets.length) {
  dv.paragraph("No `type: task` notes under `Tasks/` yet.");
  return;
}
const subtasks = tickets.flatMap(t => t.tasks);
const done = subtasks.filter(t => t.completed && t.completion).map(t => ({ ...t, when: H.toDate(t.completion) }));
const openTasks = subtasks.filter(t => !t.checked);
const due = t => (t.due ? H.toDate(t.due)?.startOf("day") : null);

const ctx = H.dashboard({ defaults: { range: "26" } });
const { state } = ctx;
const weeks = () => Number(state.range);
const rangeStart = () => today.startOf("week").minus({ weeks: weeks() - 1 });

// Projects get fixed slots by all-time ticket count, so a project keeps its colour across ranges.
const projectRank = [...tickets.reduce((m, t) => m.set(t.project, (m.get(t.project) ?? 0) + 1), new Map())]
  .sort((a, b) => b[1] - a[1]).map(([p]) => p);
const TOP = projectRank.slice(0, 4);
const PROJECT_SERIES = [...TOP.map((p, i) => ({ key: p, label: p, slot: i + 1 })), { key: "Other", label: "Other", slot: 5 }];
const projectKey = p => (TOP.includes(p) ? p : "Other");

// ---------- tiles ----------
const count = m => tickets.filter(t => t.status?.match === m);
const overdue = openTasks.filter(t => due(t) && due(t) < today);
const weekStart = today.startOf("week");
const doneThisWeek = done.filter(t => t.when >= weekStart);
const inProgress = count("inprogress");
ctx.tiles(null, [
  { value: inProgress.length, label: "In progress", sub: inProgress.slice(0, 2).map(t => t.name).join(" · "),
    onClick: inProgress.length ? e => open(inProgress[0].path, e) : null },
  { value: count("todo").length, label: "To do", tone: "2" },
  { value: openTasks.length, label: "Open subtasks", sub: overdue.length ? `${overdue.length} overdue` : "none overdue",
    tone: overdue.length ? "warn" : "3" },
  { value: doneThisWeek.length, label: "Subtasks done this week", sub: `${done.filter(t => t.when >= weekStart.minus({ weeks: 1 }) && t.when < weekStart).length} last week`, tone: "live" },
  { value: count("done").length, label: "Tickets done", sub: `${fmt.int(count("done").reduce((a, t) => a + t.points, 0))} story points`, tone: "4" },
]);

ctx.controls([{ label: "Range", key: "range", options: [["12", "12 weeks"], ["26", "26 weeks"], ["52", "1 year"]] }]);

// ---------- subtasks done per week ----------
ctx.chart(null, card => {
  H.head(card, "Subtasks done per week", "Checkboxes in task notes by their ✅ date, split by the task's project. Click a week to open its busiest ticket.");
  const buckets = H.bucket(done, t => t.when, "week", rangeStart(), today,
    () => ({ values: Object.fromEntries(PROJECT_SERIES.map(s => [s.key, 0])) }),
    (b, t) => { b.items.push(t); b.values[projectKey(t.project)] += 1; })
    .map(b => ({ ...b, label: b.start.toFormat("d LLL"), title: H.periodLabel(b.start, "week") }));
  H.bars(ctx, card, {
    buckets, series: PROJECT_SERIES, format: fmt.int, height: 210,
    tip: b => {
      const per = b.items.reduce((m, t) => m.set(t.ticketName, (m.get(t.ticketName) ?? 0) + 1), new Map());
      const top = [...per].sort((x, y) => y[1] - x[1])[0];
      return top ? [{ cls: "hc-tip-muted", label: `Most: ${top[0]} (${top[1]})` }] : [];
    },
    onClick: b => {
      const per = b.items.reduce((m, t) => m.set(t.ticket, (m.get(t.ticket) ?? 0) + 1), new Map());
      const top = [...per].sort((x, y) => y[1] - x[1])[0];
      return top ? e => open(top[0], e) : null;
    },
  });
  H.table(card, ["Week", ...PROJECT_SERIES.map(s => s.label)],
    buckets.slice().reverse().filter(b => b.items.length).map(b => [b.start.toISODate(), ...PROJECT_SERIES.map(s => b.values[s.key])]));
}, { wide: true });

const grid1 = ctx.grid();
// ---------- completion calendar ----------
ctx.chart(grid1, card => {
  H.head(card, "Completion calendar", "Subtasks ticked per day, last 26 weeks. Click a day to open the ticket with the most.");
  const perDay = new Map();
  for (const t of done) {
    const k = t.when.toISODate();
    const d = perDay.get(k) ?? { n: 0, tickets: new Map() };
    d.n += 1;
    d.tickets.set(t.ticket, (d.tickets.get(t.ticket) ?? 0) + 1);
    perDay.set(k, d);
  }
  const peak = Math.max(1, ...[...perDay.values()].map(d => d.n));
  const cells = new Map();
  for (const [k, d] of perDay) {
    const top = [...d.tickets].sort((a, b) => b[1] - a[1])[0];
    cells.set(k, {
      level: H.level(d.n, peak),
      tip: [{ label: "Subtasks done", value: d.n }, { cls: "hc-tip-muted", label: `${d.tickets.size} tickets` }],
      onClick: e => open(top[0], e),
    });
  }
  for (let d = today.startOf("week").minus({ weeks: 25 }); d <= today; d = d.plus({ days: 1 }))
    if (!cells.has(d.toISODate())) cells.set(d.toISODate(), { level: 0, tip: [{ label: "Subtasks done", value: 0 }] });
  H.heatmap(ctx, card, { cells, low: "Fewer", high: `More (peak ${peak}/day)` });
});

// ---------- open subtasks by ticket ----------
ctx.chart(grid1, card => {
  H.head(card, "Open subtasks by ticket", "Unticked checkboxes per task note. Click to open the ticket.");
  const rows = tickets.map(t => {
    const list = t.tasks.filter(x => !x.checked);
    const late = list.filter(x => due(x) && due(x) < today).length;
    return {
      label: t.name, value: list.length, name: "Open subtasks",
      slot: PROJECT_SERIES.find(s => s.key === projectKey(t.project)).slot,
      tip: [{ label: "Status", value: t.status?.label ?? "–" }, { label: "Project", value: t.project },
        late ? { label: "Overdue", value: late } : null],
      onClick: e => open(t.path, e),
    };
  });
  H.ranked(ctx, card, { rows, limit: 8 });
});

const grid2 = ctx.grid();
// ---------- by project ----------
ctx.chart(grid2, card => {
  H.head(card, "Tickets by project", "All task notes. Hover for the status split; click to open the newest ticket.");
  const rows = projectRank.map(p => {
    const list = tickets.filter(t => t.project === p);
    const newest = list.slice().sort((a, b) => b.modified - a.modified)[0];
    return {
      label: p, value: list.length, name: "Tickets",
      slot: PROJECT_SERIES.find(s => s.key === projectKey(p)).slot,
      tip: STATUSES.map(s => ({ slot: s.slot, label: s.label, value: list.filter(t => t.status === s).length })).filter(x => x.value),
      onClick: e => open(newest.path, e),
    };
  });
  H.ranked(ctx, card, { rows, limit: 8 });
});

// ---------- story points ----------
ctx.chart(grid2, card => {
  H.head(card, "Story points by project", "Sum of `story points` on done tickets; open tickets in the tooltip.");
  const rows = projectRank.map(p => {
    const list = tickets.filter(t => t.project === p && t.points);
    const sum = st => list.filter(t => t.status?.match === st).reduce((a, t) => a + t.points, 0);
    return {
      label: p, value: sum("done"), name: "Done points", slot: PROJECT_SERIES.find(s => s.key === projectKey(p)).slot,
      tip: [{ label: "In progress or to do", value: sum("inprogress") + sum("todo") }, { cls: "hc-tip-muted", label: `${list.length} pointed tickets` }],
    };
  });
  H.ranked(ctx, card, { rows, limit: 8 });
});

ctx.start();
