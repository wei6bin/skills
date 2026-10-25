# Accuracy pass

Five independent failure modes. Do all five - the second, fourth, and fifth are what
this domain adds on top of the usual two, and all three matter more here than almost
anywhere else.

## 1. Speech recognition garbling

Auto-captions are trained on general speech and fail predictably on AI-tooling product
names, model names, and coined jargon. Examples observed across agentic-coding talks:

| Transcript says | Actually |
|---|---|
| cloud code | Claude Code |
| curser, cursor ai | Cursor |
| co-pilot, github co-pilot | GitHub Copilot |
| M C P, empty CP | MCP (Model Context Protocol) |
| R A G | RAG |
| L L M, l lm | LLM |
| jenny eye, gen a i | GenAI |
| and-thropic, an-tropic | Anthropic |
| sonic, sonnet for | Sonnet (a Claude model) |
| oh pus | Opus |
| dev in | Devin |
| ayder | Aider |
| wind surf | Windsurf |
| get hub, get lab | GitHub, GitLab |
| cai see cd, ci cd | CI/CD |
| a genic, agent tick | agentic |
| vibe coating | vibe coding |
| context win dow | context window |
| few shot, one shot | few-shot, one-shot |
| p r, pull request | PR / pull request |

General classes to sweep:

- **Product and vendor names** are mangled almost every time - Anthropic, Cursor,
  Windsurf, and every model family name are all suspect.
- **Acronyms spoken letter by letter** fuse into nonsense words (MCP, RAG, CI/CD, LLM).
- **Model names and version numbers** - "Sonnet 4.5" gets split, or the version number
  is misheard as an unrelated figure.
- **Numbers** - context window sizes, benchmark percentages, pricing - the captioner
  drops units and mis-places decimals.
- **Coined jargon** ("vibe coding", "agentic", "spec-driven") often gets
  autocorrected to the nearest real word or phrase.

Rule: if a term would be wrong in a printed reference, it does not go in the output.
When a garbled token cannot be resolved from context, flag it in your report to the
user rather than guessing at it.

## 2. Opinion and prediction are not fact

A large share of this domain's content is debate, panel discussion, and punditry, not
tutorial. "AI will replace junior engineers within five years" and "TDD is dead" are
speaker positions, not verifiable claims - and a reference that repeats them in the same
voice as a fact about a context-window size misleads the reader about how settled either
one is.

For every substantive claim in the transcript, classify it before writing it down:

- **Verifiable fact** - a tool's capability, a benchmark result, a historical detail, a
  pricing figure. Fact-check this per sections 3 and 4 below.
- **Opinion or prediction** - a forecast, a value judgement, a "this is how the industry
  should work" position. Attribute it explicitly to the speaker who holds it
  ("Martin argues that...", "Matt's position is..."), keep it in the piece if it's
  substantive to the discussion, and do not silently convert it into the page's own
  voice as though the reference endorses it.

When two speakers disagree, preserve the disagreement. Do not synthesise a false
consensus or silently pick a side - present both positions and, only where there is a
genuinely settled fact underneath the disagreement, note what it is.

## 3. The speaker was wrong

Separate from opinion, and separate from transcription. Speakers misspeak, oversimplify
for a live audience, or generalise past what they actually verified. Check every
load-bearing technical claim before repeating it.

- **Silently fix** slips that change nothing structurally, e.g. a mis-said flag name.
- **Fix and report** anything a reader would act on - a wrong claim about what a tool
  does, a wrong description of how a workflow is wired.

## 4. The speaker was right on the recording date, and wrong now

This is the failure mode that does not exist in most other domains and is the reason
this pass gets its own section. Model capabilities, context-window sizes, pricing,
"X can't do Y yet" limitations, and "the only tool that does Z" claims all have a
shelf life measured in months, not years.

For every technical claim about a model or tool's capability, limits, or pricing:

- Note the video's publish date relative to today's date.
- If the claim is still accurate, keep it as stated.
- If it has been superseded, **correct it and say so explicitly** - state both what the
  speaker said and what is true now. Do not silently update history as if the speaker
  said the current thing.
- If you cannot verify current status, say so rather than asserting either the old
  figure or a guessed new one.

A fast-moving field is a reason to verify harder, not an excuse to skip verification -
readers reach for a written reference specifically because they cannot re-watch the
talk to check whether it has aged.

## 5. Survivorship bias and unqualified generalisation

Talks in this space routinely report a result from one team, one codebase, one stack
("agents cut our review time 80%") without the conditions that made it true. In a
written reference that is not just imprecise, it is advice someone will act on in the
wrong context. For every headline result:

- Name the conditions that likely mattered - codebase size, test coverage, type
  safety, language, team seniority - if the talk states or implies them.
- If the talk omits them, say the result is reported without stated conditions rather
  than presenting it as universal.
- Do not let one success story stand in as "this works for any codebase."
