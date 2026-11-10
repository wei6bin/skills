#!/usr/bin/env python3
"""Unit tests for scripts/render.py: model routing, the plugin's agent
frontmatter, the worker render, render sections, error cases, no inline
generated marker in rendered Markdown (.gitattributes marks the outputs
instead), and idempotence on the real source tree.

Run with `just test` (python3 -m unittest discover -s scripts -p 'test_*.py').
"""

import json
import re
import subprocess
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
      frontier: {claude: fable, copilot: opus-id}
      standard: {claude: sonnet, copilot: sonnet-id}
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
            json.dumps({"plugins": [{"name": "jidoka"}, {"name": "other", "skills": ["./skills/x"]}]})
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
                "pinned": agent_md("pinned", "implementation", "model:\n  claude: haiku\n"),
                "effortful": agent_md(
                    "effortful", "reasoning", "claude:\n  effort: max\n  omitClaudeMd: true\n"
                ),
            }
        )
        self.addCleanup(self.fx.close)
        self.out = self.fx.render()

    def test_role_resolves_to_the_claude_alias(self):
        claude = frontmatter(self.out / "jidoka/agents/arch.md")
        self.assertEqual(claude["model"], "fable")
        self.assertEqual(claude["effort"], "high")
        self.assertTrue(claude["description"].startswith(render.INTERNAL_PREFIX))
        self.assertEqual(claude["tools"], "Read, Grep, Glob")

    def test_standard_role_has_no_effort(self):
        claude = frontmatter(self.out / "jidoka/agents/impl.md")
        self.assertEqual(claude["model"], "sonnet")
        self.assertNotIn("effort", claude)
        self.assertEqual(claude["tools"], "Read, Edit, Bash")

    def test_pin_beats_role(self):
        self.assertEqual(frontmatter(self.out / "jidoka/agents/pinned.md")["model"], "haiku")

    def test_claude_block_effort_beats_role_effort_and_adds_its_keys(self):
        claude = frontmatter(self.out / "jidoka/agents/effortful.md")
        self.assertEqual(claude["effort"], "max")
        self.assertEqual(claude["model"], "fable")
        self.assertIs(claude["omitClaudeMd"], True)

    def test_dispatch_strings_are_left_as_written(self):
        body = (self.out / "jidoka/agents/arch.md").read_text()
        self.assertIn('agent_type: "jidoka:arch"', body)
        self.assertIn("`jidoka:line`", body)
        skill = (self.out / "jidoka/skills/line/SKILL.md").read_text()
        self.assertIn('agent_type: "jidoka:x"', skill)

    def test_marketplace_arrays_and_hooks(self):
        data = json.loads((self.out / ".claude-plugin/marketplace.json").read_text())
        by_name = {p["name"]: p for p in data["plugins"]}
        self.assertEqual(by_name["jidoka"]["agents"][0], "./agents/arch.md")
        self.assertEqual(by_name["jidoka"]["skills"], ["./skills/line"])
        self.assertEqual(by_name["other"], {"name": "other", "skills": ["./skills/x"]})
        claude = json.loads((self.out / "jidoka/hooks/hooks.json").read_text())
        entry = claude["hooks"]["PostToolUse"][0]
        self.assertEqual(entry["matcher"], "Edit|Write|MultiEdit")
        self.assertEqual(entry["hooks"][0]["command"], "${CLAUDE_PLUGIN_ROOT}/hooks/h.sh")
        self.assertEqual(entry["hooks"][0]["timeout"], 5)


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

    def test_tier_missing_a_model(self):
        models = MODELS.replace(", copilot: sonnet-id", "")
        self.assert_source_error({"a": agent_md("a", "reasoning")}, models, "tier 'standard'")

    def test_tier_model_must_be_a_string(self):
        models = MODELS.replace("copilot: sonnet-id", "copilot: [sonnet-id]")
        self.assert_source_error({"a": agent_md("a", "reasoning")}, models, "bad copilot value")

    def test_role_with_bad_effort(self):
        models = MODELS.replace("effort: high", "effort: extreme")
        self.assert_source_error({"a": agent_md("a", "reasoning")}, models, "effort")

    def test_pin_for_unknown_model(self):
        self.assert_source_error(
            {"a": agent_md("a", "reasoning", "model:\n  cursor: x\n")}, fragment="model must map"
        )

    def test_claude_block_cannot_override_top_level_keys(self):
        self.assert_source_error(
            {"a": agent_md("a", "reasoning", "claude:\n  description: Other.\n")},
            fragment="claude block cannot set ['description']",
        )

    def test_unknown_top_level_key(self):
        self.assert_source_error(
            {"a": agent_md("a", "reasoning", "copilot: {}\n")}, fragment="unknown keys ['copilot']"
        )

    def test_section_in_a_skill_is_rejected(self):
        fx = Fixture({"a": agent_md("a", "reasoning")})
        try:
            skill = fx.root / "src/skills/line/SKILL.md"
            skill.write_text(skill.read_text() + "<!-- harness: claude -->\nC.\n<!-- harness: end -->\n")
            with self.assertRaises(render.SourceError) as ctx:
                fx.render()
            self.assertIn("src/skills/line/SKILL.md:6: a skill has one render", str(ctx.exception))
        finally:
            fx.close()

    def test_marketplace_without_the_plugin_entry(self):
        fx = Fixture({"a": agent_md("a", "reasoning")})
        try:
            (fx.root / ".claude-plugin/marketplace.json").write_text('{"plugins": []}')
            with self.assertRaises(render.SourceError) as ctx:
                fx.render()
            self.assertIn("no entry for 'jidoka'", str(ctx.exception))
        finally:
            fx.close()

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
        text = agent_md("a", "reasoning") + "<!-- harness: copilot -->\nx\n<!-- harness: end -->\n"
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

        <!-- harness: worker -->
        Worker only.

        <!-- harness: end -->
        1. Shared step.
           <!-- harness: claude worker -->
        2. Both step.
           <!-- harness: end -->
        3. Last step.
        """
    )

    def test_sections_kept_only_for_named_renders(self):
        self.assertEqual(
            render.for_harness(self.BODY, "claude", "x"),
            "Intro.\n\nClaude only.\n\n1. Shared step.\n2. Both step.\n3. Last step.\n",
        )
        self.assertEqual(
            render.for_harness(self.BODY, "worker", "x"),
            "Intro.\n\nWorker only.\n\n1. Shared step.\n2. Both step.\n3. Last step.\n",
        )

    def test_sections_in_the_rendered_agent(self):
        text = agent_md("a", "reasoning") + (
            "<!-- harness: claude -->\nC.\n<!-- harness: worker -->\nW.\n<!-- harness: end -->\n"
        )
        fx = Fixture({"a": text})
        try:
            out = fx.render()
            agent = (out / "jidoka/agents/a.md").read_text()
            self.assertIn("\nC.\n", agent)
            self.assertNotIn("W.", agent)
            for path in out.rglob("*.md"):
                self.assertNotIn("<!-- harness:", path.read_text(), path)
        finally:
            fx.close()


class GeneratedMarkerTests(unittest.TestCase):
    """Rendered Markdown carries no inline marker: skills, their reference files
    and agents load into the model's context on every run, so a marker would
    cost tokens every time. Hook scripts are executed, never loaded, and keep
    their one-line GENERATED comment."""

    def setUp(self):
        self.fx = Fixture({"a": agent_md("a", "reasoning")})
        self.addCleanup(self.fx.close)
        ref = self.fx.root / "src/skills/line/references/ref.md"
        ref.parent.mkdir()
        ref.write_text("# Ref\n\nThen `jidoka:line`.\n")
        self.out = self.fx.render()

    def test_markdown_opens_with_its_frontmatter_and_has_no_marker(self):
        plugin = self.out / render.PLUGIN
        for path in (plugin / "agents/a.md", plugin / "skills/line/SKILL.md"):
            text = path.read_text()
            self.assertTrue(text.startswith("---\nname: "), path)
            _fm, body = render.split_frontmatter(text, path)
            # One blank line after the closing fence, then the body.
            self.assertRegex(body, r"\A\n[^\n<]", path)
            self.assertNotIn("GENERATED", text, path)
        ref = (plugin / "skills/line/references/ref.md").read_text()
        self.assertTrue(ref.startswith("# Ref\n\n"))
        self.assertNotIn("GENERATED", ref)

    def test_hook_scripts_keep_their_marker(self):
        lines = (self.out / render.PLUGIN / "hooks/h.sh").read_text().splitlines()
        self.assertEqual(lines[0], "#!/usr/bin/env bash")
        self.assertTrue(lines[1].startswith("# GENERATED copy of src/hooks/h.sh"))
        self.assertEqual(lines[2:], ["exit 0"])


class WorkerRenderTests(unittest.TestCase):
    """The herdr-crew skill carries every agent's worker render: what a herdr
    worker on a harness without the jidoka plugin reads as its instructions."""

    SECTIONS = (
        "<!-- harness: claude -->\nClaude only.\n"
        "<!-- harness: worker -->\nGeneric.\n"
        "<!-- harness: end -->\n"
    )

    def setUp(self):
        self.fx = Fixture(
            {
                "arch": agent_md("arch", "reasoning") + self.SECTIONS,
                "impl": agent_md("impl", "implementation", "model:\n  copilot: pinned-id\n"),
            }
        )
        self.addCleanup(self.fx.close)
        crew = self.fx.root / "src/skills/herdr-crew"
        (crew / "scripts").mkdir(parents=True)
        (crew / "SKILL.md").write_text("---\nname: herdr-crew\n---\n\nCrew.\n")
        (crew / "scripts/crew.sh").write_text("#!/usr/bin/env bash\necho crew\n")
        self.out = self.fx.render()

    def worker(self, name):
        return self.out / render.PLUGIN / "skills/herdr-crew/agents" / f"{name}.md"

    def test_worker_frontmatter_carries_routing_for_crew_sh(self):
        self.assertEqual(
            frontmatter(self.worker("arch")),
            {
                "name": "arch",
                "role": "reasoning",
                "tools": "Read, Grep, Glob",
                "claude-model": "fable",
                "claude-effort": "high",
                "copilot-model": "opus-id",
            },
        )
        impl = frontmatter(self.worker("impl"))
        self.assertEqual(impl["copilot-model"], "pinned-id")
        self.assertNotIn("claude-effort", impl)

    def test_worker_frontmatter_keeps_every_value_a_string(self):
        models = MODELS.replace("copilot: sonnet-id", 'copilot: "4.1"')
        fx = Fixture({"impl": agent_md("impl", "implementation")}, models=models)
        try:
            crew = fx.root / "src/skills/herdr-crew"
            (crew / "scripts").mkdir(parents=True)
            (crew / "SKILL.md").write_text("---\nname: herdr-crew\n---\n\nCrew.\n")
            (crew / "scripts/crew.sh").write_text("#!/usr/bin/env bash\necho crew\n")
            out = fx.render()
            fm = frontmatter(out / "jidoka/skills/herdr-crew/agents/impl.md")
            self.assertEqual(fm["copilot-model"], "4.1")
            self.assertTrue(all(isinstance(v, str) for v in fm.values()), fm)
        finally:
            fx.close()

    def test_worker_body_keeps_worker_sections_and_the_dispatch_strings(self):
        text = self.worker("arch").read_text()
        self.assertIn("\nGeneric.\n", text)
        self.assertNotIn("Claude only.", text)
        self.assertIn('`agent_type: "jidoka:arch"`', text)
        self.assertNotIn("Generic.", (self.out / "jidoka/agents/arch.md").read_text())

    def test_skill_script_gets_the_generated_comment(self):
        path = self.out / render.PLUGIN / "skills/herdr-crew/scripts/crew.sh"
        lines = path.read_text().splitlines()
        self.assertEqual(lines[0], "#!/usr/bin/env bash")
        self.assertTrue(
            lines[1].startswith("# GENERATED copy of src/skills/herdr-crew/scripts/crew.sh")
        )
        self.assertEqual(lines[2:], ["echo crew"])
        self.assertTrue(path.stat().st_mode & 0o111)

    def test_python_bytecode_beside_a_skill_script_is_not_rendered(self):
        # `just test` imports skill scripts (the refine skill's agreement.py),
        # which leaves __pycache__ in src/; CI runs `just check` after it.
        cache = self.fx.root / "src/skills/herdr-crew/scripts/__pycache__"
        cache.mkdir()
        (cache / "crew.cpython-312.pyc").write_bytes(b"\x00")
        (self.fx.root / "src/skills/herdr-crew/scripts/stray.pyc").write_bytes(b"\x00")
        out = self.fx.render()
        rendered = render.relative_files(out / render.PLUGIN / "skills/herdr-crew")
        self.assertIn("scripts/crew.sh", rendered)
        self.assertFalse([name for name in rendered if name.endswith(".pyc")], rendered)

    def test_hand_written_worker_files_are_rejected(self):
        (self.fx.root / "src/skills/herdr-crew/agents").mkdir()
        with self.assertRaises(render.SourceError):
            self.fx.render()

    def test_no_worker_render_without_the_skill(self):
        fx = Fixture({"a": agent_md("a", "reasoning")})
        try:
            out = fx.render()
            self.assertFalse((out / "jidoka/skills/herdr-crew").exists())
        finally:
            fx.close()


class RealTreeTests(unittest.TestCase):
    """Invariants on the repo's own src/, and that rendering is deterministic."""

    def test_every_claude_model_is_an_alias(self):
        for agent in render.load_agents(render.load_routing()):
            self.assertIn(agent.resolve("claude"), ("fable", "opus", "sonnet", "haiku"), agent.name)

    def test_entry_skills_are_user_only_and_companions_are_model_only(self):
        # The entry skills (`line`, `refine` before it, and the `check`
        # self-check) stay out of every session's skill listing and run only
        # when the user types them.
        # A companion stays out of the `/` menu but must stay model-invocable:
        # disable-model-invocation also blocks the Skill tool and subagent
        # preloading, which is how the orchestrator and the agents reach it.
        for skill in render.load_skills():
            fm = frontmatter(skill / "SKILL.md")
            entry = skill.name in ("line", "refine", "check")
            self.assertEqual(fm.get("disable-model-invocation", False), entry, skill.name)
            self.assertEqual(fm.get("user-invocable", True), entry, skill.name)

    def test_only_the_skills_people_run_may_ask_anything(self):
        # The line runs unattended from a signed agreement: nothing it
        # invokes may stop to ask. Only `refine` (the BA, Dev Lead and QE's
        # session) and `check` (the self-check) talk to a person.
        talkers = {"refine", "check"}
        for skill in render.load_skills():
            text = (skill / "SKILL.md").read_text(encoding="utf-8")
            if skill.name not in talkers:
                self.assertNotIn("AskUserQuestion", text, skill.name)
        for agent in render.load_agents(render.load_routing()):
            path = render.SRC / "agents" / f"{agent.name}.md"
            self.assertNotIn("AskUserQuestion", path.read_text(encoding="utf-8"), agent.name)

    def test_skill_and_agent_bodies_have_no_positional_placeholders(self):
        # Claude Code substitutes a skill's invocation arguments into its body:
        # $0, $1, ... become the words it was called with. A shell snippet that
        # uses "$2" therefore reaches the agent as a literal word. Name the
        # values instead (the project-scaffolder smoke reads STEP/WANT/GOT).
        pattern = re.compile(r"\$\{?[0-9]")
        files = sorted(render.SRC.glob("skills/*/SKILL.md")) + sorted(render.SRC.glob("agents/*.md"))
        self.assertTrue(files)
        for path in files:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(pattern.search(line), f"{path.relative_to(render.ROOT)}:{number}: {line.strip()}")

    def test_gitattributes_marks_exactly_the_rendered_paths_generated(self):
        # With no inline marker, .gitattributes is the machine-readable one:
        # every directory the renderer owns is linguist-generated, and no
        # tracked hand-written file beside them (the evals).
        def git(*args):
            try:
                result = subprocess.run(
                    ["git", "-C", str(render.ROOT), *args], capture_output=True, text=True
                )
            except FileNotFoundError:
                self.skipTest("git not installed")
            if result.returncode != 0:
                self.skipTest(f"git {args[0]} failed: {result.stderr.strip()}")
            return result.stdout.splitlines()

        rendered = [f"{rel}/any.md" for rel in render.MANAGED_DIRS]
        hand_written = [
            path
            for path in git("ls-files", "--", render.PLUGIN)
            if not any(path.startswith(f"{rel}/") for rel in render.MANAGED_DIRS)
        ] + ["src/skills/line/SKILL.md", render.MARKETPLACE_FILE]
        values = dict(
            line.rsplit(": linguist-generated: ", 1)
            for line in git("check-attr", "linguist-generated", "--", *rendered, *hand_written)
        )
        for path in rendered:
            self.assertEqual(values[path], "true", path)
        for path in hand_written:
            self.assertEqual(values[path], "unspecified", path)

    def test_render_is_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            render.render_all(Path(a))
            render.render_all(Path(b))
            self.assertEqual(render.relative_files(Path(a)), render.relative_files(Path(b)))


if __name__ == "__main__":
    unittest.main()
