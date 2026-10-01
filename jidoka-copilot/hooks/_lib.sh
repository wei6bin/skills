#!/usr/bin/env bash
# GENERATED copy of src/hooks/_lib.sh by scripts/render.py (make build). Edit the source.
# Shared helpers for the after-file-edit hooks. Sourced, never run directly.
#
# The same scripts run under three harnesses, each with its own payload and
# reply shape. Claude Code sends a PostToolUse payload (tool_input.file_path)
# and reads hookSpecificOutput.additionalContext; Copilot CLI sends a
# postToolUse payload (toolName, toolArgs) and reads a top-level
# additionalContext; Cursor sends an afterFileEdit payload (file_path) and has
# no context channel for this event. hook_init below detects which one is
# talking from the payload shape, so a script only ever calls hook_init, uses
# $file_path, and calls emit_context.

# hook_init <payload-json>
#
# Sets HOOK_HARNESS (claude | copilot | cursor | unknown) and file_path (the
# file the agent just edited, or "" when the payload carries none).
hook_init() {
  HOOK_HARNESS=$(printf '%s' "$1" | jq -r '
    if (.tool_input // null) != null then "claude"
    elif (.toolName // null) != null then "copilot"
    elif (.file_path // null) != null then "cursor"
    else "unknown" end' 2>/dev/null)
  [[ -z "$HOOK_HARNESS" ]] && HOOK_HARNESS=unknown
  file_path=$(printf '%s' "$1" | jq -r '
    .tool_input.file_path
    // .file_path
    // .toolArgs.path // .toolArgs.file_path // .toolArgs.filePath
    // empty' 2>/dev/null)
}

# find_tool_root <file> <marker>...
#
# Echoes the nearest ancestor directory of <file> that contains any of the given
# marker filenames, or "" if none is found before the filesystem root.
#
# Why this exists: a hook must run a tool from the directory that owns the tool's
# CONFIG, which in a monorepo is not the nearest package.json. pnpm/npm workspaces
# put .prettierignore and biome.json at the workspace root while every app under
# apps/* has its own package.json. Running from the app directory
# silently drops the root ignore file, so the hook reports violations on generated
# output (dev-dist/, dist/) that CI never checks - false positives that teach the
# agent to ignore the hook.
find_tool_root() {
  local dir marker found
  dir=$(cd "$(dirname "$1")" 2>/dev/null && pwd) || return 0
  shift
  while [[ -n "$dir" && "$dir" != "/" ]]; do
    for marker in "$@"; do
      # Glob markers (.prettierrc*) need the loop; plain names hit the first test.
      for found in "$dir"/$marker; do
        [[ -e "$found" ]] && { printf '%s' "$dir"; return 0; }
      done
    done
    dir=$(dirname "$dir")
  done
  printf ''
}

# emit_context <text> - the advisory channel back to the agent, in whichever
# reply shape the current harness reads. Cursor's afterFileEdit has none, so the
# hook stays silent there and only its on-disk effect (formatting) lands.
emit_context() {
  case "${HOOK_HARNESS:-unknown}" in
    claude)
      jq -n --arg ctx "$1" '{
        hookSpecificOutput: {
          hookEventName: "PostToolUse",
          additionalContext: $ctx
        }
      }'
      ;;
    copilot)
      jq -n --arg ctx "$1" '{ additionalContext: $ctx }'
      ;;
    *) ;;
  esac
}

# strip_npm_noise - npx writes npm's own warnings to stderr ("npm warn Unknown
# project config ..."), which lands in captured tool output and shows up inside
# lint diagnostics. Drop those lines only; keep everything else.
strip_npm_noise() {
  sed -e '/^npm warn /d' -e '/^npm notice/d' -e '/^npm WARN /d'
}
