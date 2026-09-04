#!/usr/bin/env bash
# Shared helpers for the PostToolUse hooks. Sourced, never executed directly.

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

# emit_context <text> — the PostToolUse advisory channel.
emit_context() {
  jq -n --arg ctx "$1" '{
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: $ctx
    }
  }'
}

# strip_npm_noise — npx writes npm's own warnings to stderr ("npm warn Unknown
# project config ..."), which lands in captured tool output and shows up inside
# lint diagnostics. Drop those lines only; keep everything else.
strip_npm_noise() {
  sed -e '/^npm warn /d' -e '/^npm notice/d' -e '/^npm WARN /d'
}
