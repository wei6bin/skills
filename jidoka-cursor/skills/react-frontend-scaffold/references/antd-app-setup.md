# Ant Design app setup (greenfield only)

Read this **only** when the app has no styling approach established yet - no UI
library in real use, no design tokens, no shared primitives. If the repo already
styles its components somehow, `references/styling-and-components.md` governs
instead, and you should not introduce Ant Design.

This file is read once per app. For the per-feature component choices you make
on every subsequent feature, see `references/antd-component-patterns.md`.

## First: check the installed version, don't write from memory

Ant Design moves faster than model training data, and v4-era code - Less
variable overrides, `antd/dist/antd.css`, `<Menu.Item>` children - is still what
most models reach for by default. Read the installed `antd` version from
`package.json` before writing a line, and if anything below disagrees with the
installed version's own types, the types win.

Traps that produce code which looks right and isn't:

| Don't write | Write instead |
| --- | --- |
| `import "antd/dist/antd.css"` | `import "antd/dist/reset.css"` - the full stylesheet is gone; v5 injects component CSS at runtime and ships only a reset |
| Less `modifyVars` / `@primary-color` overrides in the build config | `<ConfigProvider theme={{ token: { colorPrimary } }}>` - Less theming was removed with v5's CSS-in-JS engine |
| `import "antd/dist/antd.dark.css"` | `theme.darkAlgorithm` passed to `ConfigProvider` |
| `<Menu><Menu.Item/></Menu>`, `<Tabs><Tabs.TabPane/></Tabs>`, `<Collapse><Collapse.Panel/></Collapse>` | the `items` prop on each - the children APIs are deprecated/removed |
| `<Dropdown overlay={menu}>` | `<Dropdown menu={{ items }}>` |
| `<Modal visible>`, `<Drawer visible>`, `<Tooltip visible>` | `open` - renamed across every popup component |
| `import { message } from "antd"; message.success(...)` | `const { message } = App.useApp()` inside an `<App>` wrapper - the static methods render outside React context, so they ignore your theme and locale |
| `<Card bordered={false}>`, `<Input bordered={false}>` | `variant="borderless"` / `variant="outlined"` |
| `bodyStyle` / `headStyle` / `dropdownStyle` | the semantic `styles={{ body: {...} }}` / `classNames={{ ... }}` props |
| `dropdownClassName`, `dropdownRender` | `popupClassName`, `popupRender` |
| `<PageHeader>`, `<Comment>` | removed from antd core - compose them yourself, or take them from `@ant-design/pro-components` |
| `moment` adapters for DatePicker | antd ships on `dayjs`; adding moment back means an adapter you don't need |

`destroyOnClose` on `Modal`/`Drawer` was renamed to `destroyOnHidden` in later
5.x. Both matter (see the Modal-form trap in
`references/antd-component-patterns.md`) - check which one the installed types
accept rather than guessing.

**antd 6** is the current major (6.6 when this skill was embedded) and keeps
everything in the right-hand column above: `reset.css`, `ConfigProvider`
theming, `items` props, `App.useApp()`. Checked against its types: it
deprecates `destroyOnClose` (use `destroyOnHidden`), `Alert`'s `message` (use
`title`) and `Drawer`'s `width` (use `size`), and it rejects `cssVar: true`
(CSS variables are always on; `cssVar` now only takes an options object).
Deprecated props still compile, so the types will not stop you; read the
`@deprecated` tags in the installed `.d.ts` files for anything else these
references name.

## Packages

```bash
npm install antd @ant-design/icons @fontsource-variable/inter
```

That's the whole list. Ant Design v5 bundles its own CSS-in-JS engine
(`@ant-design/cssinjs`) and pulls in `dayjs` itself - there is no
emotion/styled-components peer to install, and adding a second CSS-in-JS runtime
just to restyle antd is a mistake. `@fontsource-variable/inter` self-hosts the
font: no CDN request, works offline and under a strict CSP.

