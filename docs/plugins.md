[< Back to README](../README.md)

# Plugins

> **Status: Experimental.** Plugin infrastructure is available but the ecosystem is just starting. The `wt-plugin install` CLI is not yet implemented.

set-core is designed to be extensible. Plugins add new capabilities — custom skills, agents, hooks, or CLI commands — without modifying the core. Plugins live in separate repositories and are installed into projects independently.

## Concept

A plugin is a git repository containing any combination of:
- **Skills** (`.claude/skills/`) — Claude Code slash commands
- **Commands** (`.claude/commands/`) — Claude Code slash commands (user-facing)
- **Agents** (`.claude/agents/`) — specialized subagents
- **Hooks** — Claude Code hook scripts
- **CLI tools** (`bin/`) — shell commands

When installed, a plugin's files are deployed to the target project's `.claude/` directory, just like set-core core files.

## Installation

```bash
# Planned interface (not yet implemented):
wt-plugin install <repo-url>

# Current approach: clone and manually deploy
git clone <plugin-repo> /path/to/plugin
cp -r /path/to/plugin/.claude/skills/* ~/my-project/.claude/skills/
```

## Plugin Registry

Known plugins. This list will grow as the ecosystem develops.

| Name | Repository | Description | Status |
|------|-----------|-------------|--------|
| *(no plugins registered yet)* | | | |

To list your plugin here, submit a PR adding it to this table.

## Creating a Plugin

A plugin repository should contain:

```
my-plugin/
├── README.md              # what it does, how to install
├── .claude/
│   ├── skills/            # skill definitions (SKILL.md files)
│   ├── commands/           # user-facing commands
│   └── agents/             # specialized agents
└── bin/                    # CLI tools (optional)
```

Follow the same conventions as set-core core:
- Skills have a `SKILL.md` with trigger conditions and instructions
- Commands have a matching `.md` file per command
- CLI tools are executable scripts with `--help` support

See [CONTRIBUTING.md](../CONTRIBUTING.md) for code style and conventions.

---

*See also: [Getting Started](getting-started.md) · [Architecture](architecture.md) · [CLI Reference](cli-reference.md)*
