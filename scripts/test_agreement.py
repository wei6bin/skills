#!/usr/bin/env python3
"""Unit tests for the refine skill's agreement script.

src/skills/refine/scripts/agreement.py moves the agreement between the Markdown
form line builds from and the Azure DevOps fields BA, Dev Lead and QE sign in,
hashes it and gates sign-off and jidoka-ready. These tests pin the round trip,
the hash, every check, and the Azure DevOps writes against a fake `az`.

Run: just test (python3 -m unittest discover -s scripts -p 'test_*.py').
"""

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "src/skills/refine/scripts/agreement.py"
_spec = importlib.util.spec_from_file_location("agreement", SCRIPT)
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)

URL = "https://dev.azure.com/Contoso/Bookings/_workitems/edit/4711"

SAMPLE = textwrap.dedent(
    """\
    # USR-002 - Edit a note

    Tracker: file
    Status: draft

    ## 1. Statement

    As an API client, I want to change a note's title, so that I can fix mistakes.

    ## 2. Current behaviour

    Notes can be created, listed and fetched, but not changed.

    ## 3. Desired behaviour

    `PATCH /notes/:id` with a JSON body `{ "title": ... }` replaces the title.
    The **error envelope** stays *the same*: `{ "error": { "code", "message" } }`.

    ## 4. Acceptance criteria

    | ID | Given | When | Then |
    |----|-------|------|------|
    | AC-1 | an existing note | the client sends PATCH with a title of 1-200 characters | 200 with the updated note |
    | AC-2 | no note with that id | the client sends PATCH | 404, error code `note_not_found` |
    | AC-3 (removed) | | | |

    ## 5. QE: scenarios and evidence

    | AC | Scenario | Evidence | Data |
    |---|---|---|---|
    | AC-1 | rename a note created in the test | status and body from the test run | note made by POST /notes |
    | AC-2 | patch an unknown id | status and body | id `a\\|b` |

    User roles: none, the API has no auth.

    ## 6. Dev Lead: decisions and constraints

    - Method: PATCH, title only.
    - No new dependencies.
      - nested point a
      - nested point b
    1. ordered one
    2. ordered two

    ```json
    { "error": { "code": "note_not_found" } }
    ```

    ## 7. Out of scope

    Editing the body of a note, ~~tags~~.

    ## 8. Open questions

    | ID | Question | Owner | Severity | Status |
    |---|---|---|---|---|
    | Q-1 | Reject whitespace-only titles? | BA | MEDIUM | answered |
    | Q-2 | Rate limit? | Dev Lead | LOW | deferred |

    ## 9. Decisions log

    | ID | Decision | Rationale | Rejected | Owner | Date |
    |---|---|---|---|---|---|
    | D-1 | PATCH, not PUT | only the title changes | PUT | Dev Lead | 2026-11-07 |

    ## 10. Autonomy policy

    Exit: merge
    Stop also on: nothing beyond the defaults.

    ## 11. References and suggested skills

    - See [the API guide](https://example.invalid/guide?a=1&b=2) for the envelope.
    - Graph: CAP-01.

    ## 12. Decisions made by the line

    None.

    ## 13. Sign-off

    None.
    """
)


def edited(text, old, new):
    assert old in text, old
    return A.parse(text.replace(old, new))


def signed(agreement, mode="live", names=("Ana", "Ben", "Chen")):
    """The agreement with every role signed at its current hash."""
    current = A.digest(agreement)
    rows = [A.table_line(A.TABLES[13]), A.table_line(["---"] * 5)]
    rows += [A.table_line([role, name, "2026-11-07", mode, current]) for role, name in zip(A.ROLES, names)]
    agreement.sections[13] = "\n".join(rows)
    return A.parse(A.render(agreement))


