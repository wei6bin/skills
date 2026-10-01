#!/usr/bin/env bash
# Routing smoke test on Claude Code.
#
# Loads the rendered jidoka plugin from this checkout (through a temp copy that
# carries the throwaway manifest --plugin-dir needs), asks a short non-interactive
# session to dispatch one subagent per role with a trivial prompt, then reads the
# session transcript under ~/.claude/projects/ to report the model each subagent
# actually ran on, next to the alias its rendered frontmatter asked for.
#
# Costs one short turn per agent (four by default). Not run in CI.
#
# Usage:
#   scripts/routing-smoke.sh              # code-explorer, code-architect, plan-reviewer, impl-backend
#   scripts/routing-smoke.sh --override   # plus code-explorer again with model: "haiku" on the Task call
#   SESSION_MODEL=opus scripts/routing-smoke.sh
set -euo pipefail
cd "$(dirname "$0")/.."

AGENTS=(code-explorer code-architect plan-reviewer impl-backend)
SESSION_MODEL=${SESSION_MODEL:-sonnet}
OVERRIDE=0
[[ "${1:-}" == "--override" ]] && OVERRIDE=1

command -v claude >/dev/null || { echo "claude CLI not found" >&2; exit 2; }
command -v jq >/dev/null || { echo "jq not found" >&2; exit 2; }

# --plugin-dir wants a manifest; the repo deliberately ships none (see CLAUDE.md),
# so load a temp copy that carries a throwaway one.
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp -R jidoka "$work/jidoka"
mkdir -p "$work/jidoka/.claude-plugin"
printf '{"name":"jidoka","description":"routing smoke copy"}\n' > "$work/jidoka/.claude-plugin/plugin.json"

prompt="Routing smoke test. Using the Agent (Task) tool, dispatch each of these agents exactly once, all in one parallel batch, each with the prompt: 'Reply with the single word OK and nothing else. Do not use any tools.' Agents:"
for a in "${AGENTS[@]}"; do prompt+=" jidoka:$a;"; done
if (( OVERRIDE )); then
  prompt+=" Then dispatch jidoka:code-explorer once more with the same prompt, passing model: \"haiku\" on that Task call."
fi
prompt+=" When they return, reply with exactly one line per dispatch in the form '<agent>: <its reply>' and nothing else."

echo "session model: $SESSION_MODEL; dispatching: ${AGENTS[*]}$( (( OVERRIDE )) && printf ' + code-explorer[model=haiku]')"
if ! result=$(claude -p "$prompt" \
  --plugin-dir "$work/jidoka" \
  --model "$SESSION_MODEL" \
  --output-format json \
  --allowedTools "Agent,Task" \
  --max-turns 6 2>"$work/stderr.log"); then
  echo "claude -p failed:" >&2
  cat "$work/stderr.log" >&2
  exit 1
fi

session_id=$(printf '%s' "$result" | jq -r '.session_id // empty')
if [[ -z "$session_id" ]]; then
  echo "no session_id in the output:" >&2
  printf '%s\n' "$result" | head -c 2000 >&2
  exit 1
fi
echo "session: $session_id"
printf '%s' "$result" | jq -r '.result // empty' | sed 's/^/  reply: /'

project_dir="$HOME/.claude/projects/$(pwd | tr '/' '-')"
transcript="$project_dir/$session_id.jsonl"
[[ -f "$transcript" ]] || { echo "transcript not found: $transcript" >&2; exit 1; }

# The alias the rendered frontmatter asks for.
expected() {
  awk 'NR==1{next} /^---$/{exit} /^model:/{sub(/^model:[ ]*/,""); print; exit}' "jidoka/agents/$1.md"
}
# Alias -> model-id prefix the transcript will show.
prefix_for() {
  case "$1" in
    fable) echo claude-fable ;; opus) echo claude-opus ;; sonnet) echo claude-sonnet ;; haiku) echo claude-haiku ;;
    *) echo "$1" ;;
  esac
}

# One row per dispatch: the Agent (formerly Task) tool_use carries subagent_type
# and any model override; the matching tool_result carries resolvedModel and the
# agentId of the subagent transcript.
rows=$(jq -r --slurp '
  [ .[] | select(.type=="assistant") | .message.content[]? | objects
    | select(.type=="tool_use" and (.name=="Agent" or .name=="Task"))
    | {id: .id, agent: .input.subagent_type, override: (.input.model // "")} ] as $uses
  | [ .[] | select(.type=="user") | . as $r | ($r.message.content | arrays | .[]?) | objects
    | select(.type=="tool_result")
    | {id: .tool_use_id, resolved: ($r.toolUseResult.resolvedModel // ""), agentId: ($r.toolUseResult.agentId // "")} ] as $results
  | $uses[] | . as $u | ([$results[] | select(.id==$u.id)][0] // {resolved: "", agentId: ""}) as $res
  | [$u.agent, $u.override, $res.resolved, $res.agentId] | join("|")' "$transcript")

if [[ -z "$rows" ]]; then
  echo "no subagent dispatches found in $transcript; the transcript shape may have changed" >&2
  exit 1
fi

fail=0
printf '\n%-24s %-11s %-9s %s\n' "agent" "frontmatter" "override" "model it ran on"
# A '|' delimiter keeps an empty override column in place; tabs would collapse.
while IFS='|' read -r agent override resolved agent_id; do
  [[ -z "$agent" ]] && continue
  name=${agent#jidoka:}
  fm=$(expected "$name")
  want=${override:-$fm}
  observed=$resolved
  if [[ -z "$observed" && -n "$agent_id" ]]; then
    sub="$project_dir/$session_id/subagents/agent-$agent_id.jsonl"
    if [[ -f "$sub" ]]; then
      observed=$(grep -o '"model":"[^"]*"' "$sub" | grep -v synthetic | head -1 | cut -d'"' -f4)
    fi
  fi
  mark="ok"
  [[ "$observed" == $(prefix_for "$want")* ]] || { mark="MISMATCH"; fail=1; }
  printf '%-24s %-11s %-9s %s  %s\n' "$agent" "$fm" "${override:--}" "${observed:-?}" "$mark"
done <<< "$rows"

if (( fail )); then
  echo "routing smoke: FAILED (see MISMATCH rows)"
  exit 1
fi
echo "routing smoke: every dispatch ran on the tier its frontmatter (or override) asked for"
