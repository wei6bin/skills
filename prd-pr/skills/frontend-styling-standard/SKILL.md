---
name: frontend-styling-standard
description: >-
  Establish and enforce a styling standard for a React + Ant Design (and/or Tailwind) frontend: audit current styling, define the layered model (component library + design tokens + global classes + Tailwind utilities, inline styles banned), single-source the tokens, adopt Biome, migrate off inline styles and any legacy CSS vocabulary, and enforce via CI-blocking lint. Use when the user wants to clean up or standardise frontend styling, reduce inline style={{}}, adopt design tokens or a design system, wire up Tailwind, switch to Biome, retire a legacy class vocabulary, or review a frontend for styling debt - even without naming the tools.
license: MIT
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, AskUserQuestion
---

# Frontend styling standard

Takes a React frontend from ad-hoc inline styling to a tool-enforced standard, and authors the standard document. Derived from a real migration; the sequencing and gotchas are the parts that save time.

**The rule:** component + design token + global class first; a Tailwind utility for layout; inline `style` never, unless the value is genuinely computed at runtime.

Work in phases, committing each separately. Do not start by editing components; styling debt is systemic and a scattershot pass makes it worse.

### Phase 0 - Audit

With `file:line` evidence: is the component library themed centrally (`ConfigProvider` + theme object) and used consistently over raw elements; how many `style={{` sites (`rg -c 'style=\{\{'`) and of what kind (layout, sizing, colour, one-off); are there tokens or scattered hex/px, and is the same value duplicated between the JS theme and the CSS; one class vocabulary or several; is Tailwind actually installed (`@tailwind` / `tailwind.config`); what lints today; does CI actually run lint/tests on PRs (a standard nobody enforces is a suggestion).

Reconcile the user's premise with reality before acting; "we use Tailwind" often means it is not installed. Use `AskUserQuestion` for the load-bearing forks: adopt Tailwind vs codify what exists; lint-only vs also replace the formatter.

### Phase 1 - Write the standard

A short authoritative doc from `references/standard-template.md`, centred on the **layered model**: tokens → components (themed centrally, plus a few named classes for primitives the library lacks) → Tailwind utilities for layout and spacing → inline style as a lint-ignored last resort. Give each rule a stable id (`STY-R1`…) so reviews and commits can cite it.

### Phase 2 - Enforcement first, at `warn`

Land the linter and CI before the migration so the violation count only goes down.

- Biome over ESLint (`references/biome-setup.md`); keep the existing formatter and turn Biome's off unless the user wants Biome to own formatting.
- The no-inline-style rule is a Biome **GritQL plugin** (no built-in exists); config in the same reference.
- CI, if none: install → build → typecheck → test → lint → format on PRs. In a pnpm workspace build must precede typecheck/test because consumers resolve against `dist/`.
- Ratchet: Biome has no `--max-warnings`; flip each rule `warn`→`error` when its count hits zero.

### Phase 3 - Single-source the tokens

One `tokens.ts` the component-library theme derives from, plus a **drift-guard test** that reads the CSS custom properties and fails on any divergence (`references/tokens-and-tailwind.md`).

### Phase 4 - Wire Tailwind to the tokens (if adopting)

Tailwind is the layout layer, not a replacement for the theme or component classes. CSS-first, consuming the existing tokens, preflight off (the app and library own resets). Config, the pnpm dual-Vite caveat and the spacing-scale decision are in the same reference.

### Phase 5 - Migrate in verified batches

One area at a time; build + typecheck + test + lint + format after each batch, then commit. Mechanical swaps (class renames, `--legacy-*`→`--token-*`) are safe with `perl -pi`/`sed` across a batch, then verify, watching for duplicate `className` on elements that already had one. Mapping tables in `references/migration-patterns.md`.

**The load-bearing gotcha:** unlayered design-system classes beat any `@layer`, including Tailwind's `utilities`. A utility can only add a property the class does not set, never override one it does (`cursor`, `background`, `margin`, `color`). To override, add a modifier class defined after the base. This explains most "why isn't my class working" during migration.

### Phase 6 - Enforce for real

At zero inline styles and legacy classes, flip rules to `error`, then clear the smaller findings the linter surfaces (a11y, non-null assertions; notably migrating `enabled`-gated TanStack Query hooks to `skipToken`).

## Throughout

Behaviour-preserving: update a selector that legitimately moved, never loosen a test. Keep token values byte-identical (hex case) so value tests hold. Report honestly: counts going down (e.g. inline styles 164 → 0), what is enforced, what is deliberately exempted and why.

## References

- `references/standard-template.md` - the fill-in standard doc (layered model, STY-R1..R7, rollout table).
- `references/biome-setup.md` - Biome config, the GritQL plugin, the ratchet, CI workflow.
- `references/tokens-and-tailwind.md` - `tokens.ts` + drift guard; Tailwind v4 CSS-first wiring; preflight, spacing scale, dual-Vite caveats.
- `references/migration-patterns.md` - the cascade rule, inline→utility and legacy→token mappings, lint-cleanup patterns.

Inside the prd-pr workflow this is not a per-slice skill: invoke it when the task is standing up or repairing the styling standard itself (a Phase 2 finding of styling debt, a dedicated standards slice, or a cleanup outside a story). `react-best-practices` holds the per-component conventions; `reuse-ladder` still applies before adding Biome, Tailwind or a token module.
