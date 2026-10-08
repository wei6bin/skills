# App bootstrap (greenfield only)

Read this **only** when there is no frontend app to match. It creates the app
that `references/antd-app-setup.md` then themes: the Vite project, packages and
scripts, lint and format, the dev proxy, the typed API client, the auth routes
and the test setup. If an app already exists, step zero governs: match it and
ignore everything here.

The auth pieces implement the frontend half of the backend's default session
auth (the "Frontend contract" section of `aspnet-backend-scaffold`'s
`references/cookie-session-auth.md`): an HttpOnly session cookie the SPA never
sees, a CSRF header on every mutating request, `GET /auth/me` as the source of
"who is signed in", and any 401 meaning the session ended. When the backend has
no auth, skip **Auth** and **Router**'s guard; the shell renders without a
sign-in route.

## First: check the installed versions, don't write from memory

Every tool here ships majors faster than model training data. Read what
`npm create vite` and `npm install` actually produced (`package.json`,
`tsconfig.app.json`, `vite.config.ts`) before writing code; where anything below
disagrees with the installed version's types, the types win.

Checked against create-vite 9.2, Vite 8, TypeScript 6, React 19, React Router
8, antd 6, TanStack Query 5, Vitest 5 and MSW 2:

| Assumption | Reality |
| --- | --- |
| `npm create vite` needs a TTY | `--template react-compiler-ts --no-interactive --no-immediate` runs it unattended and leaves installing to you. |
| The React templates ship ESLint | They ship **Oxlint** (`.oxlintrc.json`, `"lint": "oxlint"`); `--eslint` swaps in ESLint. Remove it: Biome is the linter here. |
| The React Compiler is a later opt-in | The `react-compiler-ts` template wires `babel-plugin-react-compiler` through `@rolldown/plugin-babel` in `vite.config.ts`. Use it, so components need no hand-written `useMemo`/`useCallback`. |
| Constructor parameter properties are fine | The template turns on `erasableSyntaxOnly`: no parameter properties, enums or namespaces. Declare fields and assign them in the constructor body. |
| `import { X }` works for a type | `verbatimModuleSyntax` is on: a type-only import must say `import type` (or `type X` inline), or the build fails. |
| Routing comes from `react-router-dom` | One package, `react-router`: `createBrowserRouter`, `RouterProvider`, `Navigate`, `Outlet` and the hooks all import from it. |
| `fetch("/api/...")` works in tests | Vitest runs Node's `fetch`, which rejects a relative URL even under jsdom. Build the URL against `window.location.origin` (see the client below); MSW handlers written with relative paths still match it. |
| antd needs a compat patch for React 19 | antd 6 supports React 19 directly; `@ant-design/v5-patch-for-react-19` is a v5-only shim. |

## Create the app

From the repo root, with `<root>` the frontend root (`frontend/` by default)
and `<name>` the npm package name:

```bash
npm create vite@latest <root> -- --template react-compiler-ts --no-interactive --no-immediate
cd <root>
npm pkg set name=<name>
npm install
npm install antd @ant-design/icons @fontsource-variable/inter react-router @tanstack/react-query
npm install -D vitest jsdom msw @testing-library/react @testing-library/dom @testing-library/user-event @testing-library/jest-dom @biomejs/biome prettier
npm uninstall oxlint && rm .oxlintrc.json
```

Delete the template's samples - `src/App.tsx`, `src/App.css`, `src/index.css`,
`src/assets/`, `public/icons.svg` and the template `README.md` (the repo's own
README describes the project). Leaving them is how a scaffold starts looking
like a tutorial. Keep `public/favicon.svg` but give it a `<title>` with the app
name, which Biome's accessibility rules require.

## Scripts

Set these in `package.json` (`npm pkg set scripts.<name>=...`). They are the
gates the workflow runs, so keep the names:

```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "typecheck": "tsc -b",
  "lint": "biome lint .",
  "format": "prettier --write .",
  "format:check": "prettier --check .",
  "test": "vitest run",
  "preview": "vite preview"
}
```

## Lint and format

Biome lints; Prettier formats. jidoka's post-edit hook auto-writes Prettier and
only reports Biome, so Prettier owning formatting is what keeps format failures
out of CI.

1. `npx biome init`, then in the generated `biome.json` set
   `"formatter": { "enabled": false }` and drop the `javascript.formatter`
   block. Keep the recommended rules and the `vcs.useIgnoreFile` setting, which
   reads the template's `.gitignore`.
2. Add `.prettierrc.json` (`{}` unless the repo has a house style) and a
   `.prettierignore` listing `dist`, `coverage` and `package-lock.json`.
