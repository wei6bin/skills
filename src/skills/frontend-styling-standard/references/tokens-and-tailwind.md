# Single-source tokens + Tailwind wiring

## Single-source the design tokens (kills theme/CSS drift)

If the component-library theme (JS) and the CSS custom properties both hardcode
the same values, they drift. Make one module the source of truth and derive the
theme from it; keep the CSS `:root` vars as the CSS-side mirror, guarded by a
test.

`tokens.ts` (raw values — keys map 1:1 to the `--x-*` custom properties):

```ts
export const color = { bluegrey: "#30515B", green: "#00AF71", /* … */ } as const;
export const space = { 1: "0.25rem", 2: "0.5rem", 3: "0.625rem", 4: "0.75rem",
  5: "1rem", 6: "1.5rem", 7: "2rem", 8: "2.5rem", 9: "3rem" } as const;
export const radius = { sm: "5px", md: "8px", lg: "16px", xl: "24px" } as const;
export const tokens = { color, space, radius } as const;
```

The antd (or MUI) theme imports from `tokens` — **no literal hex in the theme
file anymore**:

```ts
import { color } from "./tokens";
export const theme: ThemeConfig = { token: { colorPrimary: color.bluegrey, /* … */ } };
```

**Drift-guard test** — reads the CSS and fails if any token diverges from its
`--x-*` declaration. Case-normalize both sides so hex case doesn't matter:

```ts
const css = readFileSync(join(process.cwd(), "src/theme.css"), "utf8"); // cwd = package root under vitest
const cssVar = (name: string) => css.match(new RegExp(`${name}\\s*:\\s*([^;]+);`))?.[1].trim().toLowerCase();
it.each(Object.entries({ bluegrey: "--x-bluegrey", green: "--x-green" /* … */ }))(
  "color.%s matches %s", (k, v) => expect(cssVar(v)).toBe(color[k].toLowerCase()));
```

Gotcha: under vitest, `import.meta.url` may not be a `file:` URL — resolve the
CSS via `process.cwd()` (vitest runs with cwd at the package root), not
`new URL(...)`. Keep token hex **canonical (e.g. uppercase)** so any test that
asserts a theme value byte-for-byte keeps passing after the refactor.

## Tailwind v4, CSS-first, consuming the tokens

Tailwind is the layout/utility layer only. Wire it to the existing tokens so
there's one set of values.

```bash
pnpm --filter app-a --filter app-b add -D tailwindcss @tailwindcss/vite
```

Entry CSS (imported once per app, **after** the token CSS so `--x-*` exist):

```css
/* Preflight OMITTED — the app + component library already own the reset; a
   third reset regresses both. Import only theme + utilities layers. */
@layer theme, components, utilities;
@import "tailwindcss/theme.css" layer(theme);
@import "tailwindcss/utilities.css" layer(utilities);

/* Workspace packages resolve via node_modules symlinks, which Tailwind skips —
   point @source at the real sources so classes used there generate. */
@source "../../../apps";
@source "../../../packages";

/* Map colour + radius utilities onto the --x-* tokens (single source). `inline`
   keeps utilities referencing var(--x-*) rather than copying the value. */
@theme inline {
  --color-bluegrey: var(--x-bluegrey);
  --color-green: var(--x-green);
  --radius-md: var(--x-radius-md);
}
```

Add `tailwindcss()` to each app's `vite.config.ts` plugins. **No
`tailwind.config.js` needed** for token wiring in v4.

### Decisions that bite

- **Spacing scale**: check whether your token spacing values already land on
  Tailwind's default 4px grid. They often do (0.75rem = `gap-3`, 1rem = `gap-4`,
  0.625rem = `gap-2.5`). If so, **keep Tailwind's default scale** — no override,
  standard muscle memory, and utilities already agree with tokens. Only redefine
  the scale if the values genuinely don't line up.
- **Preflight**: off (see above). In v4 that means importing only the `theme`
  and `utilities` layers, never the bundled `@import "tailwindcss"`.
- **pnpm dual-Vite type clash**: `@tailwindcss/vite` may resolve against a
  second Vite instance (differs only by optional peers), so `tsc` flags the
  plugin's type in `vite.config.ts`. Cast it: `tailwindcss() as PluginOption`.
  Runtime is the same Vite; the cast reconciles types only.
- **Biome + Tailwind CSS**: set `css.parser.tailwindDirectives: true` so Biome
  accepts `@theme`/`@source`.
