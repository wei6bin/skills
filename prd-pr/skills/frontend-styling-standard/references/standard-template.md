# Styling standard — document template

A fill-in template for the standard doc. Keep it short and skimmable; push
depth into separate references. Adapt names to the project (`--x-*` tokens,
`.x-*` classes). Give every rule a stable id so reviews/commits can cite it.

---

## 0. TL;DR — the rules at a glance

| # | Rule | Enforcement |
|---|---|---|
| **STY-R1** | **No inline `style={{…}}`** for static styling. Use a layout component, a token/utility class, or Tailwind. Inline style only for genuinely dynamic values, with a `biome-ignore` + reason. | Biome plugin (`error`) |
| **STY-R2** | **Prefer the component library over raw HTML** for anything it provides (Button, Table, Form, Card, Flex, Space, Modal…). Raw elements only for real design-system primitives it doesn't ship. | Review |
| **STY-R3** | **No hardcoded values.** Every colour/space/radius/shadow/font comes from a design token. No raw hex or px in components. | Review |
| **STY-R4** | **Layout & spacing = utilities, not inline flex.** The `{display:flex,flexDirection:column,gap}` triple is banned. | Biome (via R1) + review |
| **STY-R5** | **One class vocabulary.** New/edited code uses `.x-*` (or Tailwind). Legacy classes/vars are deprecated — touch a legacy site, migrate it. | Review |
| **STY-R6** | **Single source of tokens.** Values defined once, fed to theme + CSS vars + Tailwind. Never hand-copy a hex between the theme and the CSS. | Drift-guard test |
| **STY-R7** | **`!important` frozen.** Don't add new `.<lib>-*` `!important`; restyle via the theme. | Biome `noImportantStyles` + review |

**One sentence:** component + token + global class first; Tailwind utility for
layout; inline style never (unless computed).

## 1. Why this exists

State the concrete problems the audit found, with evidence (inline-style count,
antd-layout-unused, hardcoded values, dual vocabularies, no CI). This is the
motivation, and it makes the rules land.

## 2. The layered model

Four layers, lowest precedence first; each owns one job.

```
4. Inline style{{ }}  — dynamic values ONLY                     ← last resort
3. Tailwind utilities — layout, spacing, positioning            ← default for layout
2. Component classes  — .x-* primitives + library components (themed centrally)
1. Design tokens      — the single source of truth for every value
```

## 3. The rules, in detail

For each STY-R*, give a short Do / Don't with real before/after from this
codebase. Especially R1 (inline→utility) and R5 (legacy→token).

## 4. Decision guide — "I need to…"

A table mapping intents to the right layer: stack vertically → `<Flex vertical>`
or `flex flex-col gap-N`; card surface → `.x-card`; status pill → `.x-tag`; a
colour/space value → a token; a truly dynamic value → inline + `biome-ignore`.

## 5. Component-library adoption policy

Which library components are mandatory, how the theme is configured
(`ConfigProvider` + the token-derived theme), and which primitives stay as
`.x-*` classes. Call out the project's brand/primary-colour rule explicitly if
it's a common mistake.

## 6. Tokens — the single source of truth

Point at `tokens.ts` + the drift-guard test. List the scales (spacing, radius,
colour, shadow, type).

## 7. Tailwind adoption

Config, how it consumes `--x-*`, preflight-off, the spacing-scale decision, and
the layering rule (§7.2a): Tailwind can only *add* to `.x-*`, never *override* —
use a modifier class for overrides.

## 8. Enforcement

What runs in CI, the `warn`→`error` ratchet, and what's exempted (test-file
assertions, the one designated `!important` override file) and why.

### 7.3 / 8.x Phased rollout table

Track the phases so anyone can see status:

| Phase | Scope | Exit criteria |
|---|---|---|
| P0 | Standard doc + linter/CI at `warn` | Merged; violations visible |
| P1 | Single-source tokens + drift guard | No duplicated hex |
| P2 | Install Tailwind wired to tokens | Build green |
| P3 | Migrate inline styles → utilities | Inline-style count → 0 |
| P4 | Retire legacy vocabulary | Alias block deletable |
| P5 | Flip rules `warn`→`error`; clear lint tail | CI red on any new violation |

## 9. Checklist for any frontend PR

- [ ] No new inline `style` (or dynamic-only + `biome-ignore` + reason)
- [ ] Layout via utilities/`<Flex>`, not inline flex
- [ ] Every value is a token; no raw hex/px
- [ ] Library component used where one exists
- [ ] Touched a legacy class/var? Migrated it
- [ ] No new `.<lib>-* !important`
- [ ] `lint` shows no increase in warnings
