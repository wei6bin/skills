---
name: line
description: Builds one jidoka-ready story to a PR, unattended - claims the story's signed agreement from /jidoka:refine, explores the codebase in parallel, designs and reviews the plan, implements slice by slice with one whole-story QA round, walks the test plan with Playwright, and opens a PR with AC coverage and evidence. Never asks - a gap it may close it decides and records, and anything else stops the line with a question on the story. Plan files go to docs/new-feature/{slug}/.
argument-hint: "[work item URL or id, or the path of a jidoka-ready story file]"
disable-model-invocation: true
---

# Dev Workflow - Unattended Story Build

Build one story from its signed agreement to a pull request, with nobody to
ask. Track the phases below in a todo list. Phase 8's loop position lives in
`07-progress.md`, so the run survives compaction and restarts.

**Announce at start:** "I'm using the jidoka:line skill to build this story
unattended, from its agreement to a PR."

**Nobody to ask.** Never ask a person anything, and never end your turn
waiting for an answer: the run ends with a pull request (or a local merge) or
with an andon stop. Every decision is in the agreement, or is one you make and
record (see "Decisions made by the line"), or stops the line (see "Andon").
The agents and skills you dispatch follow the same rule: they report, and you
decide.

**The agreement.** `story.md` in the plan folder, the snapshot
`agreement.py claim` writes of what BA, Dev Lead and QE signed. It is
read-only. Its format is the refine skill's
`references/agreement-format.md`. Section 4 holds the ACs, by permanent ID;
section 5 holds QE's scenarios and evidence; section 6 holds the Dev Lead's
contract decisions and constraints; section 8 holds open and deferred
questions; section 9 holds the decisions taken; section 10 holds `Exit:` and
`Stop also on:`; section 11 holds references and suggested skills. Load the
suggested skills that are installed.

**`agreement.py`** is `../refine/scripts/agreement.py` from this skill's
folder (on Claude Code,
`${CLAUDE_SKILL_DIR}/../refine/scripts/agreement.py`), run by its absolute
path with `python3`. It is the only thing that reads the tracker and writes to
it: the story's tag or Status line, its section 12 and its comments.

**Model routing.** Every agent's frontmatter already carries the model its role
resolves to (reasoning, verification, implementation, exploration; the table is
`src/models.yaml` in the plugin repo), so dispatch without a `model` by default.
Two exceptions pass the Task call's `model` parameter, which overrides
frontmatter:

- `Tier: refactor` stories dispatch `code-reviewer` with `model: "sonnet"`; a
  diff that adds no behaviour does not need the verification tier.
- A re-dispatch of an implementer after `FIXES_NEEDED` from a reviewer or the
  walker, or after a Return Report that failed your evidence check, goes one
  tier up: `model: "opus"`. The first attempt already failed at the standard
  tier; retrying it there is the expensive path.

Never pass `model` otherwise.

**Three attempts.** Every gate gets three attempts: an implementer's evidence
check, the plan review, the code and security review, the smoke, the
regression run and the walkthrough. That means the first, then two
re-dispatches on `opus` (the rule above), each quoting the failures so far
verbatim. A third failure stops the line; there is no fourth try. Every loop
below that says "until" means "until, within three attempts".

**Herdr mode.** Run `printenv HERDR_ENV` before Phase 1. If it prints `1`,
invoke `herdr-crew`, which decides whether herdr mode applies. In herdr mode
every subagent dispatch of this run, those of `project-setup` and `raise-pr`
included, goes through it: same agent, brief and batching, each worker in its
own column of a crew tab and you as herdr agent `lead`; the `model` exceptions
above become its `--model` option. Take the crew down after Phase 10 or an
andon stop. Outside herdr, or with herdr mode off, nothing below changes.

## Decisions made by the line

The agreement settles what the roles decided. When it leaves something open
that a role could reasonably have decided differently (visible behaviour,
data, API shape, error handling, wording, test scope), and the choice is
reversible and stays inside the agreement, decide it yourself and record it.
Do not stop for it. Internal structure (names, file layout, refactors) is not
logged; the code review covers it.

Record each decision in `09-decisions.md` in the plan folder the moment you
make it:

```markdown
# Decisions made by the line - {id}

| ID | Story didn't say | Line chose | Why | Confirm by | Undo by | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AD-1 | The order of the list after an edit | Unchanged | Least surprise; the list is ordered by creation | BA | Sort by update time in the list query | pending |
```

- **IDs** continue from the highest `AD-n` in `story.md`'s section 12.
- **Confirm by** is the role that owns that kind of decision: BA for behaviour
  and wording, Dev Lead for contract and data, QE for test scope.
- **Undo by** is the concrete change that reverses it.
- Commit the file with the work it explains.

Agents report the choices they made under "Flagged". Make each one that
qualifies a line decision. `raise-pr` puts the table in the pull request,
writes it to the story's section 12 and has `context-updater` record each one
as an open question. The owning role later confirms or rejects it through
`/jidoka:refine`. A pending decision does not block the merge.

## Andon

Stop the line, and never guess, when going on would:

- change, add or drop an acceptance criterion, or contradict the agreement;
- contradict a recorded decision (a decision entry in the project context,
  or a `supersedes` or `conflicts-with` edge), or run into an open question
  that blocks the work;
