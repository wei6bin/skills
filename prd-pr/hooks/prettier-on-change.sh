#!/usr/bin/env bash
# PostToolUse hook for Edit/Write/MultiEdit.
# Runs `prettier --check` on the changed file (when prettier is available
# locally) and surfaces formatting violations back to the agent so it can
# self-correct. Does NOT auto-write — the agent owns the fix so its mental
# model of the file content stays in sync.
#
# Self-gates: only acts on .ts/.tsx/.js/.jsx/.json/.md/.yml/.yaml inside
# a package.json tree where prettier is reachable via npx. Exits silently
# otherwise, so this hook is safe to ship in a generic plugin.

set -uo pipefail

input=$(cat)

file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$file_path" ]] && exit 0
[[ ! -f "$file_path" ]] && exit 0

case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx|*.json|*.md|*.yml|*.yaml|*.css|*.scss) ;;
  *) exit 0 ;;
esac

dir=$(dirname "$file_path")
pkg_root=""
while [[ "$dir" != "/" && "$dir" != "." ]]; do
  if [[ -f "$dir/package.json" ]]; then
    pkg_root="$dir"
    break
  fi
  dir=$(dirname "$dir")
done

[[ -z "$pkg_root" ]] && exit 0

cd "$pkg_root"
# Probe: does this project actually have prettier? If not, exit silently.
if ! npx --no-install prettier --version >/dev/null 2>&1; then
  exit 0
fi

output=$(npx --no-install prettier --check "$file_path" 2>&1)
status=$?

if [[ $status -ne 0 ]]; then
  jq -n --arg ctx "Prettier formatting violations in ${file_path}:

${output}

Run \`npx prettier --write ${file_path}\` (or fix manually) before continuing." '{
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: $ctx
    }
  }'
fi

exit 0
