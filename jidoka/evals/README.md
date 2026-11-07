# jidoka evals

The end-to-end verifier for the `line` and `refine` workflows, run by
`claude plugin eval` inside a container (`Dockerfile` here: Claude Code,
bubblewrap, git, curl, Python, Node 22, the .NET SDK). From the repo root:

```bash
just eval-claude                    # build the image if needed, run every case
just eval-claude --case line-greenfield-scaffold   # one case
just eval-claude --keep-temp        # keep the run directory and its trace
just HOST=1 eval-claude             # run on the host instead
```

The container needs a credential, kept out of the repo in
`~/.config/jidoka/eval.env` (override with `just EVAL_ENV=<file> eval-claude`):

```bash
claude setup-token    # in your own terminal; prints a long-lived token
mkdir -p ~/.config/jidoka
touch ~/.config/jidoka/eval.env && chmod 600 ~/.config/jidoka/eval.env
# then add one line with your editor: CLAUDE_CODE_OAUTH_TOKEN=<token>
```

These lines run in bash, zsh and fish, and an editor keeps the token out of
your shell history.

`ANTHROPIC_API_KEY=...` in the same file bills the API instead of the
subscription. Behind a TLS-inspecting proxy, `EXTRA_CA` (default
`$NODE_EXTRA_CA_CERTS`) passes its CA to the image build and the run.

Results land in `jidoka/evals/results/<timestamp>/` (git-ignored):
`aggregate-result.json` and a self-contained `report.html`. Container runs keep
the report local; a `just HOST=1 eval-claude` run also publishes it to claude.ai
as a private artifact unless you pass `--no-publish`.

## line-minimal-story

The smallest story that still crosses all ten phases. `scaffold.sh` turns the
empty run workspace into a one-commit git repo of `fixture/` (an in-memory
notes API on `node:http` with a `node:test` suite, no dependencies, no remote).
The commit also holds `docs/stories/usr-001-delete-note.md`: USR-001, "Delete
a note", as a signed, `jidoka-ready` agreement. It has two ACs on one backend
endpoint (so it classifies as `one-layer`) and `Exit: merge`. The scaffold
signs it with the refine skill's `agreement.py`, so its hashes are real. The
prompt types `/jidoka:line` on that file, and nothing stands in for a
developer: the agreement holds every decision, and a question in the run is a
failure.

The graders check three things:

- **Dispatches**: the claim (`agreement.py claim`), every phase's agent or
  skill (context builder, explorer, worktree, architect, plan reviewer,
  backend implementer, simplify, code and security reviewers, context updater,
  walker, raise-pr), no frontend implementer, all in the line's order.
- **End state on `main`**, under `docs/new-feature/usr-001-delete-a-note/` (the
  slug the script derives from the title):
  - `story.md` carrying its hash;
  - the plan documents `00`-`07`, with an `ALL_GREEN` walkthrough and a
    ledger with nothing pending;
  - `09-decisions.md`;
  - `10-summary.md`, with a row per AC.

  Beyond the plan folder: the endpoint and tests citing `AC-1` and `AC-2`,
  the project context and product knowledge, the story file at
  `Status: jidoka-done`, `BACKLOG.md` closed with a commit, and no worktree
  left. These paths exist on `main` only after the local merge.
- **Judged**: the merged endpoint and tests meet both ACs, and the run ended
  finished rather than on a question.

Not covered: the frontend half, whole-story integration and a Playwright
walkthrough (the fixture has no UI), opening a PR on a real host, Azure
DevOps, and the refactor tier.

## line-greenfield-scaffold

The new-project branch. `scaffold.sh` leaves a git repository on `main` with
an identity, no remote and no source code. Its one commit is TN-000, "Set up
TeamNotes": a signed setup agreement with no ACs and a `Stack:` line holding
the Dev Lead's answers (both layers, the development password stub, the
Neutral look, merge locally). The prompt types `/jidoka:line` on it, and
`project-setup` reads those answers instead of asking. The run scaffolds a
real .NET + React skeleton, so its Bash needs the npm and NuGet registries.
The justfile grants them (`eval_domains`), since a run's Bash has no network
beyond the domains the operator grants and a case cannot grant any itself.

The graders check that the `project-setup` skill ran before it dispatched the
`project-scaffolder` agent, and that the agent's own steps happened in order
(the worktree, both implementers with scope `project scaffold`, the context
build);
that no story phase ran (no architect, no `raise-pr`, no plan folder); the end
state on `main` (solution, API with the session ticket store, CSRF middleware
and an `InitialCreate` migration, the pinned dev port, the frontend's stack,
gate scripts, dev proxy and CSRF-sending client, both test suites, the project
context, a README naming the dev login, no worktree); and, judged, the sign-in
page and a final message that reports the gates and the proxy smoke green. The
setup story ends at `Status: jidoka-done`.

No grader runs a command, so the gates themselves are not re-run here; the
orchestrator's own evidence check and smoke are what the last-message grader
reads. To re-run them independently, pass `--keep-temp` and run
`dotnet test` and `npm test` in the kept workspace.

Not covered: a story on top of the skeleton, a folder that is not a git
repository, a repository with a remote, and adding one layer to an existing
repository.

The run's workspace root holds placeholder dotfiles the agent cannot read
(`.gitmodules`, `.gitconfig` and others). MSBuild's source-control query reads
`.gitmodules`, so `dotnet build` fails in the root checkout though it passes in
the worktree; the case's system prompt says to pass
`-p:EnableSourceControlManagerQueries=false` there. Real repositories have no
such files.

## line-not-ready and line-changed-after-signoff

The claim's two refusals, a few minutes each. Both start from the
line-minimal-story repo (each scaffold calls that one) and make one commit:

- `line-not-ready` puts USR-001 back to `Status: draft`, a story that never
  went through refinement.
