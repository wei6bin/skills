# Page design

Load the `artifact-design` skill first. This file is the subject-specific layer on top
of it, not a replacement.

## Treatment

A clinical reference is **utilitarian-editorial**: scanned repeatedly, returned to under
time pressure, read by someone who needs one fact fast. Craft goes into information
design and typographic hierarchy, not into a large hero or decorative motion.

Derive the visual identity from the subject's own world rather than a generic medical
look. Wright-Giemsa stain colours for hematology, imaging greys for radiology, an ECG
trace for cardiology. Ground the palette in something real about the material.

Avoid the current AI-generated defaults called out in `artifact-design`: warm cream with
a serif and terracotta accent, near-black with one acid pop, Inter or Space Grotesk,
emoji section markers, everything centred.

## Layout

- **Full viewport width.** A sticky left rail carrying the algorithm or chapter outline,
  content to the right. Collapse the rail to a horizontal scroller under ~1000px.
- Running prose held near 65-70ch **inside** a full-width page. Tables, diagrams and
  reference grids span the full column.
- Every wide element gets its own `overflow-x: auto` container. The body must never
  scroll sideways.
- `font-variant-numeric: tabular-nums` anywhere digits stack.

## Typography

Three roles, and a real mono face matters here because lab values, ranges and units
appear constantly:

- **Display** - headings, characterful, used with restraint
- **Body** - humanist sans for length
- **Mono** - lab values, ranges, thresholds, cutoffs

Google Fonts is the only external host the CSP permits. Always declare a fallback stack.

## Components this subject needs

**Numbered sections.** Only when the content is genuinely sequential, e.g. a diagnostic
algorithm. Numbering a non-sequence is decoration pretending to be structure.

**The algorithm diagram.** Hand-authored inline SVG driven by CSS variables so it is
theme-aware. Keep it shallow and horizontal: branch points, not a full taxonomy. This is
usually the single most valuable element on the page.

**Comparison tables.** The core unit. Header row, one row per condition, a caption
stating how to read it. Add a caption line telling the reader to read **across** the row
- the pattern identifies the condition, rarely a single cell.

**Value chips.** High / low / normal as coloured mono spans. Semantic colour must be
separate from the page accent: ochre high, steel blue low, green normal. Never encode
meaning in colour alone - the chip carries the word too.

**Callouts.** Two kinds only. A note for mechanism or context, a warning for anything
that causes harm if got wrong. More than two kinds and they stop being read.

**Worked cases.** `<details>`/`<summary>` so the reader commits before revealing. Summary
holds the vignette with its values; the body holds numbered reasoning ending in a
highlighted diagnosis line. These are the highest-value part of the page for a trainee,
so do not truncate the set.

**Quick reference table.** A consolidated lookup near the end - findings mapped back to
differentials - so the reader can enter from an observation rather than from the top.

**Practice points.** Role-specific, per `audience.md`.

## Theme

Follow the three-state pattern from `artifact-design` exactly: complete light palette on
bare `:root`, a `@media (prefers-color-scheme: dark)` block guarded as
`:root:not([data-theme="light"])`, and a `:root[data-theme="dark"]` block. Every colour
comes from a token. `body` sets an explicit background token.

Check before publishing: no colour defined only inside a media or `[data-theme]` block,
and semantic lab colours legible on both grounds - the ochre and green both need lifting
in dark mode.

## Footer

Attribute the source lecture, state that ranges and thresholds vary by laboratory and
guideline, and state plainly that the page is an educational aid rather than a treatment
protocol. One short paragraph each.
