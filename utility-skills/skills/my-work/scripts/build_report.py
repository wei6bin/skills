#!/usr/bin/env python3
"""Build an HTML review board from the Obsidian thread notes.

Reads every note in work/threads/, parses its frontmatter and its
"Discussion points & follow-ups" section, and writes a single self-contained
HTML page grouped by status. Intended for reviewing work away from Obsidian,
or sharing a snapshot with someone who does not have the vault.

Usage:
    python3 build_report.py [--vault PATH] [--out PATH] [--open]

Defaults to the user's vault and writes work/html/work-review-<date>.html
"""

import argparse
import datetime as dt
import html
import os
import re
import subprocess
import sys

import vaultpath

STATUS_ORDER = ["doing", "waiting", "backlog", "done"]
STATUS_LABEL = {
    "doing": "Doing",
    "waiting": "Waiting on someone",
    "backlog": "Backlog",
    "done": "Done",
}


def parse_frontmatter(text):
    """Return (frontmatter dict, body). Hand-rolled so the script has no deps."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw, body = text[3:end], text[end + 4 :]
    fm = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, body


def section(body, heading):
    """Extract the lines under a '## heading' up to the next '## '."""
    pat = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.M | re.I)
    m = pat.search(body)
    if not m:
        return ""
    rest = body[m.end() :]
    nxt = re.search(r"^##\s+", rest, re.M)
    return (rest[: nxt.start()] if nxt else rest).strip()


def parse_points(block):
    """Parse checkboxes and their nested dated lines into structured points.

    Threads created from the template carry an empty placeholder point until the
    user fills it in. Those are dropped rather than rendered as blank bullets,
    which would otherwise make a freshly-scaffolded thread look broken.
    """
    points = []
    for line in block.splitlines():
        top = re.match(r"^-\s*\[( |x|X)\]\s*(.*)$", line)
        if top:
            points.append(
                {"done": top.group(1).lower() == "x", "text": top.group(2).strip(), "log": []}
            )
        elif points and re.match(r"^\s+-\s+", line):
            entry = re.sub(r"^\s*-\s*", "", line).strip()
            # a bare date with no note behind it carries no information
            if entry and not re.fullmatch(r"\d{4}-\d{2}-\d{2}\s*[-–]?\s*", entry):
                points[-1]["log"].append(entry)
    return [p for p in points if p["text"]]


def md_inline(s):
    """Minimal inline markdown so the report is readable, escaped first."""
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"<em>\2</em>", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def collect(vault):
    tdir = os.path.join(vault, "work", "threads")
    if not os.path.isdir(tdir):
        sys.exit(f"No threads folder at {tdir}")
    threads = []
    for name in sorted(os.listdir(tdir)):
        if not name.endswith(".md"):
            continue
        text = open(os.path.join(tdir, name), encoding="utf-8").read()
        fm, body = parse_frontmatter(text)
        if fm.get("type") != "thread":
            continue
        points = parse_points(section(body, "Discussion points & follow-ups"))
        outcome = ""
        mo = re.search(r"\*\*Outcome:\*\*\s*(.+)", body)
        if mo:
            outcome = mo.group(1).strip().strip("_")
        threads.append(
            {
                "title": name[:-3],
                "status": (fm.get("status") or "backlog").lower(),
                "project": fm.get("project", ""),
                "people": fm.get("people", ""),
                "due": fm.get("due", ""),
                "outcome": outcome,
                "progress": [
                    re.sub(r"^\s*-\s*", "", l).strip()
                    for l in section(body, "Progress").splitlines()
                    if l.strip().startswith("-")
                ],
                "points": points,
                "open": sum(1 for p in points if not p["done"]),
            }
        )
    return threads


CSS = """
:root{--ivory:#FAF9F5;--paper:#fff;--slate:#141413;--clay:#D97757;--clay-d:#B85C3E;
--oat:#E3DACC;--olive:#788C5D;--g100:#F0EEE6;--g200:#E6E3DA;--g500:#87867F;--g700:#3D3D3A;
--serif:ui-serif,Georgia,serif;--sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
--mono:ui-monospace,"SF Mono",Menlo,monospace}
@media(prefers-color-scheme:dark){:root{--ivory:#1A1A18;--paper:#232320;--slate:#EDEBE4;
--oat:#3A382F;--g100:#2A2A26;--g200:#35342E;--g500:#9A988F;--g700:#C6C3B8;--clay-d:#E08A66;
--olive:#9CB37C}}
*{box-sizing:border-box}body{margin:0;background:var(--ivory);color:var(--slate);
font-family:var(--sans);line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:40px 28px 100px}
h1{font-family:var(--serif);font-size:clamp(30px,4vw,46px);margin:12px 0 8px;letter-spacing:-.02em}
h2{font-family:var(--serif);font-size:24px;margin:44px 0 14px}
.eyebrow{font-family:var(--mono);font-size:12px;letter-spacing:.12em;text-transform:uppercase;
color:var(--g700);background:var(--g100);border:1px solid var(--g200);padding:5px 11px;border-radius:99px}
.lede{color:var(--g700);max-width:62ch}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:26px 0 8px}
.stat{background:var(--paper);border:1.5px solid var(--oat);border-radius:13px;padding:14px 16px}
.stat .n{font-family:var(--serif);font-size:29px;font-weight:600;color:var(--clay-d);line-height:1}
.stat .l{font-family:var(--mono);font-size:11px;color:var(--g700);margin-top:5px;letter-spacing:.04em}
.card{background:var(--paper);border:1.5px solid var(--oat);border-radius:14px;padding:18px 20px;margin:12px 0}
.card.waiting{border-left:3px solid var(--clay)}
.card.doing{border-left:3px solid var(--olive)}
.card h3{font-family:var(--serif);font-size:19px;margin:0 0 6px}
.meta{font-family:var(--mono);font-size:11.5px;color:var(--g500);margin-bottom:10px}
.meta b{color:var(--g700);font-weight:600}
.outcome{font-size:14.5px;color:var(--g700);margin:0 0 12px}
ul.pts{margin:8px 0 0;padding-left:18px}
ul.pts li{margin-bottom:7px;font-size:14.5px}
ul.pts li.done{color:var(--g500);text-decoration:line-through}
ul.log{list-style:none;margin:5px 0 0;padding-left:0}
ul.log li{font-family:var(--mono);font-size:12px;color:var(--g500);padding:2px 0 2px 12px;
border-left:2px solid var(--g200);margin:3px 0}
details{margin-top:10px}summary{cursor:pointer;font-family:var(--mono);font-size:11.5px;
color:var(--g500);letter-spacing:.05em;text-transform:uppercase}
code{font-family:var(--mono);font-size:.9em;background:var(--g100);border:1px solid var(--g200);
border-radius:4px;padding:1px 4px}
a{color:var(--clay-d)}
.empty{color:var(--g500);font-style:italic}
footer{margin-top:70px;padding-top:20px;border-top:1.5px solid var(--oat);
font-family:var(--mono);font-size:12px;color:var(--g500)}
"""


def render(threads, when):
    live = [t for t in threads if t["status"] != "done"]
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>Work review - {when}</title><style>{CSS}</style></head><body><div class='wrap'>",
        f"<span class='eyebrow'>Work review · {when}</span>",
        "<h1>What is on my plate</h1>",
        "<p class='lede'>Generated from the thread notes in the Obsidian vault. "
        "Each card is one thread; the nested lines under a discussion point are the "
        "feedback and progress recorded against that specific point.</p>",
        "<div class='stats'>",
        f"<div class='stat'><div class='n'>{len(live)}</div><div class='l'>LIVE THREADS</div></div>",
        f"<div class='stat'><div class='n'>{sum(1 for t in live if t['status']=='doing')}</div><div class='l'>DOING</div></div>",
        f"<div class='stat'><div class='n'>{sum(1 for t in live if t['status']=='waiting')}</div><div class='l'>WAITING</div></div>",
        f"<div class='stat'><div class='n'>{sum(t['open'] for t in live)}</div><div class='l'>OPEN POINTS</div></div>",
        "</div>",
    ]

    for status in STATUS_ORDER:
        group = [t for t in threads if t["status"] == status]
        if not group:
            continue
        parts.append(f"<h2>{STATUS_LABEL[status]} <span class='meta'>({len(group)})</span></h2>")
        for t in group:
            bits = []
            if t["project"]:
                bits.append(f"<b>Project</b> {html.escape(t['project'])}")
            if t["people"]:
                bits.append(f"<b>With</b> {html.escape(t['people'])}")
            if t["due"]:
                bits.append(f"<b>Due</b> {html.escape(t['due'])}")
            bits.append(f"<b>Open points</b> {t['open']}")
            parts.append(f"<div class='card {status}'>")
            parts.append(f"<h3>{html.escape(t['title'])}</h3>")
            parts.append(f"<div class='meta'>{' · '.join(bits)}</div>")
            if t["outcome"]:
                parts.append(f"<p class='outcome'>{md_inline(t['outcome'])}</p>")
            if t["points"]:
                parts.append("<ul class='pts'>")
                for p in t["points"]:
                    cls = " class='done'" if p["done"] else ""
                    parts.append(f"<li{cls}>{md_inline(p['text'])}")
                    if p["log"]:
                        parts.append("<ul class='log'>")
                        parts += [f"<li>{md_inline(l)}</li>" for l in p["log"]]
                        parts.append("</ul>")
                    parts.append("</li>")
                parts.append("</ul>")
            else:
                parts.append("<p class='empty'>No discussion points recorded yet.</p>")
            if t["progress"]:
                parts.append("<details><summary>Progress log</summary><ul class='log'>")
                parts += [f"<li>{md_inline(l)}</li>" for l in t["progress"]]
                parts.append("</ul></details>")
            parts.append("</div>")

    parts.append(
        f"<footer>Generated {when} from work/threads/ · "
        f"{len(threads)} thread notes read</footer></div></body></html>"
    )
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", help="path to the Obsidian vault")
    ap.add_argument("--out")
    ap.add_argument("--open", action="store_true", help="open in the default browser")
    a = ap.parse_args()
    vault = vaultpath.resolve(a.vault)

    when = dt.date.today().isoformat()
    threads = collect(vault)
    out = a.out or os.path.join(vault, "work", "html", f"work-review-{when}.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(threads, when))

    live = [t for t in threads if t["status"] != "done"]
    print(f"{out}")
    print(f"  {len(threads)} threads ({len(live)} live), {sum(t['open'] for t in live)} open points")
    if a.open:
        subprocess.run(["open", out], check=False)


if __name__ == "__main__":
    main()
