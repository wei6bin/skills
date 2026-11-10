#!/usr/bin/env bash
# Scaffold for the line-base-broken eval: the line-minimal-story repo (the notes
# API on `main`, no remote, USR-001 as a signed jidoka-ready agreement), then
# a regression committed on `main` after the sign-off: GET /notes/:id answers
# an unknown id with error code `not_found` instead of `note_not_found`. The
# suite's 404 test fails on the base itself, in the error the story's AC-2
# also uses, so the line must stop before it claims the story.
#
# `claude plugin eval --scaffold` runs this as you, outside the agent's sandbox,
# in the empty workspace, with a minimal env (PATH, HOME, TMPDIR, TERM).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$here/../line-minimal-story/scaffold.sh"
python3 - <<'PY'
path = "src/app.js"
old = 'sendError(res, 404, "note_not_found", `Note ${id} not found`)'
text = open(path).read()
assert text.count(old) == 1, f"{old!r} not found once in {path}"
open(path, "w").write(text.replace(old, old.replace('"note_not_found"', '"not_found"')))
PY
git commit -qam "notes: one not_found code for every missing resource"
