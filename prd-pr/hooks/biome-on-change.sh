#!/usr/bin/env bash
# PostToolUse hook for Edit/Write/MultiEdit.
#
# Runs Biome's linter on the changed file and surfaces error-level findings back to
# the agent. Biome is this plugin's linter: `frontend-styling-standard` tells projects
# to adopt it over ESLint, and this is the hook that backs that recommendation. It is
# the only lint hook - projects still on ESLint get no lint feedback here by design,
# and should run the migration in `frontend-styling-standard/references/biome-setup.md`.
#
# Reports only, never fixes: Biome marks many of its fixes unsafe (removing a
# fragment around `render(<>{…}</>)` changes what render receives), so a blanket
# --write is not safe. Formatting is auto-applied by prettier-on-change.sh instead.
#
# Self-gates: only acts on files under a directory holding a biome config, where
# biome is reachable. Exits silently otherwise, so it is safe in a generic plugin.

set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

input=$(cat)

file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$file_path" ]] && exit 0
[[ ! -f "$file_path" ]] && exit 0

case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs|*.json|*.jsonc|*.css|*.vue|*.svelte) ;;
  *) exit 0 ;;
esac

root=$(find_tool_root "$file_path" "biome.json" "biome.jsonc")
[[ -z "$root" ]] && exit 0

cd "$root" || exit 0
if ! npx --no-install biome --version >/dev/null 2>&1; then
  exit 0
fi

# Biome's exit code is not usable as the signal here: it is also non-zero when the
# path is ignored by biome.json ("No files were processed"), which would flag every
# edit to generated output. summary.errors is exact - it stays 0 for infos and
# warnings, matching what a `biome lint` CI step actually fails on.
errors=$(npx --no-install biome lint --reporter=json "$file_path" 2>/dev/null \
  | jq -r '.summary.errors // 0' 2>/dev/null)
[[ "$errors" =~ ^[0-9]+$ ]] || errors=0
[[ "$errors" -eq 0 ]] && exit 0

output=$(npx --no-install biome lint --max-diagnostics=15 "$file_path" 2>&1 | strip_npm_noise)

emit_context "Biome reports ${errors} error-level finding(s) in ${file_path}. A \`biome lint\` CI step fails on exactly this:

${output}

Fix these before continuing. Do not blanket-apply \`biome lint --write\`: Biome marks many of these fixes unsafe."

exit 0
