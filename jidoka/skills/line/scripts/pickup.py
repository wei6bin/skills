#!/usr/bin/env python3
# GENERATED copy of src/skills/line/scripts/pickup.py by scripts/render.py (just build). Edit the source.
"""Pick up the oldest jidoka-ready story and run /jidoka:line on it, unattended.

A timer (cron, a systemd timer) on a machine the team controls calls this.
Each call starts at most one run:

1. It takes this machine's lock, so one machine runs one story at a time.
2. It finds the stories tagged jidoka-ready in one Azure DevOps project,
   oldest first, skipping any whose run failed here within --retry-hours.
3. It starts a fresh container that runs the line on the first of them, and
   kills it after --max-hours.

The line claims the story itself, a write Azure DevOps refuses if anyone got
there first, so two machines racing never build one story twice. A story left
jidoka-running with no change for --stale-hours is reported, never taken
over.

  pickup.py --org ORG_URL --project NAME --repo GIT_URL [--image IMAGE]
            [--env-file FILE] [--state-dir DIR] [--stale-hours N]
            [--retry-hours N] [--max-hours N] [--docker CMD] [--dry-run]

The container is the runner image (runner/Dockerfile beside this script),
which skips Claude Code's permission prompts; nothing else does. --env-file
holds its credentials (see runner/run-story.sh). Each run's output goes to
{state dir}/runs/{id}-{time}.log. Linux or macOS: the lock is flock(2).

Exit status: 0 nothing to do, another pick-up holds the lock, or the run ended
0; 1 the run failed, ended non-zero or ran out of time; 2 bad usage, or az or
docker unusable.
"""

import argparse
import datetime
import fcntl
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
    try:
        return json.loads(done.stdout or "[]")
    except ValueError as err:
        raise Usage(f"az printed something that is not JSON: {done.stdout[:200]!r}") from err


def stories(org, project, tag):
    """[(id, title, changed)] tagged `tag`, oldest change first."""
    items = az("boards", "query", "--org", org, "--project", project,
               "--wiql", WIQL.format(tag=tag), "-o", "json")
    found = []
    for item in items:
        fields = item.get("fields", {})
        tags = [t.strip().lower() for t in (fields.get("System.Tags") or "").split(";")]
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
    """An open file holding this machine's lock, or None if another pick-up
    holds it. flock(2): the kernel drops the lock when its holder exits, however
    it exits, so there is no stale lock to clear and no window to race in."""
    handle = open(path, "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def load_failures(path):
    try:
        with open(path) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_failures(path, failures):
    with open(path + ".tmp", "w") as handle:
        json.dump(failures, handle, indent=1)
    os.replace(path + ".tmp", path)


def run_command(args, url, name):
    command = [args.docker, "run", "--rm", "--name", name]
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
    parser.add_argument("--stale-hours", type=float, default=6,
                        help="report a story jidoka-running this long without a change")
    parser.add_argument("--retry-hours", type=float, default=2,
                        help="skip a story whose run failed here this recently")
    parser.add_argument("--max-hours", type=float, default=6,
                        help="kill a run that takes longer than this")
    parser.add_argument("--docker", default="docker", help="docker, or podman")
    parser.add_argument("--dry-run", action="store_true", help="say what would run; run nothing")
    args = parser.parse_args(argv)
    org = args.org.rstrip("/")
    if not args.dry_run:
        os.makedirs(os.path.join(args.state_dir, "runs"), exist_ok=True)
        lock = take_lock(os.path.join(args.state_dir, "pickup.lock"))
        if lock is None:
            print("another pick-up is running on this machine; nothing to do")
            return 0
    try:
        return pick_and_run(args, org)
    finally:
        if not args.dry_run:
            lock.close()


def pick_and_run(args, org):
    now = datetime.datetime.now(datetime.timezone.utc)
    failures_path = os.path.join(args.state_dir, "failures.json")
    failures = load_failures(failures_path)
    try:
        for story_id, title, changed in stories(org, args.project, RUNNING):
            when = parse_time(changed)
            if when and (now - when).total_seconds() > args.stale_hours * 3600:
                print(f"stale: {story_id} '{title}' has been {RUNNING} since {changed}; "
                      "check its run before anyone re-tags it")
        ready = stories(org, args.project, READY)
    except Usage as err:
        print(f"pickup.py: {err}", file=sys.stderr)
        return 2
    # A story whose run failed here recently waits: retrying it every tick
    # would starve the stories behind it and repeat whatever it posted.
    waiting = []
    for story_id, title, _ in ready:
        failed = parse_time(failures.get(str(story_id), ""))
        if failed and (now - failed).total_seconds() < args.retry_hours * 3600:
            waiting.append(story_id)
    ready = [s for s in ready if s[0] not in waiting]
    if waiting:
        print(f"waiting after a failed run here: {', '.join(map(str, waiting))}")
    if not ready:
        print(f"nothing to do: no story is tagged {READY}" + (" that is not waiting" if waiting else ""))
        return 0
    story_id, title = ready[0][:2]
    url = f"{org}/{quote(args.project)}/_workitems/edit/{story_id}"
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    name = f"jidoka-{story_id}-{stamp.lower()}"
    command = run_command(args, url, name)
    if args.dry_run:
        print(f"would run {story_id} '{title}': {' '.join(command)}")
        return 0
    log = os.path.join(args.state_dir, "runs", f"{story_id}-{stamp}.log")
    print(f"running {story_id} '{title}', log {log}")
    try:
        with open(log, "w") as out:
            code = subprocess.run(command, stdout=out, stderr=subprocess.STDOUT,
                                  timeout=args.max_hours * 3600).returncode
    except FileNotFoundError:
        print(f"pickup.py: {args.docker} is not installed", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        # The client is gone; the container is not. Stop it, so it neither
        # holds the machine nor goes on writing to the story.
        subprocess.run([args.docker, "kill", name], capture_output=True)
        code = None
    if code == 0:
        failures.pop(str(story_id), None)
    else:
        failures[str(story_id)] = now.isoformat()
    save_failures(failures_path, failures)
    if code is None:
        print(f"{story_id} ran past {args.max_hours} hours and was stopped")
        return 1
    print(f"{story_id} ended with exit {code}")
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