- touch authentication, authorisation, data visibility or personal data in a
  way the agreement does not settle;
- meet a condition in section 10's `Stop also on:`, or a question section 8
  lists as `deferred`;
- need a fourth attempt at a gate; or
- need something the run cannot fix: credentials, a broken environment, a
  failing baseline in the code a resumed story touches.

A new story's base is tested before the claim (Phase 1 step 2). A base that
fails there is a base stop, not an andon: the story is not at fault, so it
keeps its `jidoka-ready` and gets no branch, pull request or question.

To stop:

1. **Write `andon.md`** in the plan folder:
   - what stopped the line, and where (phase, slice, step);
   - what the agreement says;
   - the options, with your recommendation;
   - the role who owns the answer.
2. **Record it.** Add a row to the `## Andon` table of `07-progress.md`, and
   mark the step you were on ❌ with a one-line note. Before Phase 4 has
   written the ledger, create it from the Phase 8 Step 0 template, with no
   slice rows yet, so the stop is on record where the resumed run looks.
3. **Leave the work where anyone can pick it up.**
   - Commit everything on the branch:
     `chore({slug}): andon - {what stopped it}`.
   - With a remote: push (`git push -u origin {slug}`), then open a **draft**
     pull request titled `[blocked] {id}: {title}`, with `andon.md` as its
     body (`gh pr create --draft` or `az repos pr create --draft`). Without a
     remote, the branch stays local.
4. **Tell the story.** Run these through `agreement.py`:
   - `record {folder}/story.md --decisions {folder}/09-decisions.md`, when
     there are decisions;
   - `comment {folder}/story.md --file {folder}/andon.md`, with the draft
     PR's link added;
   - `status {folder}/story.md --set jidoka-blocked`.

   For a story file, commit the story file's change on the branch.
5. **End the run.** Leave the worktree in place. The last message is the
   andon report: the question, its owner, and the draft PR or branch. It ends
   with: "Answer it with `/jidoka:refine {story}`, which marks the story ready
   again; `/jidoka:line {story}` then resumes."

**A stop in Phase 1, before the worktree exists**, such as `Exit: pr` in a
repository with no remote, leaves no branch. Skip steps 1 to 3. Write the
question to `{scratch}/andon.md`, and run step 4 on the claim's snapshot,
`{scratch}/story.md`: the comment, then `--set jidoka-blocked`, which
releases the claim. A story file has no claim to release, so the report alone
is enough.

## Phase 1 - Readiness, claim and worktree

1. **The argument names a story.** That is a work item URL (or an id, with
   the organization from `az devops configure --list`) or the path of a story
   file. Anything else is not something the line builds. That includes pasted
   story text and a request to set up a project with no agreement behind it.
   Say so in one message that points at `/jidoka:refine`, and stop.
2. **Check the base, before the claim.** A base that does not build is not
   the story's problem, so it must not cost the story its claim, a branch or a
   question. With a remote, run `git fetch origin` first, so a branch an
   earlier run pushed is seen. Make a scratch directory outside the
   repository (`mktemp -d`). Not a git repository yet, or one with no
   commit (a new project, which step 4 starts): skip to step 3, since there
   is no base to test.
   1. **Read the story without claiming it:** for a work item,
      `agreement.py pull --ado {story} -o {scratch}/peek.md`; a story file is
      read where it is. If its Status is not `jidoka-ready`, or
      `agreement.py check --ready` on it fails, skip to step 3: the claim
      refuses it and says why.
   2. **A branch an earlier run left** (`agreement.py slug` on it names the
      branch; look for it locally and on the remote): skip to step 3. The
      resume brings the base into that branch and runs its baseline there.
   3. **The base:** what `agreement.py base` prints for it. Nothing printed
      means the remote's default branch
      (`git symbolic-ref --short refs/remotes/origin/HEAD`, without
      `origin/`; run `git remote set-head origin --auto` first if it is
      unset), or the current branch with no remote. A named base that is on
      neither the remote nor, with no remote, the repository means the
      agreement cannot be honoured: an andon stop before the worktree, run on
      `{scratch}/peek.md` (or the story file) in place of the claim's
      snapshot. The owner is the Dev Lead.
   4. **Test it:** invoke `git-worktrees` to check the base, with the slug
      and the base. It runs the baseline in the story's worktree, detached at
      the base's commit.
   5. **Read the baseline.** It is green, or its failures are outside
      anything the story touches: keep the worktree for step 5, its baseline
      the story's. Otherwise (the build fails, or a failing test covers code
      the story changes) it is a **base stop**:
      - `git-worktrees` drops the worktree. There is no claim, no branch, no
        pull request and no question on the story, which stays
        `jidoka-ready`.
      - When `JIDOKA_OUT` is set (the scheduled pick-up), write one line,
        `{base} {full commit}`, to `$JIDOKA_OUT/base-red`. The pick-up holds
        every story on this base until it moves.
      - The run's last message: the base and its commit, the build errors or
        failing tests, and that the story builds once the base is fixed. Then
        stop.
