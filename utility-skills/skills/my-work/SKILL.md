---
name: my-work
description: Manage a personal work-tracking system built on an Obsidian vault - thread notes, a TODO hub, a Bases work board, and an HTML review report. Use this whenever the user asks what is pending, what they should focus on today, what is on their plate, what is blocked or waiting on someone, or asks to create/open/update/close a task, item, thread, or follow-up. Also use when they want progress or feedback logged against something they are already tracking ("she came back on the access request", "log that I sent it"), when they want an HTML report to review their work, or when they mention their board, threads, or TODO hub. Trigger even when the user does not name the skill or the vault - phrases like "what should I work on", "add this to my list", "anything blocked?", "generate my work report", or a bare status question about their own workload are all this skill. Do not use it for issue-tracker syncing or daily journal entries if a separate skill owns those.
---

# My Work

Runs a personal work-tracking system that lives in an Obsidian vault as plain markdown. This
skill is mostly careful reading and writing of files, plus two scripts.

The system has a deliberate shape, and the value here comes from respecting it rather than
inventing a new structure each time.

## The model

Two tiers, because not everything deserves the same ceremony:

- **Threads** (`work/threads/*.md`) - one note per item that has a discussion to run, feedback
  to collect, or progress worth logging. This is where real work lives.
- **Quick tasks** - plain `- [ ]` checkboxes in `work/TODOs.md` or wherever the work lives.
  For things that need no discussion.

The distinguishing question is not size, it is *whether anything will accumulate against it*.
"Book the meeting room" is a quick task. "Get the scanner role granted on the security
platform" is a thread, because there will be a back-and-forth with an admin and the answer
matters months later.

## Setup

The scripts locate the vault in this order: a `--vault` argument, then `$OBSIDIAN_VAULT`, then
a `scripts/.vault-path` file, then `~/.config/my-work/vault-path`, then by walking up from the
current directory looking for `.obsidian`. Pin it once:

```bash
mkdir -p ~/.config/my-work && echo /path/to/your/vault > ~/.config/my-work/vault-path
```

The user-level file is the durable option, because a marketplace plugin's directory is versioned
by commit and replaced on every update - anything written beside the scripts is discarded.
`scripts/.vault-path` still wins when present, for a checkout you control; it is gitignored so an
absolute path never enters version control.

## Sources of truth

All paths are relative to the vault root.

| Path | What it is |
|---|---|
| `work/TODOs.md` | The hub. Live queries plus a few hand-maintained lists. |
| `work/threads/*.md` | One note per thread. The real source of truth for work in flight. |
| `work/Work Board.base` | Bases board, cards grouped by `status`. Reads the threads folder. |
| `_templates/Thread.md` | Template for new threads. |
| `work/html/` | Generated HTML reports, and any hand-written report artifacts. |
| `Journals/YYYY-MM-DD Ddd.md` | Daily notes. Capture happens here; it is an inbox, not a tracker. |

Plugins in play: Tasks and Dataview power the hub queries; Bases (core) powers the board.

## Thread anatomy

```markdown
---
type: thread
status: backlog | doing | waiting | done
project: platform
people: the platform admin
due: 2026-08-15
created: 2026-08-04
---

# Title

**Outcome:** one sentence - what "done" actually looks like.

## Progress
- 2026-08-04 - what happened, oldest first

## Discussion points & follow-ups
- [ ] the point to raise or the action to take  #tag
	- 2026-08-04 - what you did about it
	- 2026-08-05 (admin) - what came back

## Links
- [../html/something.html](../html/something.html)
```

The nesting is the whole point: **feedback lives under the question it answers**, not in a
separate log the reader has to correlate by date. When someone responds, append a dated line
under the relevant point rather than starting a new section.

`status` drives the board. The `#doing` *tag* is for individual tasks; thread-level state is
the frontmatter property. Do not conflate them.

## What the user usually wants

### "What's pending / what should I focus on today?"

Start here rather than grepping by hand:

Paths below are relative to this skill's directory, which is given to you as the base directory
when the skill is invoked. `cd` there first, or prefix them with it.

```bash
python3 scripts/status.py          # ranked table
python3 scripts/status.py --json    # same data, structured
```

