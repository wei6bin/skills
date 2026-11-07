# The agreement

The agreement is the one document between `refine` and `line`. BA, Dev Lead
and QE agree it and sign it in `refine`; `line` builds from it with nobody
there to ask. It is a handoff to an agent that has none of the session's
context, may start days later on another machine, and must not guess.

It has two forms and one converter. On Azure DevOps it lives in the work
item's own fields: the Acceptance Criteria field holds section 4 and the
Description holds every other section. Without a tracker it is a Markdown
file. `scripts/agreement.py` is the only code that moves it between the two,
hashes it and records sign-offs, so both skills read the same text; never
write a sign-off row, a hash, the Status line or a jidoka tag by hand.

## Layout

A title line, three metadata lines, then thirteen sections with fixed
headings, in this order. `agreement.py new` writes the empty layout and
`agreement.py check` reports every departure from it.

```markdown
# 4711 - Cancel a pending appointment

Tracker: ado https://dev.azure.com/Contoso/Bookings/_workitems/edit/4711
Status: draft
Rev: 18

## 1. Statement

As a patient, I want to cancel a pending appointment, so that the slot is
freed for someone else.

## 2. Current behaviour

Appointments can be booked and listed, not cancelled. A patient phones the
clinic, and staff cancel it in the back office.

## 3. Desired behaviour

The patient cancels from their appointment list. A pending appointment more
than 2 hours away is cancelled and its slot released; a later one is refused,
with a message saying to phone the clinic.

## 4. Acceptance criteria

| ID | Given | When | Then |
| --- | --- | --- | --- |
| AC-1 | a pending appointment of the caller, more than 2 hours away | they cancel it | 200; the appointment reads `cancelled` and its slot is bookable again |
| AC-2 | a pending appointment less than 2 hours away | they cancel it | 409, error code `too_late`; the list shows "Please call the clinic to cancel" |
| AC-3 | another patient's appointment | they cancel it | 404, error code `appointment_not_found`; nothing changes |

## 5. QE: scenarios and evidence

| AC | Scenario | Evidence | Data |
| --- | --- | --- | --- |
| AC-1 | cancel from the list | screenshot of the list after cancel; the response body | demo patient with one appointment tomorrow |
| AC-2 | cancel one starting in an hour | screenshot of the message; the response body | appointment seeded 1 hour ahead |
| AC-3 | cancel by another patient's id | the response body; a test proving the row is unchanged | two demo patients |

Demo users and their credentials: see the project's demo-accounts document.

## 6. Dev Lead: decisions and constraints

- Contract: `POST /appointments/{id}/actions/cancel`, no body; errors use the
  existing envelope `{ "error": { "code": ..., "message": ... } }`.
- The 2-hour rule is read from configuration, default 120 minutes.
- No schema change: `cancelled` is already a status value.

## 7. Out of scope

- Staff cancelling on a patient's behalf (story 4712).
- Notifying the clinician.

## 8. Open questions

| ID | Question | Owner | Severity | Status |
| --- | --- | --- | --- | --- |
| Q-1 | Is the cut-off 2 hours for every clinic? | BA | HIGH | answered |
| Q-2 | Show the cut-off time in the list? | BA | LOW | deferred |

## 9. Decisions log

| ID | Decision | Rationale | Rejected | Owner | Date |
| --- | --- | --- | --- | --- | --- |
| D-1 | One cut-off for all clinics, configurable | No clinic asked for its own | Per-clinic cut-off | BA | 2026-11-06 |
| D-2 | An action endpoint, not DELETE | The appointment is kept, its status changes | DELETE /appointments/{id} | Dev Lead | 2026-11-06 |

## 10. Autonomy policy

Exit: pr
Stop also on: any change to how slots are released.

## 11. References and suggested skills

- Parent feature 4700; sibling 4702 books appointments (context only).
- Project context: CAP-07 Appointments, DR-114 slot release.
- Suggested skills: the project's frontend conventions skill.

## 12. Decisions made by the line

None.

## 13. Sign-off

| Role | Name | Date | Mode | Hash |
| --- | --- | --- | --- | --- |
| BA | A. Tan | 2026-11-06 | live | sha256:3f9c0a1b2c3d4e5f |
| Dev Lead | B. Lim | 2026-11-06 | live | sha256:3f9c0a1b2c3d4e5f |
| QE | C. Ng | 2026-11-06 | own-account | sha256:3f9c0a1b2c3d4e5f |
```

## Metadata

- **Tracker** - `file`, or `ado` followed by a space and the work item's web
  URL.
- **Status** - `draft`, `jidoka-ready`, `jidoka-running`, `jidoka-pr` or
  `jidoka-blocked`. On Azure DevOps it is the work item's one `jidoka-*` tag
  (`pull` reads it, `status --set` writes it); in a file it is this line.
  `refine` sets only `draft` and `jidoka-ready`; the other three are the line's.
- **Rev** - Azure DevOps only: the revision `pull` read. Every write sends it,
  and Azure DevOps refuses the write if anyone saved the work item since.