3. **Claim it.** Run `agreement.py claim {story} -o {scratch}/story.md`.
   It refuses unless the story is `jidoka-ready`, its agreement passes the
   ready check and its hash matches every sign-off. It then marks the story
   `jidoka-running`, refused if anyone saved it since the read, and prints the
   story's **slug**. The slug is the branch an earlier run of the story left,
   found by the story's id, so an edited title keeps its branch. If there is
   no such branch, the slug comes from the title.
   - **A story file travels with its branch.** If a branch named by its slug
     (`agreement.py slug {file}`) already exists, an earlier run stopped
     there, and the story's current copy, answered and re-signed, is on that
     branch. Claim the copy in that branch's worktree (`git-worktrees`
     resume) instead of the one on the base branch.
   - **Refused:** drop step 2's worktree if it kept one, relay the output
     verbatim and point at `/jidoka:refine {story}`. When
     `JIDOKA_SCHEDULED=1` is set (a scheduled pick-up), also post that on the
     work item: pull it with
     `agreement.py pull --ado {story} -o {scratch}/story.md`, then
     `agreement.py comment` from that copy. Then stop. No branch, no worktree.
   - **`Exit: pr` and `git remote` prints nothing:** the agreement cannot be
     honoured. Drop step 2's worktree; this is an andon stop before the
     worktree, and the owner is the Dev Lead.
4. **New project first.** When the folder has no source code
   (`project-setup`'s Step 1 says what counts) and section 6 has a `Stack:`
   line, invoke `project-setup` with the snapshot's path. Do the same when
   the `Stack:` line names a layer the repository lacks. It reads every answer
   from that line, asks nothing, and has `project-scaffolder` land the
   skeleton on the base branch with its `docs/project_context/`. The base
   has then moved past step 2's commit: drop that worktree, and step 5
   creates the branch from the new base. Then:
   - **Make it last.** A scheduled run's container is thrown away, so with a
     remote the skeleton must leave the machine:
     - If it merged into the base, push the base (`git push origin {base}`).
     - If it was left on its branch, push that branch and open a pull request
       for it, with the setup report as its body and the `jidoka` label, as
       `raise-pr` Step 5 does.

     A push that is refused is an andon stop; the owner is the Dev Lead.
   - **No active AC** (the agreement was only the setup): run
     `agreement.py status {scratch}/story.md --set jidoka-done`, or
     `jidoka-pr` when the skeleton waits in a pull request. Then comment the
     setup report on the story. A story file's Status change is committed on
     the base branch as `docs(stories): {id} set up`. The report is the run's
     last message. Stop.
   - **ACs, and the skeleton waits in a pull request:** the story cannot be
     built on a base that lacks it. Stop the line. The question is to merge
     the skeleton's pull request, and the owner is the Dev Lead. Once it has
     merged, `/jidoka:refine` marks the story ready again, with no new
     sign-off: nothing signed changed.
   - **Otherwise** go on with the story on top of the skeleton. The auth the
     skeleton ships is done: do not plan it again.
5. **Worktree.** The branch is the slug, and the plan folder is
   `docs/new-feature/{slug}/`. The base is step 2's; `07-progress.md` records
   it as `Base:`.
   - **Step 2 kept a worktree:** make it the branch
     (`git -C {repo-root}/.worktrees/{slug} switch -c {slug}`). It starts at
     the commit step 2 tested, and that baseline is the branch's.
   - **No branch of that name**, local or on the remote, and no kept
     worktree: invoke `git-worktrees` with the slug and the base. If no
     `Skill` tool is exposed, create it via Bash with an **absolute** path
     (`git worktree add -b {slug} {repo-root}/.worktrees/{slug} origin/{base}`,
     or `{base}` with no remote; a relative path resolves against a CWD that
     may have drifted into another worktree) and verify with
     `git worktree list`. Never silently proceed on the current branch.
   - **The branch exists:** an earlier run of this story stopped. Resume it
     (see "Resume" below) instead of the rest of this step.

   Move the snapshot to `{folder}/story.md` and start `09-decisions.md` with
   its header and an empty table. For a story file, also run
   `agreement.py status {folder}/story.md --set jidoka-running` from the
   worktree's root, where the snapshot's `Source` path resolves, and include
   the story file in the commit. Then commit, the first commit on the branch:
   `docs({slug}): story {id} as signed ({hash})`.
6. **Classify the story's shape** and record the tier in the todo list. It
   sizes every later phase, and Phase 4 writes it into `07-progress.md` as the
   `Tier:` line, so later steps read the classification instead of re-deriving
   it from the diff.

| Shape                                                                                         | Explorers (Ph 2)                               | Architect writes (Ph 4)                                                                | Plan review (Ph 6) | Reviews (Ph 8)                      | Walkthrough (Ph 9)                                                    | Per-slice verify (Ph 8) |
| --------------------------------------------------------------------------------------------- | ---------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------ | ----------------------------------- | --------------------------------------------------------------------- | ----------------------- |
| **Feature, BE + FE** (`full-stack`)                                                           | 2-3                                            | four docs, `02`-`05`                                                                   | 2 reviewers        | code + security                     | Playwright walker                                                     | run the suite           |
| **Feature, one layer** (`one-layer`)                                                          | 1                                              | four docs, `02`-`05`                                                                   | 1 reviewer         | code + security                     | walker (Playwright or CLI)                                            | run the suite           |
| **Refactor / test-only / docs** (`refactor`) - no new behaviour, or production code untouched | 0 - your own Phase 2 census is the exploration | `04-task-plan.md` only (flat tasks or `Kind: sweep` slices, verification steps inline) | none               | code only, security brief folded in | none - run the story's own Verification section from the main session | build + greps           |

The third row exists because the full workflow, applied to a test-only sweep,
spends its architect on three documents nobody reads, its plan reviewers on
finding nothing, its security reviewer on a diff with no production code, and
its walker on evidence that is two shell commands. When a later phase says "per
the tier", this table is what it means.

### Resume

The branch is left from an earlier run that stopped. Its base is the
`Base:` line of the branch's `07-progress.md` (read it before the checkout
with `git show {branch}:docs/new-feature/{slug}/07-progress.md`, from
`origin/{branch}` when only the remote has it).

