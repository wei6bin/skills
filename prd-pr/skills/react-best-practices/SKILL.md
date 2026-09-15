---
name: react-best-practices
description: House conventions for React 19 + TypeScript frontends - library choices (TanStack Query, Zustand/RTK, React Hook Form + Zod, Vitest + RTL + MSW, Biome), the skipToken gating pattern, the layered styling model and its CSS-cascade gotcha. Apply when implementing React components, hooks, forms or data fetching.
license: MIT
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, AskUserQuestion
---

# React Best Practices

House choices for React 19 + TypeScript (strict) with Vite. Project conventions in `docs/project_context/` override these.

## Libraries

| Concern | Use |
|---|---|
| Server state | TanStack Query v5; query keys as co-located constants / factories |
| Global client state | Zustand (simple) or Redux Toolkit (complex) |
| Forms | React Hook Form + Zod; React 19 Actions for server forms; field-level errors; disable submit while pending |
| Routing | React Router v6 / TanStack Router; `React.lazy` + `Suspense` at route level |
| UI kit | Shadcn/ui, Ant Design, MUI or Fluent UI per project, themed centrally |
| Styling | Tailwind for layout utilities; CSS Modules for scoped dynamic styles |
| Testing | Vitest + React Testing Library + MSW; Playwright for e2e |
| Linting | Biome (formatter off; Prettier keeps `format`) |

Trust the React Compiler for memoization; add `useMemo`/`useCallback` only when profiling shows a win. Long lists: TanStack Virtual or `react-window`.

## Gate queries on `skipToken`, not `enabled`

It narrows the param type, so the non-null assertion and the redundant `enabled` both disappear:

```ts
// avoid
useQuery({ queryKey: k(dept), queryFn: () => api.list({ department: dept! }), enabled: Boolean(dept) });
// prefer
useQuery({ queryKey: k(dept), queryFn: dept ? () => api.list({ department: dept }) : skipToken });
```

Narrowing only works on a `const`/param: destructure (`const { department } = params;`) before using it in the closure. Mutations have no `skipToken`; use a shared `requireX()` guard instead of `!`.

## Styling: the layered model

Each layer owns one job; never do one layer's job in another:

1. **Design tokens** - single source of every colour, space, radius, shadow, font. No raw hex or px in components.
2. **Components** - the library's components themed centrally, plus a few named classes for primitives it lacks.
3. **Utilities (Tailwind)** - layout and spacing only: flex/grid/gap/padding/margin/width.
4. **Inline `style`** - genuinely dynamic values only, with a lint-ignore and reason.

**Cascade gotcha**: unlayered component classes beat any `@layer`, including Tailwind's `utilities`. A utility can only add a property the class does not set, never override one it does; use a modifier class defined after the base instead.

Standing up, migrating to or enforcing this standard (Biome rule, token single-sourcing, Tailwind v4 wiring, retiring a legacy vocabulary) is the `frontend-styling-standard` skill's job.

## Testing

Test behaviour through the rendered UI: query by role, label and text with `userEvent`; never component state or hook internals. Mock network at the boundary with MSW. Accessibility: semantic elements, accessible names, keyboard navigation, `aria-*` only where semantics fall short; WCAG 2.1 AA.

## Companion skills

`frontend-implementer` (the per-slice TDD loop), `frontend-styling-standard` (the styling standard and its enforcement).