Style extraction (`@ant-design/cssinjs`'s `createCache`/`extractStyle`) is an
SSR-only concern. A Vite SPA renders on the client, so skip it.

## Provider stack

```tsx
// src/main.tsx
import "@fontsource-variable/inter";
import "antd/dist/reset.css";
import { App as AntApp } from "antd";
import { ColorModeProvider } from "./theme/ColorModeProvider";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ColorModeProvider>
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </AntApp>
    </ColorModeProvider>
  </StrictMode>,
);
```

Three things here are load-bearing:

- `reset.css` is not optional - without it you get browser default margins and
  the font never applies to non-antd elements.
- `ColorModeProvider` (below) owns the `ConfigProvider`, so it sits outermost
  and every provider under it can render themed fallbacks.
- `<App>` is what makes `message`, `notification`, and `modal.confirm` read the
  theme and locale. Import it aliased (`App as AntApp`) if your own root
  component is also called `App`. Mount exactly one, at the root.

## `src/theme/theme.ts` - the Neutral Enterprise preset

The default. Restrained, legible, appropriate for line-of-business apps. Two
presets below adjust it rather than replacing it.

```ts
import type { ThemeConfig } from "antd";

// Shared by the Layout header and the sider's brand row, so the two line up.
export const HEADER_HEIGHT = 56;

export const themeConfig: ThemeConfig = {
  // antd 6 always emits CSS custom properties, so a theme/mode switch doesn't
  // re-serialise every style; on 5.12+ add `cssVar: true` for the same effect
  // (antd 6 types `cssVar` as an options object and rejects `true`).
  // hashed: false drops the hash suffix from class names - safe only with a
  // single antd version on the page.
  hashed: false,
  token: {
    colorPrimary: "#4338CA",
    colorInfo: "#4338CA",
    colorLink: "#4338CA",
    colorSuccess: "#15803D",
    colorWarning: "#B45309",
    colorError: "#B91C1C",
    borderRadius: 8,
    fontFamily: '"Inter Variable", system-ui, -apple-system, sans-serif',
    fontSize: 14,
    wireframe: false,
  },
  components: {
    Layout: { headerHeight: HEADER_HEIGHT, headerPadding: "0 16px" },
    Menu: { itemBorderRadius: 8, itemMarginInline: 8 },
    Card: { paddingLG: 20 },
    Table: { headerBorderRadius: 0 },
    Button: { fontWeight: 600 },
  },
};
```

Set the **seed** tokens and let antd derive the rest. `colorPrimary` alone
generates a ten-step palette plus hover/active/border/background variants;
hand-writing `colorPrimaryHover` next to it is how a theme ends up internally
inconsistent. Component-token names under `components` have been renamed across
5.x minors (`colorBgHeader` → `headerBg`, and similar) - check the installed
types before adding one.

Keep **one** font family for app chrome. Pairing a characterful display face
with a body face is a marketing-page technique; in dense product UI it reads as
inconsistent. The personality here comes from weight, radius, and colour, not a
second download.

### Dark mode is derived, not written twice

Unlike theme systems that want two full palettes, antd computes the dark palette
from the same seed tokens via `theme.darkAlgorithm`. Write the light seed once;
only override a token for dark when the derived value is genuinely wrong
(usually the background, or a brand colour that fails contrast on dark).

Override the background through the **seed** `colorBgBase`, never one derived
surface. A lone `colorBgLayout` leaves the containers, header and sider on
antd's derived neutral `#141414` beside a blue-black page, and the app reads as
two themes; from the seed, every background and border derives from one hue.

```ts
// src/theme/theme.ts (continued)
export const darkTokenOverrides: ThemeConfig["token"] = {
  colorPrimary: "#A5B4FC", // the light primary is too dark to read on a dark surface
  colorBgBase: "#0D1117", // the seed: layout, containers and borders all follow it
};
```

### Preset deltas

Apply these **on top of** the block above - change only the listed keys, don't
fork the whole file.

**Dense Data** - admin consoles, wide tables, users who live in the app all day.
Compose antd's compact algorithm rather than hand-shrinking every token, and set
the default control size once on `ConfigProvider` instead of passing
`size="small"` per component:

```ts
// in ColorModeProvider, alongside the light/dark algorithm:
algorithm: [isDark ? theme.darkAlgorithm : theme.defaultAlgorithm, theme.compactAlgorithm],
// on ConfigProvider itself:
componentSize="small"
// in themeConfig:
token: { borderRadius: 6, fontSize: 13, /* ...keep the rest */ },
```

**Friendly SaaS** - customer-facing, lower information density:

```ts
token: { borderRadius: 14, colorPrimary: "#7C3AED", colorInfo: "#7C3AED", colorLink: "#7C3AED" },
darkTokenOverrides: { colorPrimary: "#C4B5FD" },
```

### Deriving tokens from a brand instead of a preset

When the user wants a distinctive identity rather than a preset, invoke the
`frontend-design` skill - but scope it tightly. It exists to produce
non-templated visual identities, which is the right instinct for the token layer
and the wrong one for component styling.

It may decide: seed colour values, the type pairing, border radius, and density.
Everything it returns goes into `theme.ts` and nowhere else.

It may **not**: add bespoke CSS or stylesheet files, hand-roll replacements for
antd components, or introduce per-component styling outside
`themeConfig.components`. If a proposal can't be expressed as antd tokens, it's
out of scope here.

If `frontend-design` isn't installed, pick the closest preset and move on -
don't block on it.

## `src/theme/ColorModeProvider.tsx`

Ant Design has no built-in mode store - you own the state and hand it the right
algorithm. Persist the choice and honour the OS preference until the user
overrides it.

```tsx
type Mode = "light" | "dark" | "system";

const ColorModeContext = createContext<{ mode: Mode; setMode: (m: Mode) => void; isDark: boolean }>({
  mode: "system", setMode: () => {}, isDark: false,
});
export const useColorMode = () => useContext(ColorModeContext);

export function ColorModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(() => (localStorage.getItem("color-mode") as Mode) ?? "system");
  const [systemDark, setSystemDark] = useState(
    () => window.matchMedia("(prefers-color-scheme: dark)").matches,
  );

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => localStorage.setItem("color-mode", mode), [mode]);

  const isDark = mode === "dark" || (mode === "system" && systemDark);
  const value = useMemo(() => ({ mode, setMode, isDark }), [mode, isDark]);

  return (
    <ColorModeContext.Provider value={value}>
      <ConfigProvider
        theme={{
          ...themeConfig,
          algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
          token: { ...themeConfig.token, ...(isDark ? darkTokenOverrides : {}) },
        }}
      >
        {children}
      </ConfigProvider>
    </ColorModeContext.Provider>
  );
}
```

`theme` here is antd's exported `theme` object
(`import { ConfigProvider, theme } from "antd"`) - it carries both the
algorithms and the `useToken` hook, and it is easy to shadow with a local
variable named `theme`. Name your own config `themeConfig` for exactly that
reason.

## `src/app/AppShell.tsx`

A persistent shell is the single largest contributor to an app reading as a real
product rather than a page of components. Build it before the first feature.

```tsx
const { Header, Sider, Content } = Layout;
const SIDER_WIDTH = 240;

// Keyed by path. Home is there from day one, so the sider and the drawer are
// never empty; each feature adds its own item.
const NAV_ITEMS = [{ key: "/", icon: <HomeOutlined />, label: "Home" }];

// The longest key the pathname starts with; "/" only matches itself.
function selectedNavKey(pathname: string) {
  return NAV_ITEMS.map((item) => item.key)
    .filter((key) => (key === "/" ? pathname === "/" : pathname.startsWith(key)))
    .sort((a, b) => b.length - a.length)[0] ?? "";
}

// Exactly the header's height, with the header's hairline: the name sits on the
// header's centre line and the two bottom borders read as one line.
function Brand() {
  const { token } = theme.useToken();
  return (
    <div style={{ height: HEADER_HEIGHT, display: "flex", alignItems: "center",
                  paddingInline: token.paddingLG,
                  borderBlockEnd: `1px solid ${token.colorBorderSecondary}` }}>
      <Typography.Text strong style={{ fontSize: token.fontSizeHeading4 }}>{APP_NAME}</Typography.Text>
    </div>
  );
}

export function AppShell() {
  const { token } = theme.useToken();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const screens = Grid.useBreakpoint();
  const isDesktop = screens.md ?? true;
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const nav = (
    <Menu
      mode="inline"
      items={NAV_ITEMS}
      selectedKeys={[selectedNavKey(pathname)]}
      onClick={({ key }) => { navigate(key); setDrawerOpen(false); }}
      style={{ borderInlineEnd: "none" }}
    />
  );

  return (
    <Layout style={{ minHeight: "100dvh" }}>
      {isDesktop ? (
        <Sider
          width={SIDER_WIDTH}
          theme="light"
          style={{ position: "sticky", top: 0, height: "100dvh",
                   borderInlineEnd: `1px solid ${token.colorBorderSecondary}` }}
        >
          <Brand />
          {nav}
        </Sider>
      ) : (
        <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title={APP_NAME}
                placement="left" size={SIDER_WIDTH}
                styles={{ body: { padding: 0, paddingBlockStart: token.paddingXS } }}>
          {nav}
        </Drawer>
      )}

      <Layout style={{ minWidth: 0 }}>
        <Header style={{ position: "sticky", top: 0, zIndex: 10, display: "flex", alignItems: "center",
                         gap: token.marginSM, background: token.colorBgContainer,
                         borderBlockEnd: `1px solid ${token.colorBorderSecondary}` }}>
          {!isDesktop && (
            <Button type="text" icon={<MenuOutlined />} aria-label="Open navigation"
                    onClick={() => setDrawerOpen(true)} />
          )}
          {/* The sider carries the name on desktop; without it, the header does. */}
          <Typography.Text strong style={{ flex: 1 }}>{isDesktop ? null : APP_NAME}</Typography.Text>
          <ColorModeToggle />
        </Header>

        <Content style={{ padding: token.paddingLG, minWidth: 0 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
```

Details that are load-bearing:

- **`Menu` takes `items`, and does no route matching.** `selectedKeys` is yours
  to compute - key each nav item by its path and pick the longest one `pathname`
  starts with, or nested routes light up nothing (or everything).
- **`minWidth: 0` on the inner `Layout` and on `Content`** lets wide children
  (tables, long code blocks) scroll internally instead of forcing the whole page
  to scroll sideways.
- **`Header` has a background of its own** from antd's Layout tokens - the
  default is a dark navy that fights a light theme. Set it explicitly
  (`token.colorBgContainer` above) or via the `Layout.headerBg` component token.
- **The brand row is the header's height, from one constant.** Sized by a
  heading's own padding instead, the name lands a couple of pixels off the
  header's centre line and its divider misses the header's bottom border.
- **The name appears exactly once per layout**: in the sider on desktop, in the
  header on a phone, and as the `Drawer`'s `title` - which also fills the
  drawer's header row, otherwise an empty strip holding only the close button.
  Don't repeat the brand inside the drawer body.
- **antd 6 sizes a `Drawer` with `size`**; `width` still works but is
  deprecated.
- **`Grid.useBreakpoint()` calls `matchMedia`**, which jsdom doesn't implement.
  The shell is usually the first thing to blow up a test run - see the stub note
  in `references/testing.md`.

Adapt `<Outlet />`/`useLocation` to whatever the router provides - `children`
works equally well if there's no router yet.

### Colour-mode toggle

```tsx
function ColorModeToggle() {
  const { isDark, setMode } = useColorMode();
  return (
    <Button
      type="text"
      icon={isDark ? <SunOutlined /> : <MoonOutlined />}
      onClick={() => setMode(isDark ? "light" : "dark")}
      aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
    />
  );
}
```

Icon-only buttons need `aria-label` - antd renders the icon as decorative markup
with no accessible name of its own.

## Anti-default checklist

Stock Ant Design looks like an admin template for specific, fixable reasons.
Before calling a greenfield setup done, confirm every line:

- [ ] `colorPrimary` is **not** `#1677ff` (or v4's `#1890ff`) - the default blue
  is the single clearest tell of an unstyled antd app
- [ ] A real font is loaded and `token.fontFamily` points at it; the app is not
  silently on the default system stack
- [ ] The sider is not the stock dark-navy `Menu theme="dark"` against a light
  body, unless that contrast is a deliberate choice
- [ ] Surfaces are separated by hairline borders (`token.colorBorderSecondary`),
  not stacked shadows
- [ ] One `token.borderRadius` drives every corner in the app - antd's default 6
  is a choice, not a given
- [ ] The sider's brand row is the header's height, so the name sits on the
  header's centre line and the two hairlines join into one
- [ ] At phone width the header still shows the app name and every header
  control, and the drawer opens with the name in its header row
- [ ] The nav is never empty: Home at `/` from the first commit, selected on
  the home page
- [ ] No success toast for a result the user can already see (signing in,
  creating a row that appears) - see `references/antd-component-patterns.md`
- [ ] Dark mode actually works - toggle it and read every screen, don't assume
  `darkAlgorithm` handled it - and every surface (page, header, sider, cards)
  shares one hue
- [ ] `reset.css`, `<App>`, `ConfigProvider`, and the AppShell are all in place
  before the first feature is built
- [ ] Nothing imports the static `message`/`notification`/`Modal.confirm` - they
  render outside the theme
- [ ] No raw hex value or `px` dimension appears anywhere outside `theme.ts`;
  everything else reads `theme.useToken()`
