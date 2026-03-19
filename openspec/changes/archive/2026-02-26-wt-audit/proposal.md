## Why

Projects using set-core and Claude Code accumulate the same "meta-infrastructure" independently: design docs (`docs/design/*.md`), path-scoped rules (`.claude/rules/`), code-reviewer agents, permission allowlists, verification hooks, OpenSpec config context. Today this happens ad-hoc — each project discovers what's missing through trial and error, then creates project-specific changes to fill the gaps. There's no way to see the overall health of a project's LLM-readiness or get guidance on what's missing.

The key insight: `wt-audit` should NOT generate template files. It should **collect evidence** from the project (what exists, what patterns are in the code, what's stale) and provide **guidance with sources** so the LLM in that project can create project-specific content. This makes it equally useful for init (nothing exists yet) and update (things exist but are outdated).

## What Changes

- **`bin/wt-audit`** CLI tool — bash-based L1 scanner that checks project health across 6 dimensions: Claude Code config (permissions, hooks, agents, rules), design documentation, OpenSpec config, code quality signals, CLAUDE.md structure, and `.gitignore` coverage. Output is a structured "evidence package" with ✅/⚠️/❌ status per check, concrete file paths as sources, and actionable guidance pointing the LLM to what to read and what to create.
- **`lib/audit/`** directory — reference checks as modular bash functions (one per dimension), plus a `reference.md` describing what a well-configured project looks like (the "target state" the LLM should aim for).
- **`/wt:audit` skill** — Claude Code skill that runs `wt-audit scan`, injects the evidence package into context, and lets the LLM act on the findings interactively.
- **`set-project init` integration** — after existing deploy steps, runs `wt-audit scan` and shows a summary of remaining gaps.

## Capabilities

### New Capabilities
- `project-health-scan`: Bash-based evidence collection across 6 project dimensions — Claude Code config, design docs, OpenSpec config, code signals, CLAUDE.md structure, gitignore. Outputs structured report with status indicators (✅/⚠️/❌), source file paths, and LLM-directed guidance.
- `audit-skill`: `/wt:audit` skill that runs the scan, presents findings, and lets the LLM address gaps interactively with project-specific knowledge.

### Modified Capabilities
- `project-init-deploy`: `set-project init` runs audit scan at the end and shows gap summary.

## Impact

- New files: `bin/wt-audit`, `lib/audit/*.sh`, `lib/audit/reference.md`, `.claude/commands/wt/audit.md`
- Modified: `bin/set-project` (add post-init audit call), `.claude/skills/wt/SKILL.md` (add audit section)
- Dependencies: none (pure bash, uses existing project files)
- Deployed to all registered projects via `set-project init`