- **The base must not change.** The new snapshot's base (Phase 1 step 2.3,
  run on `{scratch}/story.md`) must be the ledger's. A merge cannot move a
  branch from one base to another. If they differ, stop the line; the owner
  is the Dev Lead, who either signs the old base again or has the branch
  deleted so the next run starts the story from its new base.
- **Bring the base in.** Have `git-worktrees` resume the branch with that
  base. It merges the base into the branch, so whatever landed there while
  the story waited (often the fix its stop asked for) is in the baseline.
  A merge conflict is an andon stop; the owner is the Dev Lead. A failing
  baseline in code the story touches is one too.

Then read its `07-progress.md`, `andon.md` and `story.md`.

1. Run `agreement.py compare {folder}/story.md {scratch}/story.md`. It lists
   each AC as unchanged, changed, evidence changed, added or removed, and
   names every other section that changed.
2. Replace `story.md` with the new snapshot, and mark the `## Andon` row
   `answered`. Commit:
   `docs({slug}): story {id} as re-signed ({hash})`.
3. Apply the comparison:
   - **Changed, added or removed ACs, or changed evidence:** the slices that
     cover them go back to ⬜ in the ledger. Re-dispatch the architect with the
     comparison to amend those slices' plan documents and add slices for new
     ACs. Then run Phase 6 on the amended documents.
   - **Another section changed:** give the architect the comparison. It names
     the slices the change touches, and those go back to ⬜.
   - **An AC reported `missing`:** AC IDs are never dropped, so the agreement
     is broken. Stop the line; the owner is the BA. An AC `restored` counts as
     added, and one `added as removed` needs nothing.
   - **Always:** every row of the final QA round goes back to ⬜, because its
     results covered the old diff.
4. Continue from the first ⬜ row, in the phase it belongs to. Phases 2 and 3
   run again only for slices the comparison touched. A ledger with no slice
   rows yet means the stop came before Phase 4: continue from the phase its
   Andon row names.

## Phase 2 - Codebase Exploration

1. If `docs/project_context/` is missing or empty, invoke
   `codebase-context-builder`; otherwise read `00_index.md` and load 2-4
   relevant files.
2. **Query the knowledge graph before searching the tree.** If
   `docs/project_context/prod_spec/graph.md` exists, read it whole and resolve
   the story against it, starting from the IDs in `story.md`'s section 11:
   - The capability map gives code anchors, your search starting points.
   - The entity map gives every rule already constraining the entities
     involved.
   - The edges say which decisions are `supersedes`/`amends` (a superseded
     entry reads like a current one; do not apply it) and which are
     `conflicts-with` (pick a side knowingly; if the agreement does not, that
     is an andon stop).
   - The open questions say whether the work is blocked or deferred. If it is,
     stop the line now.

   Then load only the cited entry IDs
   (`grep -n "\[DR-114\]" docs/project_context/prod_spec/*.md`), not the whole
   folder.
3. Per the tier, dispatch **`code-explorer` subagents in parallel**
   (`agent_type: "jidoka:code-explorer"`), seeded with the anchors and
   entry IDs from step 2: one tracing the closest similar feature end to end,
   one mapping the domain area's architecture and conventions, and (if
   full-stack) one tracing the frontend patterns. Each returns 5-10 key files.
   **Refactor tier: none.** Do the census yourself with greps over the files the
   story names (declarations, call sites, counts); a refactor's exploration is a
   count, and explorers dispatched to re-map what you just grepped are the layer
   that gets thrown away. Otherwise the count is the tier's, whatever the
   tree's size: a one-layer story in a four-file repo you have already read
   still gets its explorer. The run is unattended, so a phase skipped on
   judgement is a deviation nobody reviews.
4. Read the key files they name. Then note: the reference implementation, the
   capabilities and entities touched (graph IDs), layers affected, reusable
   code and the conventions to follow.

## Phase 3 - Settle Against the Agreement

Nobody answers questions now. Settle each open point with what you hold,
before anything is designed:

- Walk the agreement against what Phase 2 found. Check four things:
  - For each AC, is the behaviour fully determined?
  - Does the code allow each Dev Lead constraint?
  - Does the story touch a deferred question in section 8?
  - Does it meet a `Stop also on:` condition?
- **The code answers it:** note the fact and its source for the architect.
- **A role could have decided it differently, and the choice is reversible
  and inside the agreement:** decide it, and record it in `09-decisions.md`.
- **Anything on the andon list:** stop the line.

