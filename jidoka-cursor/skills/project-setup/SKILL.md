---
name: project-setup
description: Internal - offers the stack options for a new project, freezes the skeleton contract and dispatches project-scaffolder to build it. Invoked by the orchestrator when the repo has no source code or a new project is asked for.
user-invocable: false
allowed-tools: Read, Grep, Glob, Bash, AskUserQuestion
---

# Project Setup

**Announce at start:** "I'm using the project-setup skill to set up the project
before any story runs."

You take the decisions a new project needs from the user, and hand the build to
`project-scaffolder`. The decisions stay here because only the orchestrator can
ask the user. The build goes to the agent because its trail (two implementers'
Return Reports, every gate, the end-to-end smoke, the project-context write-up)
would otherwise fill the orchestrator's context, which may still have a story's
ten phases ahead. What comes back is one short report.

## Stack catalog

The only place a stack is named. Adding a stack is one row here plus its
scaffold skill (`src/skills/<name>/` in the plugin repo); the questions below
are built from this table, and the dispatch carries the chosen rows to
`project-scaffolder`, which never reads the table itself.

| Layer | Option | Scaffold skill | Root | Verify (run from the root) |
| --- | --- | --- | --- | --- |
| Backend | .NET: ASP.NET Core Minimal API, EF Core + SQLite, cookie sessions | `aspnet-backend-scaffold` | `backend/` | `dotnet build`, `dotnet test` |
| Frontend | React: TypeScript, Vite, Ant Design, TanStack Query | `react-frontend-scaffold` | `frontend/` | `npm run typecheck`, `npm run lint`, `npm run format:check`, `npm test`, `npm run build` |

In a sandboxed shell, `dotnet build` and `dotnet test` can die with
`SocketException (13): Permission denied` from `NamedPipeServerStream`:
MSBuild's worker nodes talk over a socket the sandbox blocks. Add
`-m:1 -nodeReuse:false` there; it builds in one process.

## Step 1 - Confirm there is something to scaffold

The orchestrator invokes you when either holds:

- **No source code.** This prints nothing:

  ```bash
  find . \( -path ./.git -o -path ./.worktrees -o -path ./node_modules -o -path ./docs \) -prune -o -type f \( -name package.json -o -name '*.csproj' -o -name '*.sln' -o -name '*.slnx' -o -name pyproject.toml -o -name requirements.txt -o -name go.mod -o -name pom.xml -o -name 'build.gradle*' -o -name Cargo.toml -o -name '*.cs' -o -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' -o -name '*.py' -o -name '*.go' -o -name '*.java' -o -name '*.kt' -o -name '*.rs' \) -print -quit
  ```

  Docs, a backlog, a README and a `.gitignore` are not code.

- **The user asked for a new project or a new layer** ("set up a new project",
  "scaffold a React frontend for this API"), whatever the tree holds.

Never scaffold a layer that already exists. Judge each layer from its manifests
(a `*.csproj` or other server project is a backend, a `package.json` depending
on `react` is a frontend) and offer only the missing ones. If a layer's root
directory from the catalog already exists and is not empty, ask for another
root rather than writing into it. With nothing missing, say so and return.

## Step 2 - Ask once

Every question here is independent, so ask them in **one** `AskUserQuestion`
call, each with its recommended answer first. Take the project name from the
request when it names one, else from the folder (`clinic-portal` gives
`ClinicPortal`: `ClinicPortalApi` for .NET, `clinic-portal-web` for npm), and
put it in the first question's text, so the user can rename it under Other.

1. **What to set up.** Build the options from the catalog, leaving out layers
   that already exist. While every layer has one option, ask a single question:
   "Backend + frontend: {backend} + {frontend}", "Backend only: {backend}",
   "Frontend only: {frontend}". Once a layer has two or more options, ask one
   question per layer instead, listing its options plus "None". Recommend from
   the story when there is one (a story with a UI needs the frontend);
   otherwise recommend both.
2. **How passwords are verified** - only when a backend is offered. The
   backend's default auth needs this one input and must not invent it:
   "Development stub now, decide later" (recommended: a validator registered
   only in Development that accepts the seeded dev user; outside Development
   startup fails until a real one is registered), "Local password hashes"
   (ASP.NET Core `PasswordHasher` with a hash column on the user), "AD / LDAP
   bind".
3. **Look** - only when a frontend is offered: "Neutral Enterprise"
   (recommended), "Dense Data" or "Friendly SaaS", the presets in
   `react-frontend-scaffold`'s `antd-app-setup.md`. A brand colour given under
   Other becomes the seed `colorPrimary` on the Neutral preset.
4. **Git** - only when there is a choice to make. Not a repository:
   "Initialise git on `main` and commit what is here" (recommended) or
   "Initialise git and leave the existing files untracked". A repository with a
   remote: "Merge the skeleton into {base} locally" (recommended) or "Leave it
   on its branch; I'll open the PR". A local repository with no remote merges
   without asking.

