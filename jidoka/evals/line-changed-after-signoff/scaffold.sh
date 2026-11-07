#!/usr/bin/env bash
# Scaffold for the line-changed-after-signoff eval: the line-minimal-story repo (the notes API on
# `main`, no remote, USR-001 as a signed jidoka-ready agreement), then
# one commit that edits AC-1 after the three sign-offs, as an edit made
# straight in the tracker would, leaving the story tagged jidoka-ready.
#
# `claude plugin eval --scaffold` runs this as you, outside the agent's sandbox,
# in the empty workspace, with a minimal env (PATH, HOME, TMPDIR, TERM).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$here/../line-minimal-story/scaffold.sh"
story=docs/stories/usr-001-delete-note.md
edit() {  # edit FILE OLD NEW: replace one exact fragment, or fail
  python3 - "$@" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path).read()
assert text.count(old) == 1, f"{old!r} not found once in {path}"
open(path, "w").write(text.replace(old, new))
PY
}

edit "$story" "| 204 with an empty body;" "| 200 with the deleted note;"
git commit -qam "stories: USR-001 AC-1 edited after sign-off"
