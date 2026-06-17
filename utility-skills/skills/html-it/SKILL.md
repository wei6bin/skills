---
name: html-it
description: Generates a self-contained HTML implementation plan with UI mockups, data flow diagrams, and key code snippets. Use when the user wants a visual, readable plan for a feature or task — e.g. "/html-it", "make an html plan for this". Works on the current task in context.
---

Create a thorough implementation plan as a single self-contained HTML file for the current task or feature.

## The file must include

- **Overview** — a concise summary of what is being built and why
- **UI mockups** — ASCII or CSS-based mockups of key screens or components, rendered visually in HTML
- **Data flow** — a diagram (ASCII art or SVG) showing how data moves through the system: inputs, transformations, outputs, and API/service boundaries
- **Implementation phases** — a numbered breakdown of how you'd build this step by step, with dependencies between phases made explicit
- **Key code snippets** — the most important or non-obvious pieces of code the reader should review: interfaces, core logic, tricky edge cases. Not boilerplate — only what actually matters
- **Open questions / risks** — anything unresolved that could affect the plan

## Quality bar

- Must be easy to read and digest — use clear headings, visual separation, and good typography
- Self-contained: no external CSS frameworks or CDN links — all styles inline or in a `<style>` block
- Code snippets must be syntax-highlighted (use a simple inline approach — colored `<span>` tags or a `<pre><code>` block with manual highlights are fine)
- Mockups must actually look like mockups — use borders, padding, and layout to suggest real UI, not just describe it in text

## Output

Write the file to `implementation-plan.html` in the current directory (or a path that makes sense given the project context). Then tell the user the file path so they can open it in a browser.
