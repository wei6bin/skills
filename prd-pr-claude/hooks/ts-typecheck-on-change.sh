#!/usr/bin/env bash
# PostToolUse hook for Edit/Write/MultiEdit.
# Type-checks the changed file's TS project and surfaces diagnostics back to
# the agent via additionalContext so it can self-correct.
#
# Self-gates: only acts on .ts/.tsx files inside a TypeScript project
# (detected by walking up from the file to the nearest tsconfig.json
# whose directory also has a package.json). Exits silently for any
# non-TS edit, so this hook is safe to ship in a generic plugin.

set -uo pipefail

input=$(cat)

file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$file_path" ]] && exit 0

case "$file_path" in
  *.ts|*.tsx) ;;
  *) exit 0 ;;
esac

dir=$(dirname "$file_path")
ts_root=""
while [[ "$dir" != "/" && "$dir" != "." ]]; do
  if [[ -f "$dir/tsconfig.json" && -f "$dir/package.json" ]]; then
    ts_root="$dir"
    break
  fi
  dir=$(dirname "$dir")
done

[[ -z "$ts_root" ]] && exit 0

cd "$ts_root"
output=$(npx --no-install tsc --noEmit 2>&1)
status=$?

if [[ $status -ne 0 ]]; then
  jq -n --arg ctx "TypeScript errors in ${ts_root} after edit to ${file_path}:

${output}

Fix these type errors before continuing." '{
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: $ctx
    }
  }'
fi

exit 0
