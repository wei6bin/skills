# Clinical Lecture Brief

Turn a clinical or medical YouTube lecture into a published, audience-calibrated
teaching artifact.

## What it does

Given a YouTube URL for a medical, nursing, pharmacology, or other clinical lecture,
the skill:

1. Fetches the transcript.
2. Repairs speech-recognition garbling in clinical terminology.
3. Verifies the medicine against current teaching.
4. Builds a designed HTML study reference, pitched at a named audience (e.g. "an APN
   intern", "a medical student", "residents").

The output is a published HTML Artifact. A Word `.docx` export is available as a
follow-on.

## Use

```text
/clinical-lecture-brief <youtube-url>
```

or describe what you want in natural language, e.g. "make study notes from this
lecture for a medical student" or "turn this video into a reference for residents".
