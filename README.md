# wt-tools

Autonomous multi-change orchestration for Claude Code — give it a spec, get merged features.

> **Latest update:** 2026-03-07

---

## Overview

wt-tools turns a specification document into parallel, autonomous Claude Code agents that implement, test, and merge features — while you sleep. The **sentinel** supervises the orchestrator, handles crashes, auto-approves checkpoints, and produces a summary when done. Under the hood, it decomposes your spec into independent changes, creates isolated git worktrees for each, runs Ralph loops (autonomous agent iterations), and merges results back to main with verification gates.

Beyond orchestration: **Developer Memory** gives agents persistent cross-session recall — decisions, learnings, and context accumulate across sessions so future agents don't start from zero (+34% convention compliance in benchmarks). The **Control Center GUI** shows everything at a glance: agent status, context usage, API burn rate, and orchestration progress in a compact always-on-top window.

wt-tools is modular — cherry-pick what's useful. The GUI is optional; CLI tools, Claude Code skills, memory, and the MCP server all work independently.

> **Not a weekend experiment.** wt-tools is built from real production experience — web apps, research projects, sensor systems, education platforms, mobile apps, across Linux and macOS. Every feature is battle-tested on client projects at [ITLine Kft.](https://itline.hu) and continuously updated with the latest Claude Code patterns, community contributions, and best practices from Cursor and other tools. Built on Anthropic's Claude as a stable foundation. Open source because good tooling shouldn't be gatekept.

```
spec.md ──► /wt:sentinel ──► orchestrate ──► worktrees (parallel) ──► merged features
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
                 Ralph         Memory        Verify
                 loops         recall        & merge
```

![Orchestrator TUI — live dashboard](docs/images/orchestrator-tui.png)

---

## Quick Start

```bash
# 1. Install
git clone https://github.com/tatargabor/wt-tools.git
cd wt-tools && ./install.sh

# 2. Register your project
cd ~/my-project && wt-project init

# 3. Run the sentinel (from a Claude Code session)
/wt:sentinel --spec docs/my-spec.md --max-parallel 2

# Or start simple — create a worktree and work manually
wt-new my-feature && wt-work my-feature
```

See [Getting Started](docs/getting-started.md) for the full guide.

---

## Features

**[Sentinel & Orchestration](docs/sentinel.md)** — Supervises autonomous multi-change execution. Decomposes a spec into parallel changes, dispatches each to its own worktree, monitors progress, and merges results with verification gates. [Orchestration details](docs/orchestration.md).

**[Project Setup](docs/project-setup.md)** — Register projects, deploy hooks and skills, scaffold templates, and analyze codebases. `wt-project init` is the single entry point — re-run to update. Includes project knowledge scaffolding and codebase scraping for context.

**[OpenSpec Workflow](docs/openspec.md)** — Spec-driven development skills (`/opsx:new`, `/opsx:ff`, `/opsx:apply`, `/opsx:verify`, `/opsx:archive`). Structure changes as proposal → design → specs → tasks → implementation with artifact tracking.

**[Worktrees](docs/worktrees.md)** — Git worktree management with editor integration and Claude Code auto-launch. Create, open, merge, and close worktrees from CLI (`wt-new`, `wt-work`) or from inside the agent (`/wt:new`, `/wt:merge`).

**[Ralph Loop](docs/ralph.md)** — Autonomous agent execution. Runs Claude Code in iterations through task lists, checking completion between runs. Start with `wt-loop start`, monitor with `wt-loop monitor`.

**[Developer Memory](docs/developer-memory.md)** — Per-project cognitive memory. Agents save decisions and learnings as they work — future agents recall relevant past experience automatically via 5-layer hooks. Synthetic benchmarks show +34% convention compliance.

**[Control Center GUI](docs/gui.md)** — Compact, always-on-top PySide6 window. Shows agent status, context %, API burn rate, Ralph progress, and orchestration state. Double-click to jump to any worktree.

**[Team Sync & Messaging](docs/team-sync.md)** — Cross-machine coordination without a central server. Agents see each other's status and send directed messages via a `wt-control` git branch. Experimental.

**[MCP Server](docs/mcp-server.md)** — Exposes worktree status, Ralph progress, team activity, and memory tools to Claude Code agents via Model Context Protocol.

See [CLI Reference](docs/cli-reference.md) for all commands · [Configuration](docs/configuration.md) for all settings.

### When to use what

| Situation | Tool |
|-----------|------|
| 1 agent, 1 project | You probably don't need wt-tools yet |
| 2+ agents or switching projects often | Control Center GUI + `wt-work` |
| Structured feature development | OpenSpec (`/opsx:new` → `/opsx:apply`) |
| Well-defined task list to grind through | Ralph Loop (`wt-loop start`) |
| Multiple changes from a spec | Sentinel (`/wt:sentinel --spec`) |
| Want agents to learn across sessions | Developer Memory (`wt-memory`) |

---

## Plugins

wt-tools is extensible via plugins — separate repositories that add skills, agents, hooks, or CLI commands. Plugins are deployed to a project's `.claude/` directory alongside core files. See [Plugins](docs/plugins.md) for the concept, installation pattern, and plugin registry.

---

## Installation

**Prerequisites:** Git, Python 3.10+, jq, Node.js

```bash
git clone https://github.com/tatargabor/wt-tools.git
cd wt-tools && ./install.sh
```

See [Getting Started](docs/getting-started.md) for GUI dependencies, platform notes, and project setup.

---

## Platform & Editor Support

| Platform / Tool | Status | Notes |
|-----------------|--------|-------|
| **Linux** | Primary | Tested on Ubuntu 22.04+ |
| **macOS** | Supported | Some platform-specific workarounds |
| **Windows** | Not supported | Platform stubs exist but untested |
| **Zed** | Primary editor | Best tested, recommended |
| **VS Code** | Basic support | Editor detection works, less tested |
| **Cursor / Windsurf** | Basic support | Configurable via `wt-config editor set` |
| **Claude Code** | Integrated | Auto-launch, MCP server, skill hooks |

Solo-developer project — community help with cross-platform testing is valued.

---

<details>
<summary><strong>Related Projects</strong></summary>

### Worktree + Agent Managers

| Tool | Stars | Description |
|------|-------|-------------|
| [claude-squad](https://github.com/smtg-ai/claude-squad) | 6.2k | TUI for tmux+worktree multi-agent sessions (Go) |
| [ccpm](https://github.com/automazeio/ccpm) | 7.6k | GitHub Issues as PM layer + worktree agent swarm |
| [automaker](https://github.com/AutoMaker-Org/automaker) | 3k | Electron Kanban board + autonomous AI agents |
| [agent-deck](https://github.com/asheshgoplani/agent-deck) | 1.4k | TUI+Web session manager for multiple AI agents (Go) |

### Multi-Agent Orchestration

| Tool | Stars | Description |
|------|-------|-------------|
| [ruflo](https://github.com/ruvnet/ruflo) | 19.6k | Enterprise agent swarm platform with MCP integration |
| [oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) | 8.7k | Teams-first orchestration with 32 agents, 37 skills |
| [overstory](https://github.com/jayminwest/overstory) | 748 | Multi-agent orchestration with pluggable runtime adapters |

### Feature Comparison

```
                    GUI    Worktree  Auto   Orchestr- Team   MCP    Memory
                           Isolation Loop   ation     Sync   Server
─────────────────────────────────────────────────────────────────────────
wt-tools             Y       Y       Y       Y        Y      Y       Y
claude-squad        TUI      Y       Y       -        -      -       -
ccpm                 -       Y       -       Y        Y      -       Y
automaker            Y       Y       Y       Y        Y      -       -
ruflo                -       -       Y       Y        Y      Y       Y
oh-my-claudecode     -       Y       Y       Y        Y      -       Y
agent-deck         TUI+W     Y       ~       -        -      Y       -
overstory          TUI       Y       Y       Y        Y      -       -
```

</details>

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, and pull request guidelines.

## Acknowledgements

Built and used in production by [ITLine Kft.](https://itline.hu) and [Zengo Kft.](https://zengo.eu). Thanks to our collaboration partners: [BlackBelt](https://blackbelt.hu) · [AIOrigo](https://aiorigo.com) · [MKIK (Hungarian Chamber of Commerce)](https://mkik.hu).

## License

MIT License — See [LICENSE](LICENSE) for details.
