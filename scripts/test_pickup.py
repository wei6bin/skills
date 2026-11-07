#!/usr/bin/env python3
"""Unit tests for the line skill's scheduled pick-up, src/skills/line/scripts/pickup.py.

It runs against a fake `az` (serving `az boards query` from a JSON file) and a
fake `docker` (recording its arguments): which story it picks, the container
it starts, the lock, and the stale-claim report.

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

ORG = "https://dev.azure.com/Contoso"

FAKE_AZ = """#!{python}
import json, os, sys
state = json.load(open(os.environ["FAKE_STATE"]))
args = sys.argv[1:]
wiql = args[args.index("--wiql") + 1]
tag = wiql.split("CONTAINS '")[1].split("'")[0]
items = [i for i in state["items"] if tag in i["fields"].get("System.Tags", "")]
print(json.dumps(items))
"""

FAKE_DOCKER = """#!{python}
import json, os, sys
path = os.environ["FAKE_STATE"]
state = json.load(open(path))
state.setdefault("docker", []).append(sys.argv[1:])
json.dump(state, open(path, "w"))
print("line run output")
sys.exit(state.get("docker_exit", 0))
"""


def item(story_id, tags, changed, title="A story"):
    return {"id": story_id, "fields": {"System.Title": title, "System.Tags": tags, "System.ChangedDate": changed}}


class PickupTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        (root / "bin").mkdir()
        for name, text in (("az", FAKE_AZ), ("docker", FAKE_DOCKER)):
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

    def serve(self, items, docker_exit=0):
        self.state.write_text(json.dumps({"items": items, "docker_exit": docker_exit}))

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
        self.assertEqual(call[:4], ["run", "--rm", "--env-file", "/etc/jidoka/runner.env"])
        self.assertIn("JIDOKA_STORY=https://dev.azure.com/Contoso/Book%20ings/_workitems/edit/7", call)
        self.assertIn("JIDOKA_SCHEDULED=1", call)
        self.assertIn("JIDOKA_REPO=https://example.invalid/r.git", call)
        self.assertEqual(call[-1], "jidoka-runner")
        logs = list((self.state_dir / "runs").iterdir())
        self.assertEqual(len(logs), 1)
        self.assertTrue(logs[0].name.startswith("7-"))
        self.assertIn("line run output", logs[0].read_text())
        self.assertFalse((self.state_dir / "pickup.lock").exists())

    def test_a_failed_run_exits_1_and_releases_the_lock(self):
        self.serve([item(7, "jidoka-ready", "2026-11-05T10:00:00Z")], docker_exit=3)
        code, out = self.run_pickup()
        self.assertEqual(code, 1)
        self.assertIn("ended with exit 3", out)
        self.assertFalse((self.state_dir / "pickup.lock").exists())

    def test_a_live_lock_means_another_run_is_going(self):
        self.serve([item(7, "jidoka-ready", "2026-11-05T10:00:00Z")])
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "pickup.lock").write_text(str(os.getpid()))
        code, out = self.run_pickup()
        self.assertEqual(code, 0)
        self.assertIn("another pick-up", out)
        self.assertEqual(self.docker_calls(), [])
        self.assertTrue((self.state_dir / "pickup.lock").exists())

    def test_a_dead_owner_s_lock_is_taken_over(self):
        self.serve([item(7, "jidoka-ready", "2026-11-05T10:00:00Z")])
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "pickup.lock").write_text("999999999")
        code, _ = self.run_pickup()
        self.assertEqual(code, 0)
        self.assertEqual(len(self.docker_calls()), 1)

    def test_dry_run_says_what_it_would_run(self):
        self.serve([item(7, "jidoka-ready", "2026-11-05T10:00:00Z", "Older")])
        code, out = self.run_pickup("--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("would run 7 'Older': docker run --rm", out)
        self.assertEqual(self.docker_calls(), [])
        self.assertFalse(self.state_dir.exists())

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