def work_item(agreement, rev=18, tags="api", links=True):
    description, acceptance = A.to_fields(agreement)
    item = {
        "id": 4711,
        "rev": rev,
        "url": "https://dev.azure.com/Contoso/0f1e2d/_apis/wit/workItems/4711",
        "fields": {
            "System.Title": "Edit a note",
            "System.TeamProject": "Bookings",
            "System.Tags": tags,
            A.DESCRIPTION: description,
            A.ACCEPTANCE: acceptance,
        },
    }
    if links:
        item["_links"] = {"html": {"href": URL}}
    return item


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = A.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class RoundTripTests(unittest.TestCase):
    def test_markdown_survives_the_work_item_fields(self):
        source = A.parse(SAMPLE)
        back = A.from_work_item(work_item(source))
        for number in range(1, len(A.SECTIONS) + 1):
            self.assertEqual(back.body(number), source.body(number), f"section {number}")
        self.assertEqual(back.problems, [])

    def test_the_hash_survives_the_round_trip(self):
        source = A.parse(SAMPLE.replace("USR-002", "4711"))
        self.assertEqual(A.digest(A.from_work_item(work_item(source))), A.digest(source))

    def test_metadata_comes_from_the_work_item(self):
        back = A.from_work_item(work_item(A.parse(SAMPLE), rev=21, tags="api; jidoka-ready"))
        self.assertEqual(back.title, "4711 - Edit a note")
        self.assertEqual(back.meta, {"Tracker": f"ado {URL}", "Status": "jidoka-ready", "Rev": "21"})

    def test_two_jidoka_tags_fail_the_check(self):
        back = A.from_work_item(work_item(A.parse(SAMPLE), tags="jidoka-ready; jidoka-running"))
        self.assertEqual(back.meta["Status"], "jidoka-ready, jidoka-running")
        self.assertTrue(any(p.startswith("Status") for p in A.check(back)))

    def test_tracker_url_built_without_links(self):
        back = A.from_work_item(work_item(A.parse(SAMPLE), links=False))
        self.assertEqual(back.meta["Tracker"], f"ado {URL}")

    def test_a_raw_story_keeps_its_text_before_section_1(self):
        item = {
            "id": 7, "rev": 3, "_links": {"html": {"href": URL.replace("4711", "7")}},
            "fields": {
                "System.Title": "Raw",
                A.DESCRIPTION: "<div>As a user I want X.</div><div>Status: unclear</div>",
                A.ACCEPTANCE: "<ol><li>X works</li><li>Y fails</li></ol>",
            },
        }
        back = A.from_work_item(item)
        self.assertEqual(back.preamble, "As a user I want X.\n\nStatus: unclear")
        self.assertEqual(back.meta["Status"], "draft")
        self.assertEqual(back.body(4), "1. X works\n2. Y fails")
        self.assertIn("text before section 1: move it into a section", A.check(back))

    def test_editor_html_reads_as_markdown(self):
        # What the work item's rich-text editor writes, not what push writes.
        fragment = (
            "<div><b>Given </b>a&nbsp;note</div><div><br></div>"
            "<table><tbody><tr><td><div>ID</div></td><td>Then</td></tr>"
            "<tr><td>AC-1</td><td><p>200</p><p>with a|b</p></td></tr></tbody></table>"
            "<ul><li><p>one</p></li><li>two <i>it</i></li></ul>"
        )
        self.assertEqual(
            A.html_to_md(fragment),
            "**Given** a note\n\n| ID | Then |\n| --- | --- |\n| AC-1 | 200 with a\\|b |\n\n- one\n- two *it*",
        )


class HashTests(unittest.TestCase):
    def test_formatting_does_not_change_the_hash(self):
        base = A.parse(SAMPLE)
        padded = SAMPLE.replace("| AC-1 | an existing note |", "|AC-1|   an existing note   |")
        crlf = padded.replace("\n", "\r\n").replace("## 7.", "\n\n## 7.")
        self.assertEqual(A.digest(A.parse(crlf)), A.digest(base))

    def test_metadata_and_sections_12_and_13_are_not_signed(self):
        base = A.digest(A.parse(SAMPLE))
        text = SAMPLE.replace("Status: draft", "Status: jidoka-ready\nRev: 9")
        text = text.replace("## 12. Decisions made by the line\n\nNone.", "## 12. Decisions made by the line\n\nSomething.")
        self.assertEqual(A.digest(signed(A.parse(text))), base)

    def test_an_ac_change_changes_the_hash(self):
        self.assertNotEqual(A.digest(edited(SAMPLE, "200 with", "201 with")), A.digest(A.parse(SAMPLE)))

    def test_the_title_is_signed(self):
        self.assertNotEqual(A.digest(edited(SAMPLE, "Edit a note", "Edit notes")), A.digest(A.parse(SAMPLE)))