If an answer names a stack the catalog lacks, say it has no scaffold yet and
offer to stop or to continue with no scaffold; never improvise a stack.

## Step 3 - Freeze the skeleton contract

The two halves are built concurrently and never see each other, so settle
everything they must agree on now, as Phase 4 freezes a slice's contract. Fill
this in; the dispatch carries it **verbatim**, and the scaffolder hands it to
both halves unchanged:

```text
Skeleton contract - {Name}
Layers: {backend + frontend | backend | frontend}
Backend root: backend/ ({Name}Api.slnx, {Name}Api/, {Name}Api.Tests/)
Frontend root: frontend/ (npm package {name}-web)
Backend dev URL: http://localhost:5080 (the http profile in launchSettings.json)
Frontend dev URL: http://localhost:5173 (strictPort)
API path: the SPA calls /api/...; the Vite dev proxy forwards /api to the
  backend dev URL and strips the prefix, so backend routes stay at the root
  (/auth/login). Production hosting must map /api the same way.
CSRF header: X-App-Client: 1 on every POST, PUT, PATCH and DELETE
Auth: POST /auth/login {username, password} -> 200 {user} | 401 or 503
  problem+json with errorCode; GET /auth/me -> 200 UserSummary | 401;
  POST /auth/logout -> 204. UserSummary = {id, username, displayName, role}
Errors: RFC 9110 problem details; validation errors keyed by C# property name
Credentials: {dev-stub | local-hash | ldap}
Dev login: seeded active user "dev" (display name "Dev User", role "User");
  password from DevAuth:Password in appsettings.Development.json, a throwaway
  local value. Development always signs in this way: dev-stub checks that
  value, local-hash seeds the dev user's hash from it, ldap registers the LDAP
  validator outside Development and the stub inside it.
Schema: EF Core migrations from day one (dotnet-ef pinned in a local tool
  manifest, an InitialCreate migration, Database.Migrate() in Development)
Look: {neutral | dense | friendly | neutral + colorPrimary #hex}
```

Frontend only, against a backend that already exists: fill the dev URL, API
path, CSRF header and Auth lines from that backend's code, or write
`Auth: none` when it has none (the shell then renders without a sign-in
route); the frontend matches what is there. Backend only: drop the frontend
lines.

## Step 4 - Dispatch the scaffolder

Dispatch `subagent_type: "project-scaffolder"` with:

- the repo root, as an absolute path;
- the Git answer from Step 2 ("no remote, merge locally" when there was no
  question to ask);
- the skeleton contract, verbatim;
- one stack row per layer being set up, copied from the catalog: layer,
  scaffold skill, root, Verify commands.

It creates the repository and worktree, has `impl-backend` and `impl-frontend`
build the halves in parallel, checks their work, smokes the halves together,
builds `docs/project_context/` and the README, lands the skeleton, and returns
a Return Report of eight short sections. Wait for that report before Step 5.

If it returns without one (it stopped while a half was still running, say),
do not start over. Wait until `git -C {worktree} log` on `project-skeleton`
shows every layer's final `chore({layer}): scaffold` commit, then re-dispatch
`project-scaffolder` once with the same inputs, the worktree path, and
"resume: the halves are built; start at the evidence check".

## Step 5 - Check the result

Never accept the report on trust, but check it cheaply; the scaffolder already
re-ran every gate, and this must not refill your context with their output:

1. **Landed where it says.** Merged: `git log -1 --format=%h {base}` shows the
   reported commit, and `git worktree list` no longer lists
   `project-skeleton`. Left on its branch: the branch exists with that commit.
2. **The gates still pass there.** From each layer's root on the base checkout
   (or in the worktree, if the skeleton was left on its branch), install what
   the gates need (`npm ci`; `dotnet test` restores by itself) and run each
   Verify command with its output discarded, printing only
   `ok {command}` or `FAIL {command}`. On a FAIL, re-run that one command to
   see its tail.
3. **Every report section is there**, and the smoke section shows only `ok`
   lines for a full-stack skeleton.

Anything that does not hold: re-dispatch `project-scaffolder` with the
discrepancy quoted verbatim, or fix it yourself and note the takeover.

## Step 6 - Report

Relay the scaffolder's report to the user, trimmed to what they act on:

```text
Project set up: {Name} ({layers}) - merged into {base} at {sha} | on branch project-skeleton
  Backend   {option}   {N} tests passing   ({root})
  Frontend  {option}   {N} tests passing   ({root})
  Skeleton smoke (through the dev proxy): me 401 -> login 200 -> me 200 -> logout without CSRF 403 -> logout 204 -> me 401
  Context: docs/project_context/ ({N} files)
Run: {the README's start commands}
Dev login: dev / DevAuth:Password in {path to appsettings.Development.json}
Decide before production: {from the report}
Flagged: {from the report, or none}
```

Return control. The orchestrator stops here when the request was only the
setup, or when the skeleton was left on its branch (a story needs it on its
base); otherwise it carries on with the story on top of the skeleton.
