#!/usr/bin/env python3
# GENERATED copy of src/skills/refine/scripts/agreement.py by scripts/render.py (just build). Edit the source.
"""The agreement between /jidoka:refine and /jidoka:line: convert, check, sign.

The agreement is one Markdown document, laid out in
../references/agreement-format.md. On Azure DevOps it lives in a work item's
Description and Acceptance Criteria fields; without a tracker it is a Markdown
file. This script is the only code that moves it between the two forms, so
refine (which collects the sign-offs) and line (which builds from it) hash the
same text.

  agreement.py new --id ID --title TITLE [--tracker file|URL] [-o FILE]
  agreement.py pull --ado URL|ID [--org ORG_URL] [-o FILE]
  agreement.py pull --json FILE [-o FILE]   a saved `az boards work-item show`
  agreement.py push FILE                    write both fields, read them back
  agreement.py status FILE --set STATE      the jidoka-* tag, or Status line
  agreement.py sign FILE --role ROLE --name NAME --mode MODE [--date DATE]
  agreement.py hash FILE
  agreement.py check [--ready] FILE
  agreement.py html FILE                    the two fields push would write

The line's commands, which take a snapshot (the story.md that claim writes):

  agreement.py claim STORY -o FILE [--org ORG_URL]
                                            a work item URL or id, or a story
                                            file: refuse unless jidoka-ready,
                                            mark it jidoka-running, write the
                                            snapshot the line builds from
  agreement.py compare OLD NEW              what changed, AC by AC
  agreement.py record FILE --decisions MD   the line's decisions, to section 12
  agreement.py comment FILE --file MD       a comment on the work item
  agreement.py slug FILE                    the story's branch and folder name

Exit status: 0 done, 1 problems found or a write refused, 2 bad usage or input.
Needs Python 3.8+ and nothing else. Azure DevOps calls go through the az CLI
(`az login`, with the azure-devops extension). Writes use `az rest`, because
only a JSON Patch `test` on /rev refuses a write when someone else changed the
work item since it was read; `az boards work-item update` cannot send one.
"""

import argparse
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from urllib.parse import quote

SECTIONS = (
    "Statement",
    "Current behaviour",
    "Desired behaviour",
    "Acceptance criteria",
    "QE: scenarios and evidence",
    "Dev Lead: decisions and constraints",
    "Out of scope",
    "Open questions",
    "Decisions log",
    "Autonomy policy",
    "References and suggested skills",
    "Decisions made by the line",
    "Sign-off",
)
AC_SECTION = 4
# The hash covers the title and sections 1-11. Section 12 is the line's own
# record and section 13 the sign-off itself, so writing either changes nothing
# anyone signed.
SIGNED = range(1, 12)
ROLES = ("BA", "Dev Lead", "QE")
MODES = ("live", "own-account", "solo")
STATES = ("draft", "jidoka-ready", "jidoka-running", "jidoka-pr", "jidoka-blocked", "jidoka-done")
# Source, Hash and Fetched appear only in a snapshot: the copy `claim` writes
# for the line, which names where the story lives and what was signed.
META_KEYS = ("Tracker", "Status", "Rev", "Source", "Hash", "Fetched")
TABLES = {
    4: ("ID", "Given", "When", "Then"),
    5: ("AC", "Scenario", "Evidence", "Data"),
    8: ("ID", "Question", "Owner", "Severity", "Status"),
    9: ("ID", "Decision", "Rationale", "Rejected", "Owner", "Date"),
    12: ("ID", "Story didn't say", "Line chose", "Why", "Confirm by", "Undo by", "Status"),
    13: ("Role", "Name", "Date", "Mode", "Hash"),
}
NONE = "None."

ADO_RESOURCE = "499b84ac-1321-427f-aa17-267ca6975798"  # Azure DevOps, public
DESCRIPTION = "System.Description"
ACCEPTANCE = "Microsoft.VSTS.Common.AcceptanceCriteria"

