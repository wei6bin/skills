# Audience calibration

The same talk becomes a different document for each reader. Fix the audience before
writing, and let it drive four things: **depth, vocabulary, emphasis, and the practice
section.**

## The dial

| Audience | Assume they know | Depth | Emphasise |
|---|---|---|---|
| IC engineer (junior/mid) | Day-to-day coding; less workflow-design experience | Concrete mechanics - prompts, commands, config | A copyable workflow, what to try first, common footguns |
| Senior / staff engineer | Strong engineering judgement; may be new to this specific tool or workflow | Mechanism and workflow design, evaluation criteria | Where agents fail, how to structure work for them, review discipline |
| Tech lead / EM | Team dynamics and delivery pressure; less tool-internals detail | Adoption path, process change, guardrails | Rollout sequencing, what to measure, where to slow down |
| Engineering director / VP | Org strategy, budget, risk tolerance | Compressed mechanism, expanded strategy and risk | ROI framing, vendor/tool selection criteria, org-level risk |
| Platform / DevOps engineer | Infra, CI/CD, security tooling | Integration and governance detail | Where agents plug into the pipeline, access control, auditability |

**Mixed backgrounds** are common and are a real instruction, not a contradiction. "Tech
lead with strong IC background" means: pitch adoption and process content at the tech
lead level, but you may assume hands-on fluency, so keep the concrete mechanics too.
State the read you took, so the user can correct it.

## What changes concretely

**Depth.** An IC needs the mechanism that makes a workflow reliable. A director needs
the risk and the return. Most audiences need both, in different proportions - shift the
ratio, do not delete either.

**Vocabulary.** Expand every acronym on first use regardless of audience (MCP, RAG,
CI/CD). Seniority buys compression of explanation, not of definition.

**Emphasis.** The same tool-comparison table serves different questions. For an IC, the
"how to invoke it" column is the lesson. For an EM, the "team readiness" column is.

**Practice section.** Always include one, always specific to the role:

- Guardrails to set before an agent touches `main` or production
- Metrics to track for adoption and effectiveness
- Questions to ask in a vendor demo or tool bake-off
- Review and rollback discipline for agent-authored changes
- Where **not** to reach for an agent yet

Generic caution is filler. "Never let an agent commit directly to a protected branch
without a required review, because agent-authored diffs pass CI at a lower true-positive
rate than they pass code review" earns its place. "Use AI responsibly" does not, beyond
a single line in the footer.

## Scope discipline

Do not silently widen scope to the whole AI-tooling landscape, and do not narrow a talk
that covered a full workflow into a summary of its opening minutes. Cover what the talk
covered, at the depth the audience needs.

Where the talk omits something the audience genuinely requires - a security
consideration for a platform engineer, a rollout risk for an EM - add it and **say you
added it**. That is the difference between a useful briefing and an unreliable one.