class FormatCheckTests(unittest.TestCase):
    def problems(self, old, new, ready=False):
        return A.check(edited(SAMPLE, old, new), ready=ready)

    def test_the_sample_is_valid(self):
        self.assertEqual(A.check(A.parse(SAMPLE)), [])

    def test_the_format_reference_example_is_valid(self):
        # The example in references/agreement-format.md is what refine copies
        # from, so it must pass the same check refine runs. Its hashes are
        # illustrative, so it is not ready; the format must hold.
        reference = (SCRIPT.parent.parent / "references/agreement-format.md").read_text(encoding="utf-8")
        example = reference.split("```markdown\n", 1)[1].split("\n```\n", 1)[0]
        self.assertEqual(A.check(A.parse(example)), [])

    def test_the_skeleton_is_valid(self):
        self.assertEqual(A.check(A.parse(A.render(A.skeleton("USR-9", "T", "file")))), [])

    def test_a_missing_section(self):
        found = self.problems("## 7. Out of scope\n\nEditing the body of a note, ~~tags~~.\n\n", "")
        self.assertIn("missing sections: 7. Out of scope", found)

    def test_an_unknown_heading(self):
        found = self.problems("## 7. Out of scope", "## 7. Not in scope")
        self.assertTrue(any("unknown heading '## 7. Not in scope'" in p for p in found), found)

    def test_an_empty_section(self):
        self.assertIn(
            "section 7 is empty: write 'None.' when nothing applies",
            self.problems("Editing the body of a note, ~~tags~~.", ""),
        )

    def test_a_reused_ac_id(self):
        found = self.problems("| AC-3 (removed) |", "| AC-1 (removed) |")
        self.assertIn("section 4: AC-1 is used twice; IDs are never reused", found)

    def test_an_active_ac_needs_given_when_then(self):
        self.assertIn("section 4: AC-2 has no When", self.problems("| the client sends PATCH |", "| |"))

    def test_wrong_columns(self):
        found = self.problems("| ID | Given | When | Then |", "| # | Given | When | Then |")
        self.assertTrue(any(p.startswith("section 4: columns must be") for p in found), found)

    def test_evidence_for_an_unknown_ac(self):
        self.assertIn("section 5: AC-9 is not in section 4", self.problems("| AC-2 | patch", "| AC-9 | patch"))

    def test_owner_must_be_a_role(self):
        found = self.problems("| BA | MEDIUM |", "| QA | MEDIUM |")
        self.assertIn("section 8: Q-1 Owner 'QA' must be one of BA, Dev Lead, QE", found)

    def test_exit_must_be_pr_or_merge(self):
        self.assertIn(
            "section 10: needs a line 'Exit: pr' or 'Exit: merge'",
            self.problems("Exit: merge", "Exit: ask"),
        )

    def test_a_secret_is_refused(self):
        found = self.problems("Graph: CAP-01.", "Token ghp_" + "a" * 36)
        self.assertIn("looks like a GitHub token: point to where it is kept instead", found)

    def test_tracker_must_be_file_or_a_work_item(self):
        found = self.problems("Tracker: file", f"Tracker: {URL}")
        self.assertIn("Tracker must be 'file' or 'ado <work item URL>'", found)
        self.assertEqual(self.problems("Tracker: file", f"Tracker: ado {URL}"), [])


