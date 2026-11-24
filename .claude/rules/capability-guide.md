# set-core Capability Guide

This project is **set-core** — an orchestration framework for Claude Code that manages parallel agent development via git worktrees, OpenSpec-driven planning, and automated quality gates.

## What do you want to do?

| Goal | Command | When |
|------|---------|------|
| Think through a problem | `/opsx:explore` | Before starting work, during design |
| Start a structured change | `/opsx:new <name>` | New feature, fix, or refactor |
| Quick change (all artifacts) | `/opsx:ff <name>` | When you know what to build |
| Continue a change | `/opsx:continue` | Next artifact in sequence |
| Implement tasks | `/opsx:apply` | Code the change |
| Verify implementation | `/opsx:verify` | Before archiving |
| Archive completed change | `/opsx:archive` | Finalize and close |
| Sync specs to main | `/opsx:sync` | Update main specs without archiving |
| Check the machine and every project | `set-doctor` | After an install, a pull, or when something looks off |
| Watch the fleet all day | `set-watchdog` (`status`, timer every 5 min; 🩺 badge in the fleet header) | Probes for quiet failures, GLM triage, hands real ones to the owning project |
| Deploy set-core into a project | `set-project init` (`--dry-run` first) | New project, or after set-core changed |
| Write the project role rules | `set-project roles` (`--check`, `--dry-run`) | After editing the machine-local role file |
| Hide a project nobody develops | `set-project archive <name>` | The doctor skips it; its role rule says "do not develop" |
| Search a project's knowledge | `set-kb search` / MCP `kb_search` | Before answering from memory |
| Check what a push would publish | `set-leakscan` (`--staged`, `--tree`) | Before every push; the hooks run it too |
| Answer relayed questions on your behalf | `set-auto-answer` (fleet header 🤖 panel; `auto_answer.*` in `set-config`) | It forks the asking session, checks its sources, proposes, writes after a window; never an outward step or a permission |
| Talk to another session | `sac` (set-agent-comm) | Cross-project coordination — the git-based `/set:msg` path is retired |
| Architecture before an offer | `/set:blueprint` | Research the open questions, then the plan |

**Retired** (fleet-era-consolidation, 2026-11-23): the orchestration slash commands
(`/set:sentinel`, `/set:decompose`, `/set:plan-review`, `/set:start`, `/set:write-spec`,
`/set:new`, `/set:work`, `/set:list`, `/set:merge`, `/set:close`, `/set:loop`, `/set:push`,
`/set:status`, `/set:audit`, `/set:forensics`, `/set:harvest`, `/set:help`) and the git-bus
ones (`/set:msg`, `/set:inbox`, `/set:broadcast`) are no longer deployed. The engine behind
them is dormant and is being removed in stages — see `openspec/changes/fleet-era-consolidation`.

## Key Architectural Rules

- **Layer 1 (lib/set_orch/)** is abstract — NEVER put project-specific logic here
- **Layer 2 (modules/)** implements project-type specifics (web patterns, framework detection)
- **All orchestration merges go through integration gates** — never `git merge` manually (while the engine exists)
- **Profile system is the extension point** — new behaviors go through ProjectType ABC
- **Consumer projects get set-core via `set-project init`** — templates/core/rules/ for universal rules, modules/*/templates/ for project-type rules

## Where things are, and what the CLI can do

Derivable, so not copied here: `ls lib/ modules/ bin/ .claude/` shows the layout,
`set-<tool> --help` documents every CLI tool, and the MCP tools are listed in the session's
own tool list. `/set:help` is the guided version. What is NOT derivable — the layering rules
— is in [modular-architecture](modular-architecture.md).