It prints every live thread ranked by a rough urgency score, with flags explaining why each
one surfaced. Parse frontmatter with this script rather than a regex - `^people:\s*(.*)$`
matches across the newline and captures the *next* key when the value is empty.

Then give a short prioritised answer, **not** a reprint of the table. The user can read a table
themselves; the value added is judgement about what actually deserves today.

The columns worth reasoning about:

- **`due_in`** - overdue or imminent beats everything.
- **`idle_days`** - days since the newest dated line anywhere in the note. High idle on a
  `waiting` thread means the other person has forgotten. A two-minute chase often beats an
  hour of new work.
- **`age_days`** - days since `created`. This is the honest one after a bulk migration, when
  every note has been stamped with today's date and `idle` reads 0 across the board.
- **`open_points`** on a `doing` thread - work in progress that is drifting.
- **`outcome_missing`** - unshaped, and cheap to fix while you are looking at it.

Say plainly when something looks abandoned. A three-month-old `waiting` thread usually needs
killing or restarting, not another polite bump, and the user is better served by hearing that
than by seeing it politely re-listed every morning.

### "Create a task for X"

Judge which tier it belongs to and say which you chose. For a thread:

1. Read `_templates/Thread.md` and follow its shape.
2. Write `work/threads/<Title>.md`. Use a readable title with spaces - it becomes the card
   label and the wikilink target.
3. Fill frontmatter honestly. Set `status: backlog` unless they are starting now (`doing`) or
   it is already blocked on a person (`waiting`, and put the person in `people`).
4. Write the **Outcome** line. If it cannot be written, that is a signal the task is not yet
   shaped - say so and ask one clarifying question rather than writing a vague placeholder.
5. Seed the discussion points with what is genuinely known. Do not pad with generic filler
   like "research the topic"; an empty section is more honest and less annoying than noise.
6. Add a first dated Progress line recording where this came from.

**The board updates itself.** `Work Board.base` queries the folder, so there is no separate
registration step. Do not hand-edit the `.base` file to add a card.

For a quick task, just append a `- [ ]` line to the relevant section of `work/TODOs.md`.

### "Log progress / feedback on X"

Find the thread, then append a dated line **under the specific point it relates to**. If it
relates to no existing point, either add a new point or add it to Progress, whichever fits.

Attribute feedback to whoever gave it: `- 2026-08-05 (the reviewer) - prefers the scoped
option`. Months later that attribution is often the most valuable part of the line.

Update `status` when reality changed - moving to `waiting` when the ball is in someone else's
court is what keeps the board honest.

### "Generate the HTML report"

```bash
python3 scripts/build_report.py --open
```

Writes `work/html/work-review-<date>.html` grouped by status, with each thread's open points
and their nested feedback. `--open` launches it in the browser. `--out PATH` overrides the
destination. The script has no dependencies and re-reads the vault every run, so it is always
current - never hand-write this file.

This is for reviewing away from Obsidian or sharing a snapshot with someone who lacks the
vault. For a deep-dive artifact on a single thread (like a report written for an external
reader), write bespoke HTML into `work/html/` and link it from that thread's Links section.

### "Close X"

Set `status: done`, tick the remaining points that are genuinely done, and add a closing
Progress line. Leave the note in place - the board and report filter `done` out of the live
view, and the history stays useful.

## Things that will bite you

- **Never physically move a task into the hub.** Tasks live where the work lives; the hub
  aggregates them with queries. Moving them orphans them from their context.
- **Not every checkbox is a todo.** Spec folders often use checkbox syntax for acceptance
  criteria, and runbooks use it for steps. Rolling those into a todo list can add dozens of
  phantom items. The hub queries carry an exclusion list - keep it current when editing them.
- **Journals are an inbox, not a tracker.** Items captured there and left alone go stale
  invisibly. If there are old open checkboxes in `Journals/`, surface them.
- **Wikilinks resolve by basename**, so `[[Some Thread]]` works from anywhere, but only while
  the name is unique.
- Query and Bases syntax has sharp edges that have already cost debugging time. Before editing
  `work/TODOs.md` query blocks or `work/Work Board.base`, read
  `references/vault-conventions.md` in this skill.

## Boundaries

This skill owns the vault. If a separate skill owns the team's issue tracker or the daily
journal entry, leave those to it and say so rather than writing to both. Two skills writing to
the same tracker is how duplicate work items get created.