- `line-changed-after-signoff` edits AC-1 after the three sign-offs, as an
  edit made straight in the tracker would, so its hash no longer matches.

The graders check that the claim ran and that nothing else did:

- no agent dispatched;
- no worktree and no story branch;
- the story file untouched.

Judged, the last message names the reason and points at `/jidoka:refine`.

## line-base-broken

The base check before the claim, a few minutes. The scaffold starts from the
line-minimal-story repo, whose USR-001 is signed and `jidoka-ready`, then
commits a regression on `main`: `GET /notes/:id` answers an unknown id with
error code `not_found` where the suite expects `note_not_found`. The base
fails its own tests in the error the story's AC-2 uses, so the line must stop
before it claims anything.

The graders check that the base was tested and that nothing else happened:

- `git-worktrees` invoked, and `agreement.py claim` never run;
- no agent dispatched;
- no worktree left, no story branch, no `andon.md`;
- the story file still at `Status: jidoka-ready`.

Judged, the last message names `main`, the failing test, and that the story
builds once `main` is fixed.

## line-andon-stop

An andon stop. The scaffold adds `Stop also on: any change to the note
store` to USR-001's autonomy policy and has all three roles sign again.
Deleting a note needs such a change, since the store has no delete, so the
line must stop before implementing.

The graders check the stop:

- no backend implementer dispatched;
- `story.md`, `andon.md` (about the store) and an open row in the ledger's
  `## Andon` table, all on the branch, in the kept worktree
  `.worktrees/usr-001-delete-a-note/`;
- the branch's copy of the story file at `Status: jidoka-blocked`;
- the store untouched on the branch and on `main`.

Judged, the last message names the question and its owner, and says to answer
it with `/jidoka:refine`.

Not covered: the resumed run. An eval run is one session, so answering the
question and running the line again would need a second one;
`scripts/test_agreement.py` covers `compare`, which the resume rests on.

## refine-three-roles

A live refinement session. `scaffold.sh` builds the line-minimal-story repo
(it calls that case's scaffold) and adds a second commit with USR-002, "Edit a
note", as two vague lines in `docs/stories/usr-002-edit-note.md`: a Markdown
file standing in for the tracker. The prompt types `/jidoka:refine` on that
file. The case's system prompt plays the three people in the room: the BA
(which fields change, the title rule), the Dev Lead (PATCH, the reply, no
remote) and the QE (evidence per AC, the 200-character boundary). Anything
else takes the session's own recommendation. The error envelope, the code for
an unknown note and the status for an invalid title are in the code, not in
any position, so the session has to find them.

The graders check that the skill announced itself and tagged its questions by
role (the method went to the Dev Lead, the evidence to the QE), and that
`agreement.py` did the mechanical parts (check, three `sign` calls, `--set
jidoka-ready`). Then the end state of the file: `Status: jidoka-ready`, the
fixed sections, three live sign-offs at one hash, permanent AC ids,
`Exit: merge`, no open HIGH or MEDIUM question, no file paths. Judged: the
agreement settles every planted gap, and the last message reports the story
ready for `/jidoka:line`.

Not covered: Azure DevOps (`pull`, `push` and the tag, which
`scripts/test_agreement.py` runs against a fake `az`), `--role` and `--solo`
passes, a change after sign-off, and confirming a line run's decisions.

## Running it headless

- `AskUserQuestion` is not offered in an eval run. The line asks nothing, so
  the line cases have no stand-in: their stories are signed agreements. Only
  `refine-three-roles` needs one, and its `append_system_prompt` plays the
  three people in the room.
- `jidoka/` has no `plugin.json`, so the case sets `plugins: ["../.."]` to
  load it.
- A Bash-granting eval refuses to start while the host's Docker credential
  store (`~/.docker`, or `DOCKER_CONFIG`) holds a symlink, because the Bash
  sandbox cannot reliably exclude it. Docker Desktop's "User" CLI install
  mode links its tools into `~/.docker`, which is why the eval runs in a
  container by default.
- In the container the eval's sandbox is bubblewrap, which needs user
  namespaces and a fresh `/proc`; Docker's default seccomp profile and masked
  paths block both, so the run uses `seccomp=unconfined` and
  `systempaths=unconfined`. The repo is mounted read-only; only `results/` is
  writable.
- The eval makes each run's workspace under `TMPDIR`, and its Bash sandbox
  denies writes to `/tmp` over its own grant to that workspace (Claude Code
  2.1.319). A workspace under `/tmp` leaves the run unable to write anything,
  and the line stops at its claim. So the image sets `TMPDIR=/eval-tmp`, and
  `HOST=1` sets it to `~/.cache/jidoka/eval-tmp`. On the host the sandbox
  also needs `bwrap` and `socat` (`sudo apt install bubblewrap socat`).
- On the host the sandbox reads nothing in your home but the `PATH`
  directories, and its network proxy wants the credentials in its URL. A tool
  that links elsewhere in your home is unreadable, so the next one on `PATH`
  runs instead: nvm's `npm` links into `lib/node_modules`, and Ubuntu's npm
  9.2, which never sends proxy credentials, gets `407 Proxy Authentication
  Required`. `line-greenfield-scaffold` needs npm, so run it in the container.
- On a WSL host the container shares WSL's kernel, so the eval takes it for
  WSL and refuses a Bash grant unless `/proc/mounts` shows a Windows drive it
  can put out of the sandbox's reach. The container mounts none, so
  `eval-claude` adds an empty tmpfs at `/mnt/c` whose source reads `C:`, and
  the sandbox denies it like a drive.
- One run is a full workflow: up to an hour (the case's `timeout_seconds`) and
  a few dollars across the orchestrator and nine subagents. The two refusal
  cases take minutes.
