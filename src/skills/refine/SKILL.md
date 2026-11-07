---
name: refine
description: Runs a user story's refinement with its BA, Dev Lead and QE - pulls the story (an Azure DevOps work item or a Markdown file), grounds every question in the codebase, works the gaps in rounds tagged by role, writes the agreement that /jidoka:line builds from, and records each role's sign-off before marking the story jidoka-ready. Live with the three roles in one session, one role at a time with --role, or one person for all three with --solo. Also takes the owning roles through decisions a line run made on its own.
argument-hint: "[work item URL or id, or story file path] [--role ba|dev-lead|qe] [--solo]"
disable-model-invocation: true
---

# Refine

**Announce at start:** "I'm using the jidoka:refine skill to take this story
to an agreement the line can build from."

You run the human half of jidoka. BA, Dev Lead and QE settle every decision
here, and you write those decisions down as **the agreement**: the document
`line` builds the story from, unattended, without anyone to ask. Whatever this
session leaves unsettled either stops the line or becomes a decision it takes
alone, so settle it here.

- **Format.** `references/agreement-format.md` holds the agreement's layout,
  its rules and how to write it. Read it before Step 1.
- **Script.** `scripts/agreement.py` in this skill's folder (on Claude Code,
  `${CLAUDE_SKILL_DIR}/scripts/agreement.py`). Run it by its absolute path
  with `python3`, or `python` on Windows; below, `agreement.py` stands for
  that. It needs nothing beyond Python. It is the only thing that converts,
  hashes, signs and marks the agreement: never write a sign-off row, a hash,
  a Status line or a jidoka tag yourself.
- **Questions.** Ask through `AskUserQuestion` where it is offered, otherwise
  as one chat message per round, in the format of Step 4.
- **Writes.** Running this skill on a story is the request to write its
  agreement. Change only that story's Description, Acceptance Criteria and
  jidoka tag, and only through `agreement.py`. Never its title, state or
  assignee, and never another work item: inconsistencies in siblings go in the
  report as follow-ups. The one other write is Step 3's update of the
  project's `graph.md`, a file in the repository, not the tracker.

## Step 1 - Source and mode

1. **Where the story lives.**
   - A work item URL, or an id with an organization (from the user or
     `az devops configure --list`): tracker `ado`. It needs `az login` and
     the azure-devops extension. Your working copy is
     `{temp dir}/jidoka-refine/{id}.md`, where the temp dir is `$TMPDIR`,
     else `/tmp`, else `%TEMP%`. It stays out of the repository; the work item
     is the record.
   - A Markdown file: tracker `file`. The file is the record.
   - Story text pasted in: ask once where its file goes, default
     `docs/stories/{id}-{slug}.md`, and use tracker `file`.
2. **Mode.**
   - **Live** (the default): BA, Dev Lead and QE are in the session. Ask once
     who is here and in which role. Ask every role's questions.
   - **`--role ba|dev-lead|qe`**: one person, in their own session. Ask only
     that role's questions, leave the others open in section 8, and sign
     only for that role (Mode `own-account`).
   - **`--solo`**: one person answers and signs for all three roles (Mode
     `solo`), as on a project with one developer.

## Step 2 - Context

1. **Read the story.**
   - `ado`: run `agreement.py pull --ado {url} -o {working copy}`. Then read
     its parent, siblings and linked items
     (`az boards work-item show --id {n} --org {org}`) and its discussion,
     through `az devops invoke --area wit --resource comments
     --route-parameters project={project} workItemId={id} --org {org}`. If the
     discussion cannot be read, say so and go on.
   - `file`: read the file, or the pasted text, and the items it links to.

   Write the context map:

   ```text
   Target:   {id} - {title} ({state})
   Parent:   {id} - {title}
   Siblings: {id} - {title}, ...
   Linked:   {id} - {title} (why it is linked)
   ```

2. **Pick up where it stands.** Its Status decides what this session may do:
   - **`jidoka-running`:** a line run is building it. Change nothing; say the
     change waits until the run ends, and stop.
   - **`jidoka-pr`, or later:** it is built. A change now is a new story, or
     a change to the open pull request. Say so, and stop.
   - **`jidoka-blocked`:** a line run stopped on a question, which is in the
     story's comments (or the branch's `andon.md` for a story file). That
     question is this session's first round. The story stays blocked until
     Step 7 marks it ready again.
   - **`jidoka-ready`:** every role signed it, and any change means every role
     signs again. Before you change anything, run
     `agreement.py status {file} --set draft`, so no line run builds it
     meanwhile.
   - **`draft`:** go on.

   If the text already follows the agreement format, run
   `agreement.py check {file}` and continue from it. Its section 8 holds the
   questions earlier passes left open, and section 13 holds who has signed. If
   section 12 lists line decisions with Status `pending`, do Step 3 first. Raw
   story text is the input to Step 6, which rewrites it into the format.