Summarise what the architect needs: the facts found, the line decisions so far
(`AD-n`), and the constraints that bind the design.

## Phase 4 - Architecture Design and Documents

### Step 1 - Dispatch the architect

Dispatch **1 `code-architect`** (`agent_type: "jidoka:code-architect"`)
with:

- the **absolute path of `story.md`**, the agreement it designs from;
- the Phase 2 findings and the context files loaded;
- the Phase 3 summary and `09-decisions.md`;
- the **absolute path** of the plan folder.

It designs the blueprint and writes `02-technical-plan.md` …
`05-test-plan.md` itself; you transcribe nothing. There is no overview or
business plan: `story.md` is that half. Its final message is a manifest:
summary, slice table, waves and critical path, files written, risks, and the
choices it made that the agreement did not settle.

Tell the architect the tier and two facts about the machine, or it will
over-serialise: how many worktree slots exist, and that `Kind: sweep` slices
(see `vertical-slicing`) gate on the build, not on container tests, so disjoint
sweeps are parallel-safe even when only one database container fits. **Refactor
tier:** the architect writes `04-task-plan.md` only.

### Step 2 - Check the slice list, then write the ledger

Nobody confirms the slice list; you check it against the agreement.

1. Read the documents the tier calls for. They are the source of truth; the
   manifest is a table of contents.
   - **Every tier:** every slice has a card in `04-task-plan.md`. The file
     opens with a `## Dependency graph` block whose edge table matches the
     cards' `Blocked by:` lines.
   - **Feature tiers:** every `BE + FE` slice has a frozen `Contract:`, and
     `05-test-plan.md` has concrete demo steps.
   - **Refactor tier:** every card or task carries its verification steps
     inline, and every `Kind: sweep` card names a `Files:` set disjoint from
     the other sweeps'.
2. **AC coverage.** Every active AC in `story.md` must appear by ID in at
   least one card's ACs. On a feature tier it must also appear in
   `05-test-plan.md`, with the evidence section 5 names for it. Check with
   grep, ID by ID. A plan that drops, merges away or rewords an AC, or
   designs against a Dev Lead decision, goes back to the architect with the
   gap quoted.
3. Record the architect's own choices that qualify as line decisions in
   `09-decisions.md`.
4. Small changes: edit the docs. Structural changes: re-dispatch the architect,
   within three attempts.
5. **Write the ledger.** Create `07-progress.md` in the folder from the Phase
   8 Step 0 template. If an earlier stop already created it, add the slice
   rows and keep its `## Andon` table. It holds:
   - `Tier:` from Phase 1;
   - `Base:`, the branch the worktree was cut from;
   - `Exit:`, from `story.md`'s section 10;
   - one ⬜ row per slice.

   Writing it now rather than in Phase 8 lets the run survive a compaction in
   Phases 5-7. `raise-pr` reads `Base:` and `Exit:`, then merges into that base
   or targets the PR at it instead of assuming `main`.

## Phase 5 - Finalize Documents

1. Every file the tier calls for exists and is complete (four for a feature, one
   for a refactor); re-dispatch the architect for any stub rather than filling
   it in by hand.
2. **Cross-document consistency.**
   - **Every tier:** the dependency-graph edge table agrees with the cards,
     every blocker is a real slice ID, and there is no cycle. On a mismatch,
     fix the table and re-derive.
   - **Feature tiers:** every slice has test cases in `05-test-plan.md` and
     change sites in `03-implementation-plan.md`, and every `BE + FE` contract
     also appears in `02-technical-plan.md`.
   - **Refactor tier:** the sweeps' `Files:` sets are pairwise disjoint and
     together cover the files the story names.
3. Add an index entry to `docs/new-feature/README.md` (folder, story, branch,
   later the merge commit). This is the plan-folder index, not the project's
   backlog tracker, and must not carry a status column that duplicates one;
   `raise-pr` Step 6 owns the tracker.

## Phase 6 - Quality Review

Per the tier, dispatch **`plan-reviewer` subagents in parallel**
(`agent_type: "jidoka:plan-reviewer"`) over `docs/new-feature/{folder}/`, with
the path of `story.md`. They are the plan's only reviewers, so their verdict
is the gate:

- One reviews AC coverage, security, edge cases, and whether the technical
  plan keeps to the agreement.
- One reviews slice completeness, dependency edges, test coverage and sizing.
- A one-layer feature gets only the first.

Fix every Critical and Important issue in the docs, then re-dispatch the
reviewers that raised them on the amended docs, until they raise none. A
finding that only a role can settle is an andon stop. **Refactor tier:
skip.** Your Phase 5 consistency check is the review.

## Phase 7 - Summary

Write a short summary in chat and go straight on; nobody is waiting for it. It
covers the folder path, the slices with their waves and critical path, the
line decisions so far, and the risks the reviewers flagged.

## Phase 8 - Slice-by-Slice Implementation

Implement every slice's halves - BE against the frozen contract, FE against a
**mock** of it, concurrently - **without integrating per slice**. Then run one
consolidated round over the whole diff: integrate, refactor, review, smoke,
regression. Deferring integration is safe because each backend conformance-tests
its own contract. The browser-level e2e runs once in Phase 9, not here.

### Step 0 - Progress ledger

