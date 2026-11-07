#!/usr/bin/env python3
"""Pick up the oldest jidoka-ready story and run /jidoka:line on it, unattended.

A timer (cron, a systemd timer) on a machine the team controls calls this.
Each call starts at most one run:

1. It takes this machine's lock, so one machine runs one story at a time.
2. It finds the stories tagged jidoka-ready in one Azure DevOps project,
   oldest first.
3. It starts a fresh container that runs the line on the first of them.

The line claims the story itself, a write Azure DevOps refuses if anyone got
there first, so two machines racing never build one story twice. A story left
jidoka-running with no change for --stale-hours is reported, never taken
over.

  pickup.py --org ORG_URL --project NAME --repo GIT_URL [--image IMAGE]
            [--env-file FILE] [--state-dir DIR] [--stale-hours N]
            [--docker CMD] [--dry-run]

The container is the runner image (runner/Dockerfile beside this script),
which skips Claude Code's permission prompts; nothing else does. --env-file
holds its credentials (see runner/run-story.sh). Each run's output goes to
{state dir}/runs/{id}-{time}.log.

Exit status: 0 nothing to do, another pick-up holds the lock, or the run ended
0; 1 the run failed or ended non-zero; 2 bad usage or no az.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from urllib.parse import quote

READY, RUNNING = "jidoka-ready", "jidoka-running"
WIQL = (
    "SELECT [System.Id], [System.Title], [System.Tags], [System.ChangedDate] FROM workitems "
    "WHERE [System.TeamProject] = @project AND [System.Tags] CONTAINS '{tag}' "
    "ORDER BY [System.ChangedDate] ASC"
)


class Usage(Exception):
    pass


def az(*args):
    exe = shutil.which("az")
    if not exe:
        raise Usage("the az CLI is not on PATH")
    done = subprocess.run([exe, *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise Usage((done.stderr or done.stdout).strip() or "az failed")
    return json.loads(done.stdout or "[]")


def stories(org, project, tag):
    """[(id, title, changed)] tagged `tag`, oldest change first."""
    items = az("boards", "query", "--org", org, "--project", project,
               "--wiql", WIQL.format(tag=tag), "-o", "json")
    found = []
    for item in items:
        fields = item.get("fields", {})
        tags = [t.strip() for t in (fields.get("System.Tags") or "").split(";")]
        if tag not in tags:  # CONTAINS also matches a longer tag
            continue
        found.append((item["id"], fields.get("System.Title", ""), fields.get("System.ChangedDate", "")))
    return sorted(found, key=lambda s: s[2])


def parse_time(value):
    """Azure DevOps times, such as 2026-11-07T09:12:30.53Z, to aware datetimes.
    The fraction is dropped: before Python 3.11, fromisoformat takes only 3 or
    6 digits."""
    try:
        return datetime.datetime.fromisoformat(re.sub(r"\.\d+", "", value).replace("Z", "+00:00"))
    except ValueError:
        return None


def take_lock(path):
    """True if this process now holds the lock. O_EXCL, not mkdir: some
    coreutils let two racing mkdir calls both succeed."""
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            try:
                with open(path) as held:
                    pid = int(held.read().strip() or 0)
            except (OSError, ValueError):
                pid = 0
            if pid and alive(pid):
                print(f"another pick-up (pid {pid}) is running; nothing to do")
                return False
            os.unlink(path)  # its owner died without releasing it
            continue
        with os.fdopen(fd, "w") as handle:
            handle.write(str(os.getpid()))
        return True
    return False


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def run_command(args, url):
    command = [args.docker, "run", "--rm"]
    if args.env_file:
        command += ["--env-file", args.env_file]
    for key, value in (("JIDOKA_SCHEDULED", "1"), ("JIDOKA_STORY", url),
                       ("JIDOKA_REPO", args.repo), ("JIDOKA_HOST", socket.gethostname())):
        command += ["-e", f"{key}={value}"]
    return command + [args.image]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--org", required=True, help="https://dev.azure.com/{org}")
    parser.add_argument("--project", required=True)
    parser.add_argument("--repo", required=True, help="the repository the stories are built in")
    parser.add_argument("--image", default="jidoka-runner")
    parser.add_argument("--env-file", help="the runner's credentials")
    parser.add_argument("--state-dir", default=os.path.expanduser("~/.local/state/jidoka/pickup"))
    parser.add_argument("--stale-hours", type=float, default=6)
    parser.add_argument("--docker", default="docker", help="docker, or podman")
    parser.add_argument("--dry-run", action="store_true", help="say what would run; run nothing")
    args = parser.parse_args(argv)
    org = args.org.rstrip("/")
    lock = os.path.join(args.state_dir, "pickup.lock")
    if not args.dry_run:
        os.makedirs(os.path.join(args.state_dir, "runs"), exist_ok=True)
        if not take_lock(lock):
            return 0
    try:
        return pick_and_run(args, org)
    finally:
        if not args.dry_run:
            os.unlink(lock)


def pick_and_run(args, org):
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        for story_id, title, changed in stories(org, args.project, RUNNING):
            when = parse_time(changed)
            if when and (now - when).total_seconds() > args.stale_hours * 3600:
                print(f"stale: {story_id} '{title}' has been {RUNNING} since {changed}; "
                      "check its run before anyone re-tags it")
        ready = stories(org, args.project, READY)
    except Usage as err:
        print(f"pickup.py: {err}", file=sys.stderr)
        return 2
    if not ready:
        print(f"nothing to do: no story is tagged {READY}")
        return 0
    story_id, title = ready[0][:2]
    url = f"{org}/{quote(args.project)}/_workitems/edit/{story_id}"
    command = run_command(args, url)
    if args.dry_run:
        print(f"would run {story_id} '{title}': {' '.join(command)}")
        return 0
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    log = os.path.join(args.state_dir, "runs", f"{story_id}-{stamp}.log")
    print(f"running {story_id} '{title}', log {log}")
    with open(log, "w") as out:
        code = subprocess.run(command, stdout=out, stderr=subprocess.STDOUT).returncode
    print(f"{story_id} ended with exit {code}")
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
