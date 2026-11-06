#!/usr/bin/env bash
# GENERATED copy of src/skills/herdr-crew/scripts/crew.sh by scripts/render.py (just build). Edit the source.
# crew.sh - run the jidoka line's subagents as herdr workers.
#
# The lead (the session running the line) calls this instead of its task tool
# when herdr mode is on. Workers run in a "jidoka crew" tab that starts as one
# pane and grows a column per worker: split the rightmost pane to the right (the
# prefix+v split), then even the columns out. Each slot has its own background
# tint and emoji. A released worker's column closes; the tab's last pane stays
# as a free one. A fifth concurrent worker opens another crew tab, which closes
# again once its workers are released. The lead's own agent is renamed `lead`.
# See ../SKILL.md for the protocol.
#
# Usage: crew.sh COMMAND [ARGS]
#   mode                          herdr | task: <reason>
#   up                            open the crew tab and name the lead
#   dispatch AGENT [--model M] [--effort E] <BRIEF
#                                 start a worker on the brief read from stdin
#   wait NAME... [--timeout SEC]  until each worker is ready or gone, or one
#                                 newly blocks on a prompt (default 540 s)
#   report NAME                   the worker's final answer
#   send NAME <MESSAGE            a follow-up from the lead to a live worker
#   peek NAME [--lines N]         the worker's current screen
#   release NAME...               stop the worker and close its column
#   status                        crew tabs, slots and workers, left to right
#   down                          release every worker, close the crew tabs
#   check                         self-check report (/jidoka:check)
#   config [show | set KEY VALUE | unset KEY | path]
#
# Workers run on the harness the config names (default: the lead's own). A
# Claude Code worker runs the plugin's agent natively (`claude --agent`) when
# the jidoka plugin is installed, and its report is read from its session
# transcript. Any other worker reads the agent's instructions from ../agents/
# (the worker render) and writes its report to a file. Needs bash 3.2+, jq and
# herdr; nc with -U evens out the columns.
set -euo pipefail

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
SKILL_DIR="$(cd "$(dirname "$SELF")/.." && pwd)"
PLUGIN_ROOT="$(cd "$SKILL_DIR/../.." && pwd)"
AGENTS_DIR="$SKILL_DIR/agents"
CONF="${JIDOKA_HERDR_CONF:-${XDG_CONFIG_HOME:-$HOME/.config}/jidoka/herdr.conf}"
STATE_ROOT="${JIDOKA_HERDR_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/jidoka/herdr}"
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

TAB_LABEL="jidoka crew"
SLOT_EMOJI=("🟦" "🟩" "🟧" "🟪")
SLOT_COLOR=(blue green amber purple)
TINT_DARK=("#0f1d2e" "#10241a" "#2a1d0c" "#22142c")
TINT_LIGHT=("#e6effc" "#e7f5e9" "#fbf0dc" "#f1e8fb")
INK_DARK=("122;162;247" "158;206;106" "224;175;104" "187;154;247")
INK_LIGHT=("31;87;178" "38;120;58" "160;98;12" "120;60;170")
TAB_MAX=4               # workers a crew tab holds: one per slot color
COL_MIN=40              # a column narrower than this opens another crew tab
WAIT_DEFAULT=540        # seconds: returns before a 10-minute tool ceiling
START_TIMEOUT_MS=90000  # agent start: process up and interactive
GATE_TIMEOUT_MS=20000   # prompt submission: activity seen, or settled
QUIET_SECONDS=120       # a file-report worker with no report and a still screen
# Used when herdr is not installed, so check can still list agent CLIs.
FALLBACK_KINDS="claude copilot codex gemini cursor opencode amp droid qwen kimi kiro pi"

die() { printf 'crew: %s\n' "$*" >&2; exit 1; }
words() { "$@" | tr '\n' ' ' | sed 's/ *$//'; } # a command's lines as one line
note() { printf 'crew: %s\n' "$*" >&2; }
have() { command -v "$1" >/dev/null 2>&1; }
now() { date +%s; }
usage() { sed -n '2,/^set -euo/p' "$SELF" | sed '$d' | grep -v '^# GENERATED' | sed 's/^# \{0,1\}//'; }

# --- config ---------------------------------------------------------------------

conf_get() { # KEY -> value (last one wins), or nothing
  [ -f "$CONF" ] || return 0
  awk -v want="$1" '
    /^[[:space:]]*(#|$)/ { next }
    {
      line = $0
      sub(/[[:space:]]+#.*$/, "", line)
      eq = index(line, "=")
      if (!eq) next
      key = substr(line, 1, eq - 1); val = substr(line, eq + 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
      if (val ~ /^".*"$/) val = substr(val, 2, length(val) - 2)
      if (key == want) out = val
    }
    END { if (out != "") print out }' "$CONF"
}

conf_keys() { # the keys the config sets, in file order
  [ -f "$CONF" ] || return 0
  awk '/^[[:space:]]*(#|$)/ { next } index($0, "=") {
    key = substr($0, 1, index($0, "=") - 1); gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
    if (!(key in seen)) { seen[key] = 1; print key }
  }' "$CONF"
}

conf_drop() { # KEY -> config without that key, on stdout
  awk -v want="$1" '{
    line = $0; eq = index(line, "=")
    if (line !~ /^[[:space:]]*#/ && eq) {
      key = substr(line, 1, eq - 1); gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
      if (key == want) next
    }
    print
  }' "$CONF"
}

conf_header() {
  cat <<'EOF'
# jidoka herdr mode, read by the herdr-crew skill's scripts/crew.sh.
# /jidoka:check shows what is installed and what each agent resolves to.
#
# enabled = true                 false: never use herdr mode, even in herdr
# harness = lead                 default worker harness: lead (the lead's own)
#                                or a herdr agent kind (claude, copilot, ...)
# role.verification = copilot    per role: reasoning, verification,
#                                implementation, exploration
# agent.code-reviewer = codex    per agent; beats the role
# yolo.copilot = on              no approval prompts for that harness's workers
#                                (copilot --yolo, codex and claude: their
#                                --dangerously-* flags); default off
# args.copilot = "--log-level none"    extra flags for that harness's workers
# tint = dark                    light: tints for a light terminal theme;
#                                off: emoji labels only, no background tint
EOF
}

valid_kind() { # KIND -> 0 when herdr (or the fallback list) knows it
  local k
  for k in $(kinds); do [ "$k" = "$1" ] && return 0; done
  return 1
}

conf_set() { # KEY VALUE
  local key=$1 val=$2 tmp
  case "$key" in
    enabled)
      case "$val" in true | false) ;; *) die "enabled takes true or false" ;; esac ;;
    tint)
      case "$val" in dark | light | off) ;; *) die "tint takes dark, light or off" ;; esac ;;
    harness | role.* | agent.*)
      [ "$val" = lead ] || valid_kind "$val" || die "unknown harness '$val' (kinds: lead $(kinds))"
      case "$key" in
        role.*) roles | grep -qx "${key#role.}" || die "unknown role '${key#role.}' (roles: $(words roles))" ;;
        agent.*) [ -f "$AGENTS_DIR/${key#agent.}.md" ] || die "unknown agent '${key#agent.}' (agents: $(words agent_names))" ;;
      esac
      if [ "$val" != lead ] && ! have "$(kind_bin "$val")"; then
        note "warning: '$(kind_bin "$val")' is not on PATH; $val workers fail until it is installed"
      fi ;;
    args.*) valid_kind "${key#args.}" || die "unknown harness '${key#args.}' (kinds: $(kinds))" ;;
    yolo.*)
      case "$val" in on | off) ;; *) die "$key takes on or off" ;; esac
      [ -n "$(yolo_flag "${key#yolo.}")" ] ||
        die "no known yolo flag for '${key#yolo.}' (known: claude, codex, copilot); put its flag in args.${key#yolo.}" ;;
    *) die "unknown key '$key' (keys: enabled, harness, tint, role.<role>, agent.<agent>, yolo.<kind>, args.<kind>)" ;;
  esac
  mkdir -p "$(dirname "$CONF")"
  [ -f "$CONF" ] || conf_header > "$CONF"
  tmp="$CONF.tmp.$$"
  conf_drop "$key" > "$tmp"
  case "$val" in *" "*) printf '%s = "%s"\n' "$key" "$val" >> "$tmp" ;; *) printf '%s = %s\n' "$key" "$val" >> "$tmp" ;; esac
  mv "$tmp" "$CONF"
}

