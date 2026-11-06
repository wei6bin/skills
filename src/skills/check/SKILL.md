---
name: check
description: Self-check of the jidoka setup - whether the session runs inside herdr and the line would use herdr mode, which agent CLIs are installed, and which harness each jidoka agent would run on as a herdr worker - with the option to change that routing.
argument-hint: "[nothing, or a routing change such as 'reviewers on copilot']"
disable-model-invocation: true
---

# Jidoka Check

**Announce at start:** "Running the jidoka self-check."

`crew.sh` is `${CLAUDE_SKILL_DIR}/../herdr-crew/scripts/crew.sh`, the
`../herdr-crew/scripts/crew.sh` from this skill's folder; call it by its
absolute path. Its `check` command only reads: it opens no pane and starts no
agent.

1. **Run** `crew.sh check`.
2. **Report.** Show its output verbatim in a code block, then sum it up in two
   to four lines: inside herdr or not; herdr mode on or off, and why; the
   harnesses installed; each problem, with its fix. Outside herdr, say the
   routing applies the next time the line runs in herdr.
3. **Offer to change the routing.** If the request names a change, map it to
   keys (step 4), apply it and skip the questions. Otherwise ask one
   `AskUserQuestion` call with up to four questions, offering only installed
   harnesses:
   - "Which harness should run the jidoka workers?" First option "Same as the
     lead (Recommended)" (key `harness`, value `lead`), then one per installed
     harness, four options at most.
   - "Run the plan, code and security reviewers on another harness?" First
     option "No, same as the rest (Recommended)" (no key, or unset
     `role.verification` if set), then one per other installed harness (key
     `role.verification`). Each option says which model it runs, from the
     report's "how" column: another harness can still run the same family.
   - For each harness the routing would use that the report's "approvals" row
     lists (at most two): "How should {harness} workers handle approval
     prompts?" Options "Ask in the worker's pane (Recommended)" (key
     `yolo.{harness}`, value `off`) and "Yolo: no prompts" (value `on`), whose
     description names the flag from that row and says the worker then runs
     every tool, path and command without asking.

   Mark the option matching the current config "(current)". Apply each answer
   with `crew.sh config set {key} {value}`, or `crew.sh config unset {key}` for
   the default; a kept value changes nothing. Then run `crew.sh check` again
   and show its "Worker routing" section.
4. **Keys:** `harness` (default for every agent),
   `role.{reasoning|verification|implementation|exploration}`,
   `agent.{agent}` (beats the role), `args.{harness}` (extra flags, such as
   `args.copilot "--log-level none"`), `yolo.{claude|codex|copilot} {on|off}`,
   `enabled false` (never use herdr mode) and `tint {dark|light|off}` (`light`
   for a light terminal theme, `off` for emoji labels only). Other values are
   `lead` or a harness the report lists.
