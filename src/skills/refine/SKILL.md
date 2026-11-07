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
  report as follow-ups.

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
     through `az devops invoke` (area `wit`, resource `comments`). If the
     discussion cannot be read, say so and go on.
   - `file`: read the file and the items it links to.

   Write the context map:

   ```text
   Target:   {id} - {title} ({state})
   Parent:   {id} - {title}
   Siblings: {id} - {title}, ...
   Linked:   {id} - {title} (why it is linked)
   ```

2. **Pick up where it stands.** If the text already follows the agreement
   format, run `agreement.py check` and continue from it. Its section 8 holds
   the questions earlier passes left open, and section 13 holds who has
   signed. If section 12 lists line decisions with Status `pending`, do Step
   3 first. Raw story text is the input to Step 6, which rewrites it into the
   format.
3. **Ground it in the code.** Answering facts is your job; deciding is the
   roles'. Never ask a person something the code, the tracker or the project
   context already answers. Record it with its source instead. In a checkout
   of the product's repository:
   - Read `docs/project_context/prod_spec/graph.md` if it exists: the
     capabilities and entities the story touches, decisions that are
     superseded or in conflict, and open questions. Otherwise read
     `docs/project_context/00_index.md`.
   - Trace the closest similar feature end to end. Use one `code-explorer`
     agent (`agent_type: "jidoka:code-explorer"`) if the task tool offers
     it, else do it yourself. Collect what the questions will need: the error
     envelope, sibling endpoints and screens, conventions, test patterns, seed
     users.
   - No source code yet (`project-setup`'s Step 1 says what counts): the
     Dev Lead's questions include the stack. Use `project-setup`'s Step 2
     questions when that skill is installed, otherwise ask in plain words,
     and record the answers on a `Stack:` line in section 6.

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
question becomes a decision entry, in the format the `context-updater` skill
uses. A rejected one stays an open question until the next run resolves it.

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
3. **Someone missing.** If a role cannot be in the room and will not run a
   `--role` pass, offer a questionnaire: `{temp dir}/refine-{id}-{role}.md`,
   with that role's open questions, most important first, each with its
   context, why it matters and an answer stub. Their answers come back
   through a later session.

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
   real people's data.
3. `agreement.py check {file}` until it prints `OK`.
4. **`ado`:** `agreement.py push {working copy}`. It refuses if anyone saved
   the work item since your pull. Then pull again, merge your text into theirs
   by hand, check and push. After a push, the working copy holds what the work
   item reads back: that text is what the roles sign. **`file`:** the file is
   written; it is the record.

## Step 7 - Sign-off

1. `agreement.py check --ready {file}` may list only missing sign-offs. Any
   other problem goes back to Step 4 or 6.
2. Show the agreement as it now reads: the working copy after the push, or
   the file. On a later pass, show the diff against what was last signed. Each
   role signs that text, not your summary of it.
3. Ask each role present to sign off by name, and sign each one who agrees:

   ```bash
   agreement.py sign {file} --role "Dev Lead" --name "{name}" --mode live
   ```

   Use `--mode live` in a live session, `own-account` for a `--role` pass
   (the name from `az account show --query user.name -o tsv`, or `git config
   user.name` for a file), and `solo` with `--solo`. A role that declines
   names what must change; go back to Step 4.
4. `ado`: push again, so the sign-offs are on the work item.
5. With every role signed, run `agreement.py status {file} --set
   jidoka-ready`. It re-checks the work item itself, or the file, and refuses
   unless every rule in the format's Ready section holds. Any later change to
   the agreement means every role signs again. Then run `--set draft` until
   they have.

## Step 8 - Report

The story and its Status. Who signed, with the hash. The number of questions
asked and answered, and those left open or deferred, with their owners. The
decisions logged. Follow-ups for other stories. Then the next step:
`/jidoka:line {story}` builds it once it is `jidoka-ready`. A `file` agreement
must reach the base branch before a run elsewhere can read it. Say so, and
commit it only if asked.
