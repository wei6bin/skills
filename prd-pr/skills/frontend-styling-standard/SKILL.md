---
name: frontend-styling-standard
description: >-
  Establish and enforce a styling standard for a React + Ant Design (and/or
  Tailwind) frontend: audit how styling is done today, define a layered model
  (antd components + design tokens + global CSS classes + Tailwind utilities,
  with inline styles banned), single-source the design tokens, adopt Biome for
  linting, migrate off inline styles and any legacy CSS vocabulary, and enforce
  it all via CI-blocking lint. Use this whenever the user wants to clean up or
  standardize frontend styling — reduce inline `style={{}}`, adopt design
  tokens or a design system, wire up Tailwind, switch to Biome, kill a legacy
  CSS class vocabulary, or asks for "frontend best practices", "styling
  standard", "design-system cleanup", or "make the styling consistent" — even
  if they don't name the specific tools. Also use it to review a frontend for
  styling debt.
license: MIT
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, AskUserQuestion
---

# Frontend styling standard

A repeatable workflow for taking a React frontend (Ant Design and/or Tailwind,
pnpm workspace or single app) from ad-hoc, inline-heavy styling to a
**disciplined, tool-enforced standard** — and for authoring the standard
document itself. It is derived from a real end-to-end migration; the sequencing
and the non-obvious gotchas below are the parts that save the most time.

## The one-sentence rule

**antd component + design token + global class first; a utility (Tailwind) for
layout; inline `style` never — unless the value is genuinely computed at
runtime.** Everything else follows from this.

## When to use this

- "Our components are full of inline styles / `style={{}}` everywhere."
- "Adopt a design system / design tokens / a consistent theme."
- "Set up Tailwind" or "switch us from ESLint to Biome."
- "We have two CSS class vocabularies / a legacy stylesheet to retire."
- "Write/enforce a frontend styling standard" or "review our frontend styling."

## How to work: analyze → decide → land in phases

Do **not** start editing components. Styling debt is systemic; a scattershot
pass makes it worse. Work in this order, and **commit each phase separately**
so progress is durable and reviewable.

### Phase 0 — Audit first (always)

Understand the *actual* state before proposing anything. Answer, with concrete
`file:line` evidence:

- **Component library**: Is antd (or MUI/Chakra) themed centrally
  (`ConfigProvider` + a theme object)? How consistently are its components used
  vs. raw `<div>`/`<button>`?
- **Inline styles**: Count `style={{` sites and categorize them — layout
  (flex/gap/margin), sizing (width), color, one-offs. `rg -c 'style=\{\{'`.
- **Design tokens**: Are there CSS custom properties / a token scale, or
  hardcoded hex + px scattered around? Is the same value duplicated between the
  JS theme and the CSS?
- **Class vocabularies**: One consistent prefix, or several (e.g. a modern one
  plus a legacy/aliased one mid-migration)?
- **Tailwind / linter**: Is Tailwind actually installed (grep for
  `@tailwind`/`tailwind.config`)? What lints today (ESLint config, rules)?
- **CI**: Does anything actually *run* the linter/tests on PRs? (Often the
  biggest gap — a standard nobody enforces is a suggestion.)

Then **reconcile the user's premise with reality** and surface mismatches
before acting. Users often say "we use Tailwind" when it isn't installed, or
"we have a design system" when it's half-migrated. Use `AskUserQuestion` for
the genuinely load-bearing forks (adopt Tailwind vs. codify what exists;
lint-only vs. also replace the formatter) — these change the whole plan.

If a subagent/Explore tool is available, fan out the audit across the codebase
and keep only the conclusion.

### Phase 1 — Write the standard document

Produce a short, authoritative doc (see `references/standard-template.md`).
The heart of it is the **layered model** — each layer owns one job, and you
never do one layer's job in another:

1. **Design tokens** — the single source of truth for every colour, space,
   radius, shadow, font value.
2. **Components** — the library's components (Table/Form/Modal…) themed
   centrally, plus a small set of named component classes for design-system
   primitives the library doesn't ship.
3. **Utilities (Tailwind)** — layout & spacing: flex/grid/gap/padding/margin/
   width. This is what replaces the inline-flex triple.
4. **Inline `style`** — last resort, dynamic values only, with a lint-ignore +
   reason.

Give each rule a short stable id (`STY-R1`…) so reviews and commits can cite
it. Keep it skimmable; put depth in reference files.

### Phase 2 — Set up enforcement early (so it ratchets)

Land the linter + CI *before* the big migration, at `warn`, so every new
violation is visible and the count only goes down.

- **Biome over ESLint** is the recommended linter (fast, single binary). See
  `references/biome-setup.md`. Keep the existing formatter (usually Prettier)
  and turn Biome's formatter off so they don't fight — unless the user wants
  Biome to own formatting too.
- **The "no inline style" rule** is a Biome **GritQL plugin** (Biome has no
  built-in one). Exact plugin + config in `references/biome-setup.md`.
