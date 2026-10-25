---
name: ai-swe-lecture-brief
description: Turn a YouTube talk, panel, debate, or podcast about AI and software engineering into a published, audience-calibrated teaching artifact. Fetches the transcript, repairs speech-recognition garbling of tool and model names, separates verifiable claims from speaker opinion and checks the former for currency against today's state of the art, and builds a designed HTML reference. Use when the user gives a YouTube URL of a talk, panel, debate, or podcast about AI coding agents, agentic engineering workflows, Claude Code, Cursor, Copilot, spec-driven development, AI-assisted code review/testing, or the broader shift AI is causing in software engineering work, and wants notes, a writeup, a summary, a briefing, or an artifact from it - including phrasings like "write this up for my engineering team", "make a briefing from this talk for tech leads", "summarize this AI and software engineering panel for an EM", "turn this into a reference for our platform team".
---

# AI & Software Engineering Lecture Brief

Turns a talk, panel, or debate about AI and software engineering into a reference that
is **better than the talk**: same content, corrected, checked for currency, reorganised
for retrieval, and pitched at a named engineering audience.

The output is a published HTML Artifact. A Word `.docx` is available as a follow-on
(see "Optional: Word export").

## Inputs

| Input | Required | Notes |
|---|---|---|
| YouTube URL or video ID | yes | Any format the transcript tool accepts |
| Audience | yes | e.g. "IC engineer", "tech lead", "engineering manager", "platform/DevOps engineer", "engineering director". If the user did not say, **ask** - it changes depth, vocabulary and what gets emphasised. |

## Step 1 - Fetch the transcript

```bash
~/.claude/skills/ai-swe-lecture-brief/scripts/fetch-transcript.sh '<url>' --chapters
```

Quote the URL. The script prints the transcript path as its last stdout line.

It handles this machine's TLS-inspection problem, which otherwise breaks the `yt-dlp`
fallback that YouTube forces you onto. Do not try to fix SSL failures by disabling
certificate verification; the script builds a correct trust bundle instead.

Add `--speakers` for panels, interviews, or any two-or-more-person discussion - a debate
between named speakers loses its shape without attribution. Skip it **only** for a
single-speaker talk, where it costs a whole extra pass to label every paragraph with one
name.

## Step 2 - Read the whole transcript

Read it end to end in chunks, e.g. `head -c 27000`, then `tail -c +27001 | head -c 27000`.

Do not skim and do not delegate this to a subagent that returns a summary. You are about
to make claims about tool capabilities and workflows that a reader will act on; the
summary of a summary is where errors enter.

## Step 3 - Accuracy pass

**Read `references/accuracy.md`.** Auto-generated captions mangle tool and model names
badly, speakers misspeak, verifiable claims that were true on the recording date can be
stale by the time you write this, and - specific to talks in this space - speakers state
strong opinions and predictions that must not be silently treated as fact. All four must
be handled before anything is written.

Never propagate a transcript spelling you have not recognised, never propagate a
technical claim you have not checked for currency, and never present a speaker's opinion
or prediction as settled fact. If you cannot resolve a garbled term or verify a claim,
say so in the output rather than guessing.

## Step 4 - Synthesise, do not transcribe

Write the content **in your own words and your own structure**. You are producing an
independent engineering reference informed by the talk - not a reformatted copy of
someone's slides.

Concretely:

- Reorganise for **retrieval**, not for playback order. A talk is linear because speech
  is; a reference should be a decision structure - by SDLC phase and tool for a
  workflow-focused talk, by theme and point-of-contention for a panel or debate.
- Turn tool/approach comparisons into tables. Speakers say them serially; readers want
  them adjacent. Turn a debate's opposing positions into a side-by-side, not a
  chronological transcript of who said what when.
- Add what the talk assumed but never said, and what a practitioner in the target role
  needs but a talk aimed at a general audience skips.
- Keep the speakers' genuinely good pedagogy - a memorable framing, a workflow diagram,
  a worked example or analogy that lands.
- Do not reproduce extended verbatim passages, and do not carry across filler, asides,
  or vendor pitching.

## Step 5 - Calibrate to the audience

**Read `references/audience.md`** for how depth, vocabulary, emphasis and the "practice
points" section shift by role.

## Step 6 - Design and build the page

**Load the `artifact-design` skill first** - it is mandatory before writing any artifact.
Then read `references/page-design.md` for the structure, the palette, and the components
this kind of reference needs.

Two non-negotiables from the user's global CLAUDE.md:

- Use the **full viewport width**, never a narrow centred column.
- **No em dashes.** Use a plain `-`.

## Step 7 - Publish

Publish with the `Artifact` tool. Give it a real name (a short noun phrase naming the
subject, not "AI Notes"), a one-sentence `description`, and a stable `favicon`.

Then tell the user, briefly:

- What the talk was, and what the page covers
- **Corrections you made** to the talk's content, with the correct fact
- **Claims flagged as stale** by the currency check, with what's true now
- **Opinions/predictions** you kept clearly labelled as the speakers' view rather than fact
- **Additions** you made for the audience that the talk did not cover
- Any judgement call worth reversing

That report matters. The user is relying on this page to brief their team, so silent
fixes are worse than no fixes.

## Optional: Word export

If the user wants `.docx`, generate it with `python-docx` rather than converting the
HTML. There is no pandoc or LibreOffice on this machine, and a conversion loses the
tables, colour coding and diagrams anyway.

Build the document directly from the same content: real `Heading 1/2` styles so the
Navigation Pane and a TOC field work, native tables with shaded repeating headers, and
cross-platform fonts (Georgia / Calibri / Consolas) so it renders the same on a
colleague's machine. Rasterise the pipeline diagram with Pillow, since Word will not
take inline SVG. Worked-walkthrough elements must be flattened into a printed layout:
scenario, then reasoning, then outcome.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `CERTIFICATE_VERIFY_FAILED` | Stale trust bundle. `rm ~/.cache/ai-swe-lecture-brief/ca-bundle.pem` and re-run. |
| "Transcript fetch returned empty snippets" | Normal. YouTube is refusing the direct API; the script falls back to `yt-dlp` and continues. Only a concern if the run then fails. |
| "bot detected" persists | Re-run with `YOUTUBE_TRANSCRIPT_COOKIES_FROM_BROWSER=chrome`. |
| No captions at all | Nothing to do - the video has none. Say so rather than inventing content. |
| Transcript looks like a different video | The tool caches by video ID. Re-run with `--refresh`. |