class ReadyCheckTests(unittest.TestCase):
    def test_unsigned_is_not_ready(self):
        found = A.check(A.parse(SAMPLE), ready=True)
        self.assertEqual(found, [f"section 13: {role} has not signed" for role in A.ROLES])

    def test_signed_is_ready(self):
        self.assertEqual(A.check(signed(A.parse(SAMPLE)), ready=True), [])

    def test_a_change_after_sign_off_needs_a_new_sign_off(self):
        text = A.render(signed(A.parse(SAMPLE)))
        found = A.check(edited(text, "200 with", "201 with"), ready=True)
        self.assertEqual(len(found), 3)
        self.assertIn("it changed after sign-off, so BA signs again", found[0])

    def test_an_open_medium_question_blocks(self):
        agreement = signed(edited(SAMPLE, "| MEDIUM | answered |", "| MEDIUM | open |"))
        self.assertEqual(A.check(agreement, ready=True), ["section 8: Q-1 (MEDIUM, BA) is still open"])

    def test_an_open_low_question_does_not(self):
        agreement = signed(edited(SAMPLE, "| LOW | deferred |", "| LOW | open |"))
        self.assertEqual(A.check(agreement, ready=True), [])

    def test_every_active_ac_needs_evidence(self):
        agreement = signed(edited(SAMPLE, "| AC-2 | patch an unknown id", "| AC-1 | patch an unknown id"))
        self.assertEqual(A.check(agreement, ready=True), ["section 5: AC-2 has no scenario and evidence"])

    def test_a_statement_is_required(self):
        agreement = signed(edited(SAMPLE, "As an API client, I want to change a note's title, so that I can fix mistakes.", "None."))
        self.assertEqual(A.check(agreement, ready=True), ["section 1 (Statement) must be written before sign-off"])

    def test_one_name_on_two_roles_must_be_solo(self):
        found = A.check(signed(A.parse(SAMPLE), names=("Ana", "Ana", "Chen")), ready=True)
        self.assertIn("section 13: Ana signs more than one role, so each row's Mode must be solo", found)
        self.assertEqual(A.check(signed(A.parse(SAMPLE), mode="solo", names=("Ana",) * 3), ready=True), [])

    def test_a_new_project_needs_a_stack_instead_of_acs(self):
        text = A.render(A.parse(SAMPLE))
        start, end = text.index("## 4."), text.index("## 6.")
        text = text[:start] + "## 4. Acceptance criteria\n\nNone.\n\n## 5. QE: scenarios and evidence\n\nNone.\n\n" + text[end:]
        self.assertIn(
            "section 4 has no active AC, and section 6 names no 'Stack:' for a new project",
            A.check(signed(A.parse(text)), ready=True),
        )
        with_stack = edited(text, "- Method: PATCH, title only.", "- Stack: backend .NET, frontend React")
        self.assertEqual(A.check(signed(with_stack), ready=True), [])


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "story.md")
        Path(self.path).write_text(SAMPLE, encoding="utf-8")

    def tearDown(self):
        self.dir.cleanup()

    def test_new_refuses_to_overwrite(self):
        self.assertEqual(run("new", "--id", "X", "--title", "T", "-o", self.path)[0], 2)

    def test_sign_writes_rows_in_role_order_and_replaces_a_role(self):
        for role, name in (("QE", "Chen"), ("BA", "Ana"), ("QE", "Cy"), ("Dev Lead", "Ben")):
            code, out, _ = run("sign", self.path, "--role", role, "--name", name, "--mode", "live", "--date", "2026-11-07")
            self.assertEqual(code, 0, out)
        rows = A.rows_of(A.parse(Path(self.path).read_text()), 13, [])
        self.assertEqual([(r["Role"], r["Name"]) for r in rows], [("BA", "Ana"), ("Dev Lead", "Ben"), ("QE", "Cy")])
        self.assertEqual(run("check", "--ready", self.path)[0], 0)

    def test_sign_refuses_an_agreement_that_is_not_ready(self):
        Path(self.path).write_text(SAMPLE.replace("| MEDIUM | answered |", "| MEDIUM | open |"))
        code, out, err = run("sign", self.path, "--role", "BA", "--name", "Ana", "--mode", "live")
        self.assertEqual(code, 1)
        self.assertIn("Q-1 (MEDIUM, BA) is still open", out)
        self.assertIn("not signed", err)

    def test_status_ready_on_a_file_needs_every_sign_off(self):
        self.assertEqual(run("status", self.path, "--set", "jidoka-ready")[0], 1)
        Path(self.path).write_text(A.render(signed(A.parse(SAMPLE))))
        self.assertEqual(run("status", self.path, "--set", "jidoka-ready")[0], 0)
        self.assertIn("\nStatus: jidoka-ready\n", Path(self.path).read_text())

    def test_check_exit_codes(self):
        self.assertEqual(run("check", self.path)[0], 0)
        self.assertEqual(run("check", "--ready", self.path)[0], 1)
        self.assertEqual(run("check", os.path.join(self.dir.name, "missing.md"))[0], 2)