3. Run `npm run format` once, so the tree starts formatted.

On the fresh template Biome reports `noNonNullAssertion` on
`document.getElementById("root")!` and `noSvgWithoutTitle` on the template's
SVGs. Fix them (a guard that throws, a `<title>`); never disable a rule to get
the scaffold green.

## Dev proxy and test config

The session cookie is `SameSite=Strict` with the `__Host-` prefix, so the SPA
must reach the API on its own origin. In development that is Vite's proxy: the
SPA calls `/api/...`, and the proxy forwards it to the backend with the prefix
stripped. Production hosting has to map `/api` the same way.

```ts
// vite.config.ts
/// <reference types="vitest/config" />
import babel from "@rolldown/plugin-babel";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react(), babel({ presets: [reactCompilerPreset()] })],
    server: {
      port: 5173,
      // A taken port fails loudly instead of moving to 5174 behind your back.
      strictPort: true,
      proxy: {
        "/api": {
          target: env.API_PROXY_TARGET || "http://localhost:5080",
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
    },
  };
});
```

Take the port and the backend URL from the skeleton contract when there is one.

## API client

One typed `fetch` wrapper owns the base path, the CSRF header, credentials and
error shape, so feature code never repeats them:

```ts
// src/lib/api/client.ts
// Must match CsrfHeaderMiddleware.HeaderName in the backend.
export const CSRF_HEADER = "X-App-Client";

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export class ApiError extends Error {
  readonly status: number;
  readonly errorCode: string | undefined;
  readonly fieldErrors: Record<string, string[]> | undefined;

  constructor(status: number, message: string, errorCode?: string, fieldErrors?: Record<string, string[]>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = errorCode;
    this.fieldErrors = fieldErrors;
  }
}

interface ProblemDocument {
  title?: string;
  detail?: string;
  errorCode?: string;
  errors?: Record<string, string[]>;
}

// ValidationProblem keys are C# property names ("Username"); form fields are camelCase.
function camelCaseKeys(errors?: Record<string, string[]>) {
  if (!errors) return undefined;
  return Object.fromEntries(
    Object.entries(errors).map(([key, messages]) => [
      key.replace(/(^|\.)([A-Z])/g, (_, dot: string, c: string) => dot + c.toLowerCase()),
      messages,
    ]),
  );
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
  if (MUTATING.has(method)) headers.set(CSRF_HEADER, "1");

  // Absolute on the page's own origin: same-origin in the browser, and a URL
  // Node's fetch accepts under jsdom, where a bare "/api" would throw.
  const url = new URL(`/api${path}`, window.location.origin);
  const response = await fetch(url, { ...init, method, headers, credentials: "same-origin" });

  const isJson = response.headers.get("content-type")?.includes("json") ?? false;
  const body: unknown = isJson ? await response.json() : undefined;
  if (!response.ok) {
    const problem = (body ?? {}) as ProblemDocument;
    throw new ApiError(
      response.status,
      problem.detail ?? problem.title ?? `Request failed with ${response.status}`,
      problem.errorCode,
      camelCaseKeys(problem.errors),
    );
  }
  return body as T;
}
```

No token is stored anywhere, and nothing auth-related goes into
`localStorage`; the cookie is the session.

## Auth

`src/features/auth/` holds the whole flow. `GET /auth/me` is the only source of
"who is signed in": a 401 there means nobody, not an error.

```ts
// src/features/auth/useMe.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../../lib/api/client";

export interface UserSummary {
  id: string;
  username: string;
  displayName: string;
  role: string;
}

export const meQueryKey = ["auth", "me"] as const;

async function fetchMe(): Promise<UserSummary | null> {
  try {
    return await api<UserSummary>("/auth/me");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export function useMe() {
  return useQuery({ queryKey: meQueryKey, queryFn: fetchMe, staleTime: Number.POSITIVE_INFINITY });
}

export interface LoginValues {
  username: string;
  password: string;
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: LoginValues) =>
      api<{ user: UserSummary }>("/auth/login", { method: "POST", body: JSON.stringify(values) }),
    onSuccess: ({ user }) => queryClient.setQueryData(meQueryKey, user),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>("/auth/logout", { method: "POST" }),
    // Signed out client-side whatever the server said: a 401 here means the
    // session had already ended.
    onSettled: () => {
      queryClient.clear();
      queryClient.setQueryData(meQueryKey, null);
    },
  });
}
```

```tsx
// src/features/auth/RequireAuth.tsx
export function RequireAuth() {
  const { data: me, isPending } = useMe();
  const location = useLocation();
  if (isPending) return <Skeleton active />;
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}
```

