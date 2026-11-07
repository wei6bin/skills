# Refine and the autonomous line

jidoka splits a story's journey at one point: everything a person must decide
happens in `/jidoka:refine`, and `/jidoka:line` builds the result with nobody
there to ask. This note records the design and the decisions behind it. PR 1
ships `refine`, the agreement format and its script; PR 2 makes `line`
autonomous. Until PR 2 lands, `line` runs as before and still asks its
questions.

The cut follows the plugin's name. In Toyota's jidoka the line runs on its own
and stops itself when something is wrong (the andon); people work before it
starts and on the stops, never standing beside it answering questions. Before
this split, `line` already called its Phase 4 slice confirmation "the last
question the user must be present for". The split moves that point to before
Phase 2 and gives it to a different session, with different people.

## The flow

```text
 BA --------+
 Dev Lead --+--> /jidoka:refine --> agreement --> /jidoka:line --> PR + evidence
 QE --------+    (people)           (signed,      (unattended)       |
                                     jidoka-ready)      |            |
       ^                                                | andon      |
       +----------- question posted on the story <------+            |
       +----------- each role confirms the line's decisions <--------+
```

## refine: the people's part

Three roles take part: the **BA** (behaviour, scope, rules), the **Dev Lead**
(contract, data, constraints, the stack) and the **QE**, the quality engineer
(scenarios, test data, the evidence each AC needs).

1. **Context.** It reads the story, its parent, siblings, links and
   discussion from the tracker. Then it grounds itself in the code: the
   project knowledge graph plus one `code-explorer`, so every Dev Lead
   question comes with a recommendation backed by the code. Facts are the
   agent's job; only decisions go to people.
2. **Gaps.** A generic checklist, plus the project's own
   `docs/project_context/refine-checklist.md` for domain rules. Each gap
   becomes an open question with a severity and the role that owns it.
3. **Rounds.** The gaps form a tree. Each round asks every question whose
   prerequisites are settled, each tagged `[BA]`, `[Dev Lead]` or `[QE]` and
   carrying a recommended answer that "yes" accepts.
   - **Live:** the three roles together.
   - **`--role`:** one role in their own session.
   - **`--solo`:** one person answers for all three.
   - **Questionnaire:** for someone who will not run the tool.
4. **The agreement.** The session is written up as a handoff to an agent
   that has none of its context: decisions, not discussion; behaviour, not
   procedure; every rule written out.
5. **Sign-off.** Each role signs the text as it reads back from the tracker,
   at its hash. With all three signed and no HIGH or MEDIUM question open,
   the story is marked `jidoka-ready`.
6. **The line's decisions.** When a line run made decisions alone, refine
   takes each one to its owning role to confirm or reject.

refine keeps no state of its own between sessions. Open questions,
decisions and sign-offs all live in the agreement, so the next pass, by
another role or on another day, starts from the record.

It is written to run on any harness: `AskUserQuestion` where it is offered,
chat otherwise. Its exploration falls back to the session's own when no
`code-explorer` agent exists, and its script needs only Python. BAs and QEs
can therefore run it outside Claude Code, where the jidoka plugin is not
installed.

## The agreement

The format is `src/skills/refine/references/agreement-format.md`: a title, three
metadata lines (`Tracker`, `Status`, `Rev`) and thirteen fixed sections. The
sections are statement, current and desired behaviour, acceptance criteria,
QE scenarios and evidence, Dev Lead decisions and constraints, out of scope,
open questions, decisions log, autonomy policy, references and suggested
skills, decisions made by the line, and sign-off.

- **Two forms, one converter.** On Azure DevOps the agreement uses the work
  item's own fields: the Acceptance Criteria field holds the AC table, and the
  Description holds every other section, so boards, queries and other tools
  keep working. Without a tracker it is a Markdown file. `agreement.py` is the
  only code that moves it between the two, so both skills hash the same text.
- **AC IDs are permanent.** `AC-1`, `AC-2`, ..., never reused or renumbered. A
  dropped AC stays as `AC-n (removed)`. Tests cite the IDs, so the PR's
  coverage table is built with grep, not judgement.
- **The hash** covers the title and sections 1-11, normalised so that a
  formatter cannot change it. Sections 12 and 13 are outside it, because
  writing the line's record or a sign-off changes nothing anyone signed. On
  Azure DevOps it is taken from what the work item reads back after a write,
  because its editor may rewrite the HTML.