Phase 4 Step 2 created `07-progress.md` with the `Tier:` / `Base:` / `Exit:`
lines and one ⬜ row per slice (or per task, for a flat task list). Read it and
cross-check the last ✅ against `git log --oneline` (the `feat(...)` commits and
the checkpoint are ground truth). Any ⬜ in the per-slice table → start or
resume in Step 1 at that slice; otherwise resume in Step 2 at the first ⬜ row,
in table order. Do not redo completed steps. If the file is missing, create it
now from this template, filling the three lines from the todo list and
`story.md`:

```markdown
# Progress - {slug}

Tier: {full-stack | one-layer | refactor}
Base: {base}
Exit: {pr | merge}

## Per-slice implementation

| Slice | BE | FE |
|-------|----|----|
| SLICE-01 | ⬜ | ⬜ |

## Final QA round (once, after every slice above is implemented)

| Step | Status |
|------|--------|
| Integration (whole story - every FE on the real backends, contract drift fixed) | ⬜ |
| Refactor / simplify (whole story) | ⬜ |
| Code review (full diff, branch point → HEAD) | ⬜ |
| Security review (full diff, branch point → HEAD) | ⬜ |
| Smoke (every slice's smoke sequence) | ⬜ |
| Test suite / regression (whole diff, one run - also the coverage gate and the "after" result files) | ⬜ |
| Context capture | ⬜ |
| Checkpoint commit | ⬜ |

## Andon

None.
```

The three header lines:

- **`Tier:`** is the Phase 1 classification.
- **`Base:`** is the branch the worktree was cut from.
- **`Exit:`** is the agreement's section 10.

Keep them bare: `raise-pr` and the tier branches below read them with
`grep '^Tier:'`, `'^Base:'` and `'^Exit:'`. Cells that cannot apply are `-`
from the start: the FE column of a BE-only slice, and the Integration and
Smoke rows of a story made only of `Kind: sweep` slices. An andon stop turns
`None.` into a table:
`| # | Phase | Question | Owner | Status |`, where Status is `open` or
`answered`.

`⬜` pending · `✅` done · `❌` failed/blocked (one-line note under the table) ·
`-` N/A (e.g. FE on a BE-only slice). Update a row the moment it completes. The
file is orchestrator-owned; subagents never write to it.

### Step 1 - Implement: parallel halves, parallel slices

Schedule from the `## Dependency graph` block in `04-task-plan.md` combined with
the ledger:

- **Ready frontier** = slices whose every `Blocked by:` is ✅ (roots start
  ready). Start each ready slice that has a free worktree slot, and refresh the
  frontier the moment a blocker's BE and FE both go ✅; do not wait for its
  wave.
- More ready slices than slots → start **critical-path slices first**, then
  larger ones.
- Each concurrent slice gets its own worktree. With one worktree, run slices
  sequentially but still parallelise each slice's halves.

For each slice you start:

1. **Dispatch the halves concurrently, in one batch**, per the card's `Layers:`:
   - `BE + FE`: `agent_type: "jidoka:impl-backend"` with scope
     `"SLICE-NN backend half - implement AND conformance-test the frozen contract"`
     **and** `agent_type: "jidoka:impl-frontend"` with scope
     `"SLICE-NN frontend half - build against the frozen contract with a typed
     mock; integration is one whole-story pass in Step 2"`.
     If the card says `Contract: unfrozen - serial`, run BE first, then FE.
   - `BE only` / `FE only`: dispatch that implementer.
   - Append the lean mode from the card's story points: `lean: lite` for 1-2,
     `lean: full` for 3+ (large slices still get `full`; the implementer flags
     over-scope rather than dropping ACs).

   Each implementer gets the slice card, not a file-task list, and commits per
   behaviour: `feat({layer}): SLICE-NN - {behaviour}`. Tests cite the AC IDs
   they prove (`AC-2` in the test name or as the framework's tag), so the
   pull request's coverage table can be built with grep. The FE half stays on
   its mock; do not re-dispatch it to wire in the real backend now.

   For a `Kind: sweep` card the scope is
   `"SLICE-NN {backend | frontend} half - kind: sweep"` - no contract wording,
   there is none to conformance-test - and the implementer runs
   `sweep-implementer` instead of its TDD loop: it gates on the compile step,
   runs no container suite and writes per-site findings to its own
   `08-findings-SLICE-NN.csv`. Sweeps over disjoint `Files:` sets run
   concurrently, one worktree each.

2. **Verify each Return Report against evidence you already hold.** The agent
   that wrote the report is the one it describes, so never accept it on trust -
   but pick the instrument by the slice's kind:
   - **Static checks first, always** (seconds): the build is clean; the card's
     greps return the counts it predicts; for a `Kind: sweep` or test-only slice
     every path in `git diff --name-only {branch-point}..HEAD` belongs to the
     card's `Files:` set (a path outside it is over-reach, whatever the repo
     layout); every AC the card assigns to that half appears in the report with
     a named backing test.
   - **`Kind: sweep`: compare, do not re-run.** The report carries a per-file
     table of test-marker counts at the branch point and at HEAD (the project's
     marker: `[Fact]`/`[Theory]`, `[Test]`, `it(`/`test(`, `def test_`).
     Re-derive it with the same one-liner
     (`git show {branch-point}:{file} | grep -c '{marker}'` against
     `grep -c '{marker}' {file}`) and require the columns to match file by file:
     a sweep that eats an attribute line still compiles, so the build alone
     proves nothing about lost tests. Re-run a file's classes only on a
     mismatch; the whole suite runs once, in Step 2.5, where the total is
     checked against the worktree baseline. Re-running a suite to confirm an
     accurate report is container time spent learning what the greps already
     showed.
   - **`Kind: feature`: re-run.** Run the relevant suite(s) via Bash (backend
     including its conformance tests, frontend against its mock) and compare
     counts to the report. This is where a self-graded "green" can be wrong.

   On any mismatch or missing section, re-dispatch the owner with the
   discrepancy quoted verbatim, or finish the work yourself and note the
   takeover. Each "Flagged" item is either a line decision you record, a
   question for its owner that stops the line, or a fix you route.

