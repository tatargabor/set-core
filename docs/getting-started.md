[< Back to README](../README.md)

# Getting Started

## Platform Support

wt-tools is developed and primarily tested on **Linux** (Ubuntu 22.04+). **macOS** has partial support — core functionality works, but platform-specific features are less tested. Feature development is Linux-first; contributors are actively working on improving macOS parity.

Platform-specific differences may exist in areas like window management (GUI), process signals, and shell behavior. We welcome macOS-focused contributions and bug reports.

## Prerequisites

| Requirement | Check | Purpose |
|-------------|-------|---------|
| **Git** | `git --version` | Worktree management |
| **Python 3.10+** | `python3 --version` | GUI and MCP server |
| **jq** | `jq --version` | JSON processing in shell scripts |
| **Node.js** | `node --version` | Claude Code CLI |
| **OpenSpec v1.1.1** | `openspec --version` | Spec-driven workflow (`npm i -g @fission-ai/openspec@1.1.1`) |

## Install wt-tools

```bash
git clone https://github.com/tatargabor/wt-tools.git
cd wt-tools
./install.sh
```

The installer:
- Symlinks all `wt-*` commands to `~/.local/bin`
- Sets up shell completions (bash/zsh)
- Configures the MCP server for Claude Code
- Installs GUI dependencies (PySide6, psutil, PyNaCl)
- Installs Shodh-Memory (optional, interactive prompt)
- Deploys wt-tools to all registered projects (`wt-project init`)
- Sets up editor choice, permission mode, and model prefix

## GUI Dependencies (Optional)

The installer handles GUI dependencies automatically. If you need to install manually:

```bash
pip install PySide6 psutil PyNaCl
```

### Linux: Qt Plugin Path

If you use conda or a non-system Python, set the Qt plugin path:

```bash
QT_PLUGIN_PATH="$(python -c 'import PySide6; print(PySide6.__path__[0])')/Qt/plugins" wt-control
```

## Developer Memory (Optional)

The installer offers to install Shodh-Memory. To install manually:

```bash
pip install 'shodh-memory>=0.1.81'
wt-memory health   # verify installation
```

Memory degrades gracefully — if not installed, all memory commands silently no-op.

## Register Your Project

```bash
cd ~/my-project
wt-project init
```

This registers the project, deploys hooks, commands, skills, and agents to `.claude/`, configures the MCP server, and adds memory sections to `CLAUDE.md`. Re-run anytime to update.

Use `--dry-run` to preview changes without modifying files.

## First Run

### 1. Create a worktree

```bash
wt-new add-user-auth
```

Creates a new git worktree with branch `change/add-user-auth`.

### 2. Open it

```bash
wt-work add-user-auth
```

Opens the worktree in your configured editor and starts Claude Code automatically.

### 3. Launch the Control Center (optional)

```bash
wt-control
```

A compact always-on-top window showing all worktrees and agent status. Double-click any row to jump to that worktree.

### 4. Run the sentinel (for multi-change work)

```bash
# From a Claude Code session in your project:
/wt:sentinel --spec docs/my-spec.md --max-parallel 2
```

The sentinel starts the orchestrator, monitors it, handles crashes, auto-approves checkpoints, and produces a summary when done.

### 5. Clean up

```bash
wt-merge add-user-auth    # merge branch back to main
wt-close add-user-auth    # remove worktree and branch
```

## When to Use What

| Situation | Tool |
|-----------|------|
| 1 agent, 1 project | You probably don't need wt-tools yet |
| 2+ agents or switching projects often | Control Center GUI + `wt-work` |
| Structured feature development | OpenSpec (`/opsx:new` → `/opsx:apply`) |
| Well-defined task list to grind through | Ralph Loop (`wt-loop start`) |
| Multiple changes from a spec | Sentinel (`/wt:sentinel --spec`) |
| Want agents to learn across sessions | Developer Memory (`wt-memory`) |
| Multiple machines or team members | Team Sync (`wt-control-init`) |

## Next Steps

- [Sentinel & Orchestration](sentinel.md) — autonomous multi-change execution
- [Project Setup](project-setup.md) — project registration and templates
- [OpenSpec Workflow](openspec.md) — spec-driven development skills
- [Worktree Management](worktrees.md) — CLI commands and skills
- [Ralph Loop](ralph.md) — autonomous single-change execution
- [Developer Memory](developer-memory.md) — cross-session agent recall
- [Control Center GUI](gui.md) — real-time monitoring

---

*See also: [CLI Reference](cli-reference.md) · [Configuration](configuration.md) · [Architecture](architecture.md)*
