---
name: clinical-lecture-brief
description: Turn a clinical or medical YouTube lecture into a published, audience-calibrated teaching artifact. Fetches the transcript, repairs speech-recognition garbling, verifies the medicine against current teaching, and builds a designed HTML study reference. Use when the user gives a YouTube URL of a medical, nursing, pharmacology or other clinical lecture and wants notes, a study guide, a summary, a revision page, a teaching write-up or an artifact from it - including phrasings like "write this up for an APN intern", "make study notes from this lecture for a medical student", "turn this video into a reference for residents".
---

# Clinical Lecture Brief

Turns a lecture video into a study reference that is **better than the lecture**: same
content, corrected, reorganised for retrieval, and pitched at a named audience.

The output is a published HTML Artifact. A Word `.docx` is available as a follow-on
(see "Optional: Word export").

## Inputs

| Input | Required | Notes |
|---|---|---|
| YouTube URL or video ID | yes | Any format the transcript tool accepts |
| Audience | yes | e.g. "APN intern", "medical student with APN background", "FY1", "pharmacy resident". If the user did not say, **ask** - it changes depth, vocabulary and what gets emphasised. |

## Step 1 - Fetch the transcript

```bash
~/.claude/skills/clinical-lecture-brief/scripts/fetch-transcript.sh '<url>' --chapters
```

Quote the URL. The script prints the transcript path as its last stdout line.

It handles this machine's TLS-inspection problem, which otherwise breaks the `yt-dlp`
fallback that YouTube forces you onto. Do not try to fix SSL failures by disabling
certificate verification; the script builds a correct trust bundle instead.

Add `--speakers` **only** for interviews or panels. For a single-narrator lecture it
costs a whole extra pass to label every paragraph with one name.

## Step 2 - Read the whole transcript

Read it end to end in chunks, e.g. `head -c 27000`, then `tail -c +27001 | head -c 27000`.

Do not skim and do not delegate this to a subagent that returns a summary. You are about
to make claims about medicine; the summary of a summary is where errors enter.

## Step 3 - Accuracy pass

**Read `references/accuracy.md`.** Auto-generated captions mangle medical vocabulary
badly and lecturers misspeak. Both must be fixed before anything is written.

Never propagate a transcript spelling you have not recognised. If you cannot identify a
garbled term from context, say so in the output rather than guessing.

## Step 4 - Synthesise, do not transcribe

Write the teaching content **in your own words and your own structure**. You are
producing an independent reference on the subject, informed by the lecture's clinical
approach - not a reformatted copy of someone's script.

Concretely:

- Reorganise for **retrieval**, not for playback order. A lecture is linear because
  speech is; a reference should be a decision structure.
- Turn comparisons into tables. Lecturers say them serially; readers want them adjacent.
- Add what the lecture assumed but never said, and what a practitioner in the target
  role needs but a lecture aimed at examinations skips.
- Keep the lecturer's genuinely good pedagogy - a memorable framing, a diagnostic
  sequence, a mnemonic that works.
- Do not reproduce extended verbatim passages, and do not carry across filler, asides,
  or channel promotion.

## Step 5 - Calibrate to the audience

**Read `references/audience.md`** for how depth, vocabulary, emphasis and the
"practice points" section shift by role.

## Step 6 - Design and build the page

**Load the `artifact-design` skill first** - it is mandatory before writing any artifact.
Then read `references/page-design.md` for the structure, the palette, and the components
this kind of reference needs.

Two non-negotiables from the user's global CLAUDE.md:

- Use the **full viewport width**, never a narrow centred column.
- **No em dashes.** Use a plain `-`.

## Step 7 - Publish

Publish with the `Artifact` tool. Give it a real name (a short noun phrase naming the
subject, not "Study Notes"), a one-sentence `description`, and a stable `favicon`.

Then tell the user, briefly:

- What the lecture was, and what the page covers
- **Corrections you made** to the lecture's content, with the correct fact
- **Additions** you made for the audience that the lecture did not cover
- Any judgement call worth reversing

That report matters. The user is relying on this page to teach someone, so silent fixes
are worse than no fixes.

## Optional: Word export

If the user wants `.docx`, generate it with `python-docx` rather than converting the
HTML. There is no pandoc or LibreOffice on this machine, and a conversion loses the
tables, colour coding and diagrams anyway.

Build the document directly from the same content: real `Heading 1/2` styles so the
Navigation Pane and a TOC field work, native tables with shaded repeating headers, A4
page setup, and cross-platform fonts (Georgia / Calibri / Consolas) so it renders the
same on a colleague's machine. Rasterise any diagram with Pillow, since Word will not
take inline SVG. Interactive elements such as click-to-reveal cases must be flattened
into a printed layout: vignette, then reasoning, then answer.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `CERTIFICATE_VERIFY_FAILED` | Stale trust bundle. `rm ~/.cache/clinical-lecture-brief/ca-bundle.pem` and re-run. |
| "Transcript fetch returned empty snippets" | Normal. YouTube is refusing the direct API; the script falls back to `yt-dlp` and continues. Only a concern if the run then fails. |
| "bot detected" persists | Re-run with `YOUTUBE_TRANSCRIPT_COOKIES_FROM_BROWSER=chrome`. |
| No captions at all | Nothing to do - the video has none. Say so rather than inventing content. |
| Transcript looks like a different video | The tool caches by video ID. Re-run with `--refresh`. |
