#!/usr/bin/env bash
#
# Fetch a YouTube transcript via the baoyu-youtube-transcript skill, with the
# TLS-inspection workaround this machine needs.
#
# Usage:
#   fetch-transcript.sh <youtube-url-or-id> [extra args passed to main.ts]
#
# Prints the path of the generated transcript.md on the last line of stdout.

set -uo pipefail

TRANSCRIPT_SKILL="${TRANSCRIPT_SKILL:-$HOME/.claude/skills/baoyu-youtube-transcript}"
MAIN_TS="$TRANSCRIPT_SKILL/scripts/main.ts"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/clinical-lecture-brief"
BUNDLE="$CACHE_DIR/ca-bundle.pem"

die() { printf '\nerror: %s\n' "$1" >&2; exit 1; }

[ $# -ge 1 ] || die "no YouTube URL given.  usage: fetch-transcript.sh <url> [args...]"
URL="$1"; shift

[ -f "$MAIN_TS" ] || die "baoyu-youtube-transcript not installed at $TRANSCRIPT_SKILL
Install it with:  npx skills add JimLiu/baoyu-skills@baoyu-youtube-transcript -g -y"

# ---------------------------------------------------------------------------
# CA bundle.
#
# Traffic on this machine passes through a TLS-inspecting proxy (Cloudflare
# Gateway), which re-signs certificates with a root that macOS trusts but the
# Nix-built Python behind yt-dlp does not. Rebuild a bundle that is the system
# roots plus every admin-installed root from the System keychain.
#
# NIX_SSL_CERT_FILE is the variable that actually governs here. SSL_CERT_FILE,
# CURL_CA_BUNDLE and REQUESTS_CA_BUNDLE alone do NOT fix it on a Nix toolchain;
# they are set too because other tools in the chain read them.
# ---------------------------------------------------------------------------
build_bundle() {
  mkdir -p "$CACHE_DIR"
  local sys="/etc/ssl/certs/ca-certificates.crt"
  : > "$BUNDLE"
  [ -f "$sys" ] && cat "$sys" >> "$BUNDLE"
  if [ "$(uname)" = "Darwin" ]; then
    printf '\n' >> "$BUNDLE"
    security find-certificate -a -p /Library/Keychains/System.keychain >> "$BUNDLE" 2>/dev/null
  fi
  if ! grep -q "BEGIN CERTIFICATE" "$BUNDLE" 2>/dev/null; then
    rm -f "$BUNDLE"
    return 1
  fi
  return 0
}

# Rebuild when missing or older than 7 days (roots rotate, laptops change networks).
if [ ! -s "$BUNDLE" ] || [ -n "$(find "$BUNDLE" -mtime +7 2>/dev/null)" ]; then
  echo "building CA bundle -> $BUNDLE" >&2
  build_bundle || die "could not assemble a CA bundle"
fi

if [ -s "$BUNDLE" ]; then
  export NIX_SSL_CERT_FILE="$BUNDLE"
  export SSL_CERT_FILE="$BUNDLE"
  export CURL_CA_BUNDLE="$BUNDLE"
  export REQUESTS_CA_BUNDLE="$BUNDLE"
fi

# ---------------------------------------------------------------------------
# Runtime: prefer a real bun, fall back to npx.
# ---------------------------------------------------------------------------
if command -v bun >/dev/null 2>&1; then
  RUNNER=(bun)
elif command -v npx >/dev/null 2>&1; then
  RUNNER=(npx -y bun)
else
  die "neither bun nor npx is available; install one of them"
fi

# Always quote the URL: an unquoted YouTube URL is glob-expanded by zsh/fish.
out="$("${RUNNER[@]}" "$MAIN_TS" "$URL" "$@" 2>&1)"
status=$?

printf '%s\n' "$out" >&2

if [ $status -ne 0 ]; then
  die "transcript fetch failed (exit $status). See output above.
If it is an SSL failure, delete $BUNDLE and re-run to rebuild it.
If YouTube reports bot detection, retry with:
  YOUTUBE_TRANSCRIPT_COOKIES_FROM_BROWSER=chrome $0 '$URL'"
fi

# The script prints the written path as its final line.
path="$(printf '%s\n' "$out" | grep -E '\.(md|srt)$' | tail -1)"
[ -n "$path" ] || die "fetch reported success but no output path was found"

printf '%s\n' "$path"
