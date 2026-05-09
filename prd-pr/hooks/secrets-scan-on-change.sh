#!/usr/bin/env bash
# PostToolUse hook for Edit/Write/MultiEdit.
# Pure-regex scan for high-confidence secret patterns in the changed file.
# Reports findings as additionalContext so the agent must address them
# before continuing.
#
# Conservative on purpose — only patterns with very low false-positive
# rates are flagged. Generic "api_key=" matches are excluded.
#
# Self-gates: text files only (skip binaries, lockfiles, snapshot dumps).

set -uo pipefail

input=$(cat)

file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$file_path" ]] && exit 0
[[ ! -f "$file_path" ]] && exit 0

# Skip binaries and noisy generated files.
case "$file_path" in
  *.lock|*.lockb|*lock.json|*.snap|*.png|*.jpg|*.jpeg|*.gif|*.pdf|*.zip|*.tar|*.gz|*.ico|*.woff*|*.ttf) exit 0 ;;
esac
if file -b --mime-encoding "$file_path" 2>/dev/null | grep -q binary; then
  exit 0
fi

declare -A patterns=(
  ["AWS access key id"]='AKIA[0-9A-Z]{16}'
  ["AWS secret access key (after aws_secret_access_key=)"]='aws_secret_access_key[[:space:]]*[:=][[:space:]]*[A-Za-z0-9/+=]{40}'
  ["GitHub personal access token"]='ghp_[A-Za-z0-9]{36}'
  ["GitHub OAuth token"]='gho_[A-Za-z0-9]{36}'
  ["GitHub user-to-server token"]='ghu_[A-Za-z0-9]{36}'
  ["GitHub server-to-server token"]='ghs_[A-Za-z0-9]{36}'
  ["GitHub refresh token"]='ghr_[A-Za-z0-9]{36}'
  ["Slack bot token"]='xox[baprs]-[A-Za-z0-9-]{10,}'
  ["Google API key"]='AIza[0-9A-Za-z_\-]{35}'
  ["Stripe live secret key"]='sk_live_[A-Za-z0-9]{24,}'
  ["Private key block"]='-----BEGIN ((RSA|OPENSSH|EC|DSA|PGP) )?PRIVATE KEY-----'
)

findings=""
for label in "${!patterns[@]}"; do
  pattern=${patterns[$label]}
  match=$(grep -nE "$pattern" "$file_path" 2>/dev/null | head -3)
  if [[ -n "$match" ]]; then
    findings+="
- ${label}:
${match}
"
  fi
done

if [[ -n "$findings" ]]; then
  jq -n --arg ctx "Possible committed secret(s) detected in ${file_path}:
${findings}
Remove the literal value, replace with an env-var / secret-manager lookup, and rotate the credential if it ever reached a remote." '{
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: $ctx
    }
  }'
fi

exit 0
