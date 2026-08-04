"""Locate the Obsidian vault without hardcoding anyone's home directory.

Resolution order, first hit wins:

1. an explicit ``--vault`` argument passed by the caller
2. ``$OBSIDIAN_VAULT``
3. a ``.vault-path`` file sitting next to these scripts (gitignored, so a local
   install can pin its own vault without that path entering version control)
4. walking up from the current directory looking for a ``.obsidian`` folder

Failing all four is a clear error rather than a silent wrong guess, because
writing thread notes into the wrong directory is worse than not running.
"""

import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".vault-path")


def resolve(explicit=None):
    candidates = []

    if explicit:
        candidates.append(os.path.expanduser(explicit))

    env = os.environ.get("OBSIDIAN_VAULT")
    if env:
        candidates.append(os.path.expanduser(env))

    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    candidates.append(os.path.expanduser(line))
                    break

    found = _walk_up(os.getcwd())
    if found:
        candidates.append(found)

    for c in candidates:
        if os.path.isdir(os.path.join(c, "work", "threads")):
            return c
    for c in candidates:
        if os.path.isdir(c):
            return c

    raise SystemExit(
        "Could not locate the Obsidian vault.\n"
        "Set one of the following:\n"
        "  --vault /path/to/vault\n"
        "  export OBSIDIAN_VAULT=/path/to/vault\n"
        f"  echo /path/to/vault > {CONFIG_FILE}\n"
        "or run from inside the vault."
    )


def _walk_up(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, ".obsidian")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
