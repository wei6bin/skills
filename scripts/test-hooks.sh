#!/usr/bin/env bash
# Tests for the jidoka plugin's after-file-edit hooks.
#
# Feeds each rendered hook (jidoka/hooks/) the payload Claude Code sends on
# PostToolUse, against throwaway fixture projects, and asserts on its reply and
# on what it leaves on disk. Installs pinned Prettier, Biome and TypeScript from
# npm into a temp dir first, so it needs Node and the registry. Not run in CI.
#
# Usage:
#   scripts/test-hooks.sh                # every hook
#   scripts/test-hooks.sh --bash32       # plus the secrets scan under bash 3.2
#                                        # (macOS's /bin/bash), in Docker
#   scripts/test-hooks.sh --keep         # keep the fixtures and say where
#   scripts/test-hooks.sh --hooks DIR    # test another copy of the hooks
set -uo pipefail
cd "$(dirname "$0")/.."

# Pinned so a tool release cannot change the results unannounced.
TOOLS=(prettier@3.9.10 @biomejs/biome@2.6.5 typescript@7.0.2)
BASH32_IMAGE=bash:3.2

hooks=jidoka/hooks keep=0 bash32=0
while (($#)); do
  case $1 in
    --keep) keep=1 ;;
    --bash32) bash32=1 ;;
    --hooks) hooks=${2:?--hooks needs a directory}; shift ;;
    *) echo "unknown argument: $1 (see the usage at the top of $0)" >&2; exit 2 ;;
  esac
  shift
done
H=$(cd "$hooks" 2>/dev/null && pwd) || { echo "no hooks directory: $hooks" >&2; exit 2; }
for t in jq npm npx file cmp; do
  command -v "$t" >/dev/null || { echo "$t not found" >&2; exit 2; }
done
if ((bash32)); then
  command -v docker >/dev/null || { echo "--bash32 needs docker" >&2; exit 2; }
fi

work=$(mktemp -d)
cid=""
cleanup() {
  [[ -n "$cid" ]] && docker rm -f "$cid" >/dev/null 2>&1
  if ((keep)); then echo "fixtures kept in $work"; else rm -rf "$work"; fi
}
trap cleanup EXIT

# ---- harness -------------------------------------------------------------------

pass=0 fail=0 skip=0
# Prefix that runs a hook; empty runs it through its own shebang.
HOOK_RUN=()

payload() { # <file>
  jq -cn --arg f "$1" '{
    session_id: "test-hooks", transcript_path: "/dev/null", cwd: "/",
    hook_event_name: "PostToolUse", tool_name: "Write",
    tool_input: {file_path: $f, content: ""},
    tool_response: {filePath: $f, success: true}}'
}

