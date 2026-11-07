#!/usr/bin/env bash
# Scaffold for the refine-three-roles eval: the line-minimal-story repo (the
# notes API on `main`, no remote), plus a second commit adding USR-002 as raw,
# unrefined story text with gaps for each role to settle.
#
# `claude plugin eval --scaffold` runs this as you, outside the agent's sandbox,
# in the empty workspace, with a minimal env (PATH, HOME, TMPDIR, TERM).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$here/../line-minimal-story/scaffold.sh"

# Vague on purpose. What the code answers (the error envelope, the code for an
# unknown note, the status for an invalid title) must be looked up, not asked;
# what it cannot answer (the method, which fields change, the title limit, the
# evidence) belongs to the BA, the Dev Lead or the QE.
mkdir -p docs/stories
cat > docs/stories/usr-002-edit-note.md <<'EOF'
# USR-002 Edit a note

As an API client I want to edit a note so that I can fix mistakes.

Acceptance criteria:

1. Editing a note updates it.
2. Editing a note that does not exist fails.
EOF

git add -A
git commit -qm "backlog: USR-002 Edit a note, unrefined"
