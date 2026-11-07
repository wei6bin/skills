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
NuGet registries: the justfile grants them (`eval_domains`), since a run's Bash
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

- `AskUserQuestion` is not offered in an eval run, so `line` would end its turn
  at the first checkpoint, and `refine` would wait on its first round. The
  line cases' `append_system_prompt` stands in for the developer: it
  pre-answers the plan folder, the slice list and the exit action (merge
  locally), and tells the session to take its own recommendation everywhere
  else. `refine-three-roles` does the same for its three roles.
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
