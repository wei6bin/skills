# Styling and shared components

## Identify the repo's real styling approach before assuming one

Check actual `className`/`style`/import usage in a few existing components -
don't infer the styling approach from `package.json` alone. A UI component
library (Ant Design, MUI, Chakra, Mantine) or a CSS-in-JS library can be an
installed dependency with zero real usage if the codebase moved away from it,
same as any other dead dependency. Common approaches, roughly in order of how
often they show up in this style of codebase: a utility-class framework
(Tailwind) with hand-rolled primitive components, a component library used
throughout, CSS Modules, or CSS-in-JS. Match whichever one the repo's components
actually use - mixing two approaches in one new feature reads as inconsistent
even if both are technically installed.

If the repo defines global design tokens (a `@theme` block, a CSS
custom-property sheet, a theme object passed to a provider), reference those
tokens rather than hardcoding raw values (hex colors, arbitrary pixel sizes) in
a new component.

## Which reference applies

| What you found | Do this |
| --- | --- |
| A real styling approach in use (Tailwind, CSS Modules, CSS-in-JS, a component library that isn't Ant Design) | Match it. Stop here - the rest of this file covers the hand-rolled-primitives case. Do **not** introduce Ant Design. |
| Ant Design already in real use | `references/antd-component-patterns.md` for the per-feature component mapping. The repo's own theme outranks it. |
| Nothing established - no UI library imported anywhere, no tokens, no shared primitives | `references/antd-app-setup.md`. Ant Design is this skill's greenfield default. |

"Nothing established" means exactly that: a genuinely new app, or a frontend
whose components are all unstyled. A repo with a working Tailwind setup has an
established approach even if you find it dated - swapping it is a migration the
user decides on deliberately, never a side effect of adding a feature.

## Shared primitives

If the repo hand-rolls its own primitives (buttons, inputs, etc.) rather than
using a component library, a new primitive should match their existing pattern:

- Props interface extends the native element's HTML attributes, plus whatever's
  custom.
- A `className` passthrough, spread onto the underlying element last so callers
  can override.
- Variant-to-style lookups as a plain object/record if that's the existing
  pattern, rather than introducing a new class-name utility (`cva`, `clsx`,
  etc.) the repo doesn't already use.
- Accessible ids (`useId()` or equivalent) and `aria-*`/`role` wiring matching
  the repo's existing form controls exactly, including error-message
  association.

## App-shell fallback components

If the app lazy-loads its root component behind `Suspense`/an error boundary,
check whether the fallback components carry a "keep this dependency-free"
constraint - they may render before the lazy chunk (and anything it imports) has
loaded, so importing a UI library or feature code into them could reintroduce
exactly the loading delay they exist to cover for. If such fallback components
already exist, read whatever comment/doc explains their constraints before
touching them, and keep any new one under the same constraint.

## Sizing

Prefer relative units (`rem`/`em`/percentage, or a utility framework's spacing
scale) over hardcoded pixel values, except where the repo's own baseline
definitions (breakpoints, base font size) or genuinely fixed cases (a 1px
border) already use pixels.
