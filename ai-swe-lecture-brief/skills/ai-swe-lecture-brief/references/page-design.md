# Page design

Load the `artifact-design` skill first. This file is the subject-specific layer on top
of it, not a replacement.

## Treatment

An AI-and-software-engineering briefing is **utilitarian-editorial**: scanned under
delivery pressure by an engineer or manager deciding whether to adopt something, or
forming a view on where the industry is headed. Craft goes into information design and
typographic hierarchy, not into a large hero or decorative motion.

Derive the visual identity from software engineering's own world rather than a generic
"AI" look - a terminal palette, git-diff green/red, syntax-highlighting hues. Ground it
in something real about the material.

Avoid the current AI-generated defaults called out in `artifact-design` (warm cream with
a serif and terracotta accent, near-black with one acid pop, Inter or Space Grotesk,
emoji section markers, everything centred) **and** the AI-conference-talk cliche this
subject invites specifically: a purple-to-blue gradient hero, a robot or circuit-board
texture, glowing neon "AI" wordmarks.

## Layout

- **Full viewport width.** A sticky left rail carrying the outline - the SDLC-phase
  sequence for a workflow talk (e.g. discovery/plan -> code -> review -> test -> ship ->
  operate), or the theme/point-of-contention list for a panel or debate - content to the
  right. Collapse the rail to a horizontal scroller under ~1000px.
- Running prose held near 65-70ch **inside** a full-width page. Tables, diagrams, and
  code/command blocks span the full column.
- Every wide element gets its own `overflow-x: auto` container. The body must never
  scroll sideways.
- `font-variant-numeric: tabular-nums` anywhere benchmark or pricing figures stack.

## Typography

Three roles, and a real mono face is load-bearing here because commands, prompts,
config, and model names appear constantly:

- **Display** - headings, characterful, used with restraint
- **Body** - humanist sans for length
- **Mono** - commands, prompts, code, model/version names, benchmark figures

Google Fonts is the only external host the CSP permits. Always declare a fallback stack.

## Components this subject needs

Pick components by what the talk actually is. A tool-workflow demo needs the pipeline
diagram and command blocks; a panel or debate needs the position table instead. Do not
force a workflow talk's components onto a discussion that has no workflow in it.

**The pipeline diagram** (workflow talks). Hand-authored inline SVG driven by CSS
variables so it is theme-aware. Show the SDLC phases with where agents plug into each -
branch points, not a full taxonomy. Usually the single most valuable element on a
tool-focused page.

**The position table** (panels and debates). One row per theme or point of contention,
one column per speaker, stating their position in their own terms - not a chronological
transcript of who said what when. Add a row for where they actually agree; disagreement
gets more attention than agreement in a debate, but the page should not misrepresent the
argument as having no common ground.

**Command / prompt blocks.** Real monospace blocks styled like a terminal or editor for
example prompts and CLI invocations - not prose describing what to type.

**Tool comparison tables.** Header row, one row per tool or approach, a caption stating
how to read it. Add a caption line telling the reader to read **across** the row - the
pattern identifies the right tool for their case, rarely a single cell.

**Status chips.** Current / Evolving / Superseded as coloured mono spans, used to tag
claims that the accuracy pass identified as time-sensitive. Never encode meaning in
colour alone - the chip carries the word too.

**Callouts.** Two kinds only. A note for context or nuance, a warning for anything that
causes real harm if got wrong (secrets leaking into a prompt, an agent editing
production config, an unreviewed merge to `main`). More than two kinds and they stop
being read.

**Worked walkthrough.** `<details>`/`<summary>` so the reader commits before revealing.
Summary holds the scenario, the body holds numbered reasoning ending in the outcome.
Usually the highest-value part of the page for an IC reader on a workflow talk, so do
not truncate the set.

**Quick reference table.** A consolidated lookup near the end - phase or theme mapped to
technique, tool, or position - so the reader can enter from "what am I trying to do (or
figure out)" rather than from the top.

**Practice points.** Role-specific, per `audience.md`.

## Theme

Follow the three-state pattern from `artifact-design` exactly: complete light palette on
bare `:root`, a `@media (prefers-color-scheme: dark)` block guarded as
`:root:not([data-theme="light"])`, and a `:root[data-theme="dark"]` block. Every colour
comes from a token. `body` sets an explicit background token.

Check before publishing: no colour defined only inside a media or `[data-theme]` block,
and status-chip colours legible on both grounds.

## Footer

Attribute the source talk and speaker, state that tool capabilities, pricing, and model
lineups change quickly and the reader should verify current specs before acting on them,
and state plainly that the page is a briefing rather than vendor-endorsed advice.
