#!/usr/bin/env bash
# PostToolUse hook for Edit/Write/MultiEdit.
#
# Formats the changed file with Prettier when Prettier is available locally.
#
# This hook AUTO-WRITES. It used to only report violations, on the reasoning that
# "the agent owns the fix so its mental model of the file content stays in sync" -
# but an advisory the agent may decline is not a gate, and formatting is the one
# class of fix that needs no judgement at all. Claude Code now injects its own
# notice when a PostToolUse hook modifies a file ("your next Edit will not fail
# with a stale-file error"), so the staleness concern that motivated report-only
# is handled by the harness. Lint findings still only get reported - see
# eslint-on-change.sh and biome-on-change.sh - because those need judgement.
#
# Self-gates: only acts on file types Prettier owns, inside a tree where Prettier
# is reachable via npx. Exits silently otherwise, so it is safe in a generic plugin.

set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

input=$(cat)

file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$file_path" ]] && exit 0
[[ ! -f "$file_path" ]] && exit 0

case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs|*.json|*.md|*.yml|*.yaml|*.css|*.scss|*.html|*.vue) ;;
  *) exit 0 ;;
esac

# Run from the directory that owns Prettier's ignore file / config - NOT the nearest
# package.json. --ignore-path defaults to ./.prettierignore relative to the cwd, so
# starting in a workspace app directory drops the root ignore list entirely.
root=$(find_tool_root "$file_path" ".prettierignore" ".prettierrc" ".prettierrc.*" "prettier.config.*")
[[ -z "$root" ]] && root=$(find_tool_root "$file_path" "package.json")
[[ -z "$root" ]] && exit 0

cd "$root" || exit 0
# Probe: does this project actually have prettier? If not, exit silently.
if ! npx --no-install prettier --version >/dev/null 2>&1; then
  exit 0
fi

# --ignore-unknown makes an unsupported extension a no-op rather than an error, and
# ignored paths are skipped silently, so the content hash is the only reliable
# "did anything actually change" signal.
before=$(shasum -a 256 "$file_path" 2>/dev/null | cut -d' ' -f1)
npx --no-install prettier --write --ignore-unknown --log-level=silent "$file_path" >/dev/null 2>&1
after=$(shasum -a 256 "$file_path" 2>/dev/null | cut -d' ' -f1)

[[ "$before" == "$after" ]] && exit 0

emit_context "Prettier reformatted ${file_path} on disk after your edit - it did not match the project's format check, which is typically the step that turns CI red after tests already passed.

The file now differs from what you wrote. Re-read it before your next edit to it. No action is needed otherwise; the formatting is already fixed."

exit 0
