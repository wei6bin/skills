#!/usr/bin/env bash
# GENERATED copy of src/skills/line/runner/run-story.sh by scripts/render.py (just build). Edit the source.
# Entrypoint of the jidoka runner image: one unattended /jidoka:line run on one
# story, in a fresh clone. scripts/pickup.py starts it with JIDOKA_STORY,
# JIDOKA_REPO, JIDOKA_SCHEDULED=1, JIDOKA_HOST and JIDOKA_OUT (a mounted
# folder: a run that finds the story's base broken writes base-red there),
# plus its --env-file:
#
#   CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY   the Claude credential
#   AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID
#                       a service principal the Azure DevOps organization
#                       knows. Without one, mount a person's az profile at
#                       /home/node/.azure instead (docker run -v). A PAT alone
#                       is not enough: the refused-on-conflict writes go
#                       through `az rest`, which needs an Entra login.
#   GH_TOKEN            for a GitHub repository (clone, push, gh pr create)
#   JIDOKA_GIT_NAME, JIDOKA_GIT_EMAIL
#                       the commit identity: the service account's, or the
#                       person's whose account the run uses
#   JIDOKA_MARKETPLACE  where the jidoka plugin comes from (default
#                       wei6bin/skills); JIDOKA_MAX_TURNS (default 400)
set -euo pipefail

: "${JIDOKA_STORY:?JIDOKA_STORY: the work item URL}"
: "${JIDOKA_REPO:?JIDOKA_REPO: the repository to clone}"
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "run-story: no Claude credential (CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY)" >&2
  exit 2
fi

if [ -n "${AZURE_CLIENT_ID:-}" ]; then
  az login --service-principal --username "$AZURE_CLIENT_ID" \
    --password "${AZURE_CLIENT_SECRET:?}" --tenant "${AZURE_TENANT_ID:?}" \
    --allow-no-subscriptions --output none
fi
if ! az account show --output none 2>/dev/null; then
  echo "run-story: no az login (a service principal in the env file, or a mounted ~/.azure)" >&2
  exit 2
fi

# Git over HTTPS: gh for GitHub, and for Azure Repos a credential helper that
# asks az for a fresh Entra token each time git needs one. A token fixed at the
# start would expire within the hour, and a long run's final push would fail.
if [ -n "${GH_TOKEN:-}" ]; then
  gh auth setup-git
fi
git config --global credential.https://dev.azure.com.helper \
  '!f() { [ "$1" = get ] || exit 0; echo username=jidoka; echo "password=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken --output tsv)"; }; f'
git config --global user.name "${JIDOKA_GIT_NAME:-jidoka line}"
git config --global user.email "${JIDOKA_GIT_EMAIL:-jidoka-line@users.noreply.invalid}"

work=$(mktemp -d)
git clone --quiet "$JIDOKA_REPO" "$work/repo"
cd "$work/repo"

claude plugin marketplace add "${JIDOKA_MARKETPLACE:-wei6bin/skills}"
claude plugin install jidoka@skills

exec claude -p "/jidoka:line $JIDOKA_STORY" \
  --dangerously-skip-permissions \
  --max-turns "${JIDOKA_MAX_TURNS:-400}" \
  --output-format stream-json --verbose