- **Sign-off** is a row per role: name, date, mode (`live`, `own-account` or
  `solo`) and the hash. Any later change to sections 1-11 changes the hash, so
  every role signs again; refine shows them the diff.
- **Writes are refused on conflict.** Every write sends the revision it read,
  as a JSON Patch `test` on `/rev`, and Azure DevOps refuses it if anyone
  saved the work item since. `az boards work-item update` cannot send that, so
  writes go through `az rest`; reads use `az boards`.
- **Ready** is mechanical. `agreement.py status --set jidoka-ready` refuses
  unless all of these hold: every section is valid, the statement and desired
  behaviour are written, there is an active AC (or a new project's `Stack:`),
  every AC has evidence, no HIGH or MEDIUM question is open, and all three
  roles signed at the current hash. On Azure DevOps the check reads the work
  item itself, not the local copy.

## The boundary file (PR 2)

`line` never reads the tracker's HTML directly. After its readiness check and
its claim on the story, it runs the same converter and writes `story.md` into
the plan folder (`docs/new-feature/{id}-{summary}/`). That file is the first
commit on the story's branch, with the story id, revision, hash and sign-offs
at its head. No LLM touches this step, so what the line builds against is
byte for byte what was signed.

`story.md` is read-only once written. The line's own decisions go to
`09-decisions.md` as it makes them, and to the story's section 12 at the end
of the run. On a resumed run `story.md` is replaced, and git keeps the old
one.

What stays behind in refine: the question-and-answer trail, the gap analysis
and refine's own exploration notes. The decisions log keeps each outcome, its
reason and the alternatives turned down. Project-context IDs give the line's
explorers somewhere to start. There is deliberately no second, unsigned
briefing file: two documents drift, and unsigned text in the line's input lets
unagreed decisions in.

## line: the unattended part (PR 2)

- **Starting.** By hand (`/jidoka:line <story>`), or a scheduled job picks up
  stories tagged `jidoka-ready`. A story counts as ready only when the tag is
  present, the format check passes and the hash matches the sign-offs. A
  story edited after sign-off is refused with "changed after sign-off". A
  refused story gets one message pointing at `/jidoka:refine` (also posted on
  the story for a scheduled run), and no branch.
- **Claiming.** A story carries one `jidoka-*` tag at a time:
  `jidoka-ready` becomes `jidoka-running`, then `jidoka-pr` or
  `jidoka-blocked`. Once refine answers a blocked story and the roles
  re-sign, it returns to `jidoka-ready`. The claim is the same refused-on-
  conflict write, so of two runs racing for a story, one skips it. A story
  left `jidoka-running` with no activity is reported, never taken over.
- **No questions.** Phase 3 is gone. The Phase 4 slice confirmation becomes
  the plan-reviewer's verdict, plus a check that every AC maps to a slice and
  a test-plan case. Companion skills report problems instead of asking. QE's
  scenarios drive `05-test-plan.md`, and the walker reports evidence per AC.
  The worktree is created right after the claim, so `story.md` can be the
  branch's first commit.
- **Andon.**
  - The line makes a choice itself, and records it, when the choice is
    reversible and stays inside the agreement.
  - It stops when it would have to change or add an AC, contradict the
    agreement or a recorded decision, or touch auth, data visibility or
    personal data. It also stops on the agreement's own extra stop
    conditions, and when it meets a deferred question.
  - Every check gets three attempts (the first, a retry, and a retry one
    model tier up), then andon.
  - A stop pushes the branch, opens a draft PR, posts the question on the
    story and records it in `07-progress.md`.
- **Resuming.** From the pushed branch, so any machine can resume. The new
  agreement is compared with `story.md` AC by AC:
  - unchanged ACs keep their finished slices;
  - changed or new ACs have their slices re-planned and reviewed;
  - a change outside the ACs goes to the architect as a diff;
  - the final QA round always runs again.
- **Decisions made by the line.** Only choices a role could reasonably have
  made differently are logged: behaviour, data, API shape, error handling,
  wording, test scope. Each is an `AD-n` record: what the story didn't say,
  the choice, why, which role confirms it, and how to undo it.
  - The record appears in the PR, in the story's section 12 (one write per
    run), and as an open question in the project graph.
  - Pending decisions do not block the merge.
  - Signing off counts as permission for the line to write there, and only
    there: its own section, comments, and the state change `raise-pr` already
    makes.
