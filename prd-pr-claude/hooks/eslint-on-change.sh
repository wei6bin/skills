#!/usr/bin/env bash
# PostToolUse hook for Edit/Write/MultiEdit.
# Runs eslint on the changed file (when eslint is available locally) and
# surfaces lint errors back to the agent so it can self-correct.
#
# Self-gates: only acts on JS/TS files inside a package.json tree where
# eslint is reachable via npx AND an eslint config is present. Exits
# silently otherwise, so this hook is safe to ship in a generic plugin.

set -uo pipefail

input=$(cat)

file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$file_path" ]] && exit 0
[[ ! -f "$file_path" ]] && exit 0

case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs) ;;
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
if ! npx --no-install eslint --version >/dev/null 2>&1; then
  exit 0
fi

# Probe for an eslint config before invoking — eslint v9+ exits non-zero
# if none is found, which would noisily false-positive.
has_config=0
for cfg in eslint.config.js eslint.config.mjs eslint.config.cjs eslint.config.ts \
           .eslintrc .eslintrc.js .eslintrc.cjs .eslintrc.json .eslintrc.yml .eslintrc.yaml; do
  if [[ -f "$pkg_root/$cfg" ]]; then has_config=1; break; fi
done
if [[ $has_config -eq 0 ]] && ! jq -e '.eslintConfig // empty' "$pkg_root/package.json" >/dev/null 2>&1; then
  exit 0
fi

output=$(npx --no-install eslint --no-warn-ignored "$file_path" 2>&1)
status=$?

if [[ $status -ne 0 ]]; then
  jq -n --arg ctx "ESLint errors in ${file_path}:

${output}

Fix these lint errors before continuing." '{
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: $ctx
    }
  }'
fi

exit 0
