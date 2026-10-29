#!/usr/bin/env python3
"""Convert between Atlassian Document Format (ADF) and a small Markdown subset.

acli reads and writes Jira descriptions and comments as ADF. Drafts are written
and reviewed as Markdown, then converted with this script before posting.

Supported: paragraphs, headings, bullet and ordered lists (nested), fenced code
blocks, horizontal rules, hard breaks, and **strong**, *em*, `code`, [links](url).

Usage:
  adf.py to-md   < doc.json   ADF → Markdown
  adf.py from-md < text.md    Markdown → ADF
  adf.py check   < doc.json   list node/mark types that do not round-trip (exit 1 if any)
"""
import json
import re
import sys

BLOCKS = {"doc", "paragraph", "heading", "bulletList", "orderedList", "listItem", "codeBlock", "rule"}
INLINES = {"text", "hardBreak"}
MARKS = {"strong", "em", "code", "link"}


# --- ADF → Markdown ---------------------------------------------------------

def inline_md(nodes):
    out = []
    for n in nodes or []:
        if n["type"] == "hardBreak":
            out.append("\\\n")
        elif n["type"] == "text":
            text = n.get("text", "")
            marks = {m["type"]: m for m in n.get("marks", [])}
            if "code" in marks:
                text = f"`{text}`"
            if "em" in marks:
                text = f"*{text}*"
            if "strong" in marks:
                text = f"**{text}**"
            if "link" in marks:
                text = f"[{text}]({marks['link']['attrs']['href']})"
            out.append(text)
        else:
            # mention, emoji, inlineCard, … keep whatever text they carry.
            attrs = n.get("attrs", {})
            out.append(attrs.get("text") or attrs.get("url") or attrs.get("shortName") or f"[{n['type']}]")
    return "".join(out)


def block_md(node, depth=0):
    t = node["type"]
    if t == "paragraph":
        return inline_md(node.get("content"))
    if t == "heading":
        return "#" * node.get("attrs", {}).get("level", 1) + " " + inline_md(node.get("content"))
    if t == "codeBlock":
        lang = (node.get("attrs") or {}).get("language") or ""
        return f"```{lang}\n{inline_md(node.get('content'))}\n```"
    if t == "rule":
        return "---"
    if t in ("bulletList", "orderedList"):
        lines = []
        for i, item in enumerate(node.get("content", []), 1):
            marker = "-" if t == "bulletList" else f"{i}."
            parts = item.get("content", [])
            first = block_md(parts[0], depth + 1) if parts else ""
            lines.append("  " * depth + f"{marker} {first}")
            for child in parts[1:]:
                lines.append(block_md(child, depth + 1))
        return "\n".join(lines)
    # panel, table, mediaSingle, … render children so no text is lost.
    return "\n\n".join(block_md(c, depth) for c in node.get("content", []))


def to_md(doc):
    if not doc:
        return ""
    if isinstance(doc, str):
        return doc
    return "\n\n".join(block_md(b) for b in doc.get("content", [])).strip()


def unsupported(doc):
    found = set()

    def walk(n):
        if isinstance(n, dict):
            if "type" in n and n["type"] not in BLOCKS | INLINES:
                found.add(n["type"])
            if n.get("type") == "codeBlock":
                found.update(f"codeBlock.{a}" for a in (n.get("attrs") or {}) if a not in ("language", "localId"))
            for m in n.get("marks", []):
                if m["type"] not in MARKS:
                    found.add(f"mark:{m['type']}")
            for v in n.get("content", []):
                walk(v)
    walk(doc)
    return sorted(found)


# --- Markdown → ADF ---------------------------------------------------------

INLINE_RE = re.compile(
    r"\[(?P<ltext>[^\]]+)\]\((?P<href>[^)\s]+)\)"
    r"|`(?P<code>[^`]+)`"
    r"|\*\*(?P<strong>.+?)\*\*"
    r"|(?<![\w*])\*(?P<em>[^*\s][^*]*?)\*(?![\w*])")