- **Ending.** `Exit: pr` (the default) or `Exit: merge` for a repository with
  no remote; `ask` is gone. The PR leads with the AC coverage table and the
  decisions table, and says "built against story rev N".
- **Scheduled runs.**
  - Who runs them: a timer on a machine the team controls calls a bundled
    pick-up script.
  - What they run in: each story gets a fresh container, like the eval image.
    Permission prompts are skipped only inside it.
  - Pace: one story at a time, oldest first.
  - Identity: a service account, or a person's account until one exists. The
    line's PRs carry a `jidoka` label and its comments say they came from
    `jidoka:line`.

## Decisions

| # | Decision |
| --- | --- |
| 1 | No human gate between sign-off and the PR; plan review is the plan-reviewer agent's |
| 2 | The tracker (Azure DevOps) is the record; a Markdown file stands in without one |
| 3 | refine lives in jidoka, runs on any harness, installs on its own; domain checklists stay in the project |
| 4 | Roles are BA, Dev Lead and QE; live, `--role` or `--solo`; sign-off per role at a hash |
| 5 | Andon: assume and record when reversible and inside the agreement, stop otherwise; self-made decisions go in the PR and on the story |
| 6 | Three attempts per check, then andon |
| 7 | `Exit:` lives in the agreement, default `pr`; `ask` is dropped |
| 8 | A new project's stack is a Dev Lead question in refine |
| 9 | QE's scenarios drive the test plan; evidence is reported per AC |
| 10 | The skill is named `refine` |
| 11 | Log only decisions a role could reasonably have made differently |
| 12 | One `AD-n` record format, in the PR, on the story and in the project context |
| 13 | The line's decisions live in their own section, outside what was signed |
| 14 | The line writes to the story once per run, at the end or at a stop |
| 15 | Signing off grants the line its narrow write access |
| 16 | Unconfirmed decisions are open questions in the project graph, not decision entries |
| 17 | Pending decisions do not block the merge |
| 18 | Sign-offs carry a hash of the signed text; `jidoka-ready` is a tag |
| 19 | The agreement uses the work item's standard fields |
| 20 | Open questions live in the agreement; refine keeps no state |
| 21 | line refuses a story that is not `jidoka-ready` |
| 22 | refine takes the line's decisions to their owners; the project graph catches up |
| 23 | Runs start by hand or from a scheduled pick-up of `jidoka-ready` stories |
| 24 | Two PRs: refine and the agreement first, the autonomous line second |
| 25 | Ready means tag plus valid format plus matching hash |
| 26 | One person may sign all three roles, recorded as `solo` |
| 27 | One `jidoka-*` tag at a time: ready, running, pr, blocked |
| 28 | Claims are refused-on-conflict writes; stale claims are reported, not taken |
| 29 | Scheduled runs: a team machine, a fresh container each, one at a time |
| 30 | Runs keep their state on the pushed branch, not the machine |
| 31 | A service account when there is one, a person's account until then |
| 32 | A resumed run compares the agreement AC by AC |
| 33 | AC IDs are permanent, and tests cite them |
| 34 | Thirteen fixed headings; the hash covers all but the last two |
| 35 | Each PR carries its own tests and eval cases |
| 36 | Azure DevOps and a local file; GitHub Issues later |
| 37 | This note records the design |
| 38 | The boundary file is `story.md`, unnumbered |
| 39 | The line's decisions go to `09-decisions.md`; `story.md` stays read-only |
| 40 | The worktree is created right after the claim |

Two refinements came out of building PR 1. Writes to the agreement use `az
rest` for the same reason the claim does: a write must not overwrite someone
else's edit. And because one hash covers the whole signed text, any change
after sign-off needs every role to sign again, not only the role whose part
changed. refine shows each of them the diff, so re-signing is quick.

## What each PR ships

**PR 1:**

- `src/skills/refine/`: the skill, the agreement format, the gap checklist
  and `scripts/agreement.py`;
- `scripts/test_agreement.py` in `just test`;
- the `refine-three-roles` eval case;
- the renderer skipping Python bytecode;
- `refine` registered as the third entry point, beside `line` and `check`.

**PR 2:**

- the unattended `line`: the readiness check, claim and `story.md`; the
  removed questions; andon and the attempt limits; the decisions log; the
  PR's tables;
- the companion skills without `AskUserQuestion`;
- the pick-up script;
- eval cases for a refused story, a story changed after sign-off, the updated
  minimal and greenfield stories, and a stop with its resume;
- the CLAUDE.md and workflow diagram updates.