## The sections

| # | Owner | What goes in it |
| --- | --- | --- |
| 1 | BA | One story statement: "As a {specific role}, I want {capability}, so that {benefit}". |
| 2 | BA | What happens today, so the line knows what it builds on. `None.` for a new capability with nothing before it. |
| 3 | BA | What happens after, from the user's side, edge cases included. Behaviour, not implementation. |
| 4 | BA | Acceptance criteria, one row each (rules below). |
| 5 | QE | For every active AC: a scenario, the evidence that proves it, the data it needs. Then the user roles and where test credentials are kept. |
| 6 | Dev Lead | Contract decisions (paths, status codes, error shape), key interfaces, non-functional requirements, constraints, dependencies on other stories. For a new project, a `Stack:` line. |
| 7 | BA | What this story does not do, each with the story that does it when there is one. |
| 8 | any | Questions, each with an owner, a severity and a status. |
| 9 | any | Every decision taken in the session, with the alternatives turned down. |
| 10 | Dev Lead | `Exit: pr` (open a pull request) or `Exit: merge` (merge locally: only a repository with no remote), then `Stop also on:` and any condition beyond the line's defaults that must stop it. |
| 11 | any | References for context, and the project skills the line should load. |
| 12 | line | The line's own decisions, written by the line. `None.` until it runs. |
| 13 | refine | One row per role, written by `agreement.py sign`. |

A section with nothing in it holds `None.`; an empty section fails the check.

**Acceptance criteria.** IDs are `AC-1`, `AC-2`, ... in the order they were
first written, and are never reused or renumbered: tests, evidence and the
line's pull request cite them, so an ID must mean one thing for the story's
whole life. A dropped AC keeps its row as `AC-3 (removed)` with its other
cells empty, and a new AC takes the next unused number. Every active AC fills
Given, When and Then, and Then names the observable result exactly: the
status code, the error code, the message the user reads, what changed.

**Tables.** Columns are fixed:

| Section | Columns |
| --- | --- |
| 4 | ID, Given, When, Then |
| 5 | AC, Scenario, Evidence, Data |
| 8 | ID (`Q-1`), Question, Owner, Severity, Status |
| 9 | ID (`D-1`), Decision, Rationale, Rejected, Owner, Date |
| 12 | ID (`AD-1`), Story didn't say, Line chose, Why, Confirm by, Undo by, Status |
| 13 | Role, Name, Date, Mode, Hash |

Owner and Confirm by are `BA`, `Dev Lead` or `QE`. Severity is `HIGH`,
`MEDIUM` or `LOW`. A question's Status is `open`, `answered` or `deferred`; a
line decision's is `pending`, `confirmed` or `rejected`. Mode is `live`
(signed in a refine session the person attended), `own-account` (signed in
their own session, under their own `az` login) or `solo` (one person signed
for several roles). Dates are `YYYY-MM-DD`. A table section with no rows holds
`None.` instead.

## Writing it

The agreement is a handoff, not minutes. Write it so an agent that was not in
the room can build the story from it alone, weeks from now:

- **Decisions, not discussion.** The outcome goes in the section it belongs
  to; the reasoning and the alternatives turned down go in the decisions log.
  The question-and-answer trail stays behind.
- **Behaviour, not procedure.** Say what the system does, not how to change
  it. Name interfaces, contracts and config shapes; never file paths or line
  numbers, which go stale before the line runs.
- **Every rule written out.** References are context only. Anything the line
  must obey is stated here in full, because a referenced item can change after
  sign-off without changing this agreement's hash: not "errors as in story
  4702" but the error shape itself.
- **Reference, don't copy.** Parent, siblings, designs and project-context
  entries are named by ID or URL in section 11, not pasted in.
- **No secrets, no real people's data.** Credentials appear only as a pointer
  to where they are kept; example data is made up. The check refuses
  recognisable keys and tokens.
- **Suggested skills** are the project's own skills the line should load
  (its domain or frontend conventions), by name.

## The hash and the sign-off

`agreement.py hash` hashes the title and sections 1-11 after normalising
line endings, trailing spaces, blank lines and table padding, so a formatter
cannot change it. Sections 12 and 13 are outside it: the line's record and the
sign-off itself change nothing anyone signed. On Azure DevOps the hash is
taken from what the work item reads back after a push, never from what was
sent, because the editor may rewrite the HTML.

`agreement.py sign` writes a role's row at the current hash. Any later change
to sections 1-11 changes the hash, and every role signs again; `check --ready`
names each stale sign-off.

## Ready

`agreement.py check --ready` passes, and `status --set jidoka-ready` is then
allowed, only when:

- the format check passes;
- sections 1 and 3 are written;
- there is at least one active AC, or a new project's `Stack:` line in
  section 6;
- every active AC has a scenario and evidence in section 5;
- no HIGH or MEDIUM question is `open` (LOW questions may stay open, and a
  deferred question is one the line stops on if it meets it);
- BA, Dev Lead and QE have each signed at the current hash, and a name that
  signs more than one role does so with Mode `solo`.
