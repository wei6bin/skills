#!/usr/bin/env python3
"""Scan the thread notes and print a prioritised status table.

This exists so the "what should I focus on today" question does not get answered
by hand-rolled greps each time. Frontmatter is parsed line-by-line rather than
with a regex, because `^people:\\s*(.*)$` will happily eat the newline and
capture the following key when a value is empty.

Usage:
    python3 status.py [--vault PATH] [--json]
"""

import argparse
import datetime as dt
import json
import os
import re
import sys

import vaultpath

DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
# waiting longer than this without a new dated line usually means the other
# person has forgotten, and a chase is worth more than another week of patience
STALE_DAYS = 14


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, text[end + 4 :]


def collect(vault):
    tdir = os.path.join(vault, "work", "threads")
    if not os.path.isdir(tdir):
        sys.exit(f"No threads folder at {tdir}")
    today = dt.date.today()
    out = []
    for name in sorted(os.listdir(tdir)):
        if not name.endswith(".md"):
            continue
        text = open(os.path.join(tdir, name), encoding="utf-8").read()
        fm, body = parse_frontmatter(text)
        if fm.get("type") != "thread":
            continue

        dates = sorted(DATE_RE.findall(body))
        last = dates[-1] if dates else fm.get("created", "")
        try:
            idle = (today - dt.date.fromisoformat(last)).days
        except ValueError:
            idle = None

        due = fm.get("due", "")
        try:
            due_in = (dt.date.fromisoformat(due) - today).days if due else None
        except ValueError:
            due_in = None

        outcome = re.search(r"\*\*Outcome:\*\*\s*(.+)", body)
        otext = outcome.group(1).strip() if outcome else ""

        # `idle` goes blind right after a bulk migration, since every note gets
        # stamped with the migration date. `age` from the created field survives
        # that and is what exposes a genuinely ancient item.
        try:
            age = (today - dt.date.fromisoformat(fm.get("created", ""))).days
        except ValueError:
            age = None

        out.append(
            {
                "title": name[:-3],
                "status": (fm.get("status") or "backlog").lower(),
                "project": fm.get("project", ""),
                "people": fm.get("people", ""),
                "due": due,
                "due_in": due_in,
                "idle_days": idle,
                "age_days": age,
                "open_points": len(re.findall(r"^-\s*\[ \]\s*\S", body, re.M)),
                "outcome_missing": not otext or otext.startswith("_"),
            }
        )
    return out


def flags(t):
    """Reasons this thread might deserve attention today."""
    f = []
    if t["due_in"] is not None and t["due_in"] < 0:
        f.append(f"OVERDUE by {-t['due_in']}d")
    elif t["due_in"] is not None and t["due_in"] <= 3:
        f.append(f"due in {t['due_in']}d")
    if t["status"] == "waiting" and (t["idle_days"] or 0) >= STALE_DAYS:
        who = t["people"] or "someone"
        f.append(f"stalled {t['idle_days']}d on {who}")
    if t["status"] == "doing" and t["open_points"] >= 5:
        f.append(f"{t['open_points']} open points")
    if (t["age_days"] or 0) >= 60 and t["status"] != "doing":
        f.append(f"opened {t['age_days']}d ago and still not moving")
    if t["outcome_missing"]:
        f.append("no outcome defined")
    return f


def score(t):
    s = 0
    if t["due_in"] is not None:
        s += 100 if t["due_in"] < 0 else max(0, 40 - t["due_in"] * 5)
    if t["status"] == "waiting" and (t["idle_days"] or 0) >= STALE_DAYS:
        s += 30 + min(t["idle_days"], 90) // 3
    s += {"doing": 20, "waiting": 10, "backlog": 0, "done": -100}.get(t["status"], 0)
    if t["outcome_missing"]:
        s += 8
    if (t["age_days"] or 0) >= 60:
        s += 15
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", help="path to the Obsidian vault")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    vault = vaultpath.resolve(a.vault)

    threads = [t for t in collect(vault) if t["status"] != "done"]
    threads.sort(key=score, reverse=True)

    if a.json:
        print(json.dumps(threads, indent=2))
        return

    if not threads:
        print("No live threads.")
        return

    print(f"{len(threads)} live threads, {sum(t['open_points'] for t in threads)} open points\n")
    w = max(len(t["title"]) for t in threads)
    for t in threads:
        idle = f"{t['idle_days']}d" if t["idle_days"] is not None else "?"
        age = f"{t['age_days']}d" if t["age_days"] is not None else "?"
        line = (
            f"{t['status']:8} {t['title']:{w}}  "
            f"{t['open_points']:>2} open  idle {idle:>5}  age {age:>5}  "
            f"{t['project'] or '-'}"
        )
        if t["people"]:
            line += f" / {t['people']}"
        print(line)
        for f in flags(t):
            print(f"{'':9}-> {f}")


if __name__ == "__main__":
    main()