`LoginPage` is an antd `Form` in a centred `Card` (see
`references/antd-component-patterns.md` for the form rules). On success it
navigates to `location.state.from ?? "/"`; field errors from a 400 go through
`form.setFields`; anything else shows the server's `detail` in an `Alert`
above the fields - it already says the right thing per `errorCode` (wrong
password, locked, disabled, not provisioned, auth service down). A 429 from the
login rate limiter has no problem body, so give it its own copy ("Too many
attempts. Wait a minute and try again.").

```tsx
const onFinish = async (values: LoginValues) => {
  setFormError(null);
  try {
    await login.mutateAsync(values);
    navigate(from, { replace: true });
  } catch (error) {
    if (error instanceof ApiError && error.fieldErrors) {
      form.setFields(
        Object.entries(error.fieldErrors).map(([name, errors]) => ({ name: name as keyof LoginValues, errors })),
      );
      return;
    }
    setFormError(error instanceof ApiError ? error.message : "Couldn't sign in. Try again.");
  }
};
```

Give the inputs `autoComplete="username"` and `"current-password"` so password
managers work. Show no success toast: landing on the page they asked for is the
confirmation, and a "Signed in" message over it is noise that also covers the
header's controls on a phone. The shell's header carries the signed-in user:
the display name and a `Dropdown` whose "Sign out" item runs `useLogout()` and
then navigates to `/login`.

Any 401 from any other request means the session ended (idle timeout, absolute
expiry, signed out elsewhere). Handle it once, on the query client, so no
feature has to:

```ts
// src/main.tsx (the provider stack itself is in references/antd-app-setup.md)
const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: signOutOn401 }),
  mutationCache: new MutationCache({ onError: signOutOn401 }),
});

function signOutOn401(error: Error) {
  if (error instanceof ApiError && error.status === 401) queryClient.setQueryData(meQueryKey, null);
}
```

`RequireAuth` sees `me` turn `null` and redirects to sign-in.

## Router

Export the route objects, so tests can mount the same tree in a memory router:

```tsx
// src/app/router.tsx
export const routes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [{ element: <AppShell />, children: [{ index: true, element: <HomePage /> }] }],
  },
];

// src/main.tsx
const router = createBrowserRouter(routes);
```

`HomePage` is the skeleton's only page: a page header greeting the signed-in
user and an `Empty` (`Empty.PRESENTED_IMAGE_SIMPLE`, per
`references/antd-component-patterns.md`) saying the app has no features yet.
The first story replaces it.

## Test setup

Shared once, in `src/test/`, so every feature's tests stay short:

```ts
// src/test/server.ts
import { setupServer } from "msw/node";
export const server = setupServer();
```

```ts
// src/test/setup.ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./server";

// antd calls two browser APIs jsdom does not ship (see references/testing.md).
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }),
});
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// "error": a request no handler covers fails the test instead of hanging it.
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());
```

```tsx
// src/test/render.tsx
export function renderRoute(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <ConfigProvider theme={themeConfig}>
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </AntApp>
    </ConfigProvider>,
  );
  return router;
}
```

The skeleton's own tests, each through the rendered UI against MSW handlers for
the contract's endpoints:

- an anonymous visit to `/` lands on `/login`;
- signing in sends the CSRF header, lands on `/`, and shows the user's name;
- bad credentials show the server's `detail`, and a 400's field errors appear
  under their fields;
- "Sign out" calls `POST /auth/logout` and returns to `/login`;
- a 401 from any query signs the user out;
- the client sends the CSRF header on POST/PUT/PATCH/DELETE and not on GET.

## Before the first feature

- [ ] `npm run typecheck`, `lint`, `format:check`, `test` and `build` all pass
- [ ] No template sample left: `App.tsx`, `App.css`, `index.css`, `assets/`,
  `icons.svg`, the template README
- [ ] Oxlint (or ESLint) is gone; Biome is the only linter, with its formatter
  off, and Prettier owns formatting
- [ ] `npm run dev` serves on the contract's port, and `/api` reaches the
  backend with the prefix stripped
- [ ] Every mutating request carries the CSRF header with
  `credentials: "same-origin"`, and nothing auth-related is in `localStorage`
- [ ] An anonymous visit redirects to sign-in, sign-in returns the user to
  where they were, any 401 signs them out, and "Sign out" calls the backend
- [ ] Tests stub the network with MSW and `onUnhandledRequest: "error"`; none
  needs a running backend

Then do `references/antd-app-setup.md`, if you have not already.