# invoke <hook> <payload>: sets rc, out (stdout) and ctx (the additionalContext).
invoke() {
  out=$(printf '%s' "$2" | ${HOOK_RUN[@]+"${HOOK_RUN[@]}"} "$H/$1" 2>"$work/stderr")
  rc=$?
  ctx=""
  [[ -z "$out" ]] && return 0
  ctx=$(printf '%s' "$out" | jq -er 'select(.hookSpecificOutput.hookEventName == "PostToolUse")
    | .hookSpecificOutput.additionalContext | strings' 2>/dev/null) ||
    ctx="<not a PostToolUse additionalContext reply> $out"
}

# fresh: clears the last invocation, for a check that does not invoke a hook.
fresh() { rc=- out="" ctx=""; : >"$work/stderr"; }

# expect <name> <what was expected> <command...>: the command passes or fails it.
expect() {
  local name=$1 want=$2
  shift 2
  if "$@"; then
    pass=$((pass + 1))
    printf '  ok    %s\n' "$name"
  else
    fail=$((fail + 1))
    printf '  FAIL  %s: expected %s\n' "$name" "$want"
    printf '        exit %s, stderr: %s\n' "$rc" "$(head -c 300 "$work/stderr")"
    printf '        reply: %s\n' "$(printf '%s' "$ctx" | head -c 800)"
  fi
}
skipped() { skip=$((skip + 1)); printf '  skip  %s (%s)\n' "$1" "$2"; }

is_silent() { [[ $rc -eq 0 && -z "$out" ]]; }
ctx_has() { [[ $rc -eq 0 ]] && printf '%s' "$ctx" | grep -qE -e "$1"; }
ctx_lacks() { ! printf '%s' "$ctx" | grep -qE -e "$1"; }

silent() { invoke "$1" "$(payload "$2")"; expect "$3" "exit 0 and no reply" is_silent; }
says() { invoke "$1" "$(payload "$2")"; expect "$3" "exit 0 and a reply matching /$4/" ctx_has "$4"; }
lacks() { expect "$1" "the reply not to match /$2/" ctx_lacks "$2"; }
same() { fresh; expect "$1" "$3 unchanged" cmp -s "$2" "$3"; }

# put <path> <content>: writes a fixture file, creating its directory.
put() { mkdir -p "$(dirname "$1")"; printf '%s\n' "$2" >"$1"; }

# reachable <dir> <bin>: a tool npx would find from <dir> without installing.
reachable() { (cd "$1" && npx --no-install "$2" --version >/dev/null 2>&1); }

# ---- fixtures ------------------------------------------------------------------

echo "installing ${TOOLS[*]}"
tools=$work/tools
put "$tools/package.json" '{ "name": "test-hooks-tools", "private": true }'
if ! (cd "$tools" && npm install --no-audit --no-fund --loglevel=error "${TOOLS[@]}" >"$work/npm.log" 2>&1); then
  cat "$work/npm.log" >&2
  exit 2
fi
link_tools() { ln -s "$tools/node_modules" "$1/node_modules"; }

# Secrets. The tokens are assembled from split literals, so this script holds
# none that a secret scanner would flag.
D=$work/secrets
put "$D/aws.ts" "export const id = \"AK""IAIOSFODNN7EXAMPLE\";"
put "$D/space dir/aws.ts" "export const id = \"AK""IAIOSFODNN7EXAMPLE\";"
put "$D/gh.ts" "export const t = \"gh""p_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789\";"
put "$D/slack.ts" "export const t = \"xo""xb-1234567890-abcdefghij\";"
put "$D/google.ts" "export const k = \"AI""zaSyA1234567890abcdefghijklmnopqrstuv\";"
put "$D/stripe.ts" "export const k = \"sk_""live_abcdefghijklmnopqrstuvwx\";"
put "$D/aws.env" "aws_secret_""access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
put "$D/id_rsa" "-----BEGIN RSA PRIVATE"" KEY-----"
put "$D/id_ed25519" "-----BEGIN OPENSSH PRIVATE"" KEY-----"
put "$D/clean.ts" 'export const c = 1;'
put "$D/generic.ts" 'export const api_key = "abc123secretvalue";'
put "$D/package-lock.json" "{ \"x\": \"AK""IAIOSFODNN7EXAMPLE\" }"
printf '\000\001\002AK''IAIOSFODNN7EXAMPLE\000\377' >"$D/blob.bin"

# No tool installed: every hook must stay silent and leave files alone.
N=$work/notools
put "$N/package.json" '{ "name": "notools", "private": true }'
put "$N/tsconfig.json" '{ "compilerOptions": { "strict": true, "noEmit": true }, "include": ["src"] }'
put "$N/biome.json" '{}'

# Prettier: an npm workspace whose ignore file sits at the root while the app
# has its own package.json, as in a monorepo.
P=$work/prettier-ws
put "$P/package.json" '{ "name": "pws", "private": true, "workspaces": ["apps/*"] }'
put "$P/.prettierrc.json" '{}'
put "$P/.prettierignore" 'apps/web/dist'
put "$P/apps/web/package.json" '{ "name": "web", "version": "0.0.0" }'
put "$P/apps/web/notes.txt" 'plain text'
link_tools "$P"
messy_ts='const  a = {b:1,c:2}
export function f( x:number ){return x*2+a.b}'
put "$work/seed/messy.ts" "$messy_ts"
put "$work/seed/messy.js" 'const  a = {b:1,c:2}
export function f( x ){return x*2+a.b}'
put "$work/seed/broken.ts" 'const = ;'

# Biome: recommended rules, one ignored folder, a nested package below the
# config.
B=$work/biome
put "$B/package.json" '{ "name": "bio", "private": true }'
put "$B/biome.json" '{
  "files": { "includes": ["**", "!ignored"] },
  "formatter": { "enabled": false },
  "linter": { "enabled": true, "rules": { "preset": "recommended" } }
}'
lint_error='export function f() {
  debugger;
  return 1;
}'
put "$B/src/err.ts" "$lint_error"
put "$B/ignored/err.ts" "$lint_error"
put "$B/nested/app/package.json" '{ "name": "nested-app", "private": true }'
put "$B/nested/app/src/err.ts" "$lint_error"
put "$B/src/warn.ts" 'function g() {
  const unused = 1;
  return 2;
}
export { g };'
put "$B/src/ok.ts" 'export const ok = 1;'
put "$B/src/notes.md" '# notes'
link_tools "$B"