- **CI**: if none exists, add a workflow that runs install → build →
  typecheck → test → lint → format on PRs. In a pnpm workspace, **build must
  run before typecheck/test** because packages emit to `dist/` that consumers
  resolve against.
- **Ratchet**: start rules at `warn` (CI stays green), migrate, then flip to
  `error`. Biome has no per-rule `--max-warnings N`; the ratchet is severity-
  based — flip `warn`→`error` per rule once its count hits zero.

### Phase 3 — Single-source the design tokens

If the JS theme and the CSS variables both hardcode the same values, they
*will* drift. Create one `tokens.ts` (raw values) that the component-library
theme derives from, and add a **drift-guard test** that reads the CSS and
fails if any token diverges from its matching custom property. Cheap, and it
kills an entire bug class. Pattern in `references/tokens-and-tailwind.md`.

### Phase 4 — Wire Tailwind to the tokens (if adopting it)

Tailwind is the *layout/utility* layer, not a replacement for the theme or the
component classes. Wire it CSS-first to consume the existing tokens so there's
still one set of values. Preflight OFF (the app + component library already own
resets). Full config, the pnpm dual-Vite caveat, and the spacing-scale decision
are in `references/tokens-and-tailwind.md`.

### Phase 5 — Migrate, in verified batches

Convert inline styles and any legacy vocabulary to the layered model, **one
area at a time**, running build + tests + lint after each and committing.
Mechanical, repetitive swaps (class renames, `--legacy-*`→`--token-*`) are
safe to do with `perl -pi`/`sed` across a batch, then verify. The recurring
patterns and the mapping tables are in `references/migration-patterns.md`.

**The load-bearing gotcha — CSS layers.** If the design-system classes are
*unlayered* CSS, they beat any `@layer` (including Tailwind's `utilities`
layer). So a Tailwind utility can only **add** a property the class doesn't
set — it can **never override** one it does (`cursor`, `background`, `margin`,
`color`). When you must override a component class's own property, add a
**modifier class** next to the base (defined after it), not a Tailwind utility
that will silently lose. This single fact explains most "why isn't my class
working" confusion during the migration.

### Phase 6 — Enforce for real, then clean the tail

Once inline styles and legacy classes hit zero, flip the rules to `error`. Then
clear the smaller findings the linter surfaces (a11y, correctness, non-null
assertions) so `lint` is fully clean — see
`references/migration-patterns.md` for the common ones (notably migrating
`enabled`-gated TanStack Query hooks to `skipToken` to drop `!` assertions).

## Working discipline (applies throughout)

- **Verify every batch**: build + typecheck + test + lint + format, then
  commit. Never batch a broad `perl`/`sed` swap without re-running the gate —
  and watch for duplicate `className` from swaps that hit an element that
  already had one (the typecheck catches it).
- **Behaviour-preserving**: a styling refactor should not change what tests
  assert. When a test legitimately couples to a class name you renamed, update
  the selector; don't loosen the test.
- **Keep the token values byte-identical** through refactors (e.g. hex case) so
  snapshot/value tests don't break.
- **Report honestly**: state the count going down (e.g. inline styles 164 → 0),
  what's enforced, and what's deliberately exempted (and why).

## Reference files

Read these as you reach the relevant phase:

- `references/standard-template.md` — a fill-in-the-blanks styling standard doc
  (layered model, rules STY-R1..R7, decision guide, phased rollout table).
- `references/biome-setup.md` — Biome config, the GritQL no-inline-style
  plugin, the `warn`→`error` ratchet, CI workflow, and handling a linter swap
  that surfaces new findings without breaking the build.
- `references/tokens-and-tailwind.md` — single-source `tokens.ts` + drift-guard
  test; Tailwind v4 CSS-first wiring to tokens; preflight, spacing-scale, and
  the pnpm dual-Vite type-cast caveats.
- `references/migration-patterns.md` — the CSS-layering override rule, inline-
  style→utility mappings, legacy-class→token mappings, and the common
  lint-cleanup patterns (`skipToken`, guards, DOM-root, dnd-kit dynamic style).

## Companion skills

- **`react-best-practices`** - the per-component conventions (React 19, hooks,
  data fetching, testing). This skill sets the *standard and its enforcement*;
  that one is how you write code inside it. Its Styling and Key Libraries
  sections defer to this skill.
- **`frontend-implementer`** - the per-slice TDD loop. When a slice touches
  styling, it follows the layered model above rather than re-deriving one.
- **`reuse-ladder`** - climb it before adding a dependency; Biome, Tailwind and
  a token module are each a rung worth justifying.

Inside the prd-pr workflow this is normally *not* a per-slice skill. Invoke it
when the task is standing up or repairing the styling standard itself: a Phase 2
`code-explorer` finding of styling debt, a dedicated standards slice, or the
user asking for a styling/linting cleanup outside a story.
