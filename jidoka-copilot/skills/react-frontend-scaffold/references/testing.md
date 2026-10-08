# Test file conventions

Match the repo's existing test co-location and naming (commonly co-located
`*.test.tsx`/`*.test.ts` next to the file under test, sometimes a parallel
`__tests__/` tree). Check whether unit and integration tests are split into
separate folders/configs or run together - most repos in this style run both
through the same runner, distinguished only by whether a given test stubs the
network.

## Reuse the repo's existing render/wrapper helpers

Before writing a new test, check for:

- A shared "render with providers" helper (wrapping router + query-client + any
  other required context) for component/page tests.
- The repo's convention for hook tests (`renderHook` with a local wrapper) -
  don't reuse a component-render helper for `renderHook` if the repo doesn't
  already do that; check whether a hook test even needs the same providers a
  full page does.
- A globally-wired mock server (e.g. MSW) whose lifecycle
  (`listen`/`resetHandlers`/`close`) is already set up in a shared test-setup
  file - new test files should only add handlers via that shared instance, never
  construct a second mock server.

## Stubbing the backend

```ts
const BASE = "http://localhost:5128"; // match the repo's actual dev API base URL

server.use(
  http.get(`${BASE}/antiforgery/token`, () => HttpResponse.json({ token: "csrf-abc" })),
  http.post(`${BASE}/widgets`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({ id: "1", ...body }, { status: 201 });
  }),
);
```

- If the repo's API client fetches a CSRF/auth token as a side effect of any
  mutating request, **any test that triggers a mutation must also stub that
  token endpoint**, or the request hangs waiting on a real network call that MSW
  (or equivalent) has no handler for. This is one of the most common causes of a
  silently-hanging test in this style of codebase - check for it first if a new
  mutation test times out.
- Assert on the request body a mutation actually sent, not just that the UI
  updated afterward - this is what catches bugs like sending a partial body when
  the backend expects a full one (see `references/forms-and-optimistic-ui.md`).

## Other conventions to match

- Confirm-gated actions (delete flows, etc.): check whether the repo mocks
  `window.confirm` directly or uses a custom confirm-dialog component that needs
  a different mocking approach.
- Prefer role/label-based queries (`getByRole`, `getByLabelText`) over test ids
  if that's what the repo's existing tests already do - it also tends to match
  the E2E layer's selectors, so a UI change that breaks accessibility breaks
  both layers at once.
- E2E tests (Playwright, Cypress, etc.), if present: one full user-journey spec
  per flow is common, run against a real backend rather than a mock. Extend an
  existing journey spec or add a new one per flow - don't add page-object
  abstractions unless the repo's spec files already use them or have grown
  unwieldy without them.

## If the app uses Ant Design

Component-library markup breaks a few habits carried over from testing plain
HTML, and antd needs two browser APIs jsdom doesn't ship:

- **Stub `matchMedia` and `ResizeObserver` in the shared test setup file.**
  antd's responsive helpers (`Grid.useBreakpoint`, `Layout.Sider`'s
  `breakpoint`) call `window.matchMedia`, and several components (`Table`,
  `Select`, `Tabs`) observe element size. Neither exists in jsdom, so without
  stubs the app shell throws before a single assertion runs. This is the most
  common cause of a whole antd test suite failing at once.
- **Wrap renders in `ConfigProvider` and `<App>`** in the shared render helper.
  Components read theme tokens via `theme.useToken()`, and `App.useApp()`
  outside an `<App>` falls back to the detached statics with a warning.
- **`Select` is not a native `<select>`.** `userEvent.selectOptions` does not
  work. Click the element with role `combobox`, then click the option by its
  role/name.
- **Dropdowns, modals, drawers, selects, and tooltips render in a portal**
  attached to `document.body`, outside the container `render` returns. Query
  them off `screen`, and scope assertions with
  `within(screen.getByRole("dialog"))` so you don't match the page behind the
  dialog.
- **Popups and modals animate.** A closed `Modal` is removed after its
  transition, so assert removal with `waitForElementToBeRemoved` rather than a
  synchronous `queryBy` immediately after the click.
- **`message`/`notification` auto-dismiss on a timer.** Assert on them before
  the timeout, or drive them with fake timers.
- **`Table` paginates client-side by default.** Rows on page 2 are genuinely
  absent from the DOM, so `getByText` for row 40 of 100 fails on a passing app.
  Assert against a small fixture or the visible page - and the same applies to
  rows outside the viewport when `virtual` is on.
- **`Table` needs `rowKey`** in tests as much as in the app; without it
  row-selection assertions target the wrong rows.
- A `Form.Item` with a `label` and a `name` gives its control an id and an
  accessible name, so `getByLabelText`/`getByRole("textbox", { name })` work
  exactly as the role-and-label guidance above wants - no test ids needed. A
  `Form.Item` with no `label` has no accessible name to query by; that's a bug
  in the component, not a reason to add a test id.

## Minimum coverage checklist for a new feature

- [ ] Query hook: happy path (loads data), and the pagination edge case if
  paginated
- [ ] Each mutation hook: happy path, and the validation-error path if the form
  surfaces field errors
- [ ] Each form component: successful submit, and at least one error-display
  case
- [ ] Any component with a confirm-gated or optimistic action: both the
  confirmed/committed and cancelled/rolled-back paths
- [ ] Route guards touched: authenticated and unauthenticated cases

Not every feature needs every line above (a read-only feature has no
mutation/error-display cases) - use judgment, but don't skip stubbing any
auth/CSRF side-effect endpoint on a mutation test; that's the one that produces
confusing hangs rather than clean failures.
