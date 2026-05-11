---
name: react-best-practices
description: >-
  Expert React frontend development using React 19, TypeScript, modern hooks,
  state management (Zustand/RTK), React Testing Library, and Vite.
  Apply when implementing React components, hooks, forms, or optimizing frontend performance.
license: MIT
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, AskUserQuestion
---

# React Best Practices

You are an expert React frontend engineer. Apply these patterns consistently.

## React 19 + TypeScript Foundations

- Use **TypeScript strictly** (`strict: true`). Infer types where obvious; annotate props, events, and hooks explicitly.
- Prefer **functional components with hooks** — never class components.
- Use `React.FC` sparingly; prefer explicit return types: `function Comp(): JSX.Element`.
- Target **React 19** features when available: `use()` hook, `useFormStatus`, `useOptimistic`, `useActionState`, `<Activity>`.

## Component Design

- **Single Responsibility**: each component does one thing well.
- **Composition over inheritance**: build complex UIs by composing small, focused components.
- **Co-locate** related files: `Button/Button.tsx`, `Button/Button.test.tsx`, `Button/index.ts`.
- Use **named exports** for components; barrel `index.ts` for public surface.
- Extract reusable logic into **custom hooks** (`useXxx`) that return stable references.

## Hooks Rules

- Never call hooks conditionally or inside loops.
- `useEffect` — declare all dependencies; clean up subscriptions and timers.
- Prefer `useMemo` / `useCallback` only when profiling confirms a perf win; avoid premature memoization.
- React Compiler (React 19) handles most memoization automatically — trust it.
- `useRef` for mutable values that don't trigger re-renders (DOM refs, timers, previous values).

## State Management

| Scope | Tool |
|---|---|
| Local UI state | `useState` / `useReducer` |
| Server state / caching | TanStack Query (`useQuery`, `useMutation`) |
| Global client state | **Zustand** (simple) or **Redux Toolkit** (complex) |
| Form state | React Hook Form + Zod validation |

**Zustand pattern:**
```ts
const useStore = create<State>()((set) => ({
  count: 0,
  increment: () => set((s) => ({ count: s.count + 1 })),
}));
```

**Redux Toolkit pattern:** use `createSlice`, `createAsyncThunk`, RTK Query for API calls.

## Forms

- Use **React Hook Form** with **Zod** schema validation.
- Server forms: use React 19 Actions API (`<form action={serverAction}>`).
- Always show field-level validation errors; disable submit during pending state with `useFormStatus`.

## Data Fetching

- Prefer **TanStack Query** for all server state — handles caching, refetch, loading/error states.
- For React Server Components: fetch directly in component; pass data as props to client components.
- Co-locate query keys as constants; use query factories for parameterized queries.

## Performance

- Use `React.lazy` + `Suspense` for route-level code splitting.
- Virtualize long lists with **TanStack Virtual** or `react-window`.
- Avoid inline object/function creation in JSX that breaks referential equality.
- Measure first with React DevTools Profiler before optimizing.
- Target Core Web Vitals: LCP < 2.5s, FID < 100ms, CLS < 0.1.

## Styling

- Prefer **Tailwind CSS** utility classes for most styling.
- Use **CSS Modules** for complex, scoped styles that need dynamic values.
- Design system: **Shadcn/ui** (Radix + Tailwind), **MUI**, or **Fluent UI** depending on project.
- Never use inline styles except for truly dynamic values.

## Testing

Use **Vitest** + **React Testing Library** (RTL):

```ts
import { render, screen, userEvent } from '@testing-library/react';

test('increments counter on click', async () => {
  render(<Counter />);
  await userEvent.click(screen.getByRole('button', { name: /increment/i }));
  expect(screen.getByText('1')).toBeInTheDocument();
});
```

- Test **behavior, not implementation** — query by role, label, text.
- Mock network calls with **MSW** (Mock Service Worker).
- E2E tests: **Playwright** (see `playwright-explore-website` + `playwright-generate-test` skills).
- Coverage target: 80%+ for business-critical components.

## Accessibility (a11y)

- Use semantic HTML: `<button>`, `<nav>`, `<main>`, `<section>` correctly.
- All interactive elements must be keyboard-navigable and have accessible names.
- Use `aria-*` attributes only when semantic HTML is insufficient.
- Test with axe-core (`@axe-core/react`) and keyboard navigation.
- WCAG 2.1 AA minimum compliance.

## Project Structure (Vite + React)

```
src/
├── assets/          # Static files
├── components/      # Shared UI components
│   └── Button/
│       ├── Button.tsx
│       ├── Button.test.tsx
│       └── index.ts
├── features/        # Feature-sliced: each feature owns its components, hooks, api
│   └── auth/
│       ├── components/
│       ├── hooks/
│       ├── api.ts
│       └── store.ts
├── hooks/           # App-wide custom hooks
├── lib/             # Third-party config (queryClient, store)
├── pages/           # Route-level components
├── router.tsx       # React Router v6 config
└── main.tsx         # Entry point
```

## Key Libraries

| Category | Preferred |
|---|---|
| Build | Vite + TypeScript |
| Routing | React Router v6 / TanStack Router |
| Data fetching | TanStack Query v5 |
| State | Zustand or Redux Toolkit |
| Forms | React Hook Form + Zod |
| UI | Shadcn/ui, MUI, or Fluent UI |
| Testing | Vitest + RTL + MSW + Playwright |
| Styling | Tailwind CSS |
| Linting | ESLint + Prettier |

## Companion Skills

- **`frontend-implementer`** — Implements full frontend tasks from a plan document following TDD loop
- **`playwright-explore-website`** (awesome-copilot) — Explore and document UI flows for testing
- **`playwright-generate-test`** (awesome-copilot) — Generate Playwright E2E tests from scenarios
