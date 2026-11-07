#!/usr/bin/env python3
"""Render the jidoka Claude Code plugin from the source tree in src/.

Run `just build` (python3 scripts/render.py) after editing anything under src/.
Run `just check` (python3 scripts/render.py --check) to verify the committed
outputs are current; CI runs the same check.

Source layout
  src/agents/<name>.md             one agent: body plus frontmatter (format
                                   below)
  src/skills/<skill>/...           skills, copied verbatim
  src/hooks/hooks.json             canonical hook list (event -> scripts)
  src/hooks/*.sh                   hook scripts, copied verbatim

Skill files that are not Markdown are copied byte for byte, except that a
script (first line `#!`) gets the same one-line GENERATED comment as a hook.

Outputs, owned entirely by this script and never hand-edited
  jidoka/agents/*.md               the plugin's agents
  jidoka/skills/**                 the plugin's skills
  jidoka/hooks/**                  hooks.json plus scripts
  jidoka/skills/herdr-crew/agents/*.md
                                   the worker render of every agent (see
                                   "Worker render" below)
  .claude-plugin/marketplace.json  only the agents and skills arrays of the
                                   jidoka entry

No inline marker in rendered Markdown
  Rendered skills, skill reference files and agents carry no "generated"
  comment: each loads into the model's context whenever it runs, so a marker
  would cost tokens on every load. The rule lives in CLAUDE.md ("One source,
  two renders") and .gitattributes marks the output directories
  linguist-generated. Hook scripts are executed, never loaded into context, so
  copy_script still adds a one-line GENERATED comment to each.

Agent source format (src/agents/<name>.md frontmatter)
  name: code-explorer
  description: One sentence.          # Claude gets the internal prefix
  tools: [Read, Grep, Glob]           # Claude tool names
  role: exploration                   # resolved via src/models.yaml:
                                      #   role -> tier -> model
  model:                              # optional: pin the Claude alias or the
    copilot: claude-haiku-4.5         #   Copilot worker model, overriding the
                                      #   role's tier there
  claude:                             # optional: extra Claude frontmatter keys
    omitClaudeMd: true                #   (effort here beats the role's)

Render sections (agent bodies only)
  <!-- harness: claude -->           on a line of its own, opens text only the
  ...                                named render gets; the next marker, or
  <!-- harness: worker -->           `<!-- harness: end -->`, closes it. Text
  ...                                outside a section goes to both. Put the
  <!-- harness: end -->              blank line that separates a section from
                                     what follows inside the section.
  `claude` is the plugin's agent, `worker` the worker render. Skills have one
  render, read by the lead and by every worker alike, so a section in a skill
  is an error.

Worker render (src/skills/herdr-crew/ present)
  In herdr mode a jidoka agent can run on a harness that has no jidoka plugin
  (Codex, Copilot CLI). Such a worker reads its instructions from
  jidoka/skills/herdr-crew/agents/<name>.md: the body plus the sections that
  name `worker`, under a flat frontmatter (name, role, tools as Claude names,
  claude-model, claude-effort, copilot-model) that herdr-crew/scripts/crew.sh
  reads. No description: it says when to dispatch the agent, which only the
  plugin's agent needs.

Model routing (src/models.yaml)
  tiers: <tier>: {claude: alias, copilot: model id}
  roles: <role>: {tier: <tier>, effort: <claude effort level, optional>}
  The plugin's agent gets the Claude alias and the role's effort; the worker
  render carries both, plus the id a Copilot CLI worker runs on.
"""

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("scripts/render.py needs PyYAML: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
# The two renders of an agent: the plugin's own (CLAUDE) and the worker render
# a herdr worker on another harness reads (WORKER). A section names either.
CLAUDE = "claude"
WORKER = "worker"
SECTION_NAMES = (CLAUDE, WORKER)
# What a tier names a model for: the Claude alias, and the model a herdr worker
# on Copilot CLI runs on (crew.sh passes it as `copilot --model`).
TIER_KEYS = ("claude", "copilot")
WORKER_SKILL = "herdr-crew"  # the skill whose agents/ folder holds the render
MODELS_FILE = "models.yaml"  # under src/
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

PLUGIN = "jidoka"

INTERNAL_PREFIX = "[Internal jidoka subagent - do not invoke directly] "
CLAUDE_EDIT_MATCHER = "Edit|Write|MultiEdit"
# Frontmatter keys the renderer writes itself, so a claude block cannot set them.
OWN_KEYS = {"name", "description", "tools", "model"}

MANAGED_DIRS = (
    f"{PLUGIN}/agents",
    f"{PLUGIN}/skills",
    f"{PLUGIN}/hooks",
)
MARKETPLACE_FILE = ".claude-plugin/marketplace.json"


class SourceError(Exception):
    pass


# --- source reading -----------------------------------------------------------


def split_frontmatter(text, path):
    """Return (frontmatter_text_without_fences, body) for a markdown file."""
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end < 0:
        raise SourceError(f"{path}: unterminated frontmatter")
    return text[4 : end + 1], text[end + 5 :]


def tidy_body(body):
    return body.strip("\n") + "\n"


_HARNESS_MARK = re.compile(r"\s*<!-- harness: ([a-z ]+) -->")


def for_harness(body, render, source):
    """Keep the sections that name this render (CLAUDE or WORKER), drop the rest."""
    out, keep, inside = [], True, False
    for line in body.split("\n"):
        mark = _HARNESS_MARK.fullmatch(line)
        if not mark:
            if keep:
                out.append(line)
            continue
        names = mark.group(1).split()
        if names == ["end"]:
            if not inside:
                raise SourceError(f"{source}: harness end without an open section")
            keep, inside = True, False
            continue
        unknown = set(names) - set(SECTION_NAMES)
        if unknown:
            raise SourceError(f"{source}: unknown harness {sorted(unknown)} in a section")
        keep, inside = render in names, True
    if inside:
        raise SourceError(f"{source}: harness section not closed with <!-- harness: end -->")
    return "\n".join(out)


def valid_model_value(value):
    """A model choice is a non-empty string."""
    return isinstance(value, str) and bool(value)


class Routing:
    """The tier and role tables from src/models.yaml."""

    def __init__(self, path):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        tiers, roles = data.get("tiers"), data.get("roles")
        if not isinstance(tiers, dict) or not tiers:
            raise SourceError(f"{path}: 'tiers' must be a non-empty mapping")
        if not isinstance(roles, dict) or not roles:
            raise SourceError(f"{path}: 'roles' must be a non-empty mapping")
        for name, tier in tiers.items():
            if not isinstance(tier, dict) or set(tier) != set(TIER_KEYS):
                raise SourceError(f"{path}: tier {name!r} needs exactly {TIER_KEYS}")
            for key in TIER_KEYS:
                if not valid_model_value(tier[key]):
                    raise SourceError(f"{path}: tier {name!r}: bad {key} value")
        for name, role in roles.items():
            if not isinstance(role, dict) or role.get("tier") not in tiers:
                raise SourceError(
                    f"{path}: role {name!r} needs a tier from {sorted(tiers)}"
                )
            unknown = set(role) - {"tier", "effort"}
            if unknown:
                raise SourceError(f"{path}: role {name!r}: unknown keys {sorted(unknown)}")
            if "effort" in role and role["effort"] not in EFFORT_LEVELS:
                raise SourceError(f"{path}: role {name!r}: effort not in {EFFORT_LEVELS}")
        self.tiers = tiers
        self.roles = roles


class Agent:
    def __init__(self, path, routing):
        self.path = path
        self.name = path.stem
        self.routing = routing
        text = path.read_text(encoding="utf-8")
        fm_text, body = split_frontmatter(text, path)
        if not fm_text:
            raise SourceError(f"{path}: missing frontmatter")
        fm = yaml.safe_load(fm_text) or {}
        if fm.get("name") != self.name:
            raise SourceError(f"{path}: name must be {self.name!r}")
        for key in ("description", "tools", "role"):
            if key not in fm:
                raise SourceError(f"{path}: missing {key!r}")
        allowed = {"name", "description", "tools", "role", "model", CLAUDE}
        unknown = set(fm) - allowed
        if unknown:
            raise SourceError(f"{path}: unknown keys {sorted(unknown)}")
        if not isinstance(fm["tools"], list) or not all(
            isinstance(t, str) for t in fm["tools"]
        ):
            raise SourceError(f"{path}: tools must be a list of tool names")
        if fm["role"] not in routing.roles:
            raise SourceError(
                f"{path}: role {fm['role']!r} is not in src/{MODELS_FILE} "
                f"(roles: {sorted(routing.roles)})"
            )
        overrides = fm.get("model") or {}
        if not isinstance(overrides, dict) or not set(overrides) <= set(TIER_KEYS):
            raise SourceError(f"{path}: model must map {TIER_KEYS} to ids")
        for key, value in overrides.items():
            if not valid_model_value(value):
                raise SourceError(f"{path}: model.{key}: bad value {value!r}")
        block = fm.get(CLAUDE)
        if block is not None and not isinstance(block, dict):
            raise SourceError(f"{path}: claude block must be a mapping")
        clash = set(block or {}) & OWN_KEYS
        if clash:
            raise SourceError(
                f"{path}: claude block cannot set {sorted(clash)}; "
                "set them at the top level"
            )
        claude_effort = (block or {}).get("effort")
        if claude_effort is not None and claude_effort not in EFFORT_LEVELS:
            raise SourceError(f"{path}: claude.effort not in {EFFORT_LEVELS}")
        self.fm = fm
        self.source = f"src/agents/{self.name}.md"
        self.body = tidy_body(body)
        for render in SECTION_NAMES:
            for_harness(self.body, render, self.source)  # fail on a bad section at load

    @property
    def claude_block(self):
        return self.fm.get(CLAUDE) or {}

    @property
    def role(self):
        return self.fm["role"]

    @property
    def tier(self):
        return self.routing.roles[self.role]["tier"]

    def resolve(self, key):
        """The model for a tier key: the agent's own pin if any, else its role's tier."""
        pinned = (self.fm.get("model") or {}).get(key)
        if pinned is not None:
            return pinned
        return self.routing.tiers[self.tier][key]

    def effort(self):
        """Claude Code effort: the claude block's value beats the role's."""
        return self.claude_block.get("effort", self.routing.roles[self.role].get("effort"))

    def body_for(self, render):
        return tidy_body(for_harness(self.body, render, self.source))


def load_routing():
    return Routing(SRC / MODELS_FILE)


def load_agents(routing=None):
    routing = routing or load_routing()
    agents = []
    for p in sorted(SRC.glob("agents/*.md")):
        if "." in p.stem:
            raise SourceError(
                f"{p}: one file per agent; mark render-only text with "
                "<!-- harness: ... --> sections in its body"
            )
        agents.append(Agent(p, routing))
    if not agents:
        raise SourceError("no agents found under src/agents")
    return agents


def load_skills():
    skills = sorted(p.parent for p in SRC.glob("skills/*/SKILL.md"))
    if not skills:
        raise SourceError("no skills found under src/skills")
    return skills


# --- rendering helpers ---------------------------------------------------------


_BARE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./-]*")
_NUMERIC = re.compile(r"[-+]?[0-9.]+")
_RESERVED = {"true", "false", "yes", "no", "null", "on", "off", "~"}


