#!/usr/bin/env bash
# Scaffold for the line-minimal-story eval: turns the empty run workspace into
# a one-commit git repo of the notes-api fixture on `main`, with no remote.
#
# `claude plugin eval --scaffold` runs this as you, outside the agent's sandbox,
# in the empty workspace, with a minimal env (PATH, HOME, TMPDIR, TERM).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -R "$here/fixture/." .

# Written here rather than kept in fixture/, so this repo does not carry a
# nested CLAUDE.md that sessions working on the plugin would load.
cat > CLAUDE.md <<'EOF'
# CLAUDE.md

notes-api: an in-memory notes REST API on `node:http`, no dependencies.

- Test: `npm test` (built-in `node:test`). Run: `npm start`.
- Tests for `/notes` live in `test/notes.test.js`.
- Worktree directory: `.worktrees/` (git-ignored). Create feature worktrees
  there.
- The repository is local only: there is no remote, so finished stories merge
  into `main` locally.
- Backlog: `BACKLOG.md` is the single source of truth for story status.
EOF

git init -q -b main
# The run gets a fresh HOME with no global git identity; commits need one.
git config user.name "jidoka eval"
git config user.email "jidoka-eval@example.invalid"
git add -A
git commit -qm "notes-api: initial import"