# --- harnesses and agents -------------------------------------------------------

kinds() {
  if have herdr; then
    local k
    k=$({ herdr agent 2>&1 || true; } | sed -n 's/^[[:space:]]*kinds:[[:space:]]*//p' | tr '|' ' ')
    if [ -n "$k" ]; then printf '%s\n' "$k"; return; fi
  fi
  printf '%s\n' "$FALLBACK_KINDS"
}

yolo_flag() { # KIND -> the flag that runs that harness with no approval prompts
  case "$1" in
    copilot) echo --yolo ;;
    codex) echo --dangerously-bypass-approvals-and-sandbox ;;
    claude) echo --dangerously-skip-permissions ;;
  esac
}

yolo_on() { [ "$(conf_get "yolo.$1")" = on ] && [ -n "$(yolo_flag "$1")" ]; }

kind_bin() { # herdr agent kind -> the command herdr launches for it
  case "$1" in cursor) echo cursor-agent ;; kiro) echo kiro-cli ;; *) echo "$1" ;; esac
}

agent_names() { local f; for f in "$AGENTS_DIR"/*.md; do [ -f "$f" ] && basename "$f" .md; done; }
roles() { local a; for a in $(agent_names); do afm "$a" role; done | sort -u; }

afm() { # AGENT KEY -> a frontmatter value of the agent's worker render
  local v
  v=$(awk -v k="$2" 'NR == 1 { next } /^---$/ { exit } index($0, k ": ") == 1 { print substr($0, length(k) + 3); exit }' \
    "$AGENTS_DIR/$1.md")
  case "$v" in
    \"*\") # the renderer JSON-quotes a value YAML would misread, such as 4.1
      if have jq; then jq -r . <<< "$v"; else v=${v#\"}; printf '%s\n' "${v%\"}"; fi ;;
    *) printf '%s\n' "$v" ;;
  esac
}

lead_kind() { # the harness the lead runs on, as herdr names it
  local k=""
  if [ -n "${HERDR_PANE_ID:-}" ] && have herdr && have jq; then
    k=$(herdr agent get "$HERDR_PANE_ID" 2>/dev/null | jq -r '.result.agent.agent // empty' 2>/dev/null || true)
  fi
  if [ -z "$k" ] && [ -n "${CLAUDECODE:-}" ]; then k=claude; fi
  printf '%s' "$k"
}

resolve_kind() { # AGENT -> kind: agent.<agent> > role.<role> > harness > the lead's
  local k
  k=$(conf_get "agent.$1")
  [ -n "$k" ] || k=$(conf_get "role.$(afm "$1" role)")
  [ -n "$k" ] || k=$(conf_get harness)
  if [ -z "$k" ] || [ "$k" = lead ]; then k=$(lead_kind); fi
  printf '%s' "$k"
}

claude_plugin() { # "<plugin> [<plugin-dir>]" when Claude can run jidoka agents natively
  if [ -f "$PLUGIN_ROOT/.claude-plugin/plugin.json" ] && have jq; then
    printf '%s %s' "$(jq -r '.name // "jidoka"' "$PLUGIN_ROOT/.claude-plugin/plugin.json")" "$PLUGIN_ROOT"
    return
  fi
  have claude && have jq || return 0
  local id
  id=$(claude plugin list --json 2>/dev/null |
    jq -r 'first(.[] | select(.enabled and (.id | startswith("jidoka@"))) | .id) // empty' 2>/dev/null || true)
  [ -z "$id" ] || printf '%s' "${id%%@*}"
}

# --- run state ------------------------------------------------------------------
# One run directory per lead pane: crew.json (crew tabs, each with its panes
# and their slot colors, and the lead name), one workers/<name>.json per live
# worker, and briefs/ and reports/, kept after `down` as the run's record. A
# named herdr session has its own server and pane ids, so its name leads the
# directory's: w1:p1 in two sessions is two panes.

need_herdr() {
  [ "${HERDR_ENV:-}" = 1 ] || die "not inside herdr (HERDR_ENV is not 1)"
  have herdr || die "herdr is not on PATH"
  have jq || die "jq is not on PATH"
  [ -n "${HERDR_PANE_ID:-}" ] || die "HERDR_PANE_ID is unset"
  RUN="$STATE_ROOT/$(printf '%s' "${HERDR_SESSION:+${HERDR_SESSION}_}$HERDR_PANE_ID" | tr -c 'A-Za-z0-9_-' '-')"
  STATE="$RUN/crew.json"
  mkdir -p "$RUN/workers" "$RUN/briefs" "$RUN/reports"
}

LOCKED=0
lock() { # a file created with O_EXCL (bash's noclobber) that holds the pid
  # Not mkdir: uutils coreutils' mkdir (the system one on recent Ubuntu) lets
  # two racing calls both succeed. Not flock: macOS has none.
  local i=0 holder
  until (set -C; echo $$ > "$RUN/.lock") 2>/dev/null; do
    holder=$(cat "$RUN/.lock" 2>/dev/null || true)
    if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null && (set -C; echo $$ > "$RUN/.lock-reap") 2>/dev/null; then
      # A crew.sh died holding the lock. One waiter at a time takes it away,
      # and only while that dead one still holds it: another waiter may have
      # taken it away and locked it again since this one read the pid.
      [ "$(cat "$RUN/.lock" 2>/dev/null || true)" != "$holder" ] || rm -f "$RUN/.lock"
      rm -f "$RUN/.lock-reap"
      continue
    fi
    i=$((i + 1))
    [ $i -lt 600 ] || die "lock held for 2 minutes: $RUN/.lock (remove it, and .lock-reap beside it, if no crew.sh is running)"
    sleep 0.2
  done
  LOCKED=1
}
unlock() { if [ "$LOCKED" = 1 ]; then rm -f "$RUN/.lock"; LOCKED=0; fi; }
trap unlock EXIT

state_get() { if [ -f "$STATE" ]; then jq -r "$@" "$STATE"; fi; }
state_put() { local tmp="$STATE.tmp.$$"; jq "$@" "$STATE" > "$tmp" && mv "$tmp" "$STATE"; }
wfile() { printf '%s/workers/%s.json' "$RUN" "$1"; }
wval() { jq -r "$2 // empty" "$(wfile "$1")"; }
wset() { local f tmp; f=$(wfile "$1"); shift; tmp="$f.tmp.$$"; jq "$@" "$f" > "$tmp" && mv "$tmp" "$f"; }
need_worker() { [ -f "$(wfile "$1")" ] || die "no worker '$1' (crew.sh status lists them)"; }

# --- panes ----------------------------------------------------------------------

pane_fg() { # PANE -> "<foreground pgid> <shell pid>", or nothing if it is gone
  herdr pane process-info --pane "$1" 2>/dev/null |
    jq -r '.result.process_info | "\(.foreground_process_group_id) \(.shell_pid)"' 2>/dev/null || true
}

at_shell() { local p; p=$(pane_fg "$1"); [ -n "$p" ] && [ "${p% *}" = "${p#* }" ]; }

wait_shell() { # PANE: until its shell is in the foreground again (10 s)
  local i=0
  while [ $i -lt 50 ]; do at_shell "$1" && return 0; sleep 0.2; i=$((i + 1)); done
  return 1
}

group_gone() { # PANE PGID: the shell is back in front and no process of the group is left
  local i=0
  while [ $i -lt 50 ]; do
    if at_shell "$1" && ! kill -0 -- "-$2" 2>/dev/null; then return 0; fi
    sleep 0.2; i=$((i + 1))
  done
  return 1
}

stop_pane() { # PANE: end the foreground job, every process of it; 1 when the shell is not back in front
  # The whole group, not just its leader: the shell takes the terminal back as
  # soon as its direct child exits, while helpers in the group (Copilot's
  # native binary, an agent's MCP servers) can outlive it by seconds and reset
  # the terminal's colors on their way out, after the slot is repainted.
  local p fg sh
  [ "$1" != "${HERDR_PANE_ID:-}" ] || die "refusing to stop the lead's own pane"
  p=$(pane_fg "$1"); fg=${p% *}; sh=${p#* }
  case "$fg" in '' | null | *[!0-9]*) return 0 ;; esac
  [ "$fg" != "$sh" ] || return 0
  kill -TERM -- "-$fg" 2>/dev/null || true
  group_gone "$1" "$fg" && return 0
  kill -KILL -- "-$fg" 2>/dev/null || true
  group_gone "$1" "$fg"
}

paint() { # PANE SLOT TEXT: tint the pane and show its banner
  # herdr treats a background set by OSC 11 as an override owned by the
  # process group that sent it, and restores the host's colors when that group
  # exits. So the shell itself sends it, with its printf builtin, and the tint
  # lasts as long as the pane's shell; _paint, a child, only draws the banner.
  # The shell does not see the lead's environment: pass the mode along.
  local i=$(($2 - 1)) mode set=""
  mode=$(tint_mode)
  case "$mode" in
    dark) set="printf '\\033]11;${TINT_DARK[$i]}\\007'; " ;;
    light) set="printf '\\033]11;${TINT_LIGHT[$i]}\\007'; " ;;
  esac
  herdr pane run "$1" "$set$(printf '%q' "$SELF") _paint $2 $(printf '%q' "$3") $mode" >/dev/null
}

tint_mode() { # dark (default), light or off
  case "$(conf_get tint)" in light) echo light ;; off | false) echo off ;; *) echo dark ;; esac
}

paint_free() { # PANE SLOT
  herdr pane rename "$1" "${SLOT_EMOJI[$(($2 - 1))]} slot $2 · free" >/dev/null 2>&1 || true
  paint "$1" "$2" "free"
}

settle_paint() { # PANE SLOT TEXT: that banner is up and the shell is back at its prompt
  herdr pane wait-output "$1" --match "slot $2 (${SLOT_COLOR[$(($2 - 1))]}) · $3" \
    --timeout 10000 >/dev/null 2>&1 || true
  wait_shell "$1" || true
}

cmd__paint() { # SLOT TEXT MODE - runs inside a crew pane: clear it, draw the banner
  local i=$(($1 - 1)) ink
  ink=${INK_DARK[$i]}
  [ "${3:-dark}" != light ] || ink=${INK_LIGHT[$i]}
  printf '\033[H\033[2J\033[3J'
  printf '\033[1;38;2;%sm%s jidoka crew · slot %s (%s) · %s\033[0m\n' \
    "$ink" "${SLOT_EMOJI[$i]}" "$1" "${SLOT_COLOR[$i]}" "$2"
}

# --- crew tabs ------------------------------------------------------------------
# A crew tab starts as one pane. A worker takes a free pane, or a new column:
# the tab's rightmost pane split to the right (herdr's prefix+v), then every
# column evened out. herdr 0.9.5 has no action that evens panes out, so
# equalize sets each split's ratio itself, the way vim's Ctrl-w = shares space.

# herdr pane layout -> one layout.set_split_ratio request per split that is off
# its equal share: a half's share is how many panes sit side by side in it
# along the split's direction. A split's path is the tail of its id (split_2_10
# is root, second, first), sent as booleans (true for second).
EQUALIZE='
.result.layout as $l
| [$l.splits[] | {key: (.id | split("_") | .[2:] | join("_") | if . == "root" then "" else . end), value: .}]
| if all(.key | test("^[01]*$")) then from_entries else {} end
| . as $s
| def w($p; $d):
    if $s[$p] == null then 1
    elif $s[$p].direction == $d then w($p + "0"; $d) + w($p + "1"; $d)
    else [w($p + "0"; $d), w($p + "1"; $d)] | max end;
  $s | to_entries[] | .key as $p | .value as $v
  | (w($p + "0"; $v.direction)) as $a
  | ($a / ($a + w($p + "1"; $v.direction))) as $r
  | select($r - $v.ratio > 0.001 or $r - $v.ratio < -0.001)
  | {id: "equalize", method: "layout.set_split_ratio",
     params: {tab_id: $tab, path: ($p | explode | map(. == 49)), ratio: $r}}
  | tojson'

api() { # REQUEST -> herdr's reply on its socket API; 1 when nothing answers
  # The socket covers what the 0.9.5 CLI does not, such as split ratios. herdr
  # answers one JSON line per connection and closes it; -w only bounds a server
  # that never answers.
  local out
  [ -n "${HERDR_SOCKET_PATH:-}" ] && have nc || return 1
  out=$(printf '%s\n' "$1" | nc -U -w 5 "$HERDR_SOCKET_PATH" 2>/dev/null) || return 1
  [ -n "$out" ] || return 1
  printf '%s\n' "$out"
}

split_pane() { # PANE DIRECTION -> new pane id
  local out
  out=$(herdr pane split "$1" --direction "$2" --cwd "$(state_get .cwd)" \
    --env JIDOKA_CREW_ROLE=worker --no-focus 2>&1) || die "pane split failed: $out"
  jq -r .result.pane.pane_id <<< "$out"
}

new_tab() { # LABEL -> tab id; one pane, slot 1
  local out tab
  out=$(herdr tab create --workspace "$(state_get .workspace)" --cwd "$(state_get .cwd)" \
    --label "$1" --env JIDOKA_CREW_ROLE=worker --no-focus 2>&1) || die "tab create failed: $out"
  tab=$(jq -r .result.tab.tab_id <<< "$out")
  state_put --arg t "$tab" --arg l "$1" --arg p "$(jq -r .result.root_pane.pane_id <<< "$out")" \
    '.tabs += [{tab: $t, label: $l, panes: [{pane: $p, slot: 1}]}]'
  printf '%s' "$tab"
}

tab_panes() { state_get --arg t "$1" '.tabs[] | select(.tab == $t) | .panes[].pane'; } # TAB
pane_slot() { state_get --arg p "$1" 'first(.tabs[].panes[] | select(.pane == $p) | .slot)'; } # PANE

tab_layout() { # TAB -> herdr's layout of it, panes and splits with their rects
  herdr pane layout --pane "$(tab_panes "$1" | head -n 1)" 2>/dev/null
}

equalize() { # TAB: even out its columns (and any rows), what prefix+= would do
  local plan req
  plan=$(tab_layout "$1" | jq -r --arg tab "$1" "$EQUALIZE" 2>/dev/null || true)
  [ -n "$plan" ] || return 0
  while read -r req; do api "$req" >/dev/null || true; done <<< "$plan"
}

forget_workers() { # FIELD VALUE: drop the workers whose pane or tab that was
  local f
  for f in "$RUN"/workers/*.json; do
    if [ -f "$f" ] && [ "$(jq -r ".$1" "$f")" = "$2" ]; then
      note "worker $(jq -r .name "$f") is gone: someone closed its $1"
      rm -f "$f" "${f%.json}.prompted"
    fi
  done
}

prune_tabs() { # forget crew tabs and panes that someone closed, and their workers
  local tab pane live gone
  live=$(herdr pane list 2>/dev/null | jq -r '.result.panes[].pane_id' 2>/dev/null) || return 0
  [ -n "$live" ] || return 0
  for tab in $(state_get '.tabs[].tab'); do
    gone=0
    for pane in $(tab_panes "$tab"); do
      printf '%s\n' "$live" | grep -qxF "$pane" && continue
      state_put --arg p "$pane" '.tabs |= map(.panes |= map(select(.pane != $p)))'
      forget_workers pane "$pane"
      gone=1
    done
    if [ -n "$(tab_panes "$tab")" ]; then
      [ $gone = 0 ] || equalize "$tab" # herdr gave the closed pane's room to one neighbor
      continue
    fi
    note "crew tab $tab is gone, or none of its panes is left; forgetting it"
    state_put --arg t "$tab" '.tabs |= map(select(.tab != $t))'
    forget_workers tab "$tab"
  done
}

slot_taken() { # PANE -> 0 when a worker holds it
  local f
  for f in "$RUN"/workers/*.json; do
    [ -f "$f" ] && [ "$(jq -r .pane "$f")" = "$1" ] && return 0
  done
  return 1
}

add_column() { # TAB -> a new pane at the tab's right, evened out with the rest; 1 when full, 2 when herdr fails
  local layout count width ours right slot pane
  count=$(tab_panes "$1" | wc -l | tr -d ' ')
  [ "$count" -lt "$TAB_MAX" ] || return 1
  layout=$(tab_layout "$1") || return 1
  width=$(jq -r '.result.layout.area.width // 0 | floor' <<< "$layout")
  [ $((width / (count + 1))) -ge "$COL_MIN" ] || return 1
  ours=$(state_get -c --arg t "$1" '[.tabs[] | select(.tab == $t) | .panes[].pane]')
  right=$(jq -r --argjson ours "$ours" '[.result.layout.panes[] | select(.pane_id as $p | $ours | index($p))]
    | sort_by(.rect.x + .rect.width, -.rect.y) | last | .pane_id // empty' <<< "$layout")
  [ -n "$right" ] || return 1
  slot=$(state_get --arg t "$1" --argjson max "$TAB_MAX" '[.tabs[] | select(.tab == $t) | .panes[].slot] as $used
    | first(range(1; $max + 1) | select(. as $s | $used | index($s) | not))')
  pane=$(split_pane "$right" right) || return 2 # split_pane said why
  state_put --arg t "$1" --arg p "$pane" --argjson s "$slot" \
    '(.tabs[] | select(.tab == $t) | .panes) += [{pane: $p, slot: $s}]'
  equalize "$1"
  printf '%s' "$pane"
}

claim_slot() { # -> "PANE SLOT TAB": a free crew pane, else a new column, else a new crew tab
  # Callers run it as `$(claim_slot) || die`, where errexit is off: every
  # herdr call that can fail returns here by hand.
  local n t pane tab rc
  n=$(state_get '.tabs | length')
  t=0
  while [ "$t" -lt "$n" ]; do
    tab=$(state_get ".tabs[$t].tab")
    for pane in $(tab_panes "$tab"); do
      slot_taken "$pane" && continue
      at_shell "$pane" || continue # something else runs there
      printf '%s %s %s' "$pane" "$(pane_slot "$pane")" "$tab"
      return 0
    done
    t=$((t + 1))
  done
  t=0
  while [ "$t" -lt "$n" ]; do
    tab=$(state_get ".tabs[$t].tab")
    rc=0; pane=$(add_column "$tab") || rc=$?
    if [ $rc = 0 ]; then
      printf '%s %s %s' "$pane" "$(pane_slot "$pane")" "$tab"
      return 0
    fi
    [ $rc = 1 ] || return 1 # herdr failed the split
    t=$((t + 1))
  done
  if [ "$n" -eq 0 ]; then tab=$(new_tab "$TAB_LABEL") || return 1
  else tab=$(new_tab "$TAB_LABEL $((n + 1))") || return 1; fi
  printf '%s %s %s' "$(tab_panes "$tab")" 1 "$tab"
}

free_pane() { # PANE TAB: close a worker's column, or keep a tab's last pane, free -> which
  # The first crew tab keeps its last pane, so the crew stays up between
  # dispatches, and that pane turns slot 1 again, as `up` left it; another
  # crew tab closes with its last worker.
  if [ "$(tab_panes "$2" | wc -l | tr -d ' ')" -gt 1 ]; then
    herdr pane close "$1" >/dev/null 2>&1 || true
    state_put --arg p "$1" '.tabs |= map(.panes |= map(select(.pane != $p)))'
    equalize "$2"
    echo "column closed"
  elif [ "$2" != "$(state_get '.tabs[0].tab')" ]; then
    herdr tab close "$2" >/dev/null 2>&1 || true
    state_put --arg t "$2" '.tabs |= map(select(.tab != $t))'
    echo "crew tab closed"
  elif ! at_shell "$1"; then
    # Something the stop could not end holds the terminal, and painting would
    # type into it. Close the tab instead; the next dispatch opens a new one.
    herdr tab close "$2" >/dev/null 2>&1 || true
    state_put --arg t "$2" '.tabs |= map(select(.tab != $t))'
    echo "crew tab closed, since its pane did not return to its shell"
  else
    state_put --arg p "$1" '(.tabs[].panes[] | select(.pane == $p) | .slot) = 1'
    paint_free "$1" 1
    settle_paint "$1" 1 free
    echo "pane kept, free as slot 1"
  fi
}

name_lead() {
  local cur prev n
  cur=$(state_get .lead_name)
  if [ -n "$cur" ] && herdr agent get "$cur" 2>/dev/null |
    jq -e --arg p "$HERDR_PANE_ID" '.result.agent.pane_id == $p' >/dev/null 2>&1; then
    return 0
  fi
  prev=$(herdr agent get "$HERDR_PANE_ID" 2>/dev/null | jq -r '.result.agent.name // empty' 2>/dev/null || true)
  for n in lead lead-2 lead-3 lead-4 lead-5; do
    if herdr agent rename "$HERDR_PANE_ID" "$n" >/dev/null 2>&1; then
      state_put --arg n "$n" --arg p "$prev" '.lead_name = $n | .lead_prev_name = $p'
      return 0
    fi
  done
  note "could not name this agent lead (no herdr-recognised agent in $HERDR_PANE_ID?)"
}

lead_name() { local n; n=$(state_get .lead_name); printf '%s' "${n:-$HERDR_PANE_ID}"; }

# --- workers --------------------------------------------------------------------

next_name() { # AGENT -> a worker name unique among live agents and this pane's runs
  local n live
  n=$(state_get --arg a "$1" '.counters[$a] // 0')
  live=$(herdr agent list 2>/dev/null | jq -r '.result.agents[].name // empty' 2>/dev/null || true)
  while :; do
    n=$((n + 1))
    # briefs/ outlives `down`: an earlier run's brief and report keep their names
    [ -e "$RUN/briefs/$1-$n.md" ] && continue
    printf '%s\n' "$live" | grep -qx "$1-$n" || break
  done
  state_put --arg a "$1" --argjson n "$n" '.counters[$a] = $n'
  printf '%s-%s' "$1" "$n"
}

first_prompt() { # NAME -> the one-line prompt that hands a worker its brief
  local name=$1 agent kind mode brief report lead tail
  agent=$(wval "$name" .agent); kind=$(wval "$name" .kind); mode=$(wval "$name" .mode)
  brief=$(wval "$name" .brief); report=$(wval "$name" .report); lead=$(lead_name)
  if [ "$kind" = claude ]; then
    tail="Your final message is your report to me: give it in full, in the Return Report or Output format your instructions define."
  else
    tail="When you finish, write your full final answer, in the Return Report or Output format your instructions define, to $report, then reply with only: REPORT $report"
  fi
  if [ "$mode" = native ]; then
    printf 'Lead (herdr agent %s) here. Your task brief is %s: read it and carry it out. %s If you need a decision from me first, ask it and stop; I answer in this pane.' \
      "$lead" "$brief" "$tail"
  else
    printf 'You are jidoka worker %s, started by the lead (herdr agent %s). Act as the jidoka agent %s: read %s now and follow its body as your instructions; its tools line is your tool budget. A skill it names (jidoka:x or a bare x) is the file %s/skills/x/SKILL.md: read that file whenever it says to invoke the skill. Your task brief is %s: read it and carry it out. %s If you need a decision from me first, ask it and stop; I answer in this pane.' \
      "$name" "$lead" "$agent" "$AGENTS_DIR/$agent.md" "$PLUGIN_ROOT" "$brief" "$tail"
  fi
}

alnum() { tr -cd 'A-Za-z0-9'; } # text without spacing, wrapping or borders

settle_screen() { # PANE: until its screen holds still for 1.5 s (at most 15 s)
  local i=0 same=0 h last=""
  while [ $i -lt 30 ] && [ $same -lt 3 ]; do
    h=$(herdr pane read "$1" --source visible 2>/dev/null | cksum)
    if [ "$h" = "$last" ]; then same=$((same + 1)); else same=0; last=$h; fi
    sleep 0.5; i=$((i + 1))
  done
}

claude_transcript() { # NAME -> path of its Claude Code session file, if any yet
  local sid
  sid=$(herdr agent get "$1" 2>/dev/null | jq -r '.result.agent.agent_session.value // empty' 2>/dev/null || true)
  [ -n "$sid" ] || sid=$(wval "$1" .session)
  [ -z "$sid" ] || find "$CLAUDE_HOME/projects" -maxdepth 2 -name "$sid.jsonl" 2>/dev/null | head -n 1
}

claude_prompts() { # NAME -> one line per user entry of its session file, letters and digits only
  # A prompt's content is a string or a list of blocks; a tool result's line
  # stays empty, so the count of lines only grows.
  local f
  f=$(claude_transcript "$1")
  [ -n "$f" ] || return 0
  jq -r 'select(.type == "user" and ((.isMeta // false) | not)) | .message.content
    | if type == "string" then . else [.[]? | select(.type == "text") | .text] | join(" ") end
    | gsub("[^A-Za-z0-9]"; "")' "$f" 2>/dev/null || true
}

delivered() { # NAME TEXT [SINCE] -> 0 when the worker shows it has the text
  local needle
  if [ "$(wval "$1" .kind)" = claude ]; then
    # Claude Code writes every submitted prompt to its session file. The whole
    # text, among the entries after the first SINCE: an earlier prompt that
    # starts the same way (the last follow-up) is not this one.
    needle=$(printf '%s' "$2" | alnum)
    claude_prompts "$1" | tail -n +"$((${3:-0} + 1))" | grep -F -- "$needle" >/dev/null
  else
    # A screen wraps, truncates and redraws, so only the start of the text.
    needle=$(printf '%s' "$2" | alnum | cut -c1-40)
    herdr pane read "$(wval "$1" .pane)" --source recent-unwrapped --lines 400 2>/dev/null | alnum |
      grep -F -- "$needle" >/dev/null
  fi
}

prompt_gate() { # NAME TEXT: submit, then wait until the worker takes it
  local out code try=0 since=0
  touch "$RUN/workers/$1.prompted"
  wset "$1" '.notified = false'
  [ "$(wval "$1" .kind)" != claude ] || since=$(claude_prompts "$1" | wc -l | tr -d ' ')
  while :; do
    out=$(herdr agent prompt "$1" "$2" --wait --timeout "$GATE_TIMEOUT_MS" 2>&1) && return 0
    code=$(jq -r '.error.code // empty' <<< "$out" 2>/dev/null || true)
    [ "$code" = timeout ] && return 0 # working past the gate: the normal case
    [ "$code" = agent_prompt_stalled ] || break
    # herdr saw no reaction. Either the worker has the text and herdr's state
    # rules missed it (they do not know every harness version), or the text
    # was lost, as a paste into a TUI that is still starting can be. Only a
    # Claude worker's session file proves the text did not arrive, so only a
    # Claude worker gets it again; a screen can lag, and a second copy is a
    # second task. For the others, wait reports `quiet` if nothing starts.
    if [ "$(wval "$1" .kind)" != claude ]; then
      settle_screen "$(wval "$1" .pane)"
      if delivered "$1" "$2"; then
        note "herdr did not see $1 start, but its screen shows the prompt; wait watches its report file"
      else
        note "herdr did not see $1 start and its screen does not show the prompt yet; wait reports quiet if it never starts"
      fi
      return 0
    fi
    delivered "$1" "$2" "$since" && return 0
    try=$((try + 1))
    [ $try -le 2 ] || break
    note "$1 did not get the prompt; sending it again ($try of 2)"
    settle_screen "$(wval "$1" .pane)"
  done
  printf '%s\n' "$out" >&2
  return 1
}

report_fresh() { # NAME -> 0 when its report file was written after its last prompt
  local report
  report=$(wval "$1" .report)
  [ -f "$report" ] && [ "$report" -nt "$RUN/workers/$1.prompted" ]
}

worker_state() { # NAME -> herdr agent status, or "gone" when its agent exited
  local out
  out=$(herdr agent get "$1" 2>/dev/null) || { echo gone; return; }
  jq -r '.result.agent.agent_status // "unknown"' <<< "$out"
}

notify() { # NAME
  local slot
  slot=$(wval "$1" .slot)
  herdr notification show "jidoka: $1 needs you" \
    --body "Slot $slot (${SLOT_COLOR[$((slot - 1))]}) in the crew tab is waiting on an approval or a question." \
    --sound request >/dev/null 2>&1 || true
}

start_worker() { # NAME MODEL EFFORT -> 0 started | 2 blocked at startup | 1 failed
  local name=$1 model=$2 effort=$3 agent kind pane native out code extra
  local args=() more=()
  agent=$(wval "$name" .agent); kind=$(wval "$name" .kind); pane=$(wval "$name" .pane)
  local mode=brief
  case "$kind" in
    claude)
      native=$(state_get .claude_native)
      if [ -n "$native" ]; then
        mode=native
        args+=(--agent "${native%% *}:$agent")
        case "$native" in *" "*) args+=(--plugin-dir "${native#* }") ;; esac
      else
        [ -n "$model" ] || model=$(afm "$agent" claude-model)
        [ -n "$effort" ] || effort=$(afm "$agent" claude-effort)
      fi
      [ -z "$model" ] || args+=(--model "$model")
      [ -z "$effort" ] || args+=(--effort "$effort")
      args+=(--name "$name" --add-dir "$RUN")
      ;;
    copilot)
      [ -z "$model" ] || note "--model $model is a Claude alias; $name keeps its Copilot tier model"
      args+=(--model "$(afm "$agent" copilot-model)" --name "$name" --add-dir "$RUN")
      ;;
    codex)
      [ -z "$model" ] || note "--model $model is a Claude alias; ignored for codex"
      args+=(--add-dir "$RUN")
      ;;
    *)
      [ -z "$model" ] || note "--model $model is a Claude alias; ignored for $kind"
      ;;
  esac
  if yolo_on "$kind"; then args+=("$(yolo_flag "$kind")"); fi
  extra=$(conf_get "args.$kind")
  if [ -n "$extra" ]; then read -r -a more <<< "$extra"; fi
  wset "$name" --arg m "$mode" '.mode = $m'
  out=$(herdr agent start "$name" --kind "$kind" --pane "$pane" --timeout "$START_TIMEOUT_MS" \
    -- ${args[@]+"${args[@]}"} ${more[@]+"${more[@]}"} 2>&1) || {
    code=$(jq -r '.error.code // empty' <<< "$out" 2>/dev/null || true)
    if [ "$code" = agent_not_ready ]; then return 2; fi
    printf '%s\n' "$out" >&2
    return 1
  }
  wset "$name" --arg s "$(jq -r '.result.agent.agent_session.value // empty' <<< "$out")" '.session = $s'
  # herdr calls the agent ready when it recognises it; its TUI may still be
  # drawing, and a paste then can be lost. Let the screen settle first.
  settle_screen "$pane"
}

cmd_dispatch() {
  need_herdr
  local agent=${1:-} model="" effort="" brief claim pane slot tab name kind rc
  [ -n "$agent" ] || die "usage: crew.sh dispatch AGENT [--model M] [--effort E] <BRIEF"
  shift
  agent=${agent##*:} # jidoka:code-explorer or code-explorer
  while [ $# -gt 0 ]; do
    case "$1" in
      --model) model=${2:-}; shift 2 ;;
      --effort) effort=${2:-}; shift 2 ;;
      *) die "dispatch: unknown option $1" ;;
    esac
  done
  [ -f "$AGENTS_DIR/$agent.md" ] || die "unknown agent '$agent' (agents: $(words agent_names))"
  brief=$(cat)
  [ -n "${brief//[[:space:]]/}" ] || die "dispatch: the brief comes on stdin, and it is empty"
  [ -f "$STATE" ] || cmd_up > /dev/null
  kind=$(resolve_kind "$agent")
  [ -n "$kind" ] || die "cannot tell which harness the lead runs on; set 'harness' in $CONF"
  have "$(kind_bin "$kind")" || die "$kind workers need '$(kind_bin "$kind")' on PATH (config: $CONF)"

  lock
  prune_tabs
  claim=$(claim_slot) || die "could not open a crew pane for $agent (herdr's error is above)"
  read -r pane slot tab <<< "$claim"
  name=$(next_name "$agent")
  jq -n --arg name "$name" --arg agent "$agent" --arg kind "$kind" --arg pane "$pane" \
    --arg tab "$tab" --argjson slot "$slot" --arg brief "$RUN/briefs/$name.md" \
    --arg report "$RUN/reports/$name.md" \
    '{name: $name, agent: $agent, kind: $kind, pane: $pane, tab: $tab, slot: $slot,
      mode: "", session: "", brief: $brief, report: $report, pending: false, notified: false}' \
    > "$(wfile "$name")"
  unlock

  printf '%s\n' "$brief" > "$RUN/briefs/$name.md"
  herdr pane rename "$pane" "${SLOT_EMOJI[$((slot - 1))]} $name · $kind" >/dev/null 2>&1 || true
  # Paint before the agent starts: a new column has no tint yet. The pane's
  # shell sends it, so it lasts through the agent and its exit.
  paint "$pane" "$slot" "$name"
  settle_paint "$pane" "$slot" "$name"
  rc=0; start_worker "$name" "$model" "$effort" || rc=$?
  if [ $rc = 1 ]; then
    drop_worker "$name" >/dev/null
    die "could not start $name on $kind in slot $slot (see above); released it"
  fi
  if [ $rc = 2 ]; then
    wset "$name" '.pending = true | .notified = true'
    notify "$name"
    echo "$name blocked-at-start slot $slot (${SLOT_COLOR[$((slot - 1))]}) $kind: a startup prompt waits in the pane; wait sends the brief once it is answered"
    return 0
  fi
  if ! prompt_gate "$name" "$(first_prompt "$name")"; then
    drop_worker "$name" >/dev/null
    die "$name started but did not take its brief; released it"
  fi
  echo "$name dispatched slot $slot (${SLOT_COLOR[$((slot - 1))]}) $kind $(wval "$name" .mode)$(yolo_on "$kind" && echo " yolo")"
}

cmd_wait() {
  need_herdr
  local names=() timeout=$WAIT_DEFAULT deadline n st res settled newly out i h
  local screen=() changed=()
  while [ $# -gt 0 ]; do
    case "$1" in
      --timeout) timeout=${2:-}; shift 2 ;;
      *) names+=("$1"); shift ;;
    esac
  done
  [ ${#names[@]} -gt 0 ] || die "usage: crew.sh wait NAME... [--timeout SECONDS]"
  for n in "${names[@]}"; do need_worker "$n"; done
  deadline=$(($(now) + timeout))
  while :; do
    settled=1; newly=0; out=""; i=0
    for n in "${names[@]}"; do
      i=$((i + 1))
      st=$(worker_state "$n")
      if [ "$(wval "$n" .pending)" = true ] && { [ "$st" = idle ] || [ "$st" = "done" ]; }; then
        if prompt_gate "$n" "$(first_prompt "$n")"; then
          wset "$n" '.pending = false'
          st=$(worker_state "$n")
        else
          st=$(worker_state "$n") # blocked again, or idle without its brief
          [ "$st" = blocked ] || [ "$st" = gone ] || st=no-brief
        fi
      fi
      # A worker that reports through a file is done when the file is: herdr's
      # idle for it may be a fallback guess. A still screen with no report
      # usually means it asked the lead something.
      if [ "$(wval "$n" .kind)" != claude ] && [ "$(wval "$n" .pending)" != true ] && [ "$st" != blocked ]; then
        if report_fresh "$n"; then
          st="done"
        elif [ "$st" != gone ]; then
          st=working
          h=$(herdr pane read "$(wval "$n" .pane)" --source visible 2>/dev/null | cksum)
          if [ "$h" != "${screen[$i]:-}" ]; then screen[i]=$h; changed[i]=$(now); fi
          if [ $(($(now) - ${changed[$i]})) -ge $QUIET_SECONDS ]; then st=quiet; fi
        fi
      fi
      case "$st" in
        quiet)
          res="quiet: no report yet and its screen has not changed for ${QUIET_SECONDS}s; peek it, and answer a question with send"
          newly=1 ;;
        no-brief)
          res="no-brief: its brief did not go through (herdr's error is above); wait again to resend it"
          newly=1 ;;
        idle | done) res=ready ;;
        gone) res=exited ;;
        blocked)
          res="blocked slot $(wval "$n" .slot): an approval or question waits in its pane"
          if [ "$(wval "$n" .notified)" != true ]; then
            notify "$n"; wset "$n" '.notified = true'; newly=1
          else
            settled=0
          fi ;;
        *)
          res=working; settled=0
          [ "$(wval "$n" .notified)" != true ] || wset "$n" '.notified = false' ;;
      esac
      out="$out$n $res
"
    done
    if [ $settled = 1 ] || [ $newly = 1 ] || [ "$(now)" -ge "$deadline" ]; then
      printf '%s' "$out"
      return 0
    fi
    sleep 3
  done
}

# The text of a Claude Code session's last turn: assistant text after the last
# tool call that follows the last prompt (a string user entry, not a tool
# result, meta entry or slash-command echo).
CLAUDE_FINAL='
def prompt_entry:
  .type == "user" and ((.isMeta // false) | not) and ((.isSidechain // false) | not)
  and (if (.message.content | type) == "string"
       then (.message.content | test("^\\s*<(command-|local-command-)") | not)
       else ([.message.content[]? | select(.type == "tool_result")] | length) == 0 end);
(map(prompt_entry) | rindex(true)) as $p
| if $p == null then "" else
    [.[($p + 1):][] | select(.type == "assistant" and ((.isSidechain // false) | not))
     | .message.content[]?] as $blocks
    | ($blocks | map(.type == "tool_use") | rindex(true)) as $t
    | $blocks[(if $t == null then 0 else $t + 1 end):]
    | map(select(.type == "text") | .text) | join("\n\n")
  end'

cmd_report() {
  need_herdr
  local name=${1:-} kind report f text=""
  [ -n "$name" ] || die "usage: crew.sh report NAME"
  need_worker "$name"
  kind=$(wval "$name" .kind); report=$(wval "$name" .report)
  if [ "$kind" = claude ]; then
    f=$(claude_transcript "$name")
    [ -z "$f" ] || text=$(jq -rs "$CLAUDE_FINAL" "$f" 2>/dev/null || true)
    if [ -n "${text//[[:space:]]/}" ]; then
      printf '%s\n' "$text" > "$report"
      cat "$report"
      return 0
    fi
  elif [ -f "$report" ] && [ "$report" -nt "$RUN/workers/$name.prompted" ]; then
    cat "$report"
    return 0
  fi
  note "no report from $name yet; its screen follows. If it has finished, ask it with: crew.sh send $name"
  herdr agent read "$name" --source recent-unwrapped --lines 80 2>/dev/null ||
    herdr pane read "$(wval "$name" .pane)" --source recent-unwrapped --lines 80
}

cmd_send() {
  need_herdr
  local name=${1:-} msg kind report st n f text
  [ -n "$name" ] || die "usage: crew.sh send NAME <MESSAGE"
  need_worker "$name"
  msg=$(cat)
  [ -n "${msg//[[:space:]]/}" ] || die "send: the message comes on stdin, and it is empty"
  st=$(worker_state "$name")
  case "$st" in idle | done) ;; *) die "$name is $st; wait for it to settle first" ;; esac
  kind=$(wval "$name" .kind); report=$(wval "$name" .report)
  if [ "${msg//$'\n'/}" = "$msg" ] && [ ${#msg} -le 1500 ]; then # one short line goes inline
    text="Lead: $msg"
  else
    n=1
    while [ -e "$RUN/briefs/$name.followup-$n.md" ]; do n=$((n + 1)); done
    f="$RUN/briefs/$name.followup-$n.md"
    printf '%s\n' "$msg" > "$f"
    # Its number first: a screen check compares only the start of the text.
    text="Lead follow-up $n: it is in $f - read it and answer."
  fi
  [ "$kind" = claude ] || text="$text When you finish, rewrite $report with your full updated answer, then reply with only: REPORT $report"
  prompt_gate "$name" "$text" || die "$name did not take the follow-up (crew.sh peek $name)"
  echo "$name prompted"
}

cmd_peek() {
  need_herdr
  local name=${1:-} lines=60
  [ -n "$name" ] || die "usage: crew.sh peek NAME [--lines N]"
  need_worker "$name"
  [ "${2:-}" != --lines ] || lines=${3:-60}
  herdr agent read "$name" --source recent-unwrapped --lines "$lines" 2>/dev/null ||
    herdr pane read "$(wval "$name" .pane)" --source recent-unwrapped --lines "$lines"
}

drop_worker() { # NAME: stop it, forget it, and close its column -> what became of the pane
  local pane tab
  pane=$(wval "$1" .pane); tab=$(wval "$1" .tab)
  stop_pane "$pane" || true # free_pane sees a pane that is not back at its shell
  lock
  rm -f "$(wfile "$1")" "$RUN/workers/$1.prompted"
  if herdr pane get "$pane" >/dev/null 2>&1; then
    free_pane "$pane" "$tab"
  else
    prune_tabs
    echo "its pane was already closed"
  fi
  unlock
}

cmd_release() {
  need_herdr
  local name slot
  [ $# -gt 0 ] || die "usage: crew.sh release NAME..."
  for name in "$@"; do
    if [ ! -f "$(wfile "$name")" ]; then note "no worker '$name'"; continue; fi
    slot=$(wval "$name" .slot)
    printf '%s released from slot %s (%s): ' "$name" "$slot" "${SLOT_COLOR[$((slot - 1))]}"
    drop_worker "$name"
  done
}

# --- crew -----------------------------------------------------------------------

cmd_mode() {
  local why=""
  if [ "${JIDOKA_CREW_ROLE:-}" = worker ]; then why="this session is itself a crew worker"
  elif [ "${HERDR_ENV:-}" != 1 ]; then why="not inside herdr (HERDR_ENV is not 1)"
  elif [ "$(conf_get enabled)" = false ]; then why="enabled = false in $CONF"
  elif ! have herdr; then why="herdr is not on PATH"
  elif ! have jq; then why="jq is not on PATH"
  elif [ -z "${HERDR_PANE_ID:-}" ]; then why="HERDR_PANE_ID is unset"
  elif ! herdr pane get "$HERDR_PANE_ID" >/dev/null 2>&1; then why="the herdr server does not answer for pane $HERDR_PANE_ID"
  fi
  if [ -n "$why" ]; then echo "task: $why"; else echo herdr; fi
}

cmd_up() {
  need_herdr
  local cwd pane
  lock
  if [ ! -f "$STATE" ]; then
    cwd=$(herdr pane get "$HERDR_PANE_ID" 2>/dev/null | jq -r '.result.pane.cwd // empty' 2>/dev/null || true)
    jq -n --arg lp "$HERDR_PANE_ID" --arg ws "${HERDR_WORKSPACE_ID:-}" --arg cwd "${cwd:-$PWD}" \
      --arg native "$(claude_plugin)" \
      '{lead_pane: $lp, workspace: $ws, cwd: $cwd, claude_native: $native,
        lead_name: "", lead_prev_name: "", tabs: [], counters: {}}' > "$STATE"
  fi
  prune_tabs
  if [ "$(state_get '.tabs | length')" = 0 ]; then
    new_tab "$TAB_LABEL" > /dev/null
    pane=$(tab_panes "$(state_get '.tabs[0].tab')")
    paint_free "$pane" 1
    settle_paint "$pane" 1 free
  fi
  name_lead
  unlock
  echo "crew up: tab $(state_get '.tabs[0].tab') \"$(state_get '.tabs[0].label')\"; this agent is herdr agent $(lead_name)"
  list_tab "$(state_get '.tabs[0].tab')"
  echo "each worker takes a free pane or adds a column, $TAB_MAX to a tab; release closes its column"
  echo "run dir: $RUN"
}

list_tab() { # TAB: its crew panes left to right, with slot, worker, harness and state
  local pane slot w f i
  for pane in $(tab_layout "$1" | jq -r '.result.layout.panes | sort_by(.rect.x, .rect.y) | .[].pane_id' 2>/dev/null ||
    tab_panes "$1"); do
    slot=$(pane_slot "$pane")
    [ -n "$slot" ] || continue # a pane someone else split off
    i=$((slot - 1)); w=""
    for f in "$RUN"/workers/*.json; do
      if [ -f "$f" ] && [ "$(jq -r .pane "$f")" = "$pane" ]; then w=$(jq -r .name "$f"); fi
    done
    if [ -n "$w" ]; then
      printf '  %s %s %-6s %-24s %-8s %s\n' "${SLOT_EMOJI[$i]}" "$slot" "${SLOT_COLOR[$i]}" "$w" \
        "$(wval "$w" .kind)" "$(worker_state "$w")"
    else
      printf '  %s %s %-6s free\n' "${SLOT_EMOJI[$i]}" "$slot" "${SLOT_COLOR[$i]}"
    fi
  done
}

cmd_status() {
  need_herdr
  local t n tab
  [ -f "$STATE" ] || { echo "no crew for this pane (crew.sh up opens one)"; return 0; }
  echo "lead: herdr agent $(lead_name) in $HERDR_PANE_ID"
  n=$(state_get '.tabs | length'); t=0
  while [ "$t" -lt "$n" ]; do
    tab=$(state_get ".tabs[$t].tab")
    echo "tab $tab \"$(state_get ".tabs[$t].label")\", left to right"
    list_tab "$tab"
    t=$((t + 1))
  done
  echo "run dir: $RUN"
}

cmd_down() {
  need_herdr
  local f tab tabs=0 prev cur
  [ -f "$STATE" ] || { echo "no crew for this pane"; return 0; }
  lock
  for f in "$RUN"/workers/*.json; do
    [ -f "$f" ] || continue
    stop_pane "$(jq -r .pane "$f")" || true # closing its tab below ends what is left
    rm -f "$f" "${f%.json}.prompted"
  done
  for tab in $(state_get '.tabs[].tab'); do
    herdr tab close "$tab" >/dev/null 2>&1 || true
    tabs=$((tabs + 1))
  done
  cur=$(state_get .lead_name); prev=$(state_get .lead_prev_name)
  if [ -n "$cur" ]; then
    if [ -n "$prev" ]; then
      herdr agent rename "$HERDR_PANE_ID" "$prev" >/dev/null 2>&1 || true
    else
      herdr agent rename "$HERDR_PANE_ID" --clear >/dev/null 2>&1 || true
    fi
  fi
  rm -f "$STATE"
  unlock
  echo "crew down: closed $tabs crew tab(s); briefs and reports stay in $RUN"
}

cmd_config() {
  case "${1:-show}" in
    show)
      echo "config: $CONF"
      if [ -f "$CONF" ]; then grep -v '^[[:space:]]*\(#\|$\)' "$CONF" || echo "(no settings; defaults apply)"
      else echo "(no file; defaults apply)"; fi ;;
    set) [ $# -eq 3 ] || die "usage: crew.sh config set KEY VALUE"; conf_set "$2" "$3"; echo "set $2 = $3 in $CONF" ;;
    unset)
      [ $# -eq 2 ] || die "usage: crew.sh config unset KEY"
      if conf_keys | grep -qxF -- "$2"; then
        conf_drop "$2" > "$CONF.tmp.$$" && mv "$CONF.tmp.$$" "$CONF"
        echo "unset $2 in $CONF"
      elif [ -n "$(conf_keys)" ]; then
        echo "$2 is not set in $CONF; nothing changed (set: $(conf_keys | paste -sd , - | sed 's/,/, /g'))"
      else
        echo "$2 is not set; nothing changed (no settings in $CONF)"
      fi ;;
    path) echo "$CONF" ;;
    *) die "usage: crew.sh config [show | set KEY VALUE | unset KEY | path]" ;;
  esac
}

# --- check ----------------------------------------------------------------------

row() { printf '  %-15s %s\n' "$1" "$2"; }

herdr_config() { printf '%s' "${HERDR_CONFIG_PATH:-$HOME/.config/herdr/config.toml}"; }

toast_delivery() { # herdr's [ui.toast] delivery: off (its default), herdr, terminal or system
  local f v=""
  f=$(herdr_config)
  [ ! -f "$f" ] || v=$(awk '
    /^[[:space:]]*\[/ { t = $0; sub(/#.*/, "", t); gsub(/[[:space:]]/, "", t); s = (t == "[ui.toast]"); next }
    s && /^[[:space:]]*delivery[[:space:]]*=/ {
      sub(/^[^=]*=[[:space:]]*/, ""); sub(/[[:space:]]*#.*$/, ""); gsub(/["\047]/, ""); print; exit }' "$f")
  printf '%s' "${v:-off}"
}

cmd_check() {
  local problems="" mode lead lead_label native k bin ver hooks hook_status missing="" agent role how model
  echo "jidoka check: herdr mode and worker harnesses"
  echo
  echo "Session"
  if [ "${HERDR_ENV:-}" = 1 ]; then
    row "inside herdr" "yes - workspace ${HERDR_WORKSPACE_ID:-?}, tab ${HERDR_TAB_ID:-?}, pane ${HERDR_PANE_ID:-?}"
  else
    row "inside herdr" "no (HERDR_ENV is not 1)"
  fi
  if have herdr; then
    local hs
    hs=$(herdr status 2>/dev/null || true)
    row "herdr" "$(herdr --version 2>/dev/null | head -n 1 | sed 's/^herdr //') - server $(sed -n '/^server:/,/^[a-z]/s/^  status: //p' <<< "$hs" | head -n 1), endpoint compatible: $(sed -n 's/^  endpoint_compatible: //p' <<< "$hs" | head -n 1)"
    if [ "$(toast_delivery)" = off ]; then
      row "alerts" "off - a worker waiting on a prompt shows only as its sidebar dot"
      problems="$problems
  - herdr notifications are off: a worker waiting on a prompt does not pop up.
    Set delivery = \"herdr\" (or \"system\") under [ui.toast] in
    $(herdr_config | sed "s|^$HOME/|~/|")"
    else
      row "alerts" "$(toast_delivery) - a worker waiting on a prompt raises a notification"
    fi
  else
    row "herdr" "not on PATH"
  fi
  if [ "${HERDR_ENV:-}" = 1 ] && have herdr && have jq; then
    local sock="" reply
    if ! have nc; then
      sock="nc is not on PATH"
    elif ! reply=$(api "$(jq -nc --arg t "${HERDR_TAB_ID:-}" '{id: "check", method: "layout.export", params: {tab_id: $t}}')"); then
      sock="nc -U got no answer from the herdr socket"
    elif ! jq -e .result >/dev/null 2>&1 <<< "$reply"; then
      sock="herdr refused a socket request ($(jq -r '.error.message // "no result"' <<< "$reply" 2>/dev/null))"
    fi
    if [ -z "$sock" ]; then
      row "socket API" "reached with nc -U: crew columns are evened out"
    else
      row "socket API" "$sock: crew columns stay uneven"
      problems="$problems
  - $sock, so crew columns stay uneven.
    crew.sh evens them out over the herdr socket with nc -U
    (netcat-openbsd on Linux, the built-in nc on macOS)."
    fi
  fi
  if have jq; then row "jq" "$(jq --version)"; else row "jq" "not on PATH (herdr mode needs it)"; problems="$problems
  - install jq: crew.sh parses herdr's JSON with it"; fi
  lead=$(lead_kind)
  if [ -n "$lead" ]; then lead_label="$lead"; else lead_label="unknown here"; fi
  row "lead harness" "$lead_label"
  mode=$(cmd_mode)
  if [ "$mode" = herdr ]; then
    row "herdr mode" "on - workers run in a \"$TAB_LABEL\" tab, one column and color"
    row "" "each, and this agent is renamed lead"
  else
    row "herdr mode" "off (${mode#task: }) - the line uses this harness's own subagents"
  fi

  echo
  echo "Agent CLIs (herdr agent kinds found on PATH)"
  hooks=""
  if have herdr; then hooks=$(herdr integration status 2>/dev/null || true); fi
  printf '  %-9s %-13s %-34s %s\n' kind command version "herdr state hooks"
  for k in $(kinds); do
    bin=$(kind_bin "$k")
    if ! have "$bin"; then
      if [ "$bin" = "$k" ]; then missing="$missing $k"; else missing="$missing $k($bin)"; fi
      continue
    fi
    if have timeout; then ver=$(timeout 5 "$bin" --version 2>/dev/null | head -n 1 || true)
    else ver=$("$bin" --version 2>/dev/null | head -n 1 || true); fi
    hook_status=$(printf '%s\n' "$hooks" | sed -n "s/^$([ "$k" = agy ] && echo antigravity-cli || echo "$k")\( (experimental)\)\{0,1\}: //p" |
      sed 's/ (\/.*)$//' | head -n 1)
    printf '  %-9s %-13s %-34s %s\n' "$k" "$bin" "${ver:0:34}" "${hook_status:-none}"
  done
  [ -z "$missing" ] || printf 'not on PATH:%s\n' "$missing" | fold -s -w 76 | sed 's/ *$//; s/^/  /' 

  echo
  echo "jidoka on each harness"
  native=$(claude_plugin)
  if have claude; then
    case "$native" in
      "") row "claude" "jidoka plugin not installed: Claude workers read the worker render (instructions from files)" ;;
      *" "*) row "claude" "native agents from this plugin dir (--plugin-dir ${native#* })" ;;
      *) row "claude" "native agents: claude --agent ${native}:<agent> (plugin installed)" ;;
    esac
  fi
  row "others" "read the worker render and write their report to a file"

  echo
  if [ -f "$CONF" ]; then echo "Worker routing (config: $CONF)"; else echo "Worker routing (no config at $CONF; defaults apply)"; fi
  local key
  for key in $(conf_keys); do printf '  %-22s %s\n' "$key" "$(conf_get "$key")"; done
  printf '  %-20s %-15s %-9s %s\n' agent role harness how
  for agent in $(agent_names); do
    role=$(afm "$agent" role)
    k=$(resolve_kind "$agent")
    if [ -z "$k" ]; then
      how="lead's harness (not detectable outside herdr)"; k=lead
    elif ! have "$(kind_bin "$k")"; then
      how="MISSING: '$(kind_bin "$k")' is not on PATH"
      case "$problems" in *"$k is configured"*) ;; *) problems="$problems
  - $k is configured but '$(kind_bin "$k")' is not on PATH: install it or change the config" ;; esac
    else
      case "$k" in
        claude)
          model=$(afm "$agent" claude-model)
          if [ -n "$native" ]; then how="native jidoka agent ($model)"; else how="worker render, --model $model"; fi ;;
        copilot) how="worker render, --model $(afm "$agent" copilot-model)" ;;
        *) how="worker render, $k's own model" ;;
      esac
      if yolo_on "$k"; then how="$how, yolo"; fi
    fi
    printf '  %-20s %-15s %-9s %s\n' "$agent" "$role" "$k" "$how"
  done

  local routed perms=""
  routed=$(for agent in $(agent_names); do resolve_kind "$agent"; echo; done | sort -u)
  for k in $routed; do
    [ -n "$(yolo_flag "$k")" ] || continue
    if yolo_on "$k"; then perms="$perms; $k: yolo ($(yolo_flag "$k"))"
    else perms="$perms; $k: your own settings, prompts wait in its pane"; fi
  done
  [ -z "$perms" ] || row "approvals" "${perms#; }"

  if [ -n "$hooks" ]; then
    for k in $routed; do
      if [ -z "$k" ] || ! have "$(kind_bin "$k")"; then continue; fi
      hook_status=$(printf '%s\n' "$hooks" | sed -n "s/^$k\( (experimental)\)\{0,1\}: //p" | head -n 1)
      case "$hook_status" in
        current*) ;;
        "") problems="$problems
  - herdr has no state hooks for $k: it may not see when a $k worker finishes" ;;
        *) problems="$problems
  - herdr state hooks for $k: ${hook_status%% (/*}; run: herdr integration install $k" ;;
      esac
    done
  fi

  echo
  if [ -n "$problems" ]; then echo "Problems$problems"; else echo "Problems: none"; fi
  echo
  echo "Change the routing: crew.sh config set harness <kind|lead>, role.<role> <kind>,"
  echo "agent.<agent> <kind>, yolo.<kind> on|off, args.<kind> \"<flags>\", enabled false,"
  echo "tint dark|light|off"
}

# --- main -----------------------------------------------------------------------

cmd=${1:-help}
[ $# -eq 0 ] || shift
case "$cmd" in
  mode | up | dispatch | wait | report | send | peek | release | status | down | check | config) "cmd_$cmd" "$@" ;;
  _paint) cmd__paint "$@" ;;
  help | -h | --help) usage ;;
  *) die "unknown command '$cmd' (crew.sh help lists them)" ;;
esac
