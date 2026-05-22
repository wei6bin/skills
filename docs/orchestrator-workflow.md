# Orchestrator workflow

The `orchestrator` skill drives a feature from a user story to a merged PR
through 10 phases. Each phase dispatches helper subagents or invokes companion
skills as needed. The diagram below maps phase → components → artifacts.

```mermaid
flowchart TD
    Start([User story / AC / ADO ticket]) --> P1

    subgraph P1[Phase 1 — Discovery]
        P1A[Capture title, ACs,<br/>priority, ticket ID]
    end

    subgraph P2[Phase 2 — Codebase Exploration]
        P2A[Read docs/project_context/]
        P2B[2–3× code-explorer<br/>parallel subagents]
        P2C[codebase-context-builder<br/>skill if context missing]
        P2A --> P2B
        P2C -.bootstrap.-> P2A
    end

    subgraph P3[Phase 3 — Clarifying Questions]
        P3A[One question at a time<br/>with recommended answer]
    end

    subgraph P4[Phase 4 — Architecture Design]
        P4A[1× code-architect<br/>subagent]
        P4B[vertical-slicing skill<br/>guides slice shape]
        P4B -.guides.-> P4A
    end

    subgraph P5[Phase 5 — Write Documents]
        P5W[git-worktrees skill<br/>isolate branch first]
        P5W --> P5D[("docs/new-feature/{id}/")]
        P5D --> F0[00-overview.md]
        P5D --> F1[01-business-plan.md]
        P5D --> F2[02-technical-plan.md]
        P5D --> F3[03-implementation-plan.md]
        P5D --> F4[04-task-plan.md]
        P5D --> F5[05-test-plan.md]
    end

    subgraph P6[Phase 6 — Quality Review]
        P6A[2× plan-reviewer<br/>parallel subagents]
    end

    subgraph P7[Phase 7 — Summary]
        P7A[Decisions, risks,<br/>next steps]
    end

    subgraph P8[Phase 8 — Slice-by-Slice Implementation]
        direction TB
        P8L{{For each slice}}
        P8L --> P8B[impl-backend subagent<br/>TDD red-green-refactor]
        P8B --> P8F[impl-frontend subagent<br/>TDD against real backend]
        P8F --> P8S[impl-simplify subagent<br/>scoped to this slice]
        P8S --> P8C[context-updater skill<br/>capture product knowledge]
        P8C --> P8E[Run slice e2e test<br/>+ checkpoint commit]
        P8E -.next slice.-> P8L
    end

    subgraph P9[Phase 9 — Test Plan Walkthrough]
        P9A[test-plan-walker subagent<br/>clean context]
        P9A --> P9T[test-plan-walkthrough skill<br/>drive 05-test-plan.md demos]
        P9T --> P9R[("06-walkthrough.md<br/>+ screenshots/")]
        P9R --> P9G{ALL_GREEN?}
        P9G -.FIXES_NEEDED.-> P8L
    end

    subgraph P10[Phase 10 — Branch Completion]
        P10A[raise-pr skill]
        P10A --> P10B[Run full test suite]
        P10B --> P10C{Merge / PR /<br/>keep / discard}
        P10C --> P10D[Embed walkthrough<br/>+ screenshots in PR body]
        P10D --> P10E[Clean up worktree]
    end

    P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7 --> P8 --> P9 --> P10 --> Done([Done])

    classDef subagent fill:#e3f2fd,stroke:#1976d2,color:#0d47a1
    classDef skill fill:#fff3e0,stroke:#f57c00,color:#e65100
    classDef artifact fill:#f3e5f5,stroke:#7b1fa2,color:#4a148c
    classDef phase fill:#f5f5f5,stroke:#616161,color:#212121

    class P2B,P4A,P6A,P8B,P8F,P8S,P9A subagent
    class P2C,P4B,P5W,P8C,P9T,P10A skill
    class P5D,F0,F1,F2,F3,F4,F5,P9R artifact
```

## Component legend

| Type | Examples | Where defined |
|---|---|---|
| **Subagent** (blue) | `code-explorer`, `code-architect`, `plan-reviewer`, `impl-backend`, `impl-frontend`, `impl-simplify`, `test-plan-walker` | `prd-pr/agents/*.md` |
| **Skill** (orange) | `orchestrator`, `codebase-context-builder`, `vertical-slicing`, `git-worktrees`, `raise-pr`, `react-best-practices`, `restful-api-design`, `backend-implementer`, `frontend-implementer`, `context-updater`, `test-plan-walkthrough` | `*/skills/<name>/SKILL.md` |
| **Artifact** (purple) | The 6 plan files written in Phase 5, plus `06-walkthrough.md` + `screenshots/` from Phase 9 | `docs/new-feature/{id}-{summary}/` |

## Phase → component matrix

| Phase | Subagents dispatched | Skills invoked | Output |
|---|---|---|---|
| 1 Discovery | — | — | Captured ACs, ticket metadata |
| 2 Codebase Exploration | 2–3× `code-explorer` (parallel) | `codebase-context-builder` (if missing) | Reference impl, patterns, key files |
| 3 Clarifying Questions | — | — | Resolved decisions |
| 4 Architecture Design | 1× `code-architect` | `vertical-slicing` (style guide) | Slice list + change-site map |
| 5 Write Documents | — | `git-worktrees` (isolate) | 6 plan files in `docs/new-feature/{id}/` |
| 6 Quality Review | 2× `plan-reviewer` (parallel) | — | Review findings, doc fixes |
| 7 Summary | — | — | Hand-off briefing |
| 8 Slice-by-slice Impl | per slice: `impl-backend` → `impl-frontend` → `impl-simplify` | `vertical-slicing`, `backend-implementer`, `frontend-implementer`, `react-best-practices`, `restful-api-design`, `context-updater` | Code + tests + checkpoint commits |
| 9 Test Plan Walkthrough | 1× `test-plan-walker` (clean context) | `test-plan-walkthrough` | `06-walkthrough.md` + screenshots; loops back to Phase 8 on `FIXES_NEEDED` |
| 10 Branch Completion | — | `raise-pr` | PR (walkthrough + screenshots embedded) or merge + worktree cleanup |