# TypeScript, a single project. b.ts and vendor/src/a/x.ts are red so that
# scoping to the edited file is tested.
tsconfig='{
  "compilerOptions": {
    "strict": true, "noEmit": true, "skipLibCheck": true,
    "target": "ES2022", "module": "ESNext", "moduleResolution": "Bundler"
  },
  "include": ["src"]
}'
T=$work/ts
put "$T/package.json" '{ "name": "tsp", "private": true }'
put "$T/tsconfig.json" "$tsconfig"
put "$T/src/a.ts" 'export const a: number = "x";'
put "$T/src/b.ts" 'export const b: string = 1;'
put "$T/src/clean.ts" 'export const c = 1;'
put "$T/src/a/x.ts" 'export const x = 1;'
put "$T/src/vendor/src/a/x.ts" 'export const y: number = "x";'
put "$T/src/relimport.ts" 'import { x } from "./nope";
export const y = x;'
put "$T/src/bare.ts" 'import { x } from "@acme/missing";
export const y = x;'
put "$T/src/elab.ts" 'type A = { x: { y: number } };
const v: { x: { y: string } } = { x: { y: "s" } };
export const a: A = v;'
put "$T/src/notes.js" 'export const j = 1;'
link_tools "$T"

# TypeScript in a pnpm workspace. @acme/stale resolves (through "paths") but
# lacks the export the app imports, like a sibling package built before it.
W=$work/ts-ws
put "$W/pnpm-workspace.yaml" 'packages:
  - packages/*'
put "$W/package.json" '{ "name": "root", "private": true }'
A=$W/packages/app
put "$A/package.json" '{ "name": "app", "private": true }'
put "$A/tsconfig.json" '{
  "compilerOptions": {
    "strict": true, "noEmit": true, "skipLibCheck": true,
    "target": "ES2022", "module": "ESNext", "moduleResolution": "Bundler",
    "paths": { "@acme/stale": ["./stale/index.d.ts"] }
  },
  "include": ["src"]
}'
put "$A/stale/index.d.ts" 'export declare const oldThing: number;'
put "$A/src/bare.ts" 'import { thing } from "@acme/shared";
export const t = thing;'
put "$A/src/stale.ts" 'import { newThing } from "@acme/stale";
export const t = newThing;'
put "$A/src/rel.ts" 'import { x } from "./nope";
export const y = x;'
link_tools "$A"

# TypeScript, solution style: create-vite's layout, which react-frontend-scaffold
# keeps. tsconfig.json lists no files, only references.
V=$work/vite
put "$V/package.json" '{ "name": "vite-app", "private": true, "type": "module" }'
put "$V/tsconfig.json" '{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}'
put "$V/tsconfig.app.json" '{
  "compilerOptions": {
    "tsBuildInfoFile": "./.tmp/tsconfig.app.tsbuildinfo",
    "target": "es2023",
    "module": "esnext",
    "skipLibCheck": true,

    /* Bundler mode */
    "moduleResolution": "bundler",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}'
put "$V/tsconfig.node.json" '{
  "compilerOptions": {
    "tsBuildInfoFile": "./.tmp/tsconfig.node.tsbuildinfo",
    "target": "es2023",
    "module": "esnext",
    "moduleResolution": "bundler",
    "noEmit": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}'
put "$V/vite.config.ts" 'export default {};'
put "$V/src/main.tsx" 'export const broken: number = "not a number";'
put "$V/src/ok.ts" 'export const ok = 1;'
link_tools "$V"

# TypeScript, composite project references: b builds on a. "pretty": true
# checks that the hook still gets one line per diagnostic.
C=$work/composite
put "$C/package.json" '{ "name": "composite", "private": true }'
put "$C/tsconfig.json" '{ "files": [], "references": [{ "path": "./packages/a" }, { "path": "./packages/b" }] }'
composite_opts='"composite": true, "declaration": true, "outDir": "dist", "rootDir": "src",
    "strict": true, "pretty": true,
    "target": "ES2022", "module": "ESNext", "moduleResolution": "Bundler"'
