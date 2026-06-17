---
name: spec-me
description: Interviews the user in depth about a spec file, then rewrites it with the gathered detail. Use when the user wants to flesh out a spec — e.g. "/spec-me @SPEC.md". Requires a spec file to be passed with @.
args:
  - name: spec_file
    description: The spec file to interview against and write back to (pass with @, e.g. @SPEC.md)
    required: true
---

Read the spec file at `{{spec_file}}` carefully. Your job is to interview the user until every gap, assumption, and open question in that spec has been resolved — then rewrite the file with everything you've learned.

## Interview phase

Use `AskUserQuestion` to interview the user. Go deep. Cover anything that is underspecified, ambiguous, or missing:

- **Technical implementation** — architecture choices, data models, API contracts, edge cases, error handling, performance constraints
- **UI & UX** — user flows, states, empty states, loading/error feedback, accessibility, mobile vs desktop
- **Tradeoffs** — what was ruled out and why, what risks exist, what the acceptable failure modes are
- **Concerns** — security, scale, privacy, compliance, dependencies, rollback
- **Success criteria** — how will you know this is done? what does "good" look like?

**Do not ask obvious questions** — don't ask things that are already clearly answered in the spec, and don't ask leading questions with obvious answers. Every question should surface something genuinely unknown or underexplored.

Keep going round after round until you have no remaining open questions. After each round, review what you've learned and identify what's still unclear before asking the next set.

## Write phase

Once the interview is complete, rewrite `{{spec_file}}` with a complete, detailed spec incorporating everything discussed. Structure it clearly with sections for context, requirements, design decisions, open questions resolved, and any remaining risks or constraints.
