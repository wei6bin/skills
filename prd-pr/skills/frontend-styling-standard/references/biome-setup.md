# Biome setup, the no-inline-style plugin, and CI

Biome is the recommended linter: one fast binary, no plugin-dependency sprawl.
Keep the existing formatter (usually Prettier) and turn Biome's formatter off,
unless the user wants Biome to own formatting too.

## Install & scripts

```bash
pnpm add -D -w @biomejs/biome   # -w for the workspace root
```

Point the package scripts at Biome, keep Prettier for `format`:

```jsonc
{
  "scripts": {
    "lint": "biome lint .",
    "lint:fix": "biome lint --write .",
    "format:check": "prettier --check .",
    "format": "prettier --write ."
  }
}
```

Remove ESLint and its plugins (`eslint`, `@eslint/js`, `typescript-eslint`,
`eslint-config-prettier`, `eslint-plugin-*`) and delete `eslint.config.*`.

## biome.json

```jsonc
{
  "$schema": "https://biomejs.dev/schemas/2.5.6/schema.json",
  "vcs": { "enabled": true, "clientKind": "git", "useIgnoreFile": false },
  "files": {
    "ignoreUnknown": true,
    "includes": ["**", "!**/dist", "!**/coverage", "!**/generated", "!**/*.generated.ts"]
  },
  "formatter": { "enabled": false },
  "assist": { "enabled": false },
  "css": { "parser": { "tailwindDirectives": true } },
  "linter": {
    "enabled": true,
    "rules": { "preset": "recommended" }
  },
  "plugins": ["./biome/no-inline-style.grit"],
  "overrides": [
    { "includes": ["**/*.test.tsx", "**/*.test.ts"], "linter": { "rules": { "style": { "noNonNullAssertion": "off" } } } }
  ]
}
```

Notes learned the hard way:
- `useIgnoreFile: false` when the repo's `.gitignore` isn't in the folder Biome
  runs from (e.g. a `frontend/` subdir); scope via `files.includes` instead.
- Folder ignores are `"!**/dist"` — **not** `"!**/dist/**"` (Biome warns
  otherwise).
- `css.parser.tailwindDirectives: true` is required or Biome errors on
  `@theme`/`@source`/`@apply`.
- `biome.json` is strict JSON — **no `comment` keys** anywhere; it errors.
- Biome's `recommended` set is stricter than a minimal ESLint config. It will
  surface real findings ESLint didn't (a11y, `noNonNullAssertion`, unsafe
  optional chaining). To keep the linter *swap* non-breaking, downgrade the
  newly-erroring rules to `warn` in `biome.json`, land the swap, then fix them
  and re-escalate to `error` in a follow-up. Don't let the swap break CI on
  pre-existing issues the team never opted into.

## The "no inline style" rule — a GritQL plugin

Biome has no built-in no-inline-styles rule; author one as a GritQL plugin.
`biome/no-inline-style.grit`:

```grit
// STY-R1 — flag inline style={{…}} on JSX. Static styling belongs in a
// component / design-token class / Tailwind utility. Dynamic values only.
`style={$value}` where {
  register_diagnostic(
    span = $value,
    message = "Avoid inline style={{…}} (STY-R1). Use a layout component / design-token class / Tailwind utility. Dynamic values only, with a biome-ignore + reason.",
    severity = "warn"
  )
}
```

- Start at `severity = "warn"` (CI stays green: Biome exits 0 on warnings,
  non-zero only on errors). Flip to `"error"` once every static inline style is
  migrated.
- Exempt files that legitimately need inline styles (e.g. a self-contained
  print/email stylesheet) and test files via an `overrides` entry with
  `"plugins": []`.
- Suppress a genuinely dynamic case in code with
  `// biome-ignore lint/plugin: <reason>` on the line above.
- Verify the flip worked: `biome lint .` exits 0 on clean code, and a probe
  file with a new `style={{color:"red"}}` exits 1.

## CI workflow

Often there's no CI at all — the highest-leverage single change, because an
unenforced standard is a suggestion. A minimal GitHub Actions gate (adjust
`working-directory` / package manager to the repo):

```yaml
name: Frontend CI
on:
  pull_request: { paths: ["frontend/**", ".github/workflows/frontend-ci.yml"] }
  push: { branches: [main], paths: ["frontend/**", ".github/workflows/frontend-ci.yml"] }
concurrency: { group: frontend-ci-${{ github.ref }}, cancel-in-progress: true }
defaults: { run: { working-directory: frontend } }
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with: { version: 10.33.0 }
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: pnpm, cache-dependency-path: frontend/pnpm-lock.yaml }
      - run: pnpm install --frozen-lockfile
      - run: pnpm build       # BEFORE typecheck/test — packages emit dist/ that consumers resolve
      - run: pnpm typecheck
      - run: pnpm test
      - run: pnpm lint
      - run: pnpm format:check
```

Before relying on `format:check` in CI, make it green: add generated files to
`.prettierignore` and format any pre-existing offenders.
