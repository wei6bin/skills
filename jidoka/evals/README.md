# jidoka evals

The end-to-end verifier for the `line` workflow, run by `claude plugin eval`
inside a container (`Dockerfile` here: Claude Code, bubblewrap, git, curl,
Node 22, the .NET SDK). From the repo root:

```bash
make eval-claude                      # build the image if needed, run every case
make eval-claude ARGS="--case line-greenfield-scaffold"   # one case
make eval-claude ARGS="--keep-temp"   # keep the run directory and its trace
make eval-claude HOST=1               # run on the host instead
```

The container needs a credential, kept out of the repo in
`~/.config/jidoka/eval.env` (override with `EVAL_ENV=`):

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
the report local; a `HOST=1` run also publishes it to claude.ai as a private
artifact unless `ARGS` has `--no-publish`.

## line-minimal-story

The smallest story that still crosses all ten phases. `scaffold.sh` turns the
empty run workspace into a one-commit git repo of `fixture/` (an in-memory
notes API on `node:http` with a `node:test` suite, no dependencies, no remote).
The prompt types `/jidoka:line` with USR-001, "Delete a note", two acceptance
criteria on one backend endpoint, so the story classifies as `one-layer`.

The graders check three things:

- **Dispatches**: every phase's agent or skill was called (context builder,
  explorer, worktree, architect, plan reviewer, backend implementer, simplify,
  code and security reviewers, context updater, walker, raise-pr), no frontend
  implementer was, and they ran in the line's order.
- **End state on `main`**: the plan documents `00`-`07` under
  `docs/new-feature/usr-001-delete-note/` with an `ALL_GREEN` walkthrough and
  a ledger with nothing pending, the endpoint and its tests, the project
  context and product knowledge, `BACKLOG.md` closed with a commit, no
  worktree left. These paths exist on `main` only after the local merge.
- **Judged**: the merged endpoint and tests meet both ACs, and the run ended
  finished rather than on a question.

Not covered: the frontend half, whole-story integration and a Playwright
walkthrough (the fixture has no UI), opening a PR on a real host, and the
refactor tier.

## line-greenfield-scaffold

The new-project branch. `scaffold.sh` leaves an empty git repository on `main`
with an identity and no commits, and the prompt asks `/jidoka:line` to set up
a project with no story. The case's system prompt answers the setup questions
(both layers, the development password stub, the Neutral look, merge locally).
The run scaffolds a real .NET + React skeleton, so its Bash needs the npm and
NuGet registries: the Makefile grants them (`EVAL_DOMAINS`), since a run's Bash
has no network beyond the domains the operator grants and a case cannot grant
any itself.

The graders check that the `project-setup` skill ran before it dispatched the
`project-scaffolder` agent, and that the agent's own steps happened in order
(the worktree, both implementers with scope `project scaffold`, the context
build);
that no story phase ran (no architect, no `raise-pr`, no plan folder); the end
state on `main` (solution, API with the session ticket store, CSRF middleware
and an `InitialCreate` migration, the pinned dev port, the frontend's stack,
gate scripts, dev proxy and CSRF-sending client, both test suites, the project
context, a README naming the dev login, no worktree); and, judged, the sign-in
page and a final message that reports the gates and the proxy smoke green.

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

## Running it headless

- `AskUserQuestion` is not offered in an eval run, so `line` would end its turn
  at the first checkpoint. The case's `append_system_prompt` stands in for the
  developer: it pre-answers the plan folder, the slice list and the exit action
  (merge locally), and tells the session to take its own recommendation
  everywhere else.
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
- One run is a full workflow: up to an hour (the case's `timeout_seconds`) and
  a few dollars across the orchestrator and nine subagents.