3. **Mark BE/FE ✅.** Nothing else happens per slice. Start whatever this slice
   was blocking.

### Step 2 - Consolidated quality round (once, over branch point → HEAD)

Precondition: every BE/FE cell is ✅ (or `-`). If sweeps wrote
`08-findings-SLICE-NN.csv` files, concatenate them now (header once) into
`08-findings.csv`, render any table the story requires from it with a short
script, and commit; this is the only point where findings are assembled, so no
sweep waits on another.

1. **Integrate the whole story.** Dispatch `impl-frontend` once, scope
   `"whole-story integration - replace every slice's contract mock with the
   real backends, run integration/e2e tests, fix contract drift"`, with the full
   slice list and changed-file set. If drift belongs on a backend,
   re-dispatch `impl-backend` for that slice with the mismatch quoted. Skip
   `unfrozen - serial` slices (already integrated) and `Kind: sweep` slices
   (nothing to integrate); a story made only of sweeps skips the step and its
   row is `-`. Mark ✅.

2. **Refactor.** Dispatch `agent_type: "jidoka:impl-simplify"` once with
   the folder path, the branch-point ref and the changed-file list. It
   simplifies the whole-story diff in its own context (on Claude Code by
   wrapping the built-in `simplify` skill, elsewhere with its own rules; a
   whole-story refactor read here would evict the plan docs and reports you
   still need), then conforms it to the house conventions
   (`react-best-practices`, `restful-api-design`), which the implementers
   deliberately skip, runs the tests covering the files it touched, and commits.
   Confirm its report names that run and shows it green; a missing Verification
   line means re-dispatch, not a run of your own - the full suite runs once, in
   step 5. Route any blocker under "Reported, not fixed" to the owning
   implementer. Mark ✅. It runs **before** review so the reviewers read the diff
   that ships; a simplify pass after approval means the approved diff is not the
   merged one.

3. **Review code and security in parallel.** In one batch, dispatch
   `agent_type: "jidoka:code-reviewer"` and
   `agent_type: "jidoka:security-reviewer"` over the full diff, each with:
   - the folder path and `story.md` (the ACs the diff must meet);
   - `04-task-plan.md`;
   - the `Tier:` line. A refactor-tier folder has no `02-technical-plan.md`;
     say so, so the reviewer does not go looking for it.

   The round passes only when **both** return `APPROVED`. On `FIXES_NEEDED`
   from either, re-dispatch the owning implementer(s) with the Blocker rows
   quoted verbatim. Then re-dispatch only the reviewer(s) that flagged,
   scoped to the amended diff, until both approve. Non-blockers become PR
   follow-ups. Mark both rows ✅.

   **Refactor tier** (`Tier: refactor` in `07-progress.md`): dispatch **one**
   reviewer, `code-reviewer`, with the security reviewer's test-specific brief
   folded into its prompt - "every denial, scoping and visibility test still
   proves what its name says after the rewrite". The check is worth keeping; two
   agents reading the same diff for it is not. Mark the security row `-`.

4. **Smoke.** Run every `Kind: feature` slice's `Smoke:` sequence from
   `04-task-plan.md` in slice order against the running stack; sweeps have none,
   and a story made only of sweeps marks the row `-`. After a fix, re-run only
   the failed sequences. Mark ✅.

