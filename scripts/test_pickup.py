#!/usr/bin/env python3
"""Unit tests for the line skill's scheduled pick-up, src/skills/line/scripts/pickup.py.

It runs against a fake `az` (serving `az boards query` and `work-item show`
from a JSON file), a fake `docker` (recording its arguments, and writing what
a run hands back) and a fake `git` (serving `ls-remote`): which story it
picks, the container it starts, the lock, the stale-claim report, and the
hold on a broken base.

Run: just test (python3 -m unittest discover -s scripts -p 'test_*.py').
"""

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("pickup", ROOT / "src/skills/line/scripts/pickup.py")
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)
_aspec = importlib.util.spec_from_file_location("agreement", ROOT / "src/skills/refine/scripts/agreement.py")
A = importlib.util.module_from_spec(_aspec)
_aspec.loader.exec_module(A)

ORG = "https://dev.azure.com/Contoso"

FAKE_AZ = """#!{python}
import json, os, sys
state = json.load(open(os.environ["FAKE_STATE"]))
if state.get("az_garbage"):
    print("WARNING: not json")
    sys.exit(0)
args = sys.argv[1:]
if args[:2] == ["boards", "work-item"]:
    shown = state.get("show", {{}}).get(args[args.index("--id") + 1])
    if shown is None:
        print("no such work item", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(shown))
    sys.exit(0)
wiql = args[args.index("--wiql") + 1]
tag = wiql.split("CONTAINS '")[1].split("'")[0]
items = [i for i in state["items"] if tag in i["fields"].get("System.Tags", "")]
print(json.dumps(items))
"""

FAKE_DOCKER = """#!{python}
import json, os, sys, time
path = os.environ["FAKE_STATE"]
state = json.load(open(path))
state.setdefault("docker", []).append(sys.argv[1:])
json.dump(state, open(path, "w"))
if sys.argv[1] == "run":
    print("line run output", flush=True)
    out = sys.argv[sys.argv.index("-v") + 1].split(":")[0]
    if state.get("base_red"):
        open(os.path.join(out, "base-red"), "w").write(state["base_red"] + "\\n")
    time.sleep(state.get("sleep", 0))
sys.exit(state.get("docker_exit", 0) if sys.argv[1] == "run" else 0)
"""


FAKE_GIT = """#!{python}
import json, os, sys
state = json.load(open(os.environ["FAKE_STATE"]))
if sys.argv[1] != "ls-remote" or state.get("git_fails"):
    sys.exit(128)
branch = sys.argv[3].split("refs/heads/", 1)[1]
sha = state.get("heads", {{}}).get(branch)
if sha:
    print(sha + "\\trefs/heads/" + branch)
"""

SHA1, SHA2 = "1" * 40, "2" * 40


def shown(story_id, base=None):
    """An `az boards work-item show` reply holding a signed-looking agreement
    whose section 10 names `base`, or no base."""
    agreement = A.parse(A.render(A.skeleton(f"USR-{story_id}", "A story", "file")))
    if base:
        agreement.sections[10] = f"Exit: pr\n\nBase: {base}\n\nStop also on: nothing beyond the defaults."
    description, acceptance = A.to_fields(agreement)
    return {
        "id": story_id, "rev": 3,
        "_links": {"html": {"href": f"{ORG}/Book%20ings/_workitems/edit/{story_id}"}},
        "fields": {"System.Title": "A story", "System.TeamProject": "Book ings",
                   "System.Tags": "jidoka-ready", A.DESCRIPTION: description, A.ACCEPTANCE: acceptance},
    }


def item(story_id, tags, changed, title="A story"):
    return {"id": story_id, "fields": {"System.Title": title, "System.Tags": tags, "System.ChangedDate": changed}}


class PickupTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        (root / "bin").mkdir()
        for name, text in (("az", FAKE_AZ), ("docker", FAKE_DOCKER), ("git", FAKE_GIT)):
            path = root / "bin" / name
            path.write_text(text.format(python=sys.executable))
            path.chmod(0o755)
        self.state = root / "state.json"
        self.state_dir = root / "pickup"
        self.saved = {k: os.environ.get(k) for k in ("PATH", "FAKE_STATE")}
        os.environ["PATH"] = f"{root / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"
        os.environ["FAKE_STATE"] = str(self.state)

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.dir.cleanup()

    def serve(self, items, docker_exit=0, **extra):
        self.state.write_text(json.dumps({"items": items, "docker_exit": docker_exit, **extra}))

    def lock_is_free(self):
        import fcntl
        with open(self.state_dir / "pickup.lock") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            return True

    def run_pickup(self, *extra):
        out = io.StringIO()
        argv = ["--org", ORG + "/", "--project", "Book ings", "--repo", "https://example.invalid/r.git",
                "--state-dir", str(self.state_dir), "--env-file", "/etc/jidoka/runner.env", *extra]
        with contextlib.redirect_stdout(out):
            code = P.main(argv)
        return code, out.getvalue()

    def docker_calls(self):
        return json.loads(self.state.read_text()).get("docker", [])

    def test_nothing_ready_runs_nothing(self):
        self.serve([item(1, "api", "2026-11-01T00:00:00Z")])
        code, out = self.run_pickup()
        self.assertEqual(code, 0)
        self.assertIn("nothing to do", out)
        self.assertEqual(self.docker_calls(), [])

    def test_runs_the_oldest_ready_story_in_the_runner_image(self):
        self.serve([
            item(12, "jidoka-ready", "2026-11-06T10:00:00.53Z", "Newer"),
            item(7, "api; jidoka-ready", "2026-11-05T10:00:00Z", "Older"),
            item(9, "jidoka-ready-later", "2026-11-01T00:00:00Z", "Not this tag"),
        ])
        code, out = self.run_pickup()
        self.assertEqual(code, 0, out)
        [call] = self.docker_calls()
        self.assertEqual(call[:3], ["run", "--rm", "--name"])
        self.assertTrue(call[3].startswith("jidoka-7-"))
        self.assertEqual(call[4:6], ["--env-file", "/etc/jidoka/runner.env"])
        self.assertIn("JIDOKA_STORY=https://dev.azure.com/Contoso/Book%20ings/_workitems/edit/7", call)
        self.assertIn("JIDOKA_SCHEDULED=1", call)
        self.assertIn("JIDOKA_REPO=https://example.invalid/r.git", call)
        self.assertIn("JIDOKA_OUT=/jidoka-out", call)
        mount = call[call.index("-v") + 1]
        self.assertTrue(mount.startswith(str(self.state_dir / "runs" / "7-")), mount)
        self.assertTrue(mount.endswith(".out:/jidoka-out"), mount)
        self.assertEqual(call[-1], "jidoka-runner")
        logs = list((self.state_dir / "runs").glob("*.log"))
        self.assertEqual(len(logs), 1)
        self.assertTrue(logs[0].name.startswith("7-"))
        self.assertIn("line run output", logs[0].read_text())
        self.assertTrue(self.lock_is_free())

    def test_a_failed_run_exits_1_and_releases_the_lock(self):
        self.serve([item(7, "jidoka-ready", "2026-11-05T10:00:00Z")], docker_exit=3)
        code, out = self.run_pickup()
        self.assertEqual(code, 1)
        self.assertIn("ended with exit 3", out)
        self.assertTrue(self.lock_is_free())

    def test_a_held_lock_means_another_run_is_going(self):
        import fcntl
        self.serve([item(7, "jidoka-ready", "2026-11-05T10:00:00Z")])
        self.state_dir.mkdir(parents=True)
        with open(self.state_dir / "pickup.lock", "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            code, out = self.run_pickup()
        self.assertEqual(code, 0)
        self.assertIn("another pick-up", out)
        self.assertEqual(self.docker_calls(), [])

    def test_a_lock_file_nobody_holds_does_not_block(self):
        # What a crashed pick-up leaves: the file, but no lock on it.
        self.serve([item(7, "jidoka-ready", "2026-11-05T10:00:00Z")])
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "pickup.lock").write_text("999999999")
        code, _ = self.run_pickup()
        self.assertEqual(code, 0)
        self.assertEqual(len(self.docker_calls()), 1)

    def test_a_failed_story_waits_and_the_next_one_runs(self):
        stories = [item(7, "jidoka-ready", "2026-11-05T10:00:00Z", "Older"),
                   item(8, "jidoka-ready", "2026-11-06T10:00:00Z", "Newer")]
        self.serve(stories, docker_exit=1)
        self.assertEqual(self.run_pickup()[0], 1)
        self.serve(stories)
        code, out = self.run_pickup()
        self.assertEqual(code, 0)
        self.assertIn("waiting after a failed run here: 7", out)
        self.assertIn("JIDOKA_STORY=https://dev.azure.com/Contoso/Book%20ings/_workitems/edit/8",
                      self.docker_calls()[0])
        # Once --retry-hours has passed, it is tried again.
        code, out = self.run_pickup("--retry-hours", "0")
        self.assertIn("edit/7", " ".join(self.docker_calls()[-1]))

    def test_a_run_past_its_time_is_killed(self):
        self.serve([item(7, "jidoka-ready", "2026-11-05T10:00:00Z")], sleep=30)
        code, out = self.run_pickup("--max-hours", str(1 / 3600))
        self.assertEqual(code, 1)
        self.assertIn("was stopped", out)
        calls = self.docker_calls()
        self.assertEqual(calls[-1][:1], ["kill"])
        self.assertEqual(calls[-1][1], calls[0][3])  # the container it named
        self.assertTrue(self.lock_is_free())

    def test_no_docker_is_exit_2(self):
        self.serve([item(7, "jidoka-ready", "2026-11-05T10:00:00Z")])
        self.assertEqual(self.run_pickup("--docker", "no-such-docker")[0], 2)

    def test_az_output_that_is_not_json_is_exit_2(self):
        self.serve([], az_garbage=True)
        self.assertEqual(self.run_pickup()[0], 2)

    def test_dry_run_says_what_it_would_run(self):
        self.serve([item(7, "jidoka-ready", "2026-11-05T10:00:00Z", "Older")])
        code, out = self.run_pickup("--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("would run 7 'Older': docker run --rm", out)
        self.assertEqual(self.docker_calls(), [])
        self.assertFalse(self.state_dir.exists())

    def test_a_broken_base_holds_its_stories_until_it_moves(self):
        stories = [item(7, "jidoka-ready", "2026-11-05T10:00:00Z", "On main"),
                   item(8, "jidoka-ready", "2026-11-06T10:00:00Z", "Also on main"),
                   item(9, "jidoka-ready", "2026-11-07T10:00:00Z", "On a release line")]
        show = {"7": shown(7), "8": shown(8, base="main"), "9": shown(9, base="release/2.3")}
        # 7's run stops on its base, before the claim: the story stays ready.
        self.serve(stories, show=show, heads={"main": SHA1}, base_red=f"main {SHA1}")
        code, out = self.run_pickup()
        self.assertEqual(code, 0, out)
        self.assertIn(f"base main is broken at {SHA1[:12]}", out)
        # Not a failure: nothing in failures.json, so only the hold keeps 7 back.
        self.assertEqual(json.loads((self.state_dir / "failures.json").read_text()), {})
        # 7 (the default branch) and 8 (Base: main) wait; 9 is on another base.
        self.serve(stories, show=show, heads={"main": SHA1})
        code, out = self.run_pickup()
        self.assertIn("held: base main", out)
        self.assertIn("waiting until it moves: 7, 8", out)
        [call] = self.docker_calls()
        self.assertIn("edit/9", " ".join(call))
        # Once main moves, its stories run again, oldest first.
        self.serve(stories, show=show, heads={"main": SHA2})
        code, out = self.run_pickup()
        self.assertIn("base main moved", out)
        self.assertIn("edit/7", " ".join(self.docker_calls()[-1]))
        self.assertEqual(json.loads((self.state_dir / "holds.json").read_text()), {})

    def test_a_hold_ends_after_retry_hours_when_the_remote_cannot_be_seen(self):
        stories = [item(7, "jidoka-ready", "2026-11-05T10:00:00Z")]
        self.serve(stories, show={"7": shown(7)}, base_red=f"main {SHA1}")
        self.run_pickup()
        self.serve(stories, show={"7": shown(7)}, git_fails=True)
        code, out = self.run_pickup()
        self.assertIn("nothing to do", out)
        self.assertIn("or on a held base", out)
        self.assertEqual(self.docker_calls(), [])
        code, out = self.run_pickup("--retry-hours", "0")
        self.assertIn("tried again", out)
        self.assertEqual(len(self.docker_calls()), 1)

    def test_a_hand_back_that_is_not_a_base_and_commit_is_ignored(self):
        self.serve([item(7, "jidoka-ready", "2026-11-05T10:00:00Z")], base_red="main not-a-commit")
        code, out = self.run_pickup()
        self.assertEqual(code, 0)
        self.assertNotIn("is broken", out)
        self.assertFalse((self.state_dir / "holds.json").exists())

    def test_a_stale_claim_is_reported_and_left_alone(self):
        self.serve([
            item(3, "jidoka-running", "2020-01-01T00:00:00Z", "Stuck"),
            item(4, "jidoka-running", "2999-01-01T00:00:00Z", "Fresh"),
        ])
        code, out = self.run_pickup()
        self.assertEqual(code, 0)
        self.assertIn("stale: 3 'Stuck'", out)
        self.assertNotIn("'Fresh'", out)
        self.assertEqual(self.docker_calls(), [])


if __name__ == "__main__":
    unittest.main()
