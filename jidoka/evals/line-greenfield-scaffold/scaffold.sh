#!/usr/bin/env bash
# Scaffold for the line-greenfield-scaffold eval: a git repository on `main`
# with no remote and no source code, whose one commit is TN-000, a signed,
# jidoka-ready agreement to set up the TeamNotes project. Its Stack line holds
# the Dev Lead's answers (both layers, the development password stub, the
# Neutral look, merge locally), so /jidoka:line runs project-setup without
# asking anything.
#
# `claude plugin eval --scaffold` runs this as you, outside the agent's sandbox,
# in the empty workspace, with a minimal env (PATH, HOME, TMPDIR, TERM).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
agreement() { python3 "$here/../../skills/refine/scripts/agreement.py" "$@"; }

git init -q -b main
# The run gets a fresh HOME with no global git identity; commits need one.
git config user.name "jidoka eval"
git config user.email "jidoka-eval@example.invalid"

story=docs/stories/tn-000-set-up-teamnotes.md
mkdir -p docs/stories
cat > "$story" <<'EOF'
# TN-000 - Set up TeamNotes

Tracker: file
Status: draft

## 1. Statement

As the TeamNotes team, I want a walking skeleton of the app, so that the
first stories have a backend, a frontend and a sign-in to build on.

## 2. Current behaviour

There is no code yet.

## 3. Desired behaviour

TeamNotes is a small app where a team keeps notes on their day. The
repository holds a backend and a frontend that run together locally, with a
development sign-in, and the project context later stories are built from.

## 4. Acceptance criteria

None.

## 5. QE: scenarios and evidence

None.

## 6. Dev Lead: decisions and constraints

- Stack: backend .NET + frontend React; name TeamNotes; passwords dev-stub; look neutral; git merge

## 7. Out of scope

Every feature beyond sign-in: the first stories add them.

## 8. Open questions

None.

## 9. Decisions log

| ID | Decision | Rationale | Rejected | Owner | Date |
| --- | --- | --- | --- | --- | --- |
| D-1 | Verify passwords with the development stub for now | No identity source is chosen yet | Local password hashes | Dev Lead | 2026-11-07 |

## 10. Autonomy policy

Exit: merge
Stop also on: nothing beyond the defaults.

## 11. References and suggested skills

None.

## 12. Decisions made by the line

None.

## 13. Sign-off

None.
EOF
for signer in "BA:Ana Lim" "Dev Lead:Ben Tan" "QE:Chen Ng"; do
  agreement sign "$story" --role "${signer%%:*}" --name "${signer#*:}" --mode live --date 2026-11-07 >/dev/null
done
agreement status "$story" --set jidoka-ready >/dev/null

git add -A
git commit -qm "stories: TN-000 set up TeamNotes"
