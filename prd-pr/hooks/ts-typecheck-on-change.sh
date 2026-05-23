#!/usr/bin/env bash
# PostToolUse hook for Edit/Write/MultiEdit.
# Type-checks the changed file's TS project and surfaces diagnostics back to
# the agent via additionalContext so it can self-correct.
#
# Self-gates: only acts on .ts/.tsx files inside a TypeScript project
# (detected by walking up from the file to the nearest tsconfig.json
# whose directory also has a package.json). Exits silently for any
# non-TS edit, so this hook is safe to ship in a generic plugin.
#
# Monorepo-aware (the reason this hook is careful):
#   * It reports only diagnostics for the file just edited — a single-file
#     edit should not dump the whole project's transient red back at the
#     agent (mid-slice TDD legitimately leaves other files red, and a wall
#     of unrelated errors after every keystroke derails the run and bloats
#     its context).
#   * In a workspace, unresolved-import errors against a sibling package
#     (TS2307/TS2305/TS2614/TS2724) are almost always a STALE shared-package
#     build, not a code defect. Those are surfaced as a NON-BLOCKING advisory
#     ("build workspace deps first"), never as "fix before continuing" —
#     editing source to chase them is the wrong move.

set -uo pipefail

input=$(cat)

file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$file_path" ]] && exit 0
[[ ! -f "$file_path" ]] && exit 0

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

# tsc must actually be reachable — otherwise `npx --no-install` exits non-zero
# and we would misreport "command not found" as type errors.
if ! npx --no-install tsc --version >/dev/null 2>&1; then
  exit 0
fi

output=$(npx --no-install tsc --noEmit 2>&1)
status=$?

# Clean compile — nothing to say.
[[ $status -eq 0 ]] && exit 0

# Scope to the file just edited. tsc prints paths relative to its cwd
# (ts_root), e.g. "src/Foo.tsx(12,3): error TS....".
rel_path="${file_path#"$ts_root"/}"
scoped=$(printf '%s\n' "$output" | grep -F "$rel_path" 2>/dev/null)

# No diagnostics for the edited file → the failures are elsewhere (commonly
# other files still mid-TDD in the same slice). A per-edit hook should not
# police those; the agent's pre-finish build/test run is the right gate.
[[ -z "$scoped" ]] && exit 0

# Detect a workspace so we can tell "stale shared-package build" apart from a
# genuine code error.
is_workspace=0
w="$ts_root"
while [[ "$w" != "/" && "$w" != "." ]]; do
  if [[ -f "$w/pnpm-workspace.yaml" || -f "$w/lerna.json" || -f "$w/turbo.json" ]]; then
    is_workspace=1; break
  fi
  if [[ -f "$w/package.json" ]] && jq -e '.workspaces // empty' "$w/package.json" >/dev/null 2>&1; then
    is_workspace=1; break
  fi
  w=$(dirname "$w")
done

# Does the edited file have a BARE-specifier module-resolution failure?
#   * TS2307 "Cannot find module 'x'" where x does NOT start with '.' or '/'
#     (a bare/scoped specifier → a workspace or node_modules package, i.e. a
#     build/install-order issue, not a source defect). Relative-path typos
#     ('./foo') stay blocking — those ARE the agent's to fix.
#   * TS2305/2614/2724 "module has no exported member" → the module resolved
#     but its compiled output is stale (missing a freshly-added export).
# When present in a workspace, the unresolved import CASCADES into the rest of
# the file's diagnostics (members become `any`/`unknown`, etc.), so none of
# this file's errors can be trusted until the shared package is rebuilt.
ws_artifact=0
if printf '%s\n' "$scoped" | grep -qE "TS2307: Cannot find module '[^.\/]"; then
  ws_artifact=1
fi
if printf '%s\n' "$scoped" | grep -qE 'TS2305|TS2614|TS2724'; then
  ws_artifact=1
fi

if [[ $is_workspace -eq 1 && $ws_artifact -eq 1 ]]; then
  jq -n --arg ctx "Heads-up (non-blocking): \`tsc\` cannot resolve a workspace-package import in ${rel_path}:

${scoped}

In a monorepo this means a shared workspace package's build is stale — a freshly-added export is not in its compiled output yet — and that one unresolved import cascades into the file's other diagnostics (members seen as \`any\`/\`unknown\`, etc.). Build the workspace dependencies first (e.g. \`pnpm -r build\` or the shared package's build script), then re-check. Do NOT edit source to chase these; they are build-order artifacts, not code errors, and do not block this edit." '{
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: $ctx
    }
  }'
  exit 0
fi

jq -n --arg ctx "TypeScript errors in ${rel_path} after this edit:

${scoped}

Fix these type errors before continuing." '{
  hookSpecificOutput: {
    hookEventName: "PostToolUse",
    additionalContext: $ctx
  }
}'

exit 0
