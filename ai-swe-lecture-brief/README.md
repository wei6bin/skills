# AI & Software Engineering Lecture Brief

Turn a YouTube talk, panel, debate, or podcast about AI and software engineering into a
published, audience-calibrated engineering briefing.

## What it does

Given a YouTube URL for a conference talk, podcast, panel discussion, or debate about AI
coding agents, agentic engineering workflows, AI-assisted SDLC practices, or the broader
shift AI is causing in software engineering work, the skill:

1. Fetches the transcript.
2. Repairs speech-recognition garbling of tool, product, and model names.
3. Separates verifiable technical claims from speaker opinion and prediction, and
   checks the former for currency, since this field moves faster than any other.
4. Builds a designed HTML reference, pitched at a named audience (e.g. "an IC
   engineer", "a tech lead", "an engineering director").

The output is a published HTML Artifact. A Word `.docx` export is available as a
follow-on.

## Use

```text
/ai-swe-lecture-brief <youtube-url>
```

or describe what you want in natural language, e.g. "write this up for my engineering
team" or "summarize this panel on AI and software engineering for an EM".
