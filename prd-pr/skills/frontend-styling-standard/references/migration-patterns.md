# Migration patterns

## The CSS-layering override rule (read this first)

If the design-system component classes are **unlayered** CSS, they beat any
`@layer` — including Tailwind's `utilities` layer. Cascade order is: importance
→ layer (unlayered wins over any layer) → specificity. So even a zero-specificity
unlayered rule beats a layered Tailwind utility.

Consequence for the migration:

- ✅ **Add** a property the class doesn't set → Tailwind works. `.card` sets no
  `display`, so `className="card flex flex-col gap-4"` is fine. Same for
  `flex-1`, `min-w-0`, `block`, gaps, margins on plain elements.
- ❌ **Override** a property the class *does* set → Tailwind loses.
  `.row{cursor:pointer}`, `.avatar{background}`, `.field{margin-bottom}`,
  `.p2{color}` will **not** yield to `cursor-default`, `bg-white`, `mb-0`,
  `text-*`.

When you must override a component class's own property, add a **modifier
class** defined *after* the base (same specificity, later wins) —
e.g. `.row-static{cursor:default}`, `.avatar-framed{background:…}`,
`.field-flush{margin-bottom:0}`. Only when a modifier isn't worth it (a true
one-off) keep an inline `style` with a `biome-ignore` + reason. Don't reach for
`!important` Tailwind (`mb-0!`).

(Why not move the classes into `@layer components` so utilities win naturally?
Because component libraries like antd inject their own styles *unlayered*;
layering your classes would let unlayered antd beat them and regress themed
widgets. Leave them unlayered and use modifiers.)

## Inline style → utility mappings

The dominant offender is the "inline-flex triple". Convert:

| Inline | Utility |
|---|---|
| `{display:"flex",flexDirection:"column",gap:"var(--x-s-4)"}` | `className="flex flex-col gap-3"` |
| `{display:"flex",alignItems:"center",gap:8}` | `className="flex items-center gap-2"` |
| `{flex:1,minWidth:0}` | `className="flex-1 min-w-0"` |
| `{display:"block"}` on a span | `className="block"` |
| `{margin:0}` on a heading | `className="m-0"` (or a `.flush` class) |
| `{marginTop:16}` | `className="mt-4"` |
| `{width:240}` | `className="w-[240px]"` |
| `{padding:"2rem",textAlign:"center"}` | `className="p-8 text-center"` |
| `{display:"none"}` | `className="hidden"` |

Prefer the component library's layout primitives where they read cleaner (antd
`<Flex vertical gap>` / `<Space>`). If the inline style just duplicates an
existing global rule (e.g. an input already styled by `.search input {…}`),
**delete it** rather than translate it.

## Legacy class / variable → token mappings

When retiring a legacy vocabulary bridged by an alias block, the swaps are
exact-string and safe to batch with `perl -pi` across a set of files, then
verify:

```bash
perl -pi -e '
  s/className="btn btn-ghost"/className="hh-btn hh-btn-m hh-btn-text"/g;
  s/className="callout callout-error"/className="hh-callout hh-callout-error"/g;
  s/className="card card-elevated-sm"/className="hh-card"/g;
' path/to/*.tsx
```

- `--legacy-space-N` inline vars usually map to a token step that equals a
  Tailwind step (e.g. `var(--bs-space-4)` = 1rem = `mt-4`), so migrate them
  straight to utilities and drop the inline style in one move.
- After a batch, `grep` the files for any remaining legacy token/class, and
  **typecheck** — a swap that hits an element which already had a `className`
  produces a duplicate-`className` JSX error (fix by merging into one).
- When a test couples to a renamed class (`querySelector(".callout-error")`),
  update the selector to the new class — don't loosen the test.
- The alias block (the temporary `--legacy-*`/legacy-class shim) can only be
  **deleted** once `rg` finds zero references across *all* source and tests. Add
  proper `.x-*` equivalents for any legacy class that has none
  (`.dateline`, `.empty-note`, drag-handle grips) before deleting.

## Lint-cleanup patterns (Phase 6)

Common findings after flipping to `error`, and their idiomatic fixes:

- **`noNonNullAssertion` on `enabled`-gated queries** — the biggest bucket.
  Migrate to TanStack Query **`skipToken`**: it narrows the param type so both
  the `!` and the redundant `enabled` disappear.

  ```ts
  // before
  useQuery({ queryKey: k(dept), queryFn: () => api.list({ department: dept! }), enabled: Boolean(dept) })
  // after
  useQuery({ queryKey: k(dept), queryFn: dept ? () => api.list({ department: dept }) : skipToken })
  ```

  **Closure-narrowing caveat**: this only narrows for a `const`/param. For a
  *property* access (`params.department`), destructure to a const first
  (`const { department } = params;`) or TS won't narrow it inside the query
  closure.
- **`noNonNullAssertion` in mutations** (no `skipToken`) — a shared narrowing
  guard: `function requireX(x?: string): string { if (!x) throw …; return x; }`.
- **`getElementById("root")!`** — null-check + throw before `createRoot`.
- **Unsafe optional chaining** `(x?.y as T).z` — keep it optional:
  `(x?.y as T | undefined)?.z`.
- **Map get-after-set / `arr[0]!`** — restructure (`let v = map.get(k); if (!v)
  {…}`) or use total methods (`str.charAt(0)` never returns undefined).
- **a11y** — `<span onClick>` → `<button type="button" aria-label>`; `<label>`
  → add `htmlFor` + control `id`; add `type="button"` to non-submit buttons.
- **Genuinely dynamic inline style** (e.g. a dnd-kit `style={transform}`, a
  data-driven width) — this is the sanctioned exception: keep it with
  `// biome-ignore lint/plugin: <why it's dynamic>`.
- **Intentional `!important`** (component-library overrides that must beat
  injected styles) — scope `noImportantStyles` **off for that one override
  file** rather than sprinkle ignores; keep it on everywhere else so new
  `!important` in feature code is still caught.
