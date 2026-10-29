// Profile card for person notes in People/, styled by view.css. Needs Dataview with
// "Enable JavaScript Queries" on.
// In a note:  await dv.view("Templates/Views/person-profile")
// Pass { path: "People/Name.md" } to render another person's card (previews).
// Properties read: name, relationship, role, location, birthdate, address, phone, email,
// image; and from other notes: type, meeting type, date, creation date, summary, title, tags.
// Body bullets read under Notes: **Role:**, **Team:** ([label](url)), **Slack:** ([label](url)),
// **Timezone:** (an IANA zone such as America/Chicago), **Pronouns:**.
// Folders assumed: People/, Meetings/, Daily Notes/, Tasks/, Projects/ (the CONFIG.md defaults).

const app = dv.app;
const { DateTime } = dv.luxon;
const path = input?.path ?? dv.currentFilePath;
const p = dv.page(path);
if (!p) {
  dv.paragraph(`No person note at \`${path}\`.`);
  return;
}
const name = p.file.name;
const today = DateTime.now().startOf("day");
const file = app.vault.getAbstractFileByPath(path);
const text = file ? await app.vault.cachedRead(file) : "";

// ---------- helpers ----------
const bullet = label =>
  text.match(new RegExp(`^[ \\t]*[-*] \\*\\*${label}:\\*\\*[ \\t]*(.+)$`, "m"))?.[1]?.trim();
const mdLink = s => s?.match(/^\[([^\]]+)\]\(([^)\s]+)\)\s*(.*)$/);
const asList = v => (v == null ? [] : typeof v.array === "function" ? v.array() : Array.isArray(v) ? v : [v]);
const linkPath = l => (typeof l === "string" ? l.replace(/^\[\[|\]\]$/g, "").split("|")[0] : l?.path);
const resolve = (l, from = path) => {
  const lp = linkPath(l);
  return lp ? app.metadataCache.getFirstLinkpathDest(lp, from) : null;
};
const imageSrc = pg => {
  const f = resolve(pg?.image, pg?.file?.path);
  return f && /\.(png|jpe?g|gif|webp|svg|avif)$/i.test(f.path) ? app.vault.getResourcePath(f) : null;
};
const toDate = v => (dv.value.isDate(v) ? v : v ? dv.date(String(v)) : null);
const ago = d => {
  const days = Math.round(today.diff(d.startOf("day"), "days").days);
  return days === 0 ? "today" : days === 1 ? "yesterday" : days < 0 ? `in ${-days} days` : `${days} days ago`;
};
const el = (parent, tag, cls, text) => parent.createEl(tag, { cls, text });

// Internal links: open on click (Cmd/Ctrl for a new tab), page preview on hover.
const noteLink = (parent, target, label, cls = "pp-link") => {
  const a = parent.createEl("a", { cls, text: label, href: target });
  a.addEventListener("click", e => {
    e.preventDefault();
    app.workspace.openLinkText(target, path, e.metaKey || e.ctrlKey);
  });
  a.addEventListener("mouseover", e =>
    app.workspace.trigger("hover-link", {
      event: e, source: "preview", hoverParent: dv.container, targetEl: a, linktext: target, sourcePath: path,
    }));
  return a;
};
const extLink = (parent, href, label, cls = "pp-link") =>
  parent.createEl("a", { cls: `${cls} external-link`, text: label, href, attr: { target: "_blank", rel: "noopener" } });

const initials = s => s.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join("");
const hue = s => [...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);
const avatar = (parent, pg, size = "") => {
  const src = imageSrc(pg);
  const label = pg.name || pg.file.name;
  if (src) return parent.createEl("img", { cls: `pp-avatar ${size}`, attr: { src, alt: label, loading: "lazy" } });
  const d = el(parent, "div", `pp-avatar pp-initials ${size}`, initials(label));
  d.style.setProperty("--pp-hue", hue(label));
  return d;
};

// ---------- facts from the note ----------
const title = bullet("Role");
const team = mdLink(bullet("Team"));
const slack = mdLink(bullet("Slack"));
const pronouns = bullet("Pronouns");
const tz = bullet("Timezone");
const emails = asList(p.email).map(String).map(s => s.trim()).filter(Boolean);
const phone = String(p.phone ?? "").replace(/[\u200e\u200f\u202a-\u202e\u2066-\u2069]/g, "").trim();
const address = String(p.address ?? "").trim();
const relationship = String(p.relationship ?? "").trim();
const role = String(p.role ?? "").trim();

