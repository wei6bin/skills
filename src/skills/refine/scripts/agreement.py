#!/usr/bin/env python3
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
STATES = ("draft", "jidoka-ready", "jidoka-running", "jidoka-pr", "jidoka-blocked")
META_KEYS = ("Tracker", "Status", "Rev")
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
META = re.compile(r"^(Tracker|Status|Rev): *(.*)$")
SEP_CELL = re.compile(r"^:?-{3,}:?$")
FENCE = re.compile(r"^```")
AC_ID = re.compile(r"^AC-(\d+)( \(removed\))?$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
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
            while i < len(lines) and LIST_ITEM.match(lines[i]):
                indent, marker, text = LIST_ITEM.match(lines[i]).groups()
                items.append((len(indent), "ol" if marker[0].isdigit() else "ul", text))
                i += 1
            out.append(list_html(items))
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not (
                FENCE.match(lines[i]) or lines[i].startswith("|")
                or SUBHEADING.match(lines[i]) or LIST_ITEM.match(lines[i])
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
        out = []
        for kind, text in self.blocks:
            if out and not (kind == "item" and out[-1][0] == "item"):
                out.append(("gap", ""))
            out.append((kind, text))
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
    states = [t for t in tags if t.lower().startswith("jidoka-")]
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
    match = ADO_URL.match(story)
    if match:
        org, story = match.group("org"), match.group("id")
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
    with tempfile.NamedTemporaryFile("w", dir=directory, delete=False, encoding="utf-8", newline="\n") as tmp:
        tmp.write(text)
    os.replace(tmp.name, path)


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


def cmd_status(args):
    agreement = load(args.file)
    if agreement.meta.get("Tracker") == "file":
        require_ready(agreement, args.set)
        agreement.meta["Status"] = args.set
        save(agreement, args.file)
        print(f"Status: {args.set}")
        return 0
    # On a work item the gate reads the work item itself, not the local file:
    # a local edit that was never pushed is not what the roles signed. The
    # test on /rev then makes the tag land on exactly the revision checked.
    org, story_id = work_item_target(agreement)
    item = show(story_id, org)
    require_ready(from_work_item(item), args.set)
    rev = int(item.get("rev") or item.get("fields", {}).get("System.Rev", 0))
    tags = [t.strip() for t in (item.get("fields", {}).get("System.Tags") or "").split(";") if t.strip()]
    tags = [t for t in tags if not t.lower().startswith("jidoka-")]
    if args.set != "draft":
        tags.append(args.set)
    patch(org, story_id, [
        {"op": "test", "path": "/rev", "value": rev},
        {"op": "add", "path": "/fields/System.Tags", "value": "; ".join(tags)},
    ])
    save(from_work_item(show(story_id, org)), args.file)
    print(f"Status: {args.set}")
    return 0


def cmd_sign(args):
    agreement = load(args.file)
    problems = check(agreement, ready=True, signoffs=False)
    if problems:
        report(problems, "")
        raise Refused("not signed: the agreement is not ready to sign")
    date = args.date or datetime.date.today().isoformat()
    if not DATE.match(date):
        raise UsageError(f"--date {date} must be YYYY-MM-DD")
    rows = {row["Role"]: row for row in rows_of(agreement, 13, [])}
    rows[args.role] = {"Role": args.role, "Name": args.name.strip(), "Date": date,
                       "Mode": args.mode, "Hash": digest(agreement)}
    lines = [table_line(TABLES[13]), table_line(["---"] * len(TABLES[13]))]
    lines += [table_line([rows[r][c] for c in TABLES[13]]) for r in ROLES if r in rows]
    agreement.sections[13] = "\n".join(lines)
    save(agreement, args.file)
    print(f"{args.role} signed by {args.name.strip()} ({args.mode}) at {digest(agreement)}")
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