put "$C/packages/a/tsconfig.json" "{ \"compilerOptions\": { $composite_opts }, \"include\": [\"src\"] }"
put "$C/packages/b/tsconfig.json" "{ \"compilerOptions\": { $composite_opts }, \"include\": [\"src\"], \"references\": [{ \"path\": \"../a\" }] }"
put "$C/packages/a/src/index.ts" 'export const one: number = 1;'
put "$C/packages/b/src/index.ts" 'import { one } from "../../a/src/index";
export const two: number = one + 1;
export const bad: number = "x";'
link_tools "$C"

# ---- cases ---------------------------------------------------------------------

secrets_cases() {
  local h=secrets-scan-on-change.sh
  says $h "$D/aws.ts" "AWS access key id flagged" "AWS access key id"
  lacks "only the AWS rule in that reply" "GitHub|Slack|Google|Stripe|Private"
  says $h "$D/aws.env" "AWS secret access key flagged" "AWS secret access key"
  says $h "$D/gh.ts" "GitHub token flagged" "GitHub personal access token"
  says $h "$D/slack.ts" "Slack token flagged" "Slack bot token"
  says $h "$D/google.ts" "Google API key flagged" "Google API key"
  says $h "$D/stripe.ts" "Stripe live key flagged" "Stripe live secret key"
  says $h "$D/id_rsa" "RSA private key block flagged" "Private key block"
  says $h "$D/id_ed25519" "OpenSSH private key block flagged" "Private key block"
  says $h "$D/space dir/aws.ts" "path with a space" "AWS access key id"
  silent $h "$D/clean.ts" "clean file silent"
  silent $h "$D/generic.ts" "generic api_key= not flagged"
  silent $h "$D/package-lock.json" "lockfile skipped"
  silent $h "$D/blob.bin" "binary skipped"
  silent $h "$D/missing.ts" "missing file silent"
  invoke $h '{"hook_event_name":"PostToolUse","tool_name":"Bash","tool_input":{"command":"ls"}}'
  expect "payload without a file_path silent" "exit 0 and no reply" is_silent
  invoke $h 'not json'
  expect "malformed payload silent" "exit 0 and no reply" is_silent
}

echo "== secrets-scan"
secrets_cases

echo "== prettier"
h=prettier-on-change.sh
mkdir -p "$P/apps/web/src" "$P/apps/web/dist"
cp "$work/seed/messy.ts" "$P/apps/web/src/messy.ts"
cp "$work/seed/messy.js" "$P/apps/web/dist/out.js"
cp "$work/seed/broken.ts" "$P/apps/web/src/broken.ts"
says $h "$P/apps/web/src/messy.ts" "unformatted file rewritten and reported" "Prettier reformatted"
fresh
expect "rewritten file passes prettier --check" "a clean check" \
  bash -c 'cd "$1" && npx --no-install prettier --check apps/web/src/messy.ts >/dev/null 2>&1' _ "$P"
silent $h "$P/apps/web/src/messy.ts" "formatted file silent"
silent $h "$P/apps/web/dist/out.js" "root .prettierignore honoured for a file in an app"
same "ignored file left alone" "$work/seed/messy.js" "$P/apps/web/dist/out.js"
silent $h "$P/apps/web/src/broken.ts" "syntax error silent"
same "file with a syntax error left alone" "$work/seed/broken.ts" "$P/apps/web/src/broken.ts"
silent $h "$P/apps/web/notes.txt" "extension Prettier does not own silent"
if reachable "$N" prettier; then
  skipped "no Prettier installed" "a global prettier is reachable from $N"
else
  put "$N/src/messy.ts" "$messy_ts"
  silent $h "$N/src/messy.ts" "no Prettier installed: silent"
  same "no Prettier installed: file left alone" "$work/seed/messy.ts" "$N/src/messy.ts"
fi

echo "== biome"
h=biome-on-change.sh
says $h "$B/src/err.ts" "error-level finding reported" "Biome reports 1 error-level"
says $h "$B/src/err.ts" "reply names the rule" "noDebugger"
lacks "no npm noise in the reply" "^npm (warn|WARN|notice)"
silent $h "$B/src/warn.ts" "warnings only: silent"
silent $h "$B/src/ok.ts" "clean file silent"
silent $h "$B/ignored/err.ts" "file biome.json ignores silent"
says $h "$B/nested/app/src/err.ts" "root biome.json found from a nested package" "Biome reports"
silent $h "$B/src/notes.md" "extension Biome does not lint silent"
if reachable "$N" biome; then
  skipped "no Biome installed" "a global biome is reachable from $N"
