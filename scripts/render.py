#!/usr/bin/env python3
"""Render every jidoka harness variant from the single source tree in src/.

Run `make build` (python3 scripts/render.py) after editing anything under src/.
Run `make check` (python3 scripts/render.py --check) to verify the committed
outputs are current; CI runs the same check.

Source layout
  src/agents/<name>.md             one agent: shared body plus frontmatter with
                                   per-harness blocks (format below)
  src/skills/<skill>/...           skills, copied verbatim; the Copilot copy has
                                   the plugin prefix rewritten
                                   (jidoka: -> jidoka-copilot:)
  src/hooks/hooks.json             canonical hook list (event -> scripts)
  src/hooks/*.sh                   hook scripts, copied verbatim

Outputs, owned entirely by this script and never hand-edited
  jidoka/agents/*.md               Claude Code plugin agents
  jidoka/skills/**                 Claude Code plugin skills
  jidoka/hooks/**                  Claude Code hooks.json plus scripts
  jidoka-copilot/agents/*.agent.md Copilot CLI plugin agents
  jidoka-copilot/skills/**         Copilot CLI plugin skills
  jidoka-copilot/hooks/**          Copilot hooks.json plus scripts
  jidoka-cursor/agents/*.md        Cursor plugin agents
  jidoka-cursor/skills/**          Cursor plugin skills (dispatch rewritten)
  jidoka-cursor/hooks/**           Cursor hooks.json plus scripts
  .claude-plugin/marketplace.json  only the agents and skills arrays of the
                                   jidoka and jidoka-copilot entries

No inline marker in rendered Markdown
  Rendered skills, skill reference files and agents carry no "generated"
  comment: each loads into the model's context whenever it runs, so a marker
  would cost tokens on every load in every harness. The rule lives in
  CLAUDE.md ("One source, three renders") and .gitattributes marks the output
  directories linguist-generated. Hook scripts are executed, never loaded into
  context, so copy_script still adds a one-line GENERATED comment to each.

Agent source format (src/agents/<name>.md frontmatter)
  name: code-explorer
  description: One sentence.          # shared; Claude gets the internal prefix
  tools: [Read, Grep, Glob]           # Claude tool names, mapped per harness
  role: exploration                   # resolved via src/models.yaml:
                                      #   role -> tier -> model per harness
  model:                              # optional: pin one or more harnesses,
    cursor: composer-2.5-fast         #   overriding the role's tier there
  claude:                             # optional per-harness block: extra
    omitClaudeMd: true                #   frontmatter keys (effort here beats
  copilot: {}                         #   the role's), or overrides for
  cursor: {}                          #   description and tools

Harness sections (any Markdown body under src/)
  <!-- harness: claude -->           on a line of its own, opens text only the
  ...                                named harnesses get; the next marker, or
  <!-- harness: copilot cursor -->   `<!-- harness: end -->`, closes it. Text
  ...                                outside a section goes to every harness.
  <!-- harness: end -->              Put the blank line that separates a section
                                     from what follows inside the section.

Model routing (src/models.yaml)
  tiers: <tier>: {claude: alias, copilot: [ids in priority order], cursor: slug}
  roles: <role>: {tier: <tier>, effort: <claude effort level, optional>}
  Claude gets the alias and the role's effort; Copilot gets `model` (first id),
  `models` (the list) and `modelPolicy: preferred`; Cursor gets the slug.

Harness differences this script owns
  Claude Code   tools as a comma list, description prefixed with the internal
                marker, extra keys such as effort and omitClaudeMd.
  Copilot CLI   tools mapped to Copilot aliases (read, edit, search, execute,
                agent, web), user-invocable: false, .agent.md suffix, every
                `jidoka:` prefix rewritten to `jidoka-copilot:`.
  Cursor        no tools key (readonly: true is derived when every tool is
                read-only), picker-slug model, and in agents and skills alike
                `agent_type: "jidoka:x"` rewritten to `subagent_type: "x"` and
                skill ids to bare names.
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
HARNESSES = ("claude", "copilot", "cursor")
MODELS_FILE = "models.yaml"  # under src/
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

PLUGIN = "jidoka"
COPILOT_PLUGIN = "jidoka-copilot"
CURSOR_PLUGIN = "jidoka-cursor"
MARKETPLACE = "skills"  # marketplace name; part of Copilot's install path

INTERNAL_PREFIX = "[Internal jidoka subagent - do not invoke directly] "
# Tools that never write: an agent restricted to these renders `readonly: true`
# for Cursor. Skill only loads instructions into the agent's context.
READONLY_TOOLS = {"Read", "Grep", "Glob", "WebFetch", "WebSearch", "Skill"}
COPILOT_TOOL_ALIAS = {
    "Read": "read",
    "NotebookRead": "read",
    "Edit": "edit",
    "MultiEdit": "edit",
    "Write": "edit",
    "NotebookEdit": "edit",
    "Grep": "search",
    "Glob": "search",
    "Bash": "execute",
    "Task": "agent",
    "WebFetch": "web",
    "WebSearch": "web",
    "TodoWrite": "todo",
    "Skill": "skill",
}
CLAUDE_EDIT_MATCHER = "Edit|Write|MultiEdit"
COPILOT_EDIT_MATCHER = "edit|create"
# Copilot documents no plugin-root variable for plugin hooks, so the command
# points at the documented install location of a marketplace plugin.
COPILOT_HOOKS_DIR = (
    f"$HOME/.copilot/installed-plugins/{MARKETPLACE}/{COPILOT_PLUGIN}/hooks"
)

MANAGED_DIRS = (
    f"{PLUGIN}/agents",
    f"{PLUGIN}/skills",
    f"{PLUGIN}/hooks",
    f"{COPILOT_PLUGIN}/agents",
    f"{COPILOT_PLUGIN}/skills",
    f"{COPILOT_PLUGIN}/hooks",
    f"{CURSOR_PLUGIN}/agents",
    f"{CURSOR_PLUGIN}/skills",
    f"{CURSOR_PLUGIN}/hooks",
)
PLUGIN_DIRS = {"claude": PLUGIN, "copilot": COPILOT_PLUGIN, "cursor": CURSOR_PLUGIN}
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


def for_harness(body, harness, source):
    """Keep the harness sections that name this harness and drop the rest."""
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
        unknown = set(names) - set(HARNESSES)
        if unknown:
            raise SourceError(f"{source}: unknown harness {sorted(unknown)} in a section")
        keep, inside = harness in names, True
    if inside:
        raise SourceError(f"{source}: harness section not closed with <!-- harness: end -->")
    return "\n".join(out)


def valid_model_value(harness, value):
    """A model choice is a string, or for Copilot a non-empty priority list."""
    if isinstance(value, str) and value:
        return True
    return (
        harness == "copilot"
        and isinstance(value, list)
        and bool(value)
        and all(isinstance(v, str) and v for v in value)
    )


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
            if not isinstance(tier, dict) or set(tier) != set(HARNESSES):
                raise SourceError(f"{path}: tier {name!r} needs exactly {HARNESSES}")
            for harness in HARNESSES:
                if not valid_model_value(harness, tier[harness]):
                    raise SourceError(f"{path}: tier {name!r}: bad {harness} value")
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
        allowed = {"name", "description", "tools", "role", "model", *HARNESSES}
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
        if not isinstance(overrides, dict) or not set(overrides) <= set(HARNESSES):
            raise SourceError(f"{path}: model must map harnesses ({HARNESSES}) to ids")
        for harness, value in overrides.items():
            if not valid_model_value(harness, value):
                raise SourceError(f"{path}: model.{harness}: bad value {value!r}")
        for h in HARNESSES:
            block = fm.get(h)
            if block is not None and not isinstance(block, dict):
                raise SourceError(f"{path}: {h} block must be a mapping")
        claude_effort = (fm.get("claude") or {}).get("effort")
        if claude_effort is not None and claude_effort not in EFFORT_LEVELS:
            raise SourceError(f"{path}: claude.effort not in {EFFORT_LEVELS}")
        self.fm = fm
        self.source = f"src/agents/{self.name}.md"
        self.body = tidy_body(body)
        for h in HARNESSES:
            for_harness(self.body, h, self.source)  # fail on a bad section at load

    def block(self, harness):
        return self.fm.get(harness) or {}

    @property
    def role(self):
        return self.fm["role"]

    @property
    def tier(self):
        return self.routing.roles[self.role]["tier"]

    def resolve(self, harness):
        """The model for a harness: the agent's own pin if any, else its role's tier."""
        pinned = (self.fm.get("model") or {}).get(harness)
        if pinned is not None:
            return pinned, True
        return self.routing.tiers[self.tier][harness], False

    def effort(self):
        """Claude Code effort: the claude block's value beats the role's."""
        return self.block("claude").get("effort", self.routing.roles[self.role].get("effort"))

    def body_for(self, harness):
        return tidy_body(for_harness(self.body, harness, self.source))


def load_routing():
    return Routing(SRC / MODELS_FILE)


def load_agents(routing=None):
    routing = routing or load_routing()
    agents = []
    for p in sorted(SRC.glob("agents/*.md")):
        if "." in p.stem:
            raise SourceError(
                f"{p}: one file per agent; mark harness-only text with "
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


def transform_body(body, harness):
    if harness == "copilot":
        return re.sub(r"\bjidoka:", f"{COPILOT_PLUGIN}:", body)
    if harness == "cursor":
        body = re.sub(r'agent_type: "jidoka:([a-z0-9-]+)"', r'subagent_type: "\1"', body)
        return re.sub(r"\bjidoka:([a-z0-9-]+)", r"\1", body)
    return body


def render_frontmatter(agent, harness):
    fm, block = agent.fm, agent.block(harness)
    description = block.get("description", fm["description"])
    tools = block.get("tools", fm["tools"])
    model, _pinned = agent.resolve(harness)
    skip = {"description", "tools"}
    lines = [f"name: {agent.name}"]
    if harness == "claude":
        lines.append(f"description: {yv(INTERNAL_PREFIX + description)}")
        lines.append(f"tools: {', '.join(tools)}")
        lines.append(f"model: {yv(model)}")
        effort = agent.effort()
        if effort is not None:
            lines.append(f"effort: {effort}")
        skip.add("effort")
    elif harness == "copilot":
        aliases = []
        for tool in tools:
            alias = COPILOT_TOOL_ALIAS.get(tool, tool.lower())
            if alias not in aliases:
                aliases.append(alias)
        models = model if isinstance(model, list) else [model]
        lines.append(f"description: {yv(description)}")
        lines.append(f"tools: {json.dumps(aliases)}")
        lines.append(f"model: {yv(models[0])}")
        lines.append(f"models: {json.dumps(models)}")
        lines.append("modelPolicy: preferred")
        lines.append("user-invocable: false")
    else:
        lines.append(f"description: {yv(description)}")
        lines.append(f"model: {yv(model)}")
        if set(tools) <= READONLY_TOOLS:
            lines.append("readonly: true")
    for key, value in block.items():
        if key in skip:
            continue
        lines.append(f"{key}: {yv(value)}")
    return "\n".join(lines) + "\n"


def render_agent(agent, harness):
    body = transform_body(agent.body_for(harness), harness)
    return "---\n" + render_frontmatter(agent, harness) + "---\n\n" + body


def agent_output(agent, harness):
    if harness == "claude":
        return Path(PLUGIN) / "agents" / f"{agent.name}.md"
    if harness == "copilot":
        return Path(COPILOT_PLUGIN) / "agents" / f"{agent.name}.agent.md"
    return Path(CURSOR_PLUGIN) / "agents" / f"{agent.name}.md"


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path, data):
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


# --- renderers -----------------------------------------------------------------


def render_agents(out, agents):
    for agent in agents:
        for harness in HARNESSES:
            write_text(out / agent_output(agent, harness), render_agent(agent, harness))


def render_skills(out, harness):
    plugin = PLUGIN_DIRS[harness]
    skills_root = SRC / "skills"
    for src_file in sorted(skills_root.rglob("*")):
        if src_file.is_dir():
            continue
        rel = src_file.relative_to(skills_root)
        dest = out / plugin / "skills" / rel
        if src_file.suffix != ".md":
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dest)
            continue
        text = src_file.read_text(encoding="utf-8")
        fm_text, body = split_frontmatter(text, src_file)
        fences = f"---\n{fm_text}---\n\n" if fm_text else ""
        source = f"src/skills/{rel.as_posix()}"
        body = tidy_body(for_harness(body, harness, source))
        write_text(dest, transform_body(fences + body, harness))


def copy_script(src_file, dest):
    lines = src_file.read_text(encoding="utf-8").split("\n")
    note = (
        f"# GENERATED copy of src/hooks/{src_file.name} by scripts/render.py "
        "(make build). Edit the source."
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

    copilot = {
        "version": 1,
        "hooks": {
            "postToolUse": [
                {
                    "type": "command",
                    "matcher": COPILOT_EDIT_MATCHER,
                    "bash": f'bash "{COPILOT_HOOKS_DIR}/{e["script"]}"',
                    "timeoutSec": e["timeout"],
                }
                for e in edits
            ]
        },
    }
    write_json(out / COPILOT_PLUGIN / "hooks" / "hooks.json", copilot)

    # ${CURSOR_PLUGIN_ROOT} expands to the plugin's install path; this is the
    # pattern Cursor's own plugins use for bundled scripts.
    cursor = {
        "version": 1,
        "hooks": {
            "afterFileEdit": [
                {
                    "command": f'bash "${{CURSOR_PLUGIN_ROOT}}/hooks/{e["script"]}"',
                    "timeout": e["timeout"],
                }
                for e in edits
            ]
        },
    }
    write_json(out / CURSOR_PLUGIN / "hooks" / "hooks.json", cursor)

    scripts = sorted(hooks_src.glob("*.sh"))
    for dest_dir in (
        out / PLUGIN / "hooks",
        out / COPILOT_PLUGIN / "hooks",
        out / CURSOR_PLUGIN / "hooks",
    ):
        for script in scripts:
            copy_script(script, dest_dir / script.name)


def render_marketplace(out, agents, skills):
    data = json.loads((ROOT / MARKETPLACE_FILE).read_text(encoding="utf-8"))
    names = [a.name for a in agents]
    skill_ids = [s.name for s in skills]
    seen = set()
    for entry in data["plugins"]:
        if entry["name"] == PLUGIN:
            entry["agents"] = [f"./agents/{n}.md" for n in names]
            entry["skills"] = [f"./skills/{s}" for s in skill_ids]
        elif entry["name"] == COPILOT_PLUGIN:
            entry["agents"] = [f"./agents/{n}.agent.md" for n in names]
            entry["skills"] = [f"./skills/{s}" for s in skill_ids]
        else:
            continue
        seen.add(entry["name"])
    missing = {PLUGIN, COPILOT_PLUGIN} - seen
    if missing:
        raise SourceError(f"{MARKETPLACE_FILE}: no entry for {sorted(missing)}")
    write_json(out / MARKETPLACE_FILE, data)


def render_all(out):
    agents = load_agents(load_routing())
    skills = load_skills()
    render_agents(out, agents)
    for harness in HARNESSES:
        render_skills(out, harness)
    render_hooks(out)
    render_marketplace(out, agents, skills)
    return agents


def managed_files(agents):
    return [MARKETPLACE_FILE]


# --- commands ------------------------------------------------------------------


def build():
    agents = load_agents(load_routing())
    for rel in MANAGED_DIRS:
        shutil.rmtree(ROOT / rel, ignore_errors=True)
    for rel in managed_files(agents):
        if rel != MARKETPLACE_FILE:
            (ROOT / rel).unlink(missing_ok=True)
    render_all(ROOT)
    print(f"rendered {len(agents)} agents x {len(HARNESSES)} harnesses into {ROOT}")


def relative_files(base):
    if not base.exists():
        return {}
    return {
        p.relative_to(base).as_posix(): p.read_bytes()
        for p in sorted(base.rglob("*"))
        if p.is_file()
    }


def check():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        agents = render_all(out)
        stale = []
        for rel in MANAGED_DIRS:
            expected = relative_files(out / rel)
            actual = relative_files(ROOT / rel)
            for name in sorted(set(expected) | set(actual)):
                if expected.get(name) != actual.get(name):
                    stale.append(f"{rel}/{name}")
        for rel in managed_files(agents):
            expected = (out / rel).read_bytes()
            actual = (ROOT / rel).read_bytes() if (ROOT / rel).exists() else None
            if expected != actual:
                stale.append(rel)
    if stale:
        print("rendered outputs are stale; run `make build` and commit:")
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