// ---------- backlinks, grouped by where they live ----------
// Meetings and conversations outside their usual folders are recognized by their frontmatter.
const meetingType = pg => String(pg?.["meeting type"] ?? "").trim().toLowerCase();
const isMeeting = (f, pg) => f.startsWith("Meetings/")
  || !f.startsWith("Templates/") && (pg?.type === "meeting" || !!meetingType(pg) && meetingType(pg) !== "template");
const KINDS = [
  { key: "meeting", label: "Meetings", icon: "🤝", test: isMeeting },
  { key: "comm", label: "Conversations", icon: "💬", test: (f, pg) => f.startsWith("People/Conversations/")
    || !f.startsWith("Templates/") && pg?.type === "communication" },
  { key: "daily", label: "Daily notes", icon: "📅", test: f => f.startsWith("Daily Notes/") },
  { key: "task", label: "Tasks", icon: "🎫", test: f => f.startsWith("Tasks/") },
  { key: "project", label: "Projects", icon: "🗂️", test: (f, pg) => f.startsWith("Projects/") || pg?.type === "project" },
  { key: "other", label: "Other notes", icon: "📎", test: () => true },
];
const kindOf = f => KINDS.find(k => k.test(f.path, f.page)) ?? KINDS.at(-1);
const backlinks = asList(p.file.inlinks)
  .map(l => ({ path: l.path, page: dv.page(l.path) }))
  .filter(b => b.page && b.path !== path);
for (const b of backlinks) b.kind = kindOf(b).key;
const count = key => backlinks.filter(b => b.kind === key).length;

// Open tasks that link to the person (not done or cancelled).
const openTasks = backlinks.flatMap(b =>
  asList(b.page.file.tasks).filter(t =>
    !t.completed && t.status !== "-" && asList(t.outlinks).some(o => o.path === path)));