FAKE_AZ = '''#!/usr/bin/env python3
"""A stand-in for az: serves one work item from $FAKE_AZ_STATE and applies
JSON Patch bodies to it the way Azure DevOps does, rev test included."""
import json, os, sys
path = os.environ["FAKE_AZ_STATE"]
state = json.load(open(path))
args = sys.argv[1:]
state["calls"].append(args)
item = state["item"]
if args[:3] == ["boards", "work-item", "show"]:
    print(json.dumps(item))
elif args[:3] == ["boards", "work-item", "update"]:
    state.setdefault("comments", []).append(args[args.index("--discussion") + 1])
    item["rev"] += 1
elif args[0] == "rest":
    body = json.load(open(args[args.index("--body") + 1][1:]))
    state["bodies"].append(body)
    if state.get("refuse"):
        json.dump(state, open(path, "w"))
        sys.exit("ERROR: TF26071: This work item has been changed by someone else")
    for op in body:
        if op["op"] == "test" and op["value"] != item["rev"]:
            json.dump(state, open(path, "w"))
            sys.exit("ERROR: test operation failed")
        if op["op"] == "add":
            item["fields"][op["path"][len("/fields/"):]] = op["value"]
    item["rev"] += 1
    print(json.dumps(item))
json.dump(state, open(path, "w"))
'''