else
  put "$N/src/err.ts" "$lint_error"
  silent $h "$N/src/err.ts" "no Biome installed: silent"
fi

echo "== ts-typecheck"
h=ts-typecheck-on-change.sh
says $h "$T/src/a.ts" "type error in the edited file reported" "TypeScript errors in src/a\\.ts"
says $h "$T/src/a.ts" "reply carries the diagnostic" "src/a\\.ts\\(1,14\\): error TS2322"
lacks "other files' errors left out" "src/b\\.ts|vendor"
says $h "$T/src/elab.ts" "a diagnostic keeps its indented detail lines" "incompatible between these types"
silent $h "$T/src/clean.ts" "clean file silent while others are red"
silent $h "$T/src/a/x.ts" "src/a/x.ts not blamed for src/vendor/src/a/x.ts"
says $h "$T/src/relimport.ts" "relative import typo blocks" "Fix these type errors"
says $h "$T/src/bare.ts" "bare import outside a workspace blocks" "Fix these type errors"
silent $h "$T/src/notes.js" "non-TypeScript file silent"
says $h "$A/src/bare.ts" "workspace: unresolved package import is an advisory" "Heads-up \\(non-blocking\\)"
lacks "the advisory does not say fix" "Fix these type errors"
says $h "$A/src/stale.ts" "workspace: missing export (TS2305) is an advisory" "Heads-up \\(non-blocking\\)"
says $h "$A/src/rel.ts" "workspace: relative import typo still blocks" "Fix these type errors"
says $h "$V/src/main.tsx" "solution-style tsconfig (Vite): error reported" "TypeScript errors in src/main\\.tsx"
silent $h "$V/src/ok.ts" "solution-style tsconfig: clean file silent"
fresh
expect "solution-style tsconfig: nothing emitted beside the sources" "no .js in src/" \
  test -z "$(find "$V/src" -name '*.js')"
says $h "$C/packages/b/src/index.ts" "composite references: error reported" "TypeScript errors in packages/b/src/index\\.ts"
lacks "composite references: no TS6310 from a noEmit build" "TS6310"
silent $h "$C/packages/a/src/index.ts" "composite references: clean package silent"
if reachable "$N" tsc; then
  skipped "no TypeScript installed" "a global tsc is reachable from $N"
else
  put "$N/src/err.ts" 'export const n: number = "x";'
  silent $h "$N/src/err.ts" "no TypeScript installed: silent"
fi

# Static guard for macOS's bash 3.2, which runs the hooks there through their
# `#!/usr/bin/env bash` shebang unless a newer bash comes first on PATH.
# --bash32 runs the secrets scan under a real one.
echo "== bash 3.2 syntax"
bash4='(declare|local|typeset)[[:space:]]+-[A-Za-z]*[Agnlu]|(^|[^A-Za-z_])(mapfile|readarray|coproc)([^A-Za-z_]|$)'
bash4+='|\$\{[A-Za-z_][A-Za-z0-9_]*(\[[^]]*\])?(,,?|\^\^?|@[QEPAa])\}|\|&|&>>|\[\[[[:space:]]+-v[[:space:]]'
for f in "$H"/*.sh; do
  fresh
  ctx=$(grep -nE -e "$bash4" "$f" | grep -vE '^[0-9]+:[[:space:]]*#')
  expect "$(basename "$f") uses no bash 4 syntax" "no match for the bash 4 patterns" test -z "$ctx"
done

if ((bash32)); then
  echo "== secrets-scan under bash 3.2 ($BASH32_IMAGE)"
  if cid=$(docker run -d -v "$H:$H:ro" -v "$work:$work:ro" "$BASH32_IMAGE" sleep 900) &&
    docker exec "$cid" apk add --no-cache -q jq file >"$work/apk.log" 2>&1; then
    printf '  %s\n' "$(docker exec "$cid" bash --version | head -1)"
    for f in "$H"/*.sh; do
      fresh
      expect "$(basename "$f") parses" "bash -n to pass" docker exec "$cid" bash -n "$f"
    done
    HOOK_RUN=(docker exec -i "$cid" bash)
    secrets_cases
    HOOK_RUN=()
  else
    cat "$work/apk.log" >&2 2>/dev/null
    fail=$((fail + 1))
    echo "  FAIL  could not start $BASH32_IMAGE with jq and file"
  fi
fi

echo
echo "hooks tested: $H"
echo "passed $pass, failed $fail, skipped $skip"
((fail == 0))
