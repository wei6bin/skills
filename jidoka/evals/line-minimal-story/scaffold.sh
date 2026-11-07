#!/usr/bin/env bash
# Scaffold for the line-minimal-story eval: turns the empty run workspace into
# a one-commit git repo of the notes-api fixture on `main`, with no remote, and
# USR-001 as a signed, jidoka-ready agreement in docs/stories/. The agreement
# script itself signs it, so the hashes are real. The other line cases start
# from this repo and change the agreement.
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
- Stories: signed agreements in `docs/stories/`, one file each.
EOF

agreement() { python3 "$here/../../skills/refine/scripts/agreement.py" "$@"; }
story=docs/stories/usr-001-delete-note.md
mkdir -p docs/stories
cat > "$story" <<'EOF'
# USR-001 - Delete a note

Tracker: file
Status: draft

## 1. Statement

As an API client, I want to delete a note, so that notes I no longer need stop
appearing in the list.

## 2. Current behaviour

Notes can be created, listed and fetched one at a time. Nothing removes a
note.

## 3. Desired behaviour

A client deletes a note by its id. The note is gone at once: the list no
longer shows it, and fetching it is a 404. Deleting an id that does not exist
is a 404 with the API's usual error envelope.

## 4. Acceptance criteria

| ID | Given | When | Then |
| --- | --- | --- | --- |
| AC-1 | an existing note | the client sends DELETE /notes/:id | 204 with an empty body; the note is absent from GET /notes, and GET /notes/:id returns 404 |
| AC-2 | no note with that id | the client sends DELETE /notes/:id | 404 with the standard error envelope and error code `note_not_found` |

## 5. QE: scenarios and evidence

| AC | Scenario | Evidence | Data |
| --- | --- | --- | --- |
| AC-1 | delete a note the test created, then list and fetch it | the statuses and bodies asserted in the automated suite | a note created through POST /notes in the test |
| AC-2 | delete an id that was never created | the status and error body asserted in the automated suite | id `999` |

The API has no authentication, so there are no user roles or credentials.

## 6. Dev Lead: decisions and constraints

- Contract: `DELETE /notes/:id`, no request body; 204 on success; errors use
  the existing envelope `{ "error": { "code": ..., "message": ... } }`.
- No new dependencies.

## 7. Out of scope

- Undoing a delete, or keeping deleted notes anywhere.
- Deleting several notes at once.

## 8. Open questions

None.

## 9. Decisions log

| ID | Decision | Rationale | Rejected | Owner | Date |
| --- | --- | --- | --- | --- | --- |
| D-1 | A delete removes the note for good | Nobody asked for undo, and the store is in memory | A soft delete with a deleted flag | BA | 2026-11-07 |

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

git init -q -b main
# The run gets a fresh HOME with no global git identity; commits need one.
git config user.name "jidoka eval"
git config user.email "jidoka-eval@example.invalid"
git add -A
git commit -qm "notes-api: initial import"