# The same high-confidence patterns as the plugin's secrets hook.
SECRETS = (
    ("AWS access key id", r"AKIA[0-9A-Z]{16}"),
    ("AWS secret access key", r"aws_secret_access_key\s*[:=]\s*[A-Za-z0-9/+=]{40}"),
    ("GitHub token", r"gh[pousr]_[A-Za-z0-9]{36}"),
    ("Slack token", r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    ("Google API key", r"AIza[0-9A-Za-z_\-]{35}"),
    ("Stripe live secret key", r"sk_live_[A-Za-z0-9]{24,}"),
    ("Private key block", r"-----BEGIN ((RSA|OPENSSH|EC|DSA|PGP) )?PRIVATE KEY-----"),
)

HEADING = re.compile(r"^## (\d+)\. (.+?)\s*$")
META = re.compile(r"^(Tracker|Status|Rev|Source|Hash|Fetched): *(.*)$")
SEP_CELL = re.compile(r"^:?-{3,}:?$")
FENCE = re.compile(r"^```")
AC_ID = re.compile(r"^AC-(\d+)( \(removed\))?$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BOARD_URL = re.compile(
    r"^(?P<org>https://dev\.azure\.com/[^/]+|https://[^/.]+\.visualstudio\.com)"
    r"/[^?#]*[?&]workitem=(?P<id>\d+)"
)
HASH = re.compile(r"^sha256:[0-9a-f]{16}$")
EXIT = re.compile(r"^Exit: (pr|merge)$", re.M)
STACK = re.compile(r"^(?:- )?Stack: \S", re.M)
ADO_URL = re.compile(
    r"^(?P<org>https://dev\.azure\.com/[^/]+|https://[^/.]+\.visualstudio\.com)"
    r"/(?P<project>[^/]+)/_workitems/edit/(?P<id>\d+)"
)


class UsageError(Exception):
    """Bad input: exit 2."""


class Refused(Exception):
    """A write or a gate that said no: exit 1."""


# --- Markdown text -------------------------------------------------------------


def split_row(line):
    """The cells of one pipe-table row; an escaped \\| stays in its cell."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, buf, i = [], "", 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            buf += "\\|"
            i += 2
            continue
        if s[i] == "|":
            cells.append(buf.strip())
            buf = ""
        else:
            buf += s[i]
        i += 1
    cells.append(buf.strip())
    return cells


def is_separator(cells):
    return bool(cells) and all(SEP_CELL.match(c) for c in cells)


def table_line(cells):
    return "| " + " | ".join(cells) + " |"


def normalise(text):
    """One spelling for the same content: LF endings, no trailing blanks, one
    blank line between blocks, tables padded one space a side. A formatter
    re-padding a table, or Windows line endings, must not change the hash."""
    out, fenced = [], False
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.rstrip()
        if FENCE.match(line.lstrip()):
            fenced = not fenced
        elif not fenced and line.lstrip().startswith("|"):
            cells = split_row(line)
            line = table_line(["---"] * len(cells) if is_separator(cells) else cells)
        if line == "" and out and out[-1] == "" and not fenced:
            continue
        out.append(line)
    return "\n".join(out).strip("\n") + "\n"


def first_table(body):
    """(header, rows) of the first pipe table in a section body, or None."""
    block = []
    for line in body.split("\n"):
        if line.startswith("|"):
            block.append(line)
        elif block:
            break
    if not block:
        return None
    header = split_row(block[0])
    rows = [split_row(line) for line in block[1:] if not is_separator(split_row(line))]
    return header, rows


# --- the agreement -------------------------------------------------------------


class Agreement:
    def __init__(self, title="", meta=None, preamble="", sections=None, problems=None):
        self.title = title
        self.meta = dict(meta or {})
        self.preamble = preamble
        self.sections = dict(sections or {})
        self.problems = list(problems or [])

    def body(self, number):
        return self.sections.get(number, "")


def parse_body(text):
    """Metadata, preamble and numbered sections of text with no title line."""
    meta, preamble, sections, problems, order = {}, [], {}, [], []
    current, fenced = None, False
    # Metadata is the block of Key: value lines right under the title; a
    # "Status:" line further down a raw story is the story's own text.
    meta_open = True
    for line in text.split("\n"):
        if FENCE.match(line.lstrip()):
            fenced = not fenced
        heading = None if fenced else HEADING.match(line)
        if heading:
            number, name = int(heading.group(1)), heading.group(2)
            if not 1 <= number <= len(SECTIONS) or SECTIONS[number - 1] != name:
                problems.append(f"unknown heading '{line}': the headings are fixed")
            elif number in sections:
                problems.append(f"section {number} appears twice")
            else:
                current = number
                sections[number] = []
                order.append(number)
                continue
        if current is None:
            meta_line = META.match(line) if meta_open else None
            if meta_line:
                meta[meta_line.group(1)] = meta_line.group(2).strip()
                continue
            if line.strip() or meta:
                meta_open = False
            preamble.append(line)
        else:
            sections[current].append(line)
    if order != sorted(order):
        problems.append("sections are out of order")
    bodies = {n: "\n".join(lines).strip("\n") for n, lines in sections.items()}
    return meta, "\n".join(preamble).strip("\n"), bodies, problems


def parse(text):
    lines = normalise(text).split("\n")
    title, problems = "", []
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        lines = lines[1:]
    else:
        problems.append("the first line must be the title: '# {id} - {title}'")
    meta, preamble, sections, more = parse_body("\n".join(lines))
    return Agreement(title, meta, preamble, sections, problems + more)


def render(agreement):
    out = [f"# {agreement.title}", ""]
    out += [f"{key}: {agreement.meta[key]}" for key in META_KEYS if key in agreement.meta]
    out.append("")
    if agreement.preamble:
        out += [agreement.preamble, ""]
    for number in range(1, len(SECTIONS) + 1):
        if number in agreement.sections:
            out += [f"## {number}. {SECTIONS[number - 1]}", "", agreement.sections[number], ""]
    return normalise("\n".join(out))


def digest(agreement):
    parts = [f"# {agreement.title}"]
    for number in SIGNED:
        parts += [f"## {number}. {SECTIONS[number - 1]}", agreement.body(number)]
    return "sha256:" + hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def skeleton(story_id, title, tracker):
    sections = {n: NONE for n in range(1, len(SECTIONS) + 1)}
    for number in (4, 5):
        header = TABLES[number]
        sections[number] = table_line(header) + "\n" + table_line(["---"] * len(header))
    sections[10] = "Exit: pr\n\nStop also on: nothing beyond the defaults."
    meta = {"Tracker": tracker, "Status": "draft"}
    return Agreement(f"{story_id} - {title}", meta, "", sections)


# --- checks --------------------------------------------------------------------


def rows_of(agreement, number, problems):
    """The rows of a table section; [] for 'None.' or a missing table."""
    body = agreement.body(number)
    if body == NONE or number not in agreement.sections:
        return []
    found = first_table(body)
    want = TABLES[number]
    where = f"section {number}"
    if found is None:
        problems.append(f"{where}: expected a table with columns {' | '.join(want)}, or '{NONE}'")
        return []
    header, rows = found
    if tuple(header) != want:
        problems.append(f"{where}: columns must be {' | '.join(want)}, found {' | '.join(header)}")
        return []
    good = []
    for row in rows:
        if len(row) != len(want):
            problems.append(f"{where}: row '{table_line(row)}' has {len(row)} cells, needs {len(want)}")
        else:
            good.append(dict(zip(want, row)))
    return good


def check_ids(rows, prefix, where, problems):
    seen = set()
    for row in rows:
        ident = row["ID"]
        if not re.fullmatch(rf"{prefix}-\d+", ident):
            problems.append(f"{where}: ID '{ident}' must look like {prefix}-1")
        elif ident in seen:
            problems.append(f"{where}: {ident} is used twice")
        seen.add(ident)


def check_enum(rows, column, allowed, where, problems):
    for row in rows:
        if row[column] not in allowed:
            label = row.get("ID") or row.get("Role") or "a row"
            problems.append(f"{where}: {label} {column} '{row[column]}' must be one of {', '.join(allowed)}")


def acceptance_criteria(agreement, problems):
    """{number: active?} for every AC in section 4."""
    found = {}
    for row in rows_of(agreement, 4, problems):
        match = AC_ID.match(row["ID"])
        if not match:
            problems.append(f"section 4: ID '{row['ID']}' must look like AC-1, or AC-1 (removed)")
            continue
        number, active = int(match.group(1)), not match.group(2)
        if number in found:
            problems.append(f"section 4: AC-{number} is used twice; IDs are never reused")
            continue
        found[number] = active
        if active:
            for column in ("Given", "When", "Then"):
                if not row[column]:
                    problems.append(f"section 4: AC-{number} has no {column}")
    return found


def check(agreement, ready=False, signoffs=True):
    """Problems with the agreement, as one line each. With ready, also what
    stops it from being built: an empty story, open questions, a missing or
    stale sign-off (with signoffs=False, every rule but the sign-off ones)."""
    problems = list(agreement.problems)
    tracker = agreement.meta.get("Tracker", "")
    if tracker != "file" and not (tracker.startswith("ado ") and ADO_URL.match(tracker[4:])):
        problems.append("Tracker must be 'file' or 'ado <work item URL>'")
    status = agreement.meta.get("Status", "")
    if status not in STATES:
        problems.append(f"Status '{status}' must be one of {', '.join(STATES)}")
    if agreement.preamble:
        problems.append("text before section 1: move it into a section")
    missing = [n for n in range(1, len(SECTIONS) + 1) if n not in agreement.sections]
    if missing:
        problems.append("missing sections: " + ", ".join(f"{n}. {SECTIONS[n - 1]}" for n in missing))
    for number, body in sorted(agreement.sections.items()):
        if not body.strip():
            problems.append(f"section {number} is empty: write '{NONE}' when nothing applies")

    acs = acceptance_criteria(agreement, problems)
    covered = set()
    for row in rows_of(agreement, 5, problems):
        named = re.findall(r"AC-(\d+)", row["AC"])
        if not named:
            problems.append(f"section 5: row '{row['Scenario']}' names no AC")
        for number in map(int, named):
            if number not in acs:
                problems.append(f"section 5: AC-{number} is not in section 4")
            covered.add(number)
        for column in ("Scenario", "Evidence"):
            if not row[column]:
                problems.append(f"section 5: the row for {row['AC']} has no {column}")

    questions = rows_of(agreement, 8, problems)
    check_ids(questions, "Q", "section 8", problems)
    check_enum(questions, "Owner", ROLES, "section 8", problems)
    check_enum(questions, "Severity", ("HIGH", "MEDIUM", "LOW"), "section 8", problems)
    check_enum(questions, "Status", ("open", "answered", "deferred"), "section 8", problems)

    decisions = rows_of(agreement, 9, problems)
    check_ids(decisions, "D", "section 9", problems)
    check_enum(decisions, "Owner", ROLES, "section 9", problems)
    for row in decisions:
        if not DATE.match(row["Date"]):
            problems.append(f"section 9: {row['ID']} Date '{row['Date']}' must be YYYY-MM-DD")

    if not EXIT.search(agreement.body(10)):
        problems.append("section 10: needs a line 'Exit: pr' or 'Exit: merge'")

    line_decisions = rows_of(agreement, 12, problems)
    check_ids(line_decisions, "AD", "section 12", problems)
    check_enum(line_decisions, "Confirm by", ROLES, "section 12", problems)
    check_enum(line_decisions, "Status", ("pending", "confirmed", "rejected"), "section 12", problems)

    signed = rows_of(agreement, 13, problems)
    check_enum(signed, "Role", ROLES, "section 13", problems)
    check_enum(signed, "Mode", MODES, "section 13", problems)
    roles = [row["Role"] for row in signed]
    for role in set(roles):
        if roles.count(role) > 1:
            problems.append(f"section 13: {role} signed twice")
    for row in signed:
        if not row["Name"]:
            problems.append(f"section 13: the {row['Role']} sign-off has no name")
        if not DATE.match(row["Date"]):
            problems.append(f"section 13: {row['Role']} Date '{row['Date']}' must be YYYY-MM-DD")
        if not HASH.match(row["Hash"]):
            problems.append(f"section 13: {row['Role']} Hash '{row['Hash']}' must look like sha256:<16 hex>")
    names = [row["Name"] for row in signed]
    for row in signed:
        if names.count(row["Name"]) > 1 and row["Mode"] != "solo":
            problems.append(f"section 13: {row['Name']} signs more than one role, so each row's Mode must be solo")

    text = render(agreement)
    for label, pattern in SECRETS:
        if re.search(pattern, text):
            problems.append(f"looks like a {label}: point to where it is kept instead")

    if not ready:
        return problems
    for number in (1, 3):
        if agreement.body(number) in ("", NONE):
            problems.append(f"section {number} ({SECTIONS[number - 1]}) must be written before sign-off")
    active = sorted(n for n, on in acs.items() if on)
    if not active and not STACK.search(agreement.body(6)):
        problems.append("section 4 has no active AC, and section 6 names no 'Stack:' for a new project")
    for number in active:
        if number not in covered:
            problems.append(f"section 5: AC-{number} has no scenario and evidence")
    for row in questions:
        if row["Status"] == "open" and row["Severity"] in ("HIGH", "MEDIUM"):
            problems.append(f"section 8: {row['ID']} ({row['Severity']}, {row['Owner']}) is still open")
    if signoffs:
        current = digest(agreement)
        by_role = {row["Role"]: row for row in signed}
        for role in ROLES:
            row = by_role.get(role)
            if row is None:
                problems.append(f"section 13: {role} has not signed")
            elif row["Hash"] != current:
                problems.append(
                    f"section 13: {role} signed {row['Hash']}, but the agreement now hashes to "
                    f"{current}: it changed after sign-off, so {role} signs again"
                )
    return problems


# --- HTML for Azure DevOps -----------------------------------------------------

CODE = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
STRIKE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
ITALIC = re.compile(r"(?<![\w*])\*(?=[^\s*])([^*\n]+?)(?<=[^\s*])\*(?![\w*])")
LIST_ITEM = re.compile(r"^(\s*)([-*]|\d+\.) (.*)$")
SUBHEADING = re.compile(r"^(#{3,6}) (.*)$")


def inline_html(text):
    out = []
    for index, part in enumerate(CODE.split(text)):
        if index % 2:
            out.append("<code>" + html.escape(part, quote=False) + "</code>")
            continue
        s = html.escape(part, quote=False)
        s = LINK.sub(lambda m: f'<a href="{m.group(2).replace(chr(34), "%22")}">{m.group(1)}</a>', s)
        s = BOLD.sub(r"<strong>\1</strong>", s)
        s = STRIKE.sub(r"<s>\1</s>", s)
        s = ITALIC.sub(r"<em>\1</em>", s)
        out.append(s)
    return "".join(out)


def cell_html(cell, tag):
    return f"<{tag}>{inline_html(cell.replace(chr(92) + '|', '|'))}</{tag}>"


def list_html(items):
    out, stack = [], []
    for indent, kind, text in items:
        if not stack or indent > stack[-1][0]:
            out.append(f"<{kind}>")
            stack.append((indent, kind))
        else:
            while len(stack) > 1 and indent < stack[-1][0]:
                out.append(f"</li></{stack.pop()[1]}>")
            out.append("</li>")
            if stack[-1][1] != kind:
                out.append(f"</{stack[-1][1]}><{kind}>")
                stack[-1] = (stack[-1][0], kind)
        out.append(f"<li>{inline_html(text)}")
    while stack:
        out.append(f"</li></{stack.pop()[1]}>")
    return "".join(out)


def starts_block(line):
    return bool(FENCE.match(line) or line.startswith("|") or SUBHEADING.match(line))


def md_to_html(body):
    """The Markdown subset the agreement uses: paragraphs (each line kept as a
    line), lists, pipe tables, ### headings, fenced code and inline marks."""
    out, lines, i = [], body.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif FENCE.match(line):
            lang, code = line[3:].strip(), []
            i += 1
            while i < len(lines) and not FENCE.match(lines[i]):
                code.append(lines[i])
                i += 1
            i += 1
            attr = f' class="language-{html.escape(lang)}"' if lang else ""
            out.append(f"<pre><code{attr}>{html.escape(chr(10).join(code), quote=False)}</code></pre>")
        elif line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(split_row(lines[i]))
                i += 1
            rows = [r for r in block[1:] if not is_separator(r)]
            head = "<tr>" + "".join(cell_html(c, "th") for c in block[0]) + "</tr>"
            rest = "".join("<tr>" + "".join(cell_html(c, "td") for c in r) + "</tr>" for r in rows)
            out.append(f"<table>{head}{rest}</table>")
        elif SUBHEADING.match(line):
            marks, text = SUBHEADING.match(line).groups()
            out.append(f"<h{len(marks)}>{inline_html(text)}</h{len(marks)}>")
            i += 1
        elif LIST_ITEM.match(line):
            items = []
            while i < len(lines):
                item = LIST_ITEM.match(lines[i])
                if item:
                    indent, marker, text = item.groups()
                    items.append([len(indent), "ol" if marker[0].isdigit() else "ul", text])
                elif lines[i].strip() and not starts_block(lines[i]):
                    # A wrapped item: the line continues the item above it,
                    # indented or not, as Markdown reads it.
                    items[-1][2] += " " + lines[i].strip()
                else:
                    break
                i += 1
            out.append(list_html(items))
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not (
                starts_block(lines[i]) or LIST_ITEM.match(lines[i])
            ):
                para.append(inline_html(lines[i].strip()))
                i += 1
            out.append("<p>" + "<br>".join(para) + "</p>")
    return "".join(out)


def to_fields(agreement):
    """(Description HTML, Acceptance Criteria HTML) for the work item."""
    parts = []
    for number in range(1, len(SECTIONS) + 1):
        if number != AC_SECTION and number in agreement.sections:
            parts.append(f"<h2>{number}. {html.escape(SECTIONS[number - 1])}</h2>")
            parts.append(md_to_html(agreement.sections[number]))
    return "".join(parts), md_to_html(agreement.body(AC_SECTION))


class _HtmlToMarkdown(HTMLParser):
    """Reads back what md_to_html writes, and makes a best effort at whatever
    else the work item's rich-text editor produces."""

    MARKS = {"strong": "**", "b": "**", "em": "*", "i": "*", "s": "~~", "del": "~~", "strike": "~~"}
    BLOCKS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []  # (kind, text): kind "item" joins without a blank line
        self.buf = []
        self.marks = []  # (tag, the buffer it opened in, index into it, href)
        self.lists = []  # [tag, counter]
        self.heading = 0
        self.item_prefix = None  # "- " or "1. ", indented, while in an <li>
        self.table = None  # {"rows": [...], "row": [...], "cell": [...]}
        self.pre = None  # [lang, chunks]

    def target(self):
        if self.table is not None and self.table.get("cell") is not None:
            return self.table["cell"]
        return self.buf

    def flush(self):
        text = "".join(self.buf)
        self.buf = []
        self.marks = []
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]
        if not lines:
            self.heading = 0
            return
        if self.heading:
            self.blocks.append(("block", "#" * self.heading + " " + " ".join(lines)))
            self.heading = 0
        elif self.item_prefix is not None:
            self.blocks.append(("item", self.item_prefix + " ".join(lines)))
            self.item_prefix = None
        else:
            self.blocks.append(("block", "\n".join(lines)))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.pre is not None:
            if tag == "code":
                lang = (attrs.get("class") or "").replace("language-", "")
                self.pre[0] = lang
            return
        in_cell = self.table is not None and self.table.get("cell") is not None
        if tag == "br":
            self.target().append(" " if in_cell else "\n")
        elif in_cell and tag in self.BLOCKS:
            self.target().append(" ")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.flush()
            self.heading = int(tag[1])
        elif tag in ("p", "div", "blockquote"):
            self.flush()
        elif tag in ("ul", "ol"):
            self.flush()
            self.lists.append([tag, 0])
        elif tag == "li":
            self.flush()
            if not self.lists:
                self.lists.append(["ul", 0])
            self.lists[-1][1] += 1
            indent = "".join("   " if kind == "ol" else "  " for kind, _ in self.lists[:-1])
            kind, count = self.lists[-1]
            self.item_prefix = indent + (f"{count}. " if kind == "ol" else "- ")
        elif tag == "table":
            self.flush()
            self.table = {"rows": [], "row": None, "cell": None}
        elif tag == "tr" and self.table is not None:
            self.table["row"] = []
        elif tag in ("td", "th") and self.table is not None:
            self.table["cell"] = []
        elif tag == "pre":
            self.flush()
            self.pre = ["", []]
        elif tag in self.MARKS or tag in ("code", "a"):
            target = self.target()
            self.marks.append((tag, target, len(target), attrs.get("href", "")))

    def handle_endtag(self, tag):
        if self.pre is not None:
            if tag == "pre":
                lang, chunks = self.pre
                self.pre = None
                self.blocks.append(("block", f"```{lang}\n" + "".join(chunks).strip("\n") + "\n```"))
            return
        in_cell = self.table is not None and self.table.get("cell") is not None
        if tag in ("td", "th") and in_cell:
            cell = re.sub(r"\s+", " ", "".join(self.table["cell"])).strip()
            self.table["row"].append(cell.replace("|", "\\|").replace("\\\\|", "\\|"))
            self.table["cell"] = None
        elif tag == "tr" and self.table is not None and self.table["row"] is not None:
            self.table["rows"].append(self.table["row"])
            self.table["row"] = None
        elif tag == "table" and self.table is not None:
            rows = self.table["rows"]
            self.table = None
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                lines = [table_line(rows[0]), table_line(["---"] * width)]
                lines += [table_line(r) for r in rows[1:]]
                self.blocks.append(("block", "\n".join(lines)))
        elif in_cell and tag in self.BLOCKS:
            self.target().append(" ")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "blockquote", "li"):
            self.flush()
        elif tag in ("ul", "ol"):
            self.flush()
            if self.lists:
                self.lists.pop()
            if not self.lists:
                # A blank line after a whole list, so a list that follows
                # (an <ol> after a <ul>) reads back as a list of its own.
                self.blocks.append(("break", ""))
        elif tag in self.MARKS or tag in ("code", "a"):
            self.close_mark(tag)

    def close_mark(self, tag):
        for index in range(len(self.marks) - 1, -1, -1):
            name, target, start, href = self.marks[index]
            if name == tag:
                del self.marks[index:]
                break
        else:
            return
        inner = "".join(target[start:])
        stripped = inner.strip()
        lead = inner[: len(inner) - len(inner.lstrip())]
        trail = inner[len(inner.rstrip()):]
        if not stripped:
            text = inner
        elif tag == "code":
            text = f"{lead}`{stripped}`{trail}"
        elif tag == "a":
            text = f"{lead}[{stripped}]({href}){trail}" if href else inner
        else:
            mark = self.MARKS[tag]
            text = f"{lead}{mark}{stripped}{mark}{trail}"
        del target[start:]
        target.append(text)

    def handle_data(self, data):
        if self.pre is not None:
            self.pre[1].append(data)
            return
        self.target().append(re.sub(r"[ \t\r\n\f\v\xa0]+", " ", data))

    def markdown(self):
        self.flush()
        out, broken = [], False
        for kind, text in self.blocks:
            if kind == "break":
                broken = True
                continue
            if out and (broken or not (kind == "item" and out[-1][0] == "item")):
                out.append(("gap", ""))
            out.append((kind, text))
            broken = False
        return "\n".join(text for _, text in out)