def text_node(text, marks):
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return node


def inline_adf(text, marks=None):
    marks = marks or []
    out, pos = [], 0
    for m in INLINE_RE.finditer(text):
        if m.start() > pos:
            out.append(text_node(text[pos:m.start()], marks))
        if m["ltext"] is not None:
            out += inline_adf(m["ltext"], marks + [{"type": "link", "attrs": {"href": m["href"]}}])
        elif m["code"] is not None:
            out.append(text_node(m["code"], marks + [{"type": "code"}]))
        elif m["strong"] is not None:
            out += inline_adf(m["strong"], marks + [{"type": "strong"}])
        else:
            out += inline_adf(m["em"], marks + [{"type": "em"}])
        pos = m.end()
    if pos < len(text):
        out.append(text_node(text[pos:], marks))
    return out


def paragraph(lines):
    """A trailing backslash (or two spaces) marks a hard break, as in CommonMark."""
    content = []
    for i, line in enumerate(lines):
        hard = line.endswith("\\") or line.endswith("  ")
        text = line.rstrip()
        if text.endswith("\\"):
            text = text[:-1]
        if i and content and content[-1]["type"] != "hardBreak":
            content.append(text_node(" ", []))
        content += inline_adf(text.strip())
        if hard:
            content.append({"type": "hardBreak"})
    return {"type": "paragraph", "content": content}


LIST_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<marker>[-*+]|\d+[.)])\s+(?P<text>.*)$")


def indent_width(s):
    return len(s.replace("\t", "  "))


def parse_list(lines, i, indent):
    first = LIST_RE.match(lines[i])
    kind = "bulletList" if first["marker"] in "-*+" else "orderedList"
    items = []
    while i < len(lines):
        m = LIST_RE.match(lines[i])
        if not m or indent_width(m["indent"]) < indent:
            break
        if indent_width(m["indent"]) > indent:
            # Deeper item: nest it under the previous item.
            sub, i = parse_list(lines, i, indent_width(m["indent"]))
            items[-1]["content"].append(sub)
            continue
        items.append({"type": "listItem", "content": [paragraph([m["text"]])]})
        i += 1
    return {"type": kind, "content": items}, i


def from_md(text):
    lines = text.replace("\r\n", "\n").split("\n")
    blocks, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("```"):
            lang, body = line[3:].strip(), []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            node = {"type": "codeBlock", "content": [text_node("\n".join(body), [])] if body else []}
            if lang:
                node["attrs"] = {"language": lang}
            blocks.append(node)
        elif re.match(r"^#{1,6} ", line):
            level = len(line) - len(line.lstrip("#"))
            blocks.append({"type": "heading", "attrs": {"level": level},
                           "content": inline_adf(line[level:].strip())})
            i += 1
        elif re.match(r"^\s*(-{3,}|\*{3,})\s*$", line):
            blocks.append({"type": "rule"})
            i += 1
        elif LIST_RE.match(line):
            node, i = parse_list(lines, i, indent_width(LIST_RE.match(line)["indent"]))
            blocks.append(node)
        else:
            para = []
            while (i < len(lines) and lines[i].strip() and not lines[i].startswith("```")
                   and not LIST_RE.match(lines[i]) and not re.match(r"^#{1,6} ", lines[i])):
                para.append(lines[i])
                i += 1
            blocks.append(paragraph(para))
    return {"type": "doc", "version": 1, "content": blocks}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("to-md", "from-md", "check"):
        sys.exit(__doc__)
    data = sys.stdin.read()
    if sys.argv[1] == "from-md":
        json.dump(from_md(data), sys.stdout, ensure_ascii=False)
    elif sys.argv[1] == "to-md":
        print(to_md(json.loads(data)))
    else:
        found = unsupported(json.loads(data))
        print("\n".join(found) if found else "ok")
        sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