def yv(value):
    """Format a scalar as YAML: bare when unambiguous, JSON-quoted otherwise."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        raise SourceError(f"unsupported frontmatter value {value!r}")
    if (
        _BARE.fullmatch(value)
        and not _NUMERIC.fullmatch(value)
        and value.lower() not in _RESERVED
    ):
        return value
    return json.dumps(value, ensure_ascii=False)


def render_frontmatter(agent):
    fm = agent.fm
    lines = [
        f"name: {agent.name}",
        f"description: {yv(INTERNAL_PREFIX + fm['description'])}",
        f"tools: {', '.join(fm['tools'])}",
        f"model: {yv(agent.resolve('claude'))}",
    ]
    effort = agent.effort()
    if effort is not None:
        lines.append(f"effort: {effort}")
    for key, value in agent.claude_block.items():
        if key != "effort":
            lines.append(f"{key}: {yv(value)}")
    return "\n".join(lines) + "\n"


def render_agent(agent):
    return "---\n" + render_frontmatter(agent) + "---\n\n" + agent.body_for(CLAUDE)


def render_worker(agent):
    """The agent as a worker on another harness reads it (herdr mode)."""
    # Every value through yv, as in the plugin's agents: a model id such as 4.1
    # would otherwise read as a number. crew.sh's afm unquotes what yv quotes.
    lines = [
        f"name: {yv(agent.name)}",
        f"role: {yv(agent.role)}",
        f"tools: {yv(', '.join(agent.fm['tools']))}",
        f"claude-model: {yv(agent.resolve('claude'))}",
    ]
    effort = agent.effort()
    if effort is not None:
        lines.append(f"claude-effort: {yv(effort)}")
    lines.append(f"copilot-model: {yv(agent.resolve('copilot'))}")
    return "---\n" + "\n".join(lines) + "\n---\n\n" + agent.body_for(WORKER)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path, data):
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


# --- renderers -----------------------------------------------------------------


def render_agents(out, agents):
    for agent in agents:
        write_text(out / PLUGIN / "agents" / f"{agent.name}.md", render_agent(agent))


def render_workers(out, agents):
    """Write every agent's worker render into the plugin's herdr-crew/agents/."""
    skill = SRC / "skills" / WORKER_SKILL
    if not skill.is_dir():
        return
    if (skill / "agents").exists():
        raise SourceError(
            f"src/skills/{WORKER_SKILL}/agents/ is rendered from src/agents/; "
            "do not author files there"
        )
    for agent in agents:
        dest = out / PLUGIN / "skills" / WORKER_SKILL / "agents" / f"{agent.name}.md"
        write_text(dest, render_worker(agent))


def is_bytecode(path):
    """Python's import cache, which `just test` leaves beside a skill script it
    imports. Never source: rendering it would make `just check` fail whenever
    the tests ran first, as they do in CI."""
    return "__pycache__" in path.parts or path.suffix == ".pyc"


def render_skills(out):
    skills_root = SRC / "skills"
    for src_file in sorted(skills_root.rglob("*")):
        if src_file.is_dir() or is_bytecode(src_file.relative_to(skills_root)):
            continue
        rel = src_file.relative_to(skills_root)
        dest = out / PLUGIN / "skills" / rel
        if src_file.suffix != ".md":
            if src_file.read_bytes().startswith(b"#!"):
                copy_script(src_file, dest, f"src/skills/{rel.as_posix()}")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dest)
            continue
        text = src_file.read_text(encoding="utf-8")
        fm_text, body = split_frontmatter(text, src_file)
        fences = f"---\n{fm_text}---\n\n" if fm_text else ""
        for number, line in enumerate(text.split("\n"), 1):
            if _HARNESS_MARK.fullmatch(line):
                raise SourceError(
                    f"src/skills/{rel.as_posix()}:{number}: a skill has one render, "
                    "read by the lead and every worker; harness sections are for agents"
                )
        write_text(dest, fences + tidy_body(body))


def copy_script(src_file, dest, source):
    lines = src_file.read_text(encoding="utf-8").split("\n")
    note = (
        f"# GENERATED copy of {source} by scripts/render.py "
        "(just build). Edit the source."
    )
    if lines and lines[0].startswith("#!"):
        lines.insert(1, note)
    else:
        lines.insert(0, note)
    write_text(dest, "\n".join(lines))
    dest.chmod(0o755)


def render_hooks(out):
    hooks_src = SRC / "hooks"
    spec = json.loads((hooks_src / "hooks.json").read_text(encoding="utf-8"))
    edits = spec.get("afterFileEdit")
    if not isinstance(edits, list) or not edits:
        raise SourceError("src/hooks/hooks.json needs a non-empty afterFileEdit list")
    for entry in edits:
        if not (hooks_src / entry["script"]).exists():
            raise SourceError(f"src/hooks/hooks.json: no such script {entry['script']}")
        entry.setdefault("timeout", 30)

    claude = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": CLAUDE_EDIT_MATCHER,
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"${{CLAUDE_PLUGIN_ROOT}}/hooks/{e['script']}",
                            "timeout": e["timeout"],
                        }
                        for e in edits
                    ],
                }
            ]
        }
    }
    write_json(out / PLUGIN / "hooks" / "hooks.json", claude)

    for script in sorted(hooks_src.glob("*.sh")):
        copy_script(script, out / PLUGIN / "hooks" / script.name, f"src/hooks/{script.name}")


def render_marketplace(out, agents, skills):
    data = json.loads((ROOT / MARKETPLACE_FILE).read_text(encoding="utf-8"))
    names = [a.name for a in agents]
    skill_ids = [s.name for s in skills]
    entry = next((e for e in data["plugins"] if e["name"] == PLUGIN), None)
    if entry is None:
        raise SourceError(f"{MARKETPLACE_FILE}: no entry for {PLUGIN!r}")
    entry["agents"] = [f"./agents/{n}.md" for n in names]
    entry["skills"] = [f"./skills/{s}" for s in skill_ids]
    write_json(out / MARKETPLACE_FILE, data)


def render_all(out):
    agents = load_agents(load_routing())
    skills = load_skills()
    render_agents(out, agents)
    render_skills(out)
    render_workers(out, agents)
    render_hooks(out)
    render_marketplace(out, agents, skills)
    return agents


# --- commands ------------------------------------------------------------------


def build():
    agents = load_agents(load_routing())
    for rel in MANAGED_DIRS:
        shutil.rmtree(ROOT / rel, ignore_errors=True)
    render_all(ROOT)
    print(f"rendered {len(agents)} agents into {ROOT / PLUGIN}")


def relative_files(base):
    if not base.exists():
        return {}
    return {
        p.relative_to(base).as_posix(): p.read_bytes()
        for p in sorted(base.rglob("*"))
        if p.is_file() and not is_bytecode(p.relative_to(base))
    }


def check():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        render_all(out)
        stale = []
        for rel in MANAGED_DIRS:
            expected = relative_files(out / rel)
            actual = relative_files(ROOT / rel)
            for name in sorted(set(expected) | set(actual)):
                if expected.get(name) != actual.get(name):
                    stale.append(f"{rel}/{name}")
        actual = ROOT / MARKETPLACE_FILE
        if not actual.exists() or (out / MARKETPLACE_FILE).read_bytes() != actual.read_bytes():
            stale.append(MARKETPLACE_FILE)
    if stale:
        print("rendered outputs are stale; run `just build` and commit:")
        for path in stale:
            print(f"  {path}")
        return 1
    print("rendered outputs are current")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed outputs match src/ without writing anything",
    )
    args = parser.parse_args(argv)
    try:
        return check() if args.check else build()
    except SourceError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