def html_to_md(fragment):
    parser = _HtmlToMarkdown()
    parser.feed(fragment or "")
    parser.close()
    return parser.markdown().strip("\n")


def from_work_item(item):
    """The agreement held in an `az boards work-item show` reply."""
    fields = item.get("fields", {})
    story_id = item.get("id") or fields.get("System.Id")
    link = ((item.get("_links") or {}).get("html") or {}).get("href", "")
    if not ADO_URL.match(link):
        api = re.match(r"^(https://dev\.azure\.com/[^/]+|https://[^/.]+\.visualstudio\.com)", item.get("url", ""))
        project = fields.get("System.TeamProject", "")
        if not api or not project:
            raise UsageError("the work item names no organization and project; pass a work item URL")
        link = f"{api.group(1)}/{quote(project)}/_workitems/edit/{story_id}"
    tags = [t.strip() for t in (fields.get("System.Tags") or "").split(";") if t.strip()]
    # Read case-blind: a tag typed by hand as Jidoka-Ready is still the state.
    states = [t.lower() for t in tags if t.lower().startswith("jidoka-")]
    meta = {
        "Tracker": f"ado {link}",
        "Status": ", ".join(states) if states else "draft",
        "Rev": str(item.get("rev") or fields.get("System.Rev", "")),
    }
    _, preamble, sections, problems = parse_body(normalise(html_to_md(fields.get(DESCRIPTION, ""))))
    acceptance = html_to_md(fields.get(ACCEPTANCE, "")).strip("\n")
    if acceptance or sections:
        sections[AC_SECTION] = normalise(acceptance).strip("\n") if acceptance else ""
    title = f"{story_id} - {fields.get('System.Title', '').strip()}"
    return parse(render(Agreement(title, meta, preamble, sections, problems)))


