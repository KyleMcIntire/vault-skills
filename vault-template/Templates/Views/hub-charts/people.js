// People dashboard for the People Hub.
// In the hub:  await dv.view("Templates/Views/hub-charts", { hub: "people" })
// Reads notes tagged #person under People/ (not the one with `relationship: me`).
// Properties: name, relationship (coworker, manager, family, friend, other), location, role
// (the team, for coworkers and managers), image. Edit CIRCLES to add your own relationships.

const { fmt, open } = H;
const CIRCLES = {
  coworker: "Work", manager: "Work", family: "Family", friend: "Friends", other: "Other",
};

const people = dv.pages('#person and "People"')
  .where(p => p.relationship != "me")
  .array()
  .map(p => {
    const relationship = String(p.relationship ?? "").trim().toLowerCase();
    return {
      path: p.file.path,
      name: String(p.name ?? p.file.name),
      circle: CIRCLES[relationship] ?? "Other",
      work: relationship === "coworker" || relationship === "manager",
      location: String(p.location ?? "").trim() || "Unknown",
      team: String(p.role ?? "").trim() || "(no team)",
      photo: !!p.image,
    };
  });
if (!people.length) {
  dv.paragraph("No `#person` notes under `People/` yet.");
  return;
}

const ctx = H.dashboard();
const work = people.filter(p => p.work);
const inCircle = c => people.filter(p => p.circle === c).length;
const withPhoto = people.filter(p => p.photo).length;
ctx.tiles(null, [
  { value: fmt.int(people.length), label: "People", sub: `${new Set(people.map(p => p.circle)).size} circles` },
  { value: fmt.int(work.length), label: "Work circle", sub: `${new Set(work.map(p => p.team)).size} teams`, tone: "2" },
  { value: inCircle("Family") + inCircle("Friends"), label: "Family and friends", tone: "3" },
  { value: fmt.pct(withPhoto, people.length), label: "Have a photo", sub: `${people.length - withPhoto} without one`, tone: withPhoto === people.length ? "live" : "idle" },
]);

const grid1 = ctx.grid();
ctx.chart(grid1, card => {
  H.head(card, "People by circle");
  const counts = new Map();
  for (const p of people) counts.set(p.circle, (counts.get(p.circle) ?? 0) + 1);
  H.ranked(ctx, card, { rows: [...counts].map(([c, value]) => ({ label: c, value, name: "People" })), limit: 0 });
});
ctx.chart(grid1, card => {
  H.head(card, "Where the work circle is", "`location` on coworkers and managers; top 8.");
  const counts = new Map();
  for (const p of work) counts.set(p.location, (counts.get(p.location) ?? 0) + 1);
  H.ranked(ctx, card, { rows: [...counts].map(([label, value]) => ({ label, value, name: "People" })), slot: 3 });
});
ctx.chart(null, card => {
  H.head(card, "Work circle by team", "`role` on coworkers and managers; top 12. Click a team to open someone on it.");
  const byTeam = new Map();
  for (const p of work) byTeam.set(p.team, [...(byTeam.get(p.team) ?? []), p]);
  H.ranked(ctx, card, {
    rows: [...byTeam].map(([team, list]) => ({
      label: team, value: list.length, name: "People",
      tip: list.slice(0, 4).map(p => ({ cls: "hc-tip-muted", label: p.name })),
      onClick: e => open(list[0].path, e),
    })),
    limit: 12, slot: 2,
  });
}, { wide: true });

ctx.start();
