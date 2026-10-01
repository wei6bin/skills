#!/usr/bin/env python3
"""Unit tests for scripts/render.py: model routing, per-harness frontmatter,
the dispatch rewrites, error cases, and idempotence on the real source tree.

Run with `make test` (python3 -m unittest discover -s scripts -p 'test_*.py').
"""

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render  # noqa: E402
import yaml  # noqa: E402

MODELS = textwrap.dedent(
    """\
    tiers:
      frontier: {claude: fable, copilot: [opus-id, sonnet-id], cursor: cursor-opus}
      standard: {claude: sonnet, copilot: [sonnet-id], cursor: cursor-composer}
    roles:
      reasoning: {tier: frontier, effort: high}
      implementation: {tier: standard}
    """
)


def agent_md(name, role, extra="", tools="Read, Grep, Glob"):
    return textwrap.dedent(
        f"""\
        ---
        name: {name}
        description: "Does {name}."
        tools: [{tools}]
        role: {role}
        """
    ) + extra + textwrap.dedent(
        f"""\
        ---

        Body of {name}. Invoke `jidoka:line` then dispatch
        `agent_type: "jidoka:{name}"`.
        """
    )


class Fixture:
    """A throwaway src/ tree that render.py reads instead of the repo's."""

    def __init__(self, agents, models=MODELS):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "src" / "agents").mkdir(parents=True)
        (root / "src" / "skills" / "line").mkdir(parents=True)
        (root / "src" / "hooks").mkdir(parents=True)
        (root / ".claude-plugin").mkdir()
        (root / "src" / "models.yaml").write_text(models)
        for name, text in agents.items():
            (root / "src" / "agents" / f"{name}.md").write_text(text)
        (root / "src" / "skills" / "line" / "SKILL.md").write_text(
            '---\nname: line\n---\n\nDispatch `agent_type: "jidoka:x"` after `jidoka:line`.\n'
        )
        (root / "src" / "hooks" / "hooks.json").write_text(
            json.dumps({"afterFileEdit": [{"script": "h.sh", "timeout": 5}]})
        )
        (root / "src" / "hooks" / "h.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
        (root / ".claude-plugin" / "marketplace.json").write_text(
            json.dumps({"plugins": [{"name": "jidoka"}, {"name": "jidoka-copilot"}]})
        )
        self.root = root
        self.saved = (render.ROOT, render.SRC)
        render.ROOT, render.SRC = root, root / "src"

    def close(self):
        render.ROOT, render.SRC = self.saved
        self.tmp.cleanup()

    def render(self):
        out = self.root / "out"
        render.render_all(out)
        return out


def frontmatter(path):
    fm_text, _ = render.split_frontmatter(path.read_text(), path)
    return yaml.safe_load(fm_text)


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture(
            {
                "arch": agent_md("arch", "reasoning"),
                "impl": agent_md("impl", "implementation", tools="Read, Edit, Bash"),
                "pinned": agent_md(
                    "pinned", "implementation", "model:\n  cursor: pinned-slug\n"
                ),
                "effortful": agent_md("effortful", "reasoning", "claude:\n  effort: max\n"),
            }
        )
        self.addCleanup(self.fx.close)
        self.out = self.fx.render()

    def test_role_resolves_per_harness(self):
        claude = frontmatter(self.out / "jidoka/agents/arch.md")
        self.assertEqual(claude["model"], "fable")
        self.assertEqual(claude["effort"], "high")
        self.assertTrue(claude["description"].startswith(render.INTERNAL_PREFIX))
        self.assertEqual(claude["tools"], "Read, Grep, Glob")

        copilot = frontmatter(self.out / "jidoka-copilot/agents/arch.agent.md")
        self.assertEqual(copilot["model"], "opus-id")
        self.assertEqual(copilot["models"], ["opus-id", "sonnet-id"])
        self.assertEqual(copilot["modelPolicy"], "preferred")
        self.assertIs(copilot["user-invocable"], False)
        self.assertEqual(copilot["tools"], ["read", "search"])

        cursor = frontmatter(self.out / "jidoka-cursor/agents/arch.md")
        self.assertEqual(cursor["model"], "cursor-opus")
        self.assertIs(cursor["readonly"], True)
        self.assertNotIn("tools", cursor)

    def test_standard_role_has_no_effort_and_no_readonly_when_it_can_write(self):
        claude = frontmatter(self.out / "jidoka/agents/impl.md")
        self.assertEqual(claude["model"], "sonnet")
        self.assertNotIn("effort", claude)
        cursor = frontmatter(self.out / "jidoka-cursor/agents/impl.md")
        self.assertNotIn("readonly", cursor)
        copilot = frontmatter(self.out / "jidoka-copilot/agents/impl.agent.md")
        self.assertEqual(copilot["tools"], ["read", "edit", "execute"])

    def test_pin_beats_role_for_that_harness_only(self):
        cursor = frontmatter(self.out / "jidoka-cursor/agents/pinned.md")
        self.assertEqual(cursor["model"], "pinned-slug")
        claude = frontmatter(self.out / "jidoka/agents/pinned.md")
        self.assertEqual(claude["model"], "sonnet")
        header = (self.out / "jidoka-cursor/agents/pinned.md").read_text().splitlines()
        self.assertTrue(any("pinned in the source" in line for line in header))

    def test_claude_block_effort_beats_role_effort(self):
        claude = frontmatter(self.out / "jidoka/agents/effortful.md")
        self.assertEqual(claude["effort"], "max")
        self.assertEqual(claude["model"], "fable")

    def test_rewrites_per_harness(self):
        body = (self.out / "jidoka-copilot/agents/arch.agent.md").read_text()
        self.assertIn('agent_type: "jidoka-copilot:arch"', body)
        self.assertIn("`jidoka-copilot:line`", body)
        self.assertNotIn("jidoka:arch", body)
        body = (self.out / "jidoka-cursor/agents/arch.md").read_text()
        self.assertIn('subagent_type: "arch"', body)
        self.assertIn("`line`", body)
        self.assertNotIn("jidoka:", body)
        skill = (self.out / "jidoka-cursor/skills/line/SKILL.md").read_text()
        self.assertIn('subagent_type: "x"', skill)
        skill = (self.out / "jidoka/skills/line/SKILL.md").read_text()
        self.assertIn('agent_type: "jidoka:x"', skill)

    def test_marketplace_arrays_and_hooks(self):
        data = json.loads((self.out / ".claude-plugin/marketplace.json").read_text())
        by_name = {p["name"]: p for p in data["plugins"]}
        self.assertEqual(by_name["jidoka"]["agents"][0], "./agents/arch.md")
        self.assertEqual(by_name["jidoka-copilot"]["agents"][0], "./agents/arch.agent.md")
        self.assertEqual(by_name["jidoka"]["skills"], ["./skills/line"])
        claude = json.loads((self.out / "jidoka/hooks/hooks.json").read_text())
        self.assertEqual(
            claude["hooks"]["PostToolUse"][0]["hooks"][0]["command"],
            "${CLAUDE_PLUGIN_ROOT}/hooks/h.sh",
        )
        cursor = json.loads((self.out / "jidoka-cursor/hooks/hooks.json").read_text())
        self.assertIn("${CURSOR_PLUGIN_ROOT}/hooks/h.sh", cursor["hooks"]["afterFileEdit"][0]["command"])
        copilot = json.loads((self.out / "jidoka-copilot/hooks/hooks.json").read_text())
        self.assertEqual(copilot["hooks"]["postToolUse"][0]["matcher"], "edit|create")


class ErrorTests(unittest.TestCase):
    def assert_source_error(self, agents, models=MODELS, fragment=""):
        fx = Fixture(agents, models)
        try:
            with self.assertRaises(render.SourceError) as ctx:
                fx.render()
            self.assertIn(fragment, str(ctx.exception))
        finally:
            fx.close()

    def test_unknown_role(self):
        self.assert_source_error({"a": agent_md("a", "nope")}, fragment="role 'nope'")

    def test_missing_role(self):
        text = agent_md("a", "reasoning").replace("role: reasoning\n", "")
        self.assert_source_error({"a": text}, fragment="missing 'role'")

    def test_tier_missing_a_harness(self):
        models = MODELS.replace(", cursor: cursor-composer", "")
        self.assert_source_error({"a": agent_md("a", "reasoning")}, models, "tier 'standard'")

    def test_role_with_bad_effort(self):
        models = MODELS.replace("effort: high", "effort: extreme")
        self.assert_source_error({"a": agent_md("a", "reasoning")}, models, "effort")

    def test_pin_for_unknown_harness(self):
        self.assert_source_error(
            {"a": agent_md("a", "reasoning", "model:\n  gemini: x\n")}, fragment="model must map"
        )

    def test_per_harness_body_file_is_rejected(self):
        fx = Fixture({"a": agent_md("a", "reasoning")})
        try:
            (fx.root / "src/agents/a.claude.md").write_text("body\n")
            with self.assertRaises(render.SourceError) as ctx:
                fx.render()
            self.assertIn("one file per agent", str(ctx.exception))
        finally:
            fx.close()

    def test_unclosed_harness_section(self):
        text = agent_md("a", "reasoning") + "<!-- harness: claude -->\nonly\n"
        self.assert_source_error({"a": text}, fragment="not closed")

    def test_unknown_harness_in_section(self):
        text = agent_md("a", "reasoning") + "<!-- harness: gemini -->\nx\n<!-- harness: end -->\n"
        self.assert_source_error({"a": text}, fragment="unknown harness")

    def test_harness_end_without_section(self):
        text = agent_md("a", "reasoning") + "<!-- harness: end -->\n"
        self.assert_source_error({"a": text}, fragment="without an open section")


class HarnessSectionTests(unittest.TestCase):
    BODY = textwrap.dedent(
        """\
        Intro.

        <!-- harness: claude -->
        Claude only.

        <!-- harness: copilot cursor -->
        Copilot and Cursor.

        <!-- harness: end -->
        1. Shared step.
           <!-- harness: cursor -->
        2. Cursor step.
           <!-- harness: end -->
        3. Last step.
        """
    )

    def test_sections_kept_only_for_named_harnesses(self):
        self.assertEqual(
            render.for_harness(self.BODY, "claude", "x"),
            "Intro.\n\nClaude only.\n\n1. Shared step.\n3. Last step.\n",
        )
        self.assertEqual(
            render.for_harness(self.BODY, "copilot", "x"),
            "Intro.\n\nCopilot and Cursor.\n\n1. Shared step.\n3. Last step.\n",
        )
        self.assertEqual(
            render.for_harness(self.BODY, "cursor", "x"),
            "Intro.\n\nCopilot and Cursor.\n\n1. Shared step.\n2. Cursor step.\n"
            "3. Last step.\n",
        )

    def test_sections_in_rendered_agent_and_skill(self):
        fx = Fixture({"a": agent_md("a", "reasoning") + "<!-- harness: claude -->\nC.\n<!-- harness: end -->\n"})
        try:
            skill = fx.root / "src/skills/line/SKILL.md"
            skill.write_text(skill.read_text() + "<!-- harness: cursor -->\nK.\n<!-- harness: end -->\n")
            out = fx.render()
            self.assertIn("\nC.\n", (out / "jidoka/agents/a.md").read_text())
            self.assertNotIn("C.", (out / "jidoka-copilot/agents/a.agent.md").read_text())
            self.assertIn("\nK.\n", (out / "jidoka-cursor/skills/line/SKILL.md").read_text())
            self.assertNotIn("K.", (out / "jidoka/skills/line/SKILL.md").read_text())
            for path in out.rglob("*.md"):
                self.assertNotIn("<!-- harness:", path.read_text(), path)
        finally:
            fx.close()


class RealTreeTests(unittest.TestCase):
    """Invariants on the repo's own src/, and that rendering is deterministic."""

    def test_every_claude_model_is_an_alias(self):
        for agent in render.load_agents(render.load_routing()):
            model, _ = agent.resolve("claude")
            self.assertIn(model, ("fable", "opus", "sonnet", "haiku"), agent.name)

    def test_entry_skill_is_user_only_and_companions_are_model_only(self):
        # `line` stays out of every session's skill listing and runs only when
        # the user types it. A companion stays out of the `/` menu but must stay
        # model-invocable: disable-model-invocation also blocks the Skill tool
        # and subagent preloading, which is how the orchestrator and the agents
        # reach it.
        for skill in render.load_skills():
            fm = frontmatter(skill / "SKILL.md")
            entry = skill.name == "line"
            self.assertEqual(fm.get("disable-model-invocation", False), entry, skill.name)
            self.assertEqual(fm.get("user-invocable", True), entry, skill.name)

    def test_render_is_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            render.render_all(Path(a))
            render.render_all(Path(b))
            self.assertEqual(render.relative_files(Path(a)), render.relative_files(Path(b)))


if __name__ == "__main__":
    unittest.main()