3. **Ground it in the code.** Answering facts is your job; deciding is the
   roles'. Never ask a person something the code, the tracker or the project
   context already answers. Record it with its source instead. In a checkout
   of the product's repository:
   - Read `docs/project_context/prod_spec/graph.md` if it exists: the
     capabilities and entities the story touches, decisions that are
     superseded or in conflict, and open questions. Otherwise read
     `docs/project_context/00_index.md`.
   - Trace the closest similar feature end to end yourself, not through an
     agent: later rounds look things up again, in code you have already read.
     Collect what the questions will need: where the story and the code
     disagree, the error envelope, sibling endpoints and screens,
     conventions, test patterns, seed users.
   - Find the branches the story could land on, for the Dev Lead's base
     question: the default branch
     (`git symbolic-ref --short refs/remotes/origin/HEAD`), and the release
     lines when a `lines.tsv` sits in a folder above the repository (an agent
     harness). Its `# line env <repo>...` header names a column per
     repository: this repository's is the one named like its folder, and a
     cell's first branch is the line's. A line whose branch is missing from
     the remote is not a choice; say so.
   - No source code yet (`project-setup`'s Step 1 says what counts): the
     Dev Lead's questions include the stack. Use `project-setup`'s Step 2
     questions when that skill is installed. Otherwise ask in plain words for
     the layers and their technology, the project name, how passwords are
     verified, the look, and whether the skeleton merges or waits on its own
     branch. Record the answers on one `Stack:` line in section 6, in the form
     `project-setup`'s Step 2 shows. The line builds the skeleton from that
     line alone.

   Without a checkout, say so once. Mark any recommendation that would need
   the code "not checked against the code".

## Step 3 - The line's decisions (only when section 12 has pending rows)

A line run decided these alone, because the agreement did not settle them.
Put each `pending` row to the role in its Confirm by column, grouped by role,
in one round:

- **Confirmed:** add a decisions-log row (`D-n`, Rationale ending "from
  AD-m"), and set the row's Status to `confirmed`.
- **Rejected:** set Status `rejected`, and write what is wanted instead as a
  changed or new AC or a decision. The next line run makes the change.

Either way the signed text changes, so the story goes back through Step 7.
In a checkout, also record the outcome in
`docs/project_context/prod_spec/graph.md`. A confirmed decision's open
question becomes a decision entry: use the format the `context-updater` skill
uses when it is installed, else a dated entry with the decision, its
rationale and the `AD-n` it came from. A rejected one stays an open question
until the next run resolves it.

## Step 4 - Gaps, then rounds

1. **Find the gaps.** Apply `references/gap-checklist.md`, then the project's
   `docs/project_context/refine-checklist.md` if it exists. Every gap becomes
   a section 8 row (`Q-n`), with an owner, a severity and Status `open`:
   - **BA:** behaviour, scope, rules, wording, cross-story consistency.
   - **Dev Lead:** contract, data, non-functional requirements, constraints,
     dependencies, the stack.
   - **QE:** scenarios, test data, failure and boundary cases, the evidence
     for each AC.

   Show the count by severity and role, and each HIGH gap in one line. Do not
   paste the whole list.
2. **Work the rounds.** The gaps form a tree: some answers depend on others.
   Each round asks the **frontier**, meaning every open question whose
   prerequisites are settled. A question that depends on another one still
   open waits for a later round. Ask HIGH first, then MEDIUM. Each question
   carries its owner, what the story says now, why that is a gap, concrete
   options, and your recommended answer, worded so that "yes" accepts it:

   ```text
   ❓ **Q3 [Dev Lead] - Page size**: The story says "list the appointments"
   but not how many come back at once. The other list endpoints page at 50
   with `?page=`.

   ➡️ Page at 50 with `?page=`, as the other list endpoints do.
   ```

   Accept terse answers and map them to their question. When an answer points
   at another work item, read it before the next round. Each answer sets its
   question to `answered`, and adds a decisions-log row with the rationale,
   the rejected alternatives, the owner and today's date. In `--role` mode
   ask only that role's frontier. Once no HIGH or MEDIUM question is open,
   ask once whether any LOW one should be settled now. Those left stay open
   or `deferred`: the line stops if it meets a deferred one.
3. **Someone missing.** Their questions stay `open` in section 8, which is
   how they reach that role: through their own `--role` pass. If they will
   not run one, offer a questionnaire, a convenience for whoever is present to
   send them. Write it to `{temp dir}/jidoka-refine/{id}-{role}-questions.md`,
   with that role's open questions, most important first, each with its
   context, why it matters and an answer stub. Their answers are entered
   later, by them in a `--role` pass, or by anyone pasting them into a
   session, which records them as Step 4.2 does.

## Step 5 - Persist before you stop

If the session ends with questions still open, still do Step 6 for what is
settled. Section 8 carries the rest, so the next pass, by another role or on
another day, starts from the record and not from your memory.

## Step 6 - Write the agreement

1. Start from the text pulled in Step 2. For raw story text,
   `agreement.py new --id {id} --title "{title}" --tracker {file | url}`
   prints the empty layout; fill it in and write it over the raw text. On
   `ado` the working copy is already pulled. Keep its title and metadata
   lines, and replace the rest with the agreement.
2. Fill every section as `references/agreement-format.md` says, under its
   writing rules. Those rules come from a handoff to an agent with no
   context: decisions, not discussion; behaviour, not procedure; no file
   paths; every rule written out, never only referenced; no secrets and no
   real people's data. A story landing on a branch other than the default
   gets a `Base:` line in section 10 naming that branch, never the release
   line; the decisions log names the line it was chosen for.
3. `agreement.py check {file}` until it prints `OK`.
4. **`ado`:** `agreement.py push {working copy}`. After a push, the working
   copy holds what the work item reads back: that text is what the roles
   sign. **`file`:** the file is written; it is the record.

   The push is refused if anyone saved the work item since your pull. Then do
   not pull over your working copy, which holds your unpushed changes:
   1. Pull to a second file, `agreement.py pull --ado {url} -o {temp
      dir}/jidoka-refine/{id}.theirs.md`. It holds their edit and the new
      Rev.
   2. Carry your changes into it.
   3. Check it and push it.
   4. Use it as the working copy from then on.

## Step 7 - Sign-off

Sign-off happens once, at the end, on the final text. Every answer changes
the text, and a changed text needs every signature again, so nobody signs
while a question is still open.

1. Run `agreement.py check --ready {file}`. It may list only missing
   sign-offs; any other problem goes back to Step 4 or 6. **If a HIGH or
   MEDIUM question is still open**, whoever owns it, nobody signs this
   session. That covers another role's question in a `--role` pass, and a role
   missing from a live one. Leave the story `draft`, and report who must
   answer what. The pass that closes the last such question starts the
   sign-off, and every role then signs the final text.
2. Show the agreement as it now reads: the working copy after the push, or
   the file. Each role signs that text, not your summary of it. On a pass that
   changed a signed agreement, also show what changed: each section this
   session edited, before and after (for a story file, `git diff`). The
   agreement keeps only a hash of what was signed, not the text.
3. Ask each role present to sign off by name, and sign each one who agrees:

   ```bash
   agreement.py sign {file} --role "Dev Lead" --name "{name}" --mode live
   ```

   - **`live`:** signed in this session.
   - **`own-account`:** signed in their own `--role` session. The name comes
     from `az account show --query user.name -o tsv`, or `git config
     user.name` for a story file.
   - **`solo`:** one person signing more than one role. They sign every one
     of their roles `solo`, in a live session or with `--solo`, and the
     script refuses a second role signed any other way.

   A role that declines names what must change; go back to Step 4.
4. **`ado`:** push again, so the sign-offs are on the work item. The push
   prints the hash the read-back text has. If it differs from the hash the
   roles signed, the round trip changed the text: show them the read-back,
   and they sign again.
5. With every role signed, run
   `agreement.py status {file} --set jidoka-ready`. It re-checks the work
   item itself, or the file, and refuses unless every rule in the format's
   Ready section holds. From then on, any change to the agreement means every
   role signs again, which is why Step 2.2 sets a ready story back to
   `draft` first.

## Step 8 - Report

The story and its Status. Who signed, with the hash. The number of questions
asked and answered, and those left open or deferred, with their owners. The
decisions logged. Follow-ups for other stories. Then the next step: once it
is `jidoka-ready`, `/jidoka:line {story}` builds it unattended, or the
scheduled pick-up does. A `file` agreement
must reach the base branch before a run elsewhere can read it. Say so, and
commit it only if asked.