// ---------- dated mentions, with the line that mentions them ----------
const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const mentionRe = new RegExp(`\\[\\[(?:[^\\]|#]*/)?${esc(name)}(?:\\.md)?(?:[|#]|\\]\\])`);
const headingDate = line => {
  const m = line.match(/^#{1,6}\s.*?(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (!m) return null;
  const d = DateTime.fromObject({ year: +m[1], month: +m[2], day: +m[3] });
  return d.isValid ? d : null;
};
const clean = s => s
  .replace(/^(?:\s*>)+/, "")
  .replace(/^\s*(?:[-*+]|\d+\.)\s+(?:\[.\]\s+)?/, "")
  .replace(/^#+\s*/, "")
  .replace(/\s\^[\w-]+\s*$/, "")
  .replace(/<br\s*\/?>/gi, " · ")
  .replace(/\s*\|\s*/g, " · ")
  .replace(/^[\s·]+|[\s·]+$/g, "")
  .replace(/\[\[[^\]|]+\|([^\]]+)\]\]/g, "$1")
  .replace(/\[\[([^\]]+)\]\]/g, (_, a) => a.split("/").pop().split("#")[0])
  .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
  .replace(/[📅✅⏳🔁➕🛫❌⏫🔼🔽🔺⏬]️?\s*\d{4}-\d{2}-\d{2}/gu, "")
  .replace(/:[A-Z][a-z]+[A-Za-z0-9]*:/g, "")
  .replace(/[*_`]|<!--.*?-->/g, "")
  .replace(/\s+/g, " ")
  .trim();

const TEXT_KINDS = new Set(["meeting", "comm", "daily", "task", "project", "other"]);
const scanned = backlinks
  .filter(b => TEXT_KINDS.has(b.kind) && !b.path.startsWith("People/") || b.kind === "comm")
  .sort((a, b) => b.page.file.mtime - a.page.file.mtime)
  .slice(0, 60);
const mentions = [];
for (const b of scanned) {
  const f = app.vault.getAbstractFileByPath(b.path);
  if (!f) continue;
  const body = (await app.vault.cachedRead(f)).replace(/^---\n[\s\S]*?\n---\n/, "");
  const pageDate = toDate(b.page.date) ?? toDate(b.page["creation date"]);
  const summary = b.page.summary ? clean(String(b.page.summary)) : "";
  // One entry per note per day: rolling logs get one per dated section, while a
  // single-date note (meeting, call) shows its summary, else the first line that mentions them.
  const byDay = new Map();
  let current = null;
  for (const line of body.split("\n")) {
    current = headingDate(line) ?? current;
    if (!mentionRe.test(line)) continue;
    const date = current ?? pageDate ?? b.page.file.mtime;
    const day = date.toISODate();
    if (byDay.has(day)) continue;
    const snippet = !current && summary ? summary : clean(line);
    byDay.set(day, { ...b, date, snippet: snippet.length > 2 ? snippet : summary });
  }
  // Linked only from frontmatter (attendees, person): still a dated mention.
  if (!byDay.size) byDay.set("", { ...b, date: pageDate ?? b.page.file.mtime, snippet: summary });
  mentions.push(...byDay.values());
}
mentions.sort((a, b) => b.date - a.date);
const recent = mentions.filter(m => m.date <= DateTime.now().plus({ days: 1 })).slice(0, 8);
const lastContact = mentions.find(m => ["meeting", "comm", "daily"].includes(m.kind) && m.date <= DateTime.now());

// ---------- people they show up with ----------
const isPerson = pg => pg?.file?.path?.startsWith("People/") && !pg.file.path.startsWith("People/Conversations/")
  && asList(pg.tags).map(String).includes("person");
const together = new Map();
for (const b of backlinks.filter(b => b.kind === "meeting" || b.kind === "comm")) {
  for (const o of new Set(asList(b.page.file.outlinks).map(o => o.path))) {
    const pg = dv.page(o);
    if (!isPerson(pg) || o === path || pg.relationship === "me") continue;
    together.set(o, (together.get(o) ?? 0) + 1);
  }
}
const oftenWith = [...together.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10)
  .map(([o, n]) => ({ page: dv.page(o), n }));

const group = role
  ? { label: role, pages: dv.pages('"People"').where(x => String(x.role ?? "").trim() === role) }
  : relationship
    ? { label: relationship, pages: dv.pages('"People"').where(x => isPerson(x) && String(x.relationship ?? "").trim() === relationship) }
    : null;
const peers = group ? group.pages.where(x => x.file.path !== path && x.relationship !== "me").sort(x => x.file.name).array() : [];

// ---------- render ----------
const root = el(dv.container, "div", "pp-card");
root.style.setProperty("--pp-hue", hue(name));

// Hero: photo, headline, chips, contact.
const hero = el(root, "div", "pp-hero");
avatar(el(hero, "div", "pp-photo"), p, "pp-xl");
const info = el(hero, "div", "pp-info");
const headline = el(info, "div", "pp-headline");
el(headline, "span", "pp-name", p.name && p.name !== name ? `${p.name}` : name);
if (pronouns) el(headline, "span", "pp-pronouns", pronouns);
if (title) el(info, "div", "pp-title", title);

const chips = el(info, "div", "pp-chips");
const chip = (icon, label, cls = "") => {
  const c = el(chips, "span", `pp-chip ${cls}`);
  el(c, "span", "pp-chip-icon", icon);
  if (label) el(c, "span", "", label);
  return c;
};
if (relationship) chip("🫂", relationship[0].toUpperCase() + relationship.slice(1), "pp-accent");
if (role) {
  const c = chip("🧭", "", "pp-accent");
  team ? extLink(c, team[2], role) : el(c, "span", "", role);
  if (/manager/i.test(team?.[3] ?? "")) el(c, "span", "pp-muted", " · manager");
}
if (p.location) chip("📍", String(p.location));
if (tz) {
  const there = DateTime.now().setZone(tz);
  if (there.isValid) {
    const diff = (there.offset - DateTime.now().offset) / 60;
    const rel = diff === 0 ? "same time" : `${diff > 0 ? "+" : "−"}${Math.abs(diff)} h`;
    const c = chip("🕒", `${there.toFormat("h:mm a")} there · ${rel}`);
    c.title = tz;
    const hour = there.hour;
    if (hour < 8 || hour >= 18) c.addClass("pp-off-hours");
  }
}
const born = toDate(p.birthdate);
if (born?.isValid) {
  let next = born.set({ year: today.year });
  if (next < today) next = next.plus({ years: 1 });
  const days = Math.round(next.diff(today, "days").days);
  const turns = next.year - born.year;
  const c = chip("🎂", days === 0 ? `Turns ${turns} today!` : `${born.toFormat("LLL d")} · turns ${turns} in ${days} days`);
  if (days <= 14) c.addClass("pp-soon");
}
if (lastContact) {
  const c = chip("👋", "Last seen ");
  noteLink(c, lastContact.path, ago(lastContact.date));
}

const contact = el(info, "div", "pp-contact");
for (const e of emails) extLink(el(contact, "span", "pp-contact-item"), `mailto:${e}`, `✉️ ${e}`);
if (phone) extLink(el(contact, "span", "pp-contact-item"), `tel:${phone.replace(/[^\d+]/g, "")}`, `📞 ${phone}`);
if (slack) extLink(el(contact, "span", "pp-contact-item"), slack[2], `💬 ${slack[1]}`);
if (address) extLink(el(contact, "span", "pp-contact-item"), `https://maps.apple.com/?q=${encodeURIComponent(address)}`, `🏠 ${address}`);

// Stat tiles.
const stats = el(root, "div", "pp-stats");
const tile = (icon, value, label, colour) => {
  const t = el(stats, "div", `pp-stat${value ? "" : " pp-zero"}`);
  t.style.setProperty("--pp-stat", colour);
  el(t, "div", "pp-stat-value", `${icon} ${value}`);
  el(t, "div", "pp-stat-label", label);
};
const palette = { meeting: "#5ab0ff", comm: "#f687b3", daily: "#7bd88f", task: "#f6a85a", project: "#c49bff", other: "#9aa3b5" };
for (const k of KINDS) {
  const n = count(k.key);
  if (n || ["meeting", "comm", "daily"].includes(k.key)) tile(k.icon, n, k.label, palette[k.key]);
}
tile("☑️", openTasks.length, "Open tasks", "#ffd27a");

// Columns: recent mentions, often with, group.
const cols = el(root, "div", "pp-columns");
if (recent.length) {
  const box = el(cols, "div", "pp-box pp-wide");
  el(box, "div", "pp-box-title", "🕰️ Recent mentions");
  const ul = el(box, "ul", "pp-timeline");
  for (const m of recent) {
    const li = el(ul, "li", `pp-kind-${m.kind}`);
    li.style.setProperty("--pp-stat", palette[m.kind]);
    const meta = el(li, "div", "pp-when");
    el(meta, "span", "pp-date", m.date.toFormat("LLL d, yyyy"));
    el(meta, "span", "pp-muted", ` · ${KINDS.find(k => k.key === m.kind).icon} `);
    noteLink(meta, m.path, m.page.title ? String(m.page.title) : m.page.file.name);
    if (m.snippet) el(li, "div", "pp-snippet", m.snippet.length > 180 ? `${m.snippet.slice(0, 177)}…` : m.snippet);
  }
}
const faces = (heading, list, badge) => {
  if (!list.length) return;
  const box = el(cols, "div", "pp-box");
  el(box, "div", "pp-box-title", heading);
  const grid = el(box, "div", "pp-faces");
  for (const { page: pg, n } of list) {
    const a = noteLink(grid, pg.file.path, "", "pp-face");
    avatar(a, pg);
    el(a, "span", "pp-face-name", (pg.file.name).split(" ")[0]);
    if (badge && n) el(a, "span", "pp-badge", String(n));
    a.title = badge && n ? `${pg.file.name} · together in ${n} notes` : pg.file.name;
  }
};
faces("👥 Often with", oftenWith, true);
if (group) {
  const shown = peers.slice(0, 18).map(page => ({ page }));
  faces(`🧩 Also in ${group.label}${peers.length > shown.length ? ` (${peers.length})` : ""}`, shown, false);
}
if (!recent.length && !oftenWith.length && !peers.length)
  el(cols, "div", "pp-box pp-empty", "Nothing links here yet. Mention them in a daily note, meeting or conversation and it will show up.");
