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
| Archive multiple changes | `/opsx:bulk-archive` | Batch cleanup |
| Sync specs to main | `/opsx:sync` | Update main specs without archiving |
| Run full orchestration | `/set:sentinel` | Autonomous multi-change execution |
| Decompose spec into plan | `/set:decompose` | Break spec into orchestration changes |
| Review a plan | `/set:plan-review` | Validate plan quality |
| Create worktree | `/set:new <id>` | Parallel development branch |
| Open worktree in editor | `/set:work <id>` | Start working in a worktree |
| List worktrees | `/set:list` | See active parallel work |
| Merge worktree | `/set:merge <id>` | Merge via integration gates |
| Close worktree | `/set:close <id>` | Clean up finished work |
| Check project health | `/set:audit` | Diagnose config/setup issues |
| Forensics on a finished run | `/set:forensics` | Post-run debugging / error triage |
| See agent activity | `/set:status` | What's everyone working on |
| Send message to agent | `/set:msg` | Cross-agent communication |
| Check inbox | `/set:inbox` | Read messages from other agents |
| Broadcast status | `/set:broadcast` | Tell team what you're doing |
| Push branch | `/set:push` | Push to remote |
| Start agent loop | `/set:loop` | Autonomous Ralph loop |
| Onboarding walkthrough | `/opsx:onboard` | First time? Start here |
| Quick help | `/set:help` | Feature reference |

## Typical Workflows

**Structured change (most common):**
```
/opsx:explore  →  /opsx:new  →  /opsx:apply  →  /opsx:verify  →  /opsx:archive
```

**Quick fix:**
```
/opsx:ff <name>  →  /opsx:apply  →  /opsx:verify  →  /opsx:archive
```

**Full autonomous orchestration:**
```
/set:sentinel --spec <path> --max-parallel 3
```

**Consumer project diagnostics:**
Read run logs → fix set-core bugs → `set-project init` to redeploy

## Key Architectural Rules

- **Layer 1 (lib/set_orch/)** is abstract — NEVER put project-specific logic here
- **Layer 2 (modules/)** implements project-type specifics (web patterns, framework detection)
- **All merges go through integration gates** — never `git merge` manually
- **Profile system is the extension point** — new behaviors go through ProjectType ABC
- **Consumer projects get set-core via `set-project init`** — templates/core/rules/ for universal rules, modules/*/templates/ for project-type rules

## Where things are, and what the CLI can do

Derivable, so not copied here: `ls lib/ modules/ bin/ .claude/` shows the layout,
`set-<tool> --help` documents every CLI tool, and the MCP tools are listed in the session's
own tool list. `/set:help` is the guided version. What is NOT derivable — the layering rules
— is in [modular-architecture](modular-architecture.md).
