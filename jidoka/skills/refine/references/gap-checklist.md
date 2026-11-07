# Gap checklist

Run every General check, then the groups the story touches. Each check names
the role that owns the answer; a gap becomes a question in section 8 with that
owner. Before asking anyone, try to answer the check from the code, the
tracker or the project context: a check the code answers is a fact you record,
not a question.

Severity: **HIGH** blocks building or contradicts something (another story,
the code, a recorded decision); **MEDIUM** is a detail the line would
otherwise have to guess; **LOW** is cosmetic or can safely wait.

## General

| Check | Owner |
| --- | --- |
| The statement names a specific role and a benefit, not an implementation | BA |
| Every behaviour in the description has an AC, and every AC traces to the description | BA |
| ACs cover the failure paths, not only the happy path | BA |
| Each Then is observable: status code, error code, message text, what changed | BA |
| Terms match the sibling stories and the project's glossary; no two names for one thing | BA |
| No AC contradicts a sibling story, the current behaviour or a recorded decision | BA |
| What is out of scope is said, with the story that covers it | BA |
| Dependencies on other stories, teams or systems are named, with their state | Dev Lead |
| Placeholders are gone ("TBD", "xxx", "documented separately") | BA |

## API

| Check | Owner |
| --- | --- |
| Method matches the behaviour (create, replace, partial update, action, delete) | Dev Lead |
| Path, parameters and request body are defined, mandatory fields marked | Dev Lead |
| Success status and response body are defined ("no body" counts) | Dev Lead |
| Every error has a status, an error code and the shared error envelope | Dev Lead |
| Authentication and the 401 / 403 / 404 distinction are stated, or marked as handled elsewhere | Dev Lead |
| Idempotency, concurrency (two edits at once) and pagination are decided where they apply | Dev Lead |

## User interface

| Check | Owner |
| --- | --- |
| Loading, empty, error and success states are described | BA |
| Every action's outcome is visible: what the user sees after it | BA |
| Validation messages are worded, and say when they appear | BA |
| Designs are linked, and the story says which one wins where they differ | BA |
| Keyboard use and screen-reader labels for new controls | QE |

## Data

| Check | Owner |
| --- | --- |
| Fields, types, limits and defaults are defined | Dev Lead |
| Schema or migration impact is stated, including existing rows | Dev Lead |
| Who may see and change each piece of data; nothing sensitive leaks into logs | Dev Lead |
| Dates and times: time zone, format, boundaries ("within 2 hours" of what) | BA |
| Retention, deletion and history, where the story touches them | BA |

## Non-functional

| Check | Owner |
| --- | --- |
| Performance or volume expectations that change the design | Dev Lead |
| Configuration: what is configurable, and its default | Dev Lead |
| Audit and observability: what must be recorded | Dev Lead |
| Backward compatibility for existing clients and data | Dev Lead |

## Testing and evidence

| Check | Owner |
| --- | --- |
| Every AC has a scenario QE would run | QE |
| Every AC names the evidence that proves it: a screenshot, a response body, a test report | QE |
| Test data and user roles exist, or the story says how they are made | QE |
| Negative and boundary cases are covered (limits, the cut-off itself, empty input) | QE |
| Where test credentials are kept is known; the credentials never go in the story | QE |
| Anything that cannot be tested automatically is called out, with how it will be shown | QE |

## Project checks

A project can add its own checks in `docs/project_context/refine-checklist.md`
(domain rules, standards, regulations), in the same two-column form. Run them
after these.