# --- Azure DevOps through the az CLI -------------------------------------------


def az(*args):
    exe = shutil.which("az")
    if not exe:
        raise UsageError("the az CLI is not on PATH: install it, then `az login`")
    done = subprocess.run([exe, *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise Refused((done.stderr or done.stdout).strip() or f"az {args[0]} failed")
    return done.stdout


def work_item_target(agreement):
    tracker = agreement.meta.get("Tracker", "")
    match = ADO_URL.match(tracker[4:]) if tracker.startswith("ado ") else None
    if not match:
        raise UsageError("this agreement's Tracker is not an Azure DevOps work item URL")
    return match.group("org"), match.group("id")


def show(story, org=None):
    match = ADO_URL.match(story) or BOARD_URL.match(story)
    if match:
        org, story = match.group("org"), match.group("id")
    elif not story.isdigit():
        raise UsageError(
            f"{story} is not a work item: pass its URL (.../_workitems/edit/123, or a board link "
            "with ?workitem=123) or its id with --org"
        )
    args = ["boards", "work-item", "show", "--id", story, "--expand", "all", "-o", "json"]
    if org:
        args += ["--org", org]
    return json.loads(az(*args))


def patch(org, story_id, operations):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as body:
        json.dump(operations, body)
    try:
        return az(
            "rest", "--method", "patch", "--resource", ADO_RESOURCE,
            "--headers", "Content-Type=application/json-patch+json",
            "--url", f"{org}/_apis/wit/workitems/{story_id}?api-version=7.1",
            "--body", f"@{body.name}",
        )
    except Refused as err:
        rev = operations[0]["value"]
        raise Refused(
            f"Azure DevOps refused the write ({err}). If someone changed the work item after "
            f"rev {rev}, pull it again, merge your change into what they wrote, and push."
        ) from err
    finally:
        os.unlink(body.name)


def require_rev(agreement):
    rev = agreement.meta.get("Rev", "")
    if not rev.isdigit():
        raise UsageError("no Rev line: pull the work item first, then edit what you pulled")
    return int(rev)


# --- commands --------------------------------------------------------------------


def load(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return parse(handle.read())
    except OSError as err:
        raise UsageError(f"cannot read {path}: {err.strerror}") from err


def save(agreement, path):
    text = render(agreement)
    if path in (None, "-"):
        sys.stdout.write(text)
        return
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    if os.path.exists(path):
        mode = os.stat(path).st_mode & 0o777
    else:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    # Write beside the target and rename over it, so a reader never sees half a
    # file; keep the target's mode, since a temp file is created 0600.
    with tempfile.NamedTemporaryFile("w", dir=directory, delete=False, encoding="utf-8", newline="\n") as tmp:
        try:
            tmp.write(text)
        except BaseException:
            tmp.close()
            os.unlink(tmp.name)
            raise
    try:
        os.chmod(tmp.name, mode)
        os.replace(tmp.name, path)
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


def report(problems, success):
    for problem in problems:
        print(f"- {problem}")
    if problems:
        print(f"{len(problems)} problem(s)")
        return 1
    print(success)
    return 0


def cmd_new(args):
    tracker = args.tracker if args.tracker == "file" else f"ado {args.tracker}"
    agreement = skeleton(args.id, args.title, tracker)
    if args.output and args.output != "-" and os.path.exists(args.output):
        raise UsageError(f"{args.output} exists; refine edits it in place instead")
    save(agreement, args.output)
    return 0


def cmd_pull(args):
    if args.json:
        try:
            with open(args.json, encoding="utf-8") as handle:
                item = json.load(handle)
        except (OSError, ValueError) as err:
            raise UsageError(f"cannot read {args.json}: {err}") from err
    else:
        item = show(args.ado, args.org)
    save(from_work_item(item), args.output)
    return 0


def cmd_push(args):
    agreement = load(args.file)
    problems = check(agreement)
    if problems:
        report(problems, "")
        raise Refused("not pushed: fix the problems above first")
    org, story_id = work_item_target(agreement)
    rev = require_rev(agreement)
    description, acceptance = to_fields(agreement)
    patch(org, story_id, [
        {"op": "test", "path": "/rev", "value": rev},
        {"op": "add", "path": f"/fields/{DESCRIPTION}", "value": description},
        {"op": "add", "path": f"/fields/{ACCEPTANCE}", "value": acceptance},
    ])
    back = from_work_item(show(story_id, org))
    save(back, args.file)
    print(f"pushed rev {rev} -> {back.meta.get('Rev')}; {args.file} now holds what the work item "
          f"reads back, which hashes to {digest(back)}")
    return 0


def require_ready(agreement, state):
    if state != "jidoka-ready":
        return
    problems = check(agreement, ready=True)
    if problems:
        report(problems, "")
        raise Refused("not marked jidoka-ready: fix the problems above first")


def is_snapshot(agreement):
    return "Hash" in agreement.meta


def git_toplevel(folder):
    """The root of the git work tree holding folder, or '' outside one."""
    try:
        done = subprocess.run(["git", "-C", folder, "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True)
    except OSError:
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def story_file(agreement, path):
    """The file that holds a file-tracker story: the snapshot's Source, or the
    file itself. A snapshot is read-only; writes go to the story. Source is
    relative to the repository root, so it resolves against the work tree
    that holds the snapshot, never the current directory: a command run from
    another checkout must not edit that checkout's copy."""
    if not is_snapshot(agreement):
        return path
    source = agreement.meta.get("Source", "")
    if not source:
        raise UsageError(f"{path} is a snapshot with no Source line")
    root = git_toplevel(os.path.dirname(os.path.abspath(path)))
    return os.path.join(root, source) if root else source


def set_tag(item, state):
    """Swap the work item's one jidoka-* tag for state, refused on conflict;
    returns the work item as the write left it."""
    fields = item.get("fields", {})
    org, story_id = work_item_target(from_work_item(item))
    rev = int(item.get("rev") or fields.get("System.Rev", 0))
    tags = [t.strip() for t in (fields.get("System.Tags") or "").split(";") if t.strip()]
    tags = [t for t in tags if not t.lower().startswith("jidoka-")]
    if state != "draft":
        tags.append(state)
    return json.loads(patch(org, story_id, [
        {"op": "test", "path": "/rev", "value": rev},
        {"op": "add", "path": "/fields/System.Tags", "value": "; ".join(tags)},
    ]))


# Which state each target may be set from. refine moves a story between draft
# and jidoka-ready; a story a run holds, or has finished, is never reopened by
# hand, so a line run cannot lose its claim and a merged story stays shut.
# A story file has no claim (only its branch copy reads jidoka-running), so
# the line's end states are also allowed from jidoka-ready. --force is for a
# person repairing a story a crashed run left behind.
FROM = {
    "draft": {"draft", "jidoka-ready", "jidoka-blocked"},
    "jidoka-ready": {"draft", "jidoka-blocked", "jidoka-ready"},
    "jidoka-running": {"jidoka-ready"},
    "jidoka-blocked": {"jidoka-running", "jidoka-ready"},
    "jidoka-pr": {"jidoka-running", "jidoka-ready"},
    "jidoka-done": {"jidoka-running", "jidoka-pr", "jidoka-ready"},
}


def require_transition(current, state, force):
    if force or current in FROM.get(state, ()):
        return
    raise Refused(
        f"not changed: the story is '{current}', and {state} is set only from "
        f"{', '.join(sorted(FROM.get(state, ())))} (--force overrides, for a story a crashed run left behind)"
    )


def cmd_status(args):
    agreement = load(args.file)
    if agreement.meta.get("Tracker") == "file":
        path = story_file(agreement, args.file)
        story = load(path) if path != args.file else agreement
        require_transition(story.meta.get("Status", ""), args.set, args.force)
        require_ready(story, args.set)
        story.meta["Status"] = args.set
        save(story, path)
        print(f"Status: {args.set} ({path})")
        return 0
    # On a work item the gate reads the work item itself, not the local file:
    # a local edit that was never pushed is not what the roles signed. The
    # test on /rev then makes the tag land on exactly the revision checked.
    org, story_id = work_item_target(agreement)
    item = show(story_id, org)
    current = from_work_item(item)
    require_transition(current.meta.get("Status", ""), args.set, args.force)
    require_ready(current, args.set)
    back = from_work_item(set_tag(item, args.set))
    if is_snapshot(agreement):
        print(f"Status: {args.set}")  # the line's snapshot is read-only
    elif same_text(agreement, current):
        save(back, args.file)
        print(f"Status: {args.set}")
    else:
        # The copy has edits the work item does not: keep them. Its Rev stays
        # the one they were based on, so their push is refused until pulled
        # and merged, rather than overwriting what changed meanwhile.
        print(f"Status: {args.set}. {args.file} has changes the work item does not, so it was "
              "left as it is; pull again before you push them.")
    return 0


def same_text(one, other):
    """The same agreement text, metadata aside."""
    return (one.title, one.preamble, one.sections) == (other.title, other.preamble, other.sections)


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def slug(agreement, folder=None):
    """The story's branch and plan-folder name. The first run derives it from
    the title: 'USR-001 - Delete a note' is usr-001-delete-a-note. A later run
    takes the branch an earlier run left, found by the story's id, so a title
    edited after an andon stop does not orphan the branch. folder is a
    directory in the repository to look in (default: the current one)."""
    name = slugify(agreement.title)
    if len(name) > 50:
        name = name[:50].rsplit("-", 1)[0]
    prefix = slugify(agreement.title.split(" - ", 1)[0]) + "-"
    found = []
    for refs, strip in (("refs/heads", 2), ("refs/remotes", 3)):
        try:
            done = subprocess.run(
                ["git", "-C", folder or os.getcwd(), "for-each-ref", f"--format=%(refname:lstrip={strip})", refs],
                capture_output=True, text=True)
        except OSError:
            break
        if done.returncode == 0:
            found += [b for b in done.stdout.split() if b.startswith(prefix) and b not in found]
    return found[0] if found else name


NOT_READY = {
    "draft": "it has not been through refinement: run /jidoka:refine on it",
    "jidoka-running": "another run holds it",
    "jidoka-blocked": "a run stopped on a question; answer it through /jidoka:refine, which marks it ready again",
    "jidoka-pr": "a run already opened its pull request",
    "jidoka-done": "it is built and merged",
}


def refuse_unless_ready(agreement):
    status = agreement.meta.get("Status", "")
    if status != "jidoka-ready":
        reason = NOT_READY.get(status, "its Status is not one the line knows")
        raise Refused(f"not claimed: Status is '{status}', not jidoka-ready - {reason}")
    problems = check(agreement, ready=True)
    if problems:
        report(problems, "")
        raise Refused("not claimed: it is tagged jidoka-ready, but the agreement fails the ready check above")


def repo_path(path):
    """path relative to the root of the repository holding it, so the line's
    later writes find the story from any worktree of that repository."""
    root = git_toplevel(os.path.dirname(os.path.abspath(path)))
    relative = os.path.relpath(os.path.abspath(path), root or os.getcwd())
    return relative.replace(os.sep, "/")


def demote_if_not_ready(item, agreement):
    """A work item tagged jidoka-ready whose agreement fails the ready check
    (edited after sign-off, say) is not ready: tag it draft, so neither the
    scheduled pick-up nor a person retries it until the roles sign again."""
    if agreement.meta.get("Status") != "jidoka-ready":
        return
    problems = check(agreement, ready=True)
    if not problems:
        return
    report(problems, "")
    try:
        set_tag(item, "draft")
        note = "it is marked draft until BA, Dev Lead and QE sign it again in /jidoka:refine"
    except Refused as err:
        note = f"marking it draft failed too ({err})"
    raise Refused(f"not claimed: it is tagged jidoka-ready, but the agreement fails the ready check above; {note}")


def cmd_claim(args):
    fetched = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    story = args.story
    if not (ADO_URL.match(story) or BOARD_URL.match(story) or story.isdigit()):
        # A story file: nothing else can run it, so there is no claim to
        # win; its Status changes on the story's branch as the run goes.
        agreement = load(story)
        if agreement.meta.get("Tracker") != "file":
            raise UsageError(f"{story} is a copy of a work item: pass the work item URL instead")
        refuse_unless_ready(agreement)
        snapshot = parse(render(agreement))
        snapshot.meta["Source"] = repo_path(story)
        folder = os.path.dirname(os.path.abspath(story))
    else:
        item = show(story, args.org)
        agreement = from_work_item(item)
        demote_if_not_ready(item, agreement)
        refuse_unless_ready(agreement)
        # The tag swap is refused if anyone saved the work item after the
        # read above, so of two runs racing for one story, one loses here.
        # The snapshot is the text that was checked; only its Rev moves on.
        claimed = set_tag(item, "jidoka-running")
        snapshot = parse(render(agreement))
        snapshot.meta["Rev"] = str(claimed.get("rev") or snapshot.meta.get("Rev", ""))
        folder = None
    snapshot.meta["Status"] = "jidoka-running"
    snapshot.meta["Hash"] = digest(snapshot)
    snapshot.meta["Fetched"] = fetched
    save(snapshot, args.output)
    print(f"claimed {snapshot.title} at {snapshot.meta['Hash']}; slug {slug(snapshot, folder)}; "
          f"snapshot in {args.output}")
    return 0


def ac_map(agreement):
    """{AC number: (active, its row, the section 5 rows that name it)}."""
    evidence = rows_of(agreement, 5, [])
    found = {}
    for row in rows_of(agreement, 4, []):
        match = AC_ID.match(row["ID"])
        if match:
            number = int(match.group(1))
            named = [tuple(e.values()) for e in evidence if number in map(int, re.findall(r"AC-(\d+)", e["AC"]))]
            found[number] = (not match.group(2), tuple(row.values())[1:], tuple(named))
    return found


def compare(old, new):
    lines = []
    if old.title != new.title:
        lines.append(f"title changed: '{old.title}' -> '{new.title}'")
    before, after = ac_map(old), ac_map(new)
    for number in sorted(set(before) | set(after)):
        was, now = before.get(number), after.get(number)
        if was is None:
            state = "added" if now[0] else "added as removed"
        elif now is None:
            state = "missing: AC ids are never dropped, so the agreement is broken"
        elif was[0] and not now[0]:
            state = "removed"
        elif not was[0] and now[0]:
            state = "restored"
        elif was[1] != now[1]:
            state = "changed"
        elif was[2] != now[2]:
            state = "evidence changed"
        else:
            state = "unchanged"
        lines.append(f"AC-{number} {state}")
    for number in SIGNED:
        if number not in (4, 5) and old.body(number) != new.body(number):
            lines.append(f"section {number} ({SECTIONS[number - 1]}) changed")
    lines.append(f"hash {digest(old)} -> {digest(new)}")
    return lines


def cmd_compare(args):
    print("\n".join(compare(load(args.old), load(args.new))))
    return 0


def read_line_decisions(path):
    """The rows of the first table in path with section 12's columns."""
    try:
        with open(path, encoding="utf-8") as handle:
            text = normalise(handle.read())
    except OSError as err:
        raise UsageError(f"cannot read {path}: {err.strerror}") from err
    want = TABLES[12]
    header = table_line(want)
    lines = text.split("\n")
    table = []
    if header in lines:
        for line in lines[lines.index(header):]:
            if not line.startswith("|"):
                break
            table.append(line)
    holder = Agreement(sections={12: "\n".join(table)})
    problems = []
    rows = rows_of(holder, 12, problems) if holder.body(12) else []
    check_ids(rows, "AD", path, problems)
    check_enum(rows, "Confirm by", ROLES, path, problems)
    check_enum(rows, "Status", ("pending", "confirmed", "rejected"), path, problems)
    if problems:
        report(problems, "")
        raise UsageError(f"{path}: fix the decisions table (columns {' | '.join(want)})")
    return rows


def merge_decisions(existing, new):
    """New rows replace pending ones with the same ID and are appended
    otherwise. A row a role already confirmed or rejected is kept as it is,
    and a new row that differs from it under the same ID is an error: the
    run numbered its decisions from the wrong place."""
    rows = {row["ID"]: row for row in existing}
    clashes = []
    for row in new:
        held = rows.get(row["ID"])
        if held is None or held["Status"] == "pending":
            rows[row["ID"]] = row
        elif any(held[c] != row[c] for c in TABLES[12] if c != "Status"):
            clashes.append(f"{row['ID']} ({held['Status']})")
    if clashes:
        raise UsageError(
            f"{', '.join(clashes)} already decided on the story: number this run's decisions "
            "after the highest AD-n in story.md's section 12"
        )
    ordered = sorted(rows.values(), key=lambda r: int(r["ID"].split("-")[1]))
    if not ordered:
        return NONE
    lines = [table_line(TABLES[12]), table_line(["---"] * len(TABLES[12]))]
    return "\n".join(lines + [table_line([row[c] for c in TABLES[12]]) for row in ordered])


def cmd_record(args):
    agreement = load(args.file)
    new = read_line_decisions(args.decisions)
    if agreement.meta.get("Tracker") == "file":
        path = story_file(agreement, args.file)
        story = load(path)
        story.sections[12] = merge_decisions(rows_of(story, 12, []), new)
        save(story, path)
        print(f"section 12 of {path} holds {len(new)} decision(s) from this run")
        return 0
    org, story_id = work_item_target(agreement)
    # Section 12 is outside the hash, so the merge is mechanical; on a
    # conflict, read the work item again and redo it.
    for attempt in range(3):
        current = from_work_item(show(story_id, org))
        current.sections[12] = merge_decisions(rows_of(current, 12, []), new)
        problems = check(current)
        if problems:
            report(problems, "")
            raise Refused("not recorded: the work item's agreement no longer passes the format check")
        description, _ = to_fields(current)
        try:
            patch(org, story_id, [
                {"op": "test", "path": "/rev", "value": int(current.meta["Rev"])},
                {"op": "add", "path": f"/fields/{DESCRIPTION}", "value": description},
            ])
            break
        except Refused:
            if attempt == 2:
                raise
    print(f"section 12 of work item {story_id} holds {len(new)} decision(s) from this run")
    return 0


COMMENT_MARK = "<p><em>Written by jidoka:line.</em></p>"


def cmd_comment(args):
    agreement = load(args.file)
    if agreement.meta.get("Tracker") == "file":
        print("a story file has no discussion: the pull request or the run's report carries this")
        return 0
    try:
        with open(args.text, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as err:
        raise UsageError(f"cannot read {args.text}: {err.strerror}") from err
    org, story_id = work_item_target(agreement)
    az("boards", "work-item", "update", "--id", story_id, "--org", org,
       "--discussion", COMMENT_MARK + md_to_html(normalise(text).strip("\n")), "-o", "none")
    print(f"commented on work item {story_id}")
    return 0


def cmd_slug(args):
    print(slug(load(args.file), os.path.dirname(os.path.abspath(args.file))))
    return 0


def cmd_sign(args):
    agreement = load(args.file)
    # Section 13's own rules are checked on the row being written, below, not
    # on the rows already there: a sign-off that fixes a bad row must not be
    # refused because of that row.
    problems = [p for p in check(agreement, ready=True, signoffs=False) if not p.startswith("section 13:")]
    if problems:
        report(problems, "")
        raise Refused("not signed: the agreement is not ready to sign")
    date = args.date or datetime.date.today().isoformat()
    if not DATE.match(date):
        raise UsageError(f"--date {date} must be YYYY-MM-DD")
    name = args.name.strip()
    if not name or "|" in name:
        raise UsageError("--name must be a person's name, not empty and without '|'")
    rows = {row["Role"]: row for row in rows_of(agreement, 13, []) if row["Role"] in ROLES}
    others = [row for role, row in rows.items() if role != args.role and row["Name"] == name]
    if others and args.mode != "solo":
        raise Refused(
            f"not signed: {name} already signed as {', '.join(r['Role'] for r in others)}; one person "
            "signing more than one role signs each with --mode solo"
        )
    rows[args.role] = {"Role": args.role, "Name": name, "Date": date,
                       "Mode": args.mode, "Hash": digest(agreement)}
    lines = [table_line(TABLES[13]), table_line(["---"] * len(TABLES[13]))]
    lines += [table_line([rows[r][c] for c in TABLES[13]]) for r in ROLES if r in rows]
    agreement.sections[13] = "\n".join(lines)
    save(agreement, args.file)
    print(f"{args.role} signed by {name} ({args.mode}) at {digest(agreement)}")
    return 0


def cmd_hash(args):
    print(digest(load(args.file)))
    return 0


def cmd_check(args):
    agreement = load(args.file)
    problems = check(agreement, ready=args.ready)
    if args.ready:
        success = f"READY: signed by {', '.join(ROLES)} at {digest(agreement)}"
    else:
        success = f"OK: the format is valid; it hashes to {digest(agreement)}"
    return report(problems, success)


def cmd_html(args):
    description, acceptance = to_fields(load(args.file))
    print(f"--- {DESCRIPTION}\n{description}\n--- {ACCEPTANCE}\n{acceptance}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new", help="write an empty agreement")
    p.add_argument("--id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--tracker", default="file", help="'file', or the work item URL")
    p.add_argument("-o", "--output")
    p.set_defaults(run=cmd_new)

    p = sub.add_parser("pull", help="read a work item into the agreement's Markdown")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--ado", help="work item URL, or id with --org")
    source.add_argument("--json", help="a saved `az boards work-item show -o json` reply")
    p.add_argument("--org", help="organization URL, when --ado is a bare id")
    p.add_argument("-o", "--output")
    p.set_defaults(run=cmd_pull)

    p = sub.add_parser("push", help="write the agreement to its work item, then read it back")
    p.add_argument("file")
    p.set_defaults(run=cmd_push)

    p = sub.add_parser("status", help="set the jidoka-* tag (ADO) or the Status line (file)")
    p.add_argument("file")
    p.add_argument("--set", required=True, choices=STATES)
    p.add_argument("--force", action="store_true",
                   help="skip the check of the current state (repairing a stuck story)")
    p.set_defaults(run=cmd_status)

    p = sub.add_parser("sign", help="record one role's sign-off at the current hash")
    p.add_argument("file")
    p.add_argument("--role", required=True, choices=ROLES)
    p.add_argument("--name", required=True)
    p.add_argument("--mode", required=True, choices=MODES)
    p.add_argument("--date")
    p.set_defaults(run=cmd_sign)

    p = sub.add_parser("hash", help="print the hash of the signed sections")
    p.add_argument("file")
    p.set_defaults(run=cmd_hash)

    p = sub.add_parser("check", help="check the format; with --ready, whether line may build it")
    p.add_argument("--ready", action="store_true")
    p.add_argument("file")
    p.set_defaults(run=cmd_check)

    p = sub.add_parser("html", help="print the two fields push would write")
    p.add_argument("file")
    p.set_defaults(run=cmd_html)

    p = sub.add_parser("claim", help="the line's start: refuse unless ready, mark running, snapshot")
    p.add_argument("story", help="work item URL, id with --org, or a story file")
    p.add_argument("--org", help="organization URL, when the story is a bare id")
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(run=cmd_claim)

    p = sub.add_parser("compare", help="what changed between two agreements, AC by AC")
    p.add_argument("old")
    p.add_argument("new")
    p.set_defaults(run=cmd_compare)

    p = sub.add_parser("record", help="write the line's decisions into the story's section 12")
    p.add_argument("file", help="the snapshot (or the story)")
    p.add_argument("--decisions", required=True, help="a file with a section 12 table")
    p.set_defaults(run=cmd_record)

    p = sub.add_parser("comment", help="post a comment on the story's work item")
    p.add_argument("file", help="the snapshot (or the story)")
    p.add_argument("--file", dest="text", required=True, help="the comment, in Markdown")
    p.set_defaults(run=cmd_comment)

    p = sub.add_parser("slug", help="print the story's branch and folder name")
    p.add_argument("file")
    p.set_defaults(run=cmd_slug)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except UsageError as err:
        print(f"agreement.py: {err}", file=sys.stderr)
        return 2
    except Refused as err:
        print(f"agreement.py: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
