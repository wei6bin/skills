#!/usr/bin/env bash
# PostToolUse hook for Edit/Write/MultiEdit.
# Runs eslint on the changed file (when eslint is available locally) and
# surfaces lint errors back to the agent so it can self-correct.
#
# Self-gates: only acts on JS/TS files under a directory that actually holds an
# eslint config, where eslint is reachable via npx. Exits silently otherwise, so
# this hook is safe to ship in a generic plugin.
#
# Reports only, never fixes: lint findings need judgement (many autofixes are
# marked unsafe and change behaviour). Formatting is the opposite and is
# auto-applied - see prettier-on-change.sh.

set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

input=$(cat)

file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$file_path" ]] && exit 0
[[ ! -f "$file_path" ]] && exit 0

case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs) ;;
  *) exit 0 ;;
esac

# Run from the directory that owns the eslint config, which in a monorepo is the
# workspace root, not the nearest package.json. eslint v9 resolves flat config from
# the cwd upward, and exits non-zero when it finds none - so locating the config
# first is both the correctness fix and the false-positive guard.
pkg_root=$(find_tool_root "$file_path" \
  "eslint.config.js" "eslint.config.mjs" "eslint.config.cjs" "eslint.config.ts" \
  ".eslintrc" ".eslintrc.*")

if [[ -z "$pkg_root" ]]; then
  # Legacy fallback: eslintConfig embedded in the nearest package.json.
  pkg_root=$(find_tool_root "$file_path" "package.json")
  [[ -z "$pkg_root" ]] && exit 0
  jq -e '.eslintConfig // empty' "$pkg_root/package.json" >/dev/null 2>&1 || exit 0
fi

cd "$pkg_root" || exit 0
if ! npx --no-install eslint --version >/dev/null 2>&1; then
  exit 0
fi

output=$(npx --no-install eslint --no-warn-ignored "$file_path" 2>&1 | strip_npm_noise)
status=$?

if [[ $status -ne 0 ]]; then
  emit_context "ESLint errors in ${file_path}:

${output}

Fix these lint errors before continuing."
fi

exit 0
