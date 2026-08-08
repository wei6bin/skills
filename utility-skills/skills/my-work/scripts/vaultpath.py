"""Locate the Obsidian vault without hardcoding anyone's home directory.

Resolution order, first hit wins:

1. an explicit ``--vault`` argument passed by the caller
2. ``$OBSIDIAN_VAULT``
3. a ``.vault-path`` file sitting next to these scripts (gitignored, so a local
   install can pin its own vault without that path entering version control)
4. ``~/.config/my-work/vault-path``
5. walking up from the current directory looking for a ``.obsidian`` folder

Steps 3 and 4 differ in lifetime, not in kind. When the skill is installed as a
marketplace plugin its directory is versioned by commit, so anything written
beside the scripts is discarded on the next plugin update; the user-level file
outlives that. The script-adjacent file is still checked first, because someone
who pinned a path for one specific checkout means that checkout.

Failing all five is a clear error rather than a silent wrong guess, because
writing thread notes into the wrong directory is worse than not running.
"""

import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".vault-path")

USER_CONFIG_FILE = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "my-work",
    "vault-path",
)


def resolve(explicit=None):
    candidates = []

    if explicit:
        candidates.append(os.path.expanduser(explicit))

    env = os.environ.get("OBSIDIAN_VAULT")
    if env:
        candidates.append(os.path.expanduser(env))

    for path in (CONFIG_FILE, USER_CONFIG_FILE):
        pinned = _read_pin(path)
        if pinned:
            candidates.append(pinned)

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
        "Pin it once (survives plugin updates):\n"
        f"  mkdir -p {os.path.dirname(USER_CONFIG_FILE)}\n"
        f"  echo /path/to/vault > {USER_CONFIG_FILE}\n"
        "Or, for a single run:\n"
        "  --vault /path/to/vault\n"
        "  export OBSIDIAN_VAULT=/path/to/vault\n"
        "or run from inside the vault."
    )


def _read_pin(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                return os.path.expanduser(line)
    return None


def _walk_up(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, ".obsidian")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