class AzureDevOpsTests(unittest.TestCase):
    """push and status against a fake az: what is sent, and what is kept."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        (root / "bin").mkdir()
        fake = root / "bin/az"
        fake.write_text(FAKE_AZ.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
        fake.chmod(0o755)
        self.state = root / "state.json"
        self.path = str(root / "story.md")
        self.env = {"PATH": f"{root / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}", "FAKE_AZ_STATE": str(self.state)}
        self.saved = {key: os.environ.get(key) for key in self.env}
        os.environ.update(self.env)

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.dir.cleanup()

    def serve(self, item, refuse=False):
        self.state.write_text(json.dumps({"item": item, "calls": [], "bodies": [], "refuse": refuse}))

    def served(self):
        return json.loads(self.state.read_text())

    def pull(self):
        code, out, err = run("pull", "--ado", URL, "-o", self.path)
        self.assertEqual(code, 0, err)
        return Path(self.path).read_text()

    def test_pull_uses_az_boards(self):
        self.serve(work_item(A.parse(SAMPLE)))
        self.assertIn("Rev: 18", self.pull())
        self.assertEqual(
            self.served()["calls"][0],
            ["boards", "work-item", "show", "--id", "4711", "--expand", "all", "-o", "json",
             "--org", "https://dev.azure.com/Contoso"],
        )

    def test_push_tests_the_rev_and_reads_back(self):
        self.serve(work_item(A.parse(SAMPLE)))
        Path(self.path).write_text(self.pull().replace("200 with", "201 with"))
        code, out, err = run("push", self.path)
        self.assertEqual(code, 0, err)
        body = self.served()["bodies"][0]
        self.assertEqual(body[0], {"op": "test", "path": "/rev", "value": 18})
        self.assertEqual([op["path"] for op in body[1:]], [f"/fields/{A.DESCRIPTION}", f"/fields/{A.ACCEPTANCE}"])
        text = Path(self.path).read_text()
        self.assertIn("Rev: 19", text)
        self.assertIn("201 with", text)
        self.assertIn(A.digest(A.parse(text)), out)

    def test_push_is_refused_when_someone_else_wrote_first(self):
        self.serve(work_item(A.parse(SAMPLE)))
        pulled = self.pull()
        item = self.served()["item"]
        item["rev"] = 19  # someone saved the work item after our pull
        self.serve(item)
        Path(self.path).write_text(pulled)
        code, _, err = run("push", self.path)
        self.assertEqual(code, 1)
        self.assertIn("pull it again, merge your change into what they wrote, and push", err)
        self.assertIn("Rev: 18", Path(self.path).read_text())

    def test_push_refuses_an_invalid_agreement_without_calling_az(self):
        self.serve(work_item(A.parse(SAMPLE)))
        Path(self.path).write_text(self.pull().replace("Exit: merge", "Exit: ask"))
        calls = len(self.served()["calls"])
        self.assertEqual(run("push", self.path)[0], 1)
        self.assertEqual(len(self.served()["calls"]), calls)

    def test_ready_tag_swaps_only_the_jidoka_tag(self):
        ready = signed(A.parse(SAMPLE.replace("USR-002", "4711")))
        self.serve(work_item(ready, tags="api; jidoka-blocked; team-a"))
        self.pull()
        code, _, err = run("status", self.path, "--set", "jidoka-ready")
        self.assertEqual(code, 0, err)
        served = self.served()
        self.assertEqual(served["bodies"][0][0], {"op": "test", "path": "/rev", "value": 18})
        self.assertEqual(served["item"]["fields"]["System.Tags"], "api; team-a; jidoka-ready")
        self.assertIn("Status: jidoka-ready", Path(self.path).read_text())

    def test_ready_tag_checks_the_work_item_not_the_local_file(self):
        # Signed locally, never pushed: the work item still holds the unsigned text.
        self.serve(work_item(A.parse(SAMPLE.replace("USR-002", "4711"))))
        Path(self.path).write_text(A.render(signed(A.parse(self.pull()))))
        code, out, _ = run("status", self.path, "--set", "jidoka-ready")
        self.assertEqual(code, 1)
        self.assertIn("BA has not signed", out)
        self.assertEqual(self.served()["bodies"], [])

    # --- the line's commands --------------------------------------------------

    def ready_item(self, tags="api; jidoka-ready"):
        return work_item(signed(A.parse(SAMPLE.replace("USR-002", "4711"))), tags=tags)

    def claim(self):
        snapshot = os.path.join(self.dir.name, "story.md")
        return run("claim", URL, "-o", snapshot), snapshot

    def test_claim_swaps_ready_for_running_and_writes_the_snapshot(self):
        self.serve(self.ready_item())
        (code, out, err), snapshot = self.claim()
        self.assertEqual(code, 0, err + out)
        served = self.served()
        self.assertEqual(served["bodies"][0][0], {"op": "test", "path": "/rev", "value": 18})
        self.assertEqual(served["item"]["fields"]["System.Tags"], "api; jidoka-running")
        snap = A.parse(Path(snapshot).read_text())
        self.assertEqual(snap.meta["Status"], "jidoka-running")
        self.assertEqual(snap.meta["Rev"], "19")
        self.assertEqual(snap.meta["Hash"], A.digest(snap))
        self.assertRegex(snap.meta["Fetched"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z$")
        self.assertIn("slug 4711-edit-a-note", out)
        self.assertEqual(A.check(snap, ready=True), [])

    def test_claim_refuses_a_story_another_run_holds(self):
        self.serve(self.ready_item(tags="jidoka-running"))
        (code, _, err), snapshot = self.claim()
        self.assertEqual(code, 1)
        self.assertIn("another run holds it", err)
        self.assertEqual(self.served()["bodies"], [])
        self.assertFalse(os.path.exists(snapshot))

    def test_claim_refuses_a_story_changed_after_sign_off(self):
        item = self.ready_item()
        item["fields"][A.ACCEPTANCE] = item["fields"][A.ACCEPTANCE].replace("200 with", "201 with")
        self.serve(item)
        (code, out, err), _ = self.claim()
        self.assertEqual(code, 1)
        self.assertIn("it changed after sign-off", out)
        self.assertIn("fails the ready check", err)
        self.assertEqual(self.served()["bodies"], [])

    def test_claim_loses_a_race(self):
        self.serve(self.ready_item(), refuse=True)
        (code, _, err), snapshot = self.claim()
        self.assertEqual(code, 1)
        self.assertIn("refused the write", err)
        self.assertFalse(os.path.exists(snapshot))

    def test_status_on_a_snapshot_leaves_the_snapshot_alone(self):
        self.serve(self.ready_item())
        (_, _, _), snapshot = self.claim()
        before = Path(snapshot).read_text()
        self.assertEqual(run("status", snapshot, "--set", "jidoka-blocked")[0], 0)
        self.assertEqual(self.served()["item"]["fields"]["System.Tags"], "api; jidoka-blocked")
        self.assertEqual(Path(snapshot).read_text(), before)

    def test_record_merges_the_line_decisions_and_keeps_the_signed_hash(self):
        # A role already confirmed AD-1 after an earlier run; this run's table
        # still lists it as pending, and adds AD-2.
        agreement = A.from_work_item(self.ready_item())
        agreement.sections[12] = "\n".join([
            A.table_line(A.TABLES[12]), A.table_line(["---"] * 7),
            A.table_line(["AD-1", "Whether a whitespace title is trimmed", "Trim, then validate",
                          "Matches create", "BA", "Drop the trim", "confirmed"]),
        ])
        item = work_item(agreement, tags="jidoka-running")
        self.serve(item)
        (_, _, _), snapshot = self.claim_running(item)
        decisions = os.path.join(self.dir.name, "09-decisions.md")
        Path(decisions).write_text(DECISIONS)
        code, out, err = run("record", snapshot, "--decisions", decisions)
        self.assertEqual(code, 0, err + out)
        back = A.from_work_item(self.served()["item"])
        rows = A.rows_of(back, 12, [])
        self.assertEqual([(r["ID"], r["Status"]) for r in rows], [("AD-1", "confirmed"), ("AD-2", "pending")])
        self.assertEqual(A.check(back, ready=True), [])
        self.assertEqual(len(self.served()["bodies"][-1]), 2)  # rev test + Description only

    def claim_running(self, item):
        snapshot = os.path.join(self.dir.name, "story.md")
        snap = A.from_work_item(item)
        snap.meta.update(Hash=A.digest(snap), Fetched="2026-11-07T10:00Z")
        Path(snapshot).write_text(A.render(snap))
        return (0, "", ""), snapshot

    def test_comment_goes_through_az_boards_with_the_mark(self):
        self.serve(self.ready_item())
        (_, _, _), snapshot = self.claim()
        text = os.path.join(self.dir.name, "question.md")
        Path(text).write_text("**Stopped:** the store must change.\n\n- Q: may it?")
        self.assertEqual(run("comment", snapshot, "--file", text)[0], 0)
        comment = self.served()["comments"][0]
        self.assertTrue(comment.startswith(A.COMMENT_MARK))
        self.assertIn("<strong>Stopped:</strong>", comment)


DECISIONS = textwrap.dedent(
    """\
    # Decisions made by the line - USR-002

    | ID | Story didn't say | Line chose | Why | Confirm by | Undo by | Status |
    | --- | --- | --- | --- | --- | --- | --- |
    | AD-1 | Whether a whitespace title is trimmed | Trim, then validate | Matches create | BA | Drop the trim | pending |
    | AD-2 | The order of the updated list | Unchanged order | Least surprise | BA | Sort on update | pending |

    Notes below the table are ignored.
    """
)


class LineFileTrackerTests(unittest.TestCase):
    """The line's commands on a story kept as a Markdown file in the repo."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.dir.name)
        os.makedirs("docs/stories")
        self.story = "docs/stories/usr-002-edit-note.md"
        ready = signed(A.parse(SAMPLE))
        ready.meta["Status"] = "jidoka-ready"
        Path(self.story).write_text(A.render(ready))

    def tearDown(self):
        os.chdir(self.cwd)
        self.dir.cleanup()

    def test_claim_writes_a_snapshot_and_leaves_the_story_file(self):
        before = Path(self.story).read_text()
        code, out, err = run("claim", self.story, "-o", "story.md")
        self.assertEqual(code, 0, err + out)
        snap = A.parse(Path("story.md").read_text())
        self.assertEqual(snap.meta["Source"], self.story)
        self.assertEqual(snap.meta["Status"], "jidoka-running")
        self.assertEqual(snap.meta["Hash"], A.digest(A.parse(before)))
        self.assertEqual(Path(self.story).read_text(), before)
        self.assertIn("slug usr-002-edit-a-note", out)

    def test_claim_records_the_path_from_the_repository_root(self):
        # Claimed from a worktree's copy, by a path that starts outside it,
        # the Source must still be the path inside the repository.
        import subprocess
        subprocess.run(["git", "init", "-q", "wt"], check=True)
        os.makedirs("wt/docs/stories")
        Path("wt/docs/stories/x.md").write_text(Path(self.story).read_text())
        code, out, err = run("claim", os.path.abspath("wt/docs/stories/x.md"), "-o", "story.md")
        self.assertEqual(code, 0, err + out)
        self.assertEqual(A.parse(Path("story.md").read_text()).meta["Source"], "docs/stories/x.md")

    def test_claim_refuses_a_draft_and_names_refine(self):
        Path(self.story).write_text(Path(self.story).read_text().replace("Status: jidoka-ready", "Status: draft"))
        code, _, err = run("claim", self.story, "-o", "story.md")
        self.assertEqual(code, 1)
        self.assertIn("run /jidoka:refine on it", err)
        self.assertFalse(os.path.exists("story.md"))

    def test_status_and_record_write_the_story_file_not_the_snapshot(self):
        run("claim", self.story, "-o", "story.md")
        snapshot = Path("story.md").read_text()
        self.assertEqual(run("status", "story.md", "--set", "jidoka-done")[0], 0)
        Path("09-decisions.md").write_text(DECISIONS)
        self.assertEqual(run("record", "story.md", "--decisions", "09-decisions.md")[0], 0)
        story = A.parse(Path(self.story).read_text())
        self.assertEqual(story.meta["Status"], "jidoka-done")
        self.assertEqual([r["ID"] for r in A.rows_of(story, 12, [])], ["AD-1", "AD-2"])
        self.assertEqual(A.check(story, ready=True), [])
        self.assertEqual(Path("story.md").read_text(), snapshot)

    def test_record_refuses_a_bad_decisions_table(self):
        run("claim", self.story, "-o", "story.md")
        Path("09-decisions.md").write_text(DECISIONS.replace("| BA | Drop the trim |", "| QA | Drop the trim |"))
        self.assertEqual(run("record", "story.md", "--decisions", "09-decisions.md")[0], 2)

    def test_comment_on_a_file_story_is_a_no_op(self):
        run("claim", self.story, "-o", "story.md")
        Path("q.md").write_text("question")
        code, out, _ = run("comment", "story.md", "--file", "q.md")
        self.assertEqual(code, 0)
        self.assertIn("no discussion", out)

    def test_compare_reports_ac_by_ac(self):
        old = A.parse(SAMPLE)
        text = SAMPLE.replace("200 with the updated note", "200 with the note")
        text = text.replace("| AC-2 | patch an unknown id | status and body |", "| AC-2 | patch an unknown id | the body |")
        text = text.replace("| AC-3 (removed) | | | |", "| AC-3 (removed) | | | |\n| AC-4 | a note | PATCH with no fields | 422 |")
        text = text.replace("Editing the body of a note", "Editing a note's body")
        self.assertEqual(
            A.compare(old, A.parse(text))[:-1],
            ["AC-1 changed", "AC-2 evidence changed", "AC-3 unchanged", "AC-4 added",
             "section 7 (Out of scope) changed"],
        )
        self.assertEqual(A.compare(old, old)[:-1], ["AC-1 unchanged", "AC-2 unchanged", "AC-3 unchanged"])

    def test_slug_is_stable_and_bounded(self):
        self.assertEqual(A.slug(A.parse(SAMPLE)), "usr-002-edit-a-note")
        long = A.parse(SAMPLE.replace("Edit a note", "Edit a note " + "and more words " * 6))
        self.assertLessEqual(len(A.slug(long)), 50)
        self.assertFalse(A.slug(long).endswith("-"))


if __name__ == "__main__":
    unittest.main()