5. **Regression - one run serves every gate.** Run the project's full existing
   suite (unit, integration, component, pre-existing e2e) over the whole diff
   **once**, through the project's target that also measures coverage and
   keeps the test-result files (usually a Makefile target taking a results
   directory). That single run serves four purposes:
   - the regression gate;
   - the coverage gate;
   - the container-budget pin;
   - the "after" half of any before/after diff the story requires.

   Its passing count must be at least the baseline `git-worktrees` reported at
   worktree creation plus the story's new tests. A lower total is a lost
   test, whatever the sweep reports said. Do not run a bare suite first for
   the result files and the coverage suite again for the threshold; that is
   the same suite twice. Fix failures before marking ✅. Do not write or run
   the story's new browser e2e here; that is Phase 9.

   **Gates run strictly one at a time.** Never launch one detached while another
   runs in the foreground: a coverage-instrumented container suite starved by a
   parallel build fails on database timeouts and the whole run is wasted. If a
   make target already chains the gates serially, call it rather than
   decomposing it.

   **Long jobs get a bounded watcher, never an open-ended one.** A job longer
   than the Bash tool's ceiling runs detached (`nohup run.sh &`) and writes its
   `DONE` marker from an `EXIT` trap, never from a last line: a last line is
   skipped when `set -e` aborts the script, and under `| tee` a bare `$?` is
   tee's 0, so the failure path - the one the marker exists for - never produces
   one.

   ```bash
   # run.sh
   set -o pipefail
   trap 'echo "exit=$?" > "$S/DONE"' EXIT
   make coverage RESULTS="$S" 2>&1 | tee "$S/run.log"   # the project's suite-with-coverage target
   ```

   The watcher must exit on its own before the ceiling, because its exit is what
   re-invokes you; a loop killed at the ceiling re-invokes nothing. The loop
   below sleeps up to 8.5 min, so call it with the tool's maximum timeout
   (`timeout: 600000`); under the default 2-minute ceiling shorten it to
   `seq 1 3`. If the harness blocks a foreground `sleep`, use its Monitor /
   until-loop tool on the same `DONE`-file condition instead:

   ```bash
   for i in $(seq 1 17); do [ -f "$S/DONE" ] && break; sleep 30; done
   if   [ -f "$S/DONE" ];                       then echo "DONE: $(cat "$S/DONE")"
   elif [ -n "$(find "$S/run.log" -mmin -3)" ]; then echo "RUNNING - re-arm the watcher"
   else echo "STALLED - log silent for 3 min; check uptime and orphaned test hosts before relaunching"; fi
   ```

   On `RUNNING` re-arm the same watcher immediately; on `STALLED` diagnose
   before relaunching. Never write "the watcher will need one re-arm" and stop;
   nothing re-arms it, and the session idles until someone notices, which in an
   unattended run is never.

6. **Capture product knowledge.** Invoke `context-updater` in the main session
   (never as a subagent) once for the whole story, with `09-decisions.md`. It
   records the behaviour implemented, the domain rules enforced, config
   decisions and non-obvious design choices. Each pending line decision
   becomes an open question, never a decision entry. Mark ✅.

7. **Checkpoint.** Commit, then mark ✅:

   ```bash
   git commit --allow-empty -m "checkpoint: {story} - all slices integrated after consolidated review/refactor/smoke"
   ```

### Step 3 - Report

A slice-by-slice log in chat covering:

- what each slice built, and its files;
- what the refactor changed;
- the review, smoke and regression outcomes;
- the line decisions;
- anything skipped or flagged.

Then go straight to Phase 9.

## Phase 9 - Test Plan Walkthrough

Precondition: every cell in `07-progress.md` is ✅ (or `-`). Otherwise return to
Phase 8.

**Refactor tier: no walker.** Run the story's own Verification section (or the
cards' `Verify:` lines) from the main session and write `06-walkthrough.md`
yourself: one row per slice or task with its command, observed output and ✅/❌,
under an `ALL_GREEN` / `FIXES_NEEDED` verdict. Commit it:

```bash
git add docs/new-feature/{folder}/06-walkthrough.md && git commit -m "docs({slug}): verification walkthrough"
```

The walker path commits in its own Step 6, and an uncommitted file 404s from the
PR body and is discarded with the worktree. Then go to Phase 10; `raise-pr` Step
1.5 accepts this file as-is. A refactor has no browser flow to record.

Dispatch `agent_type: "jidoka:test-plan-walker"` in a clean context (the
walkthrough produces dozens of screenshots) with:

- the folder path, branch name and app URL;
- the path of `story.md`, so its report gives evidence per AC ID in the form
  section 5 asks for;
- a pointer to where demo credentials live, never the credentials.

It writes a Playwright spec per slice from `05-test-plan.md` (self-capturing
screenshots), runs them headless, persists them into the project's e2e suite and
writes `06-walkthrough.md`.

- `ALL_GREEN` → Phase 10.
- `FIXES_NEEDED` → re-dispatch the owning implementer per Blocker, then
  re-dispatch the walker scoped to **the affected slices only**; it re-runs
  those specs and amends `06-walkthrough.md`. Loop until green.
- `PARTIAL` → fix the environmental issue it names and re-dispatch with
  `Resume from: SLICE-NN step-NN`. An issue the run cannot fix is an andon
  stop.

Non-blocker findings go into the PR body as follow-ups.

## Phase 10 - Branch Completion

Invoke `raise-pr`. It does the following, in order:

1. Verifies the CI gate and checks the walkthrough artifacts, re-dispatching
   the walker if they are missing.
2. Writes `10-summary.md`, the pull request's body. It leads with the AC
   coverage table (each AC by ID, its tests, the result and its evidence) and
   the decisions table from `09-decisions.md`, and states which revision of
   the agreement it built against.
3. Executes the `Exit:` action recorded in `07-progress.md`. A draft pull
   request an andon stop opened becomes the real one.
4. In its Step 6, tells the story what shipped through `agreement.py`:
   section 12, the comment, and `jidoka-pr` or `jidoka-done`. It also closes
   out the project's **backlog tracker**.
5. Removes the worktree, last.

Do not treat that last step as optional: everything before it writes only
inside `docs/new-feature/`, and a shipped story still reading `jidoka-running`
or `Ready` gets built again.
