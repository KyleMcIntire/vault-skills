// Mood and task dashboard for the Daily Notes Hub.
// In the hub:  await dv.view("Templates/Views/hub-charts", { hub: "daily" })
// Reads notes under Daily Notes/ with `type: Daily Note`. Properties: date (YYYY-MM-DD, falls back
// to the file name) and mood (one of the values in MOODS below). Also reads the Tasks-plugin
// checkboxes in those notes: ✅ completion dates, and the #work tag to split the weekly bars.

const { DateTime, fmt } = H;
const today = DateTime.now().startOf("day");

const notes = dv.pages('"Daily Notes"')
  .where(p => String(p.type ?? "") === "Daily Note")
  .array()
  .map(p => {
    const date = H.toDate(p.date) ?? DateTime.fromISO(p.file.name);
    if (!date?.isValid) return null;
    const tasks = [...(p.file.tasks.array ? p.file.tasks.array() : p.file.tasks)];
    return { path: p.file.path, date: date.startOf("day"), mood: String(p.mood ?? "").trim(), tasks };
  })
  .filter(Boolean);
if (!notes.length) {
  dv.paragraph("No daily notes with `type: Daily Note` yet.");
  return;
}
const byDay = new Map(notes.map(n => [n.date.toISODate(), n]));

const ctx = H.dashboard({ defaults: { range: "30" } });
const { state } = ctx;
const days = () => Number(state.range);
const rangeStart = () => today.minus({ days: days() - 1 });

// ---------- tiles ----------
const todayNote = byDay.get(today.toISODate());
const weekStart = today.startOf("week");
const tasksThisWeek = notes.flatMap(n => n.tasks).filter(t => t.completed && t.completion && H.toDate(t.completion) >= weekStart);
const moodNote = todayNote?.mood ? todayNote : notes.filter(n => n.mood && n.date <= today).sort((a, b) => b.date - a.date)[0];
ctx.tiles(null, [
  { value: tasksThisWeek.length, label: "Tasks done this week", sub: `${tasksThisWeek.filter(t => t.tags?.includes("#work")).length} tagged #work`, tone: "2" },
  moodNote ? { value: moodNote.mood, label: moodNote === todayNote ? "Mood today" : `Mood · ${moodNote.date.toFormat("d LLL")}`, tone: "4" } : null,
]);

ctx.controls([{ label: "Range", key: "range", options: [["30", "30 days"], ["90", "90 days"], ["365", "1 year"]] }]);

const grid = ctx.grid();
// ---------- mood by month ----------
// Edit this list to match the moods you use in the `mood` property.
const MOODS = [
  { key: "✅ Good", label: "✅ Good", slot: 1 },
  { key: "👍 Normal", label: "👍 Normal", slot: 2 },
  { key: "🥱 Tired", label: "🥱 Tired", slot: 3 },
  { key: "😬 Anxious", label: "😬 Anxious", slot: 4 },
  { key: "😞 Rough", label: "😞 Rough", slot: 5 },
];
ctx.chart(grid, card => {
  H.head(card, "Mood by month", "Days logged with each mood, last 12 months. Days without a mood are left out.");
  const known = new Set(MOODS.map(m => m.key));
  const buckets = H.bucket(notes.filter(n => known.has(n.mood)), n => n.date, "month", today.startOf("month").minus({ months: 11 }), today,
    () => ({ values: Object.fromEntries(MOODS.map(m => [m.key, 0])) }), (b, n) => { b.values[n.mood] += 1; })
    .map(b => ({ ...b, label: b.start.toFormat("LLL"), title: H.periodLabel(b.start, "month") }));
  H.bars(ctx, card, { buckets, series: MOODS, format: fmt.int, height: 190 });
  const other = notes.filter(n => n.mood && !known.has(n.mood)).length;
  if (other) H.empty(card, `${other} days use another mood value.`);
});

// ---------- tasks done per week ----------
const KINDS = [{ key: "work", label: "#work", slot: 1 }, { key: "personal", label: "Other", slot: 2 }];
ctx.chart(grid, card => {
  H.head(card, "Tasks done per week", "Tasks in daily notes, by their ✅ date.");
  const done = notes.flatMap(n => n.tasks).filter(t => t.completed && t.completion);
  const start = state.range === "30" ? today.startOf("week").minus({ weeks: 7 }) : rangeStart().startOf("week");
  const buckets = H.bucket(done, t => H.toDate(t.completion), "week", start, today,
    () => ({ values: { work: 0, personal: 0 } }), (b, t) => { b.values[t.tags?.includes("#work") ? "work" : "personal"] += 1; })
    .map(b => ({ ...b, label: b.start.toFormat("d LLL"), title: H.periodLabel(b.start, "week") }));
  H.bars(ctx, card, { buckets, series: KINDS, format: fmt.int, height: 190 });
});

ctx.start();
