## Context

wt-tools deploys hooks, commands, and skills to projects via `wt-project init` → `deploy_wt_tools()` → `wt-deploy-hooks`. Three gaps were discovered through the eg-sales project where an agent implemented 136 files (180+ tasks) but committed none:

1. **activity-track.sh not deployed**: settings.json references `.claude/hooks/activity-track.sh` (relative path) but the file is never copied to target projects. Only works in wt-tools itself where it's in git. 11/13 projects affected.
2. **CLAUDE.md missing auto-commit**: The CLAUDE.md generator only includes the Persistent Memory section. The "Auto-Commit After Apply" instruction exists in wt-tools' own CLAUDE.md but is never propagated.
3. **apply skill missing commit step**: Neither SKILL.md nor apply.md mention committing after implementation.

## Goals / Non-Goals

**Goals:**
- Fix activity tracking hook deployment for all projects
- Ensure agents auto-commit after `/opsx:apply`
- Follow existing patterns (PATH-based hooks, CLAUDE.md template snippets)

**Non-Goals:**
- Adding a hard hook that auto-commits (too risky, agents should decide)
- Changing the openspec npm package templates (out of our control)
- Backwards-compatible migration for the old `.claude/hooks/` path

## Decisions

### D1: Move activity-track.sh to PATH as `wt-hook-activity`

**Choice**: Rename to `bin/wt-hook-activity`, symlink via install.sh, reference as `wt-hook-activity` in settings.json.

**Rationale**: All other hooks (wt-hook-stop, wt-hook-skill, wt-hook-memory) are PATH-based. The relative-path approach was an anomaly. PATH-based hooks:
- Work immediately in all projects without file copying
- Auto-update when wt-tools is updated (symlink to source)
- Don't need per-project deployment logic

**Alternative considered**: Copy `.claude/hooks/` in `deploy_wt_tools()`. Rejected because it adds per-project versioning complexity and is inconsistent with the existing pattern.

### D2: CLAUDE.md auto-commit snippet in deploy_wt_tools()

**Choice**: Add the snippet alongside the existing memory snippet in `deploy_wt_tools()`, with its own marker for idempotent updates.

**Rationale**: CLAUDE.md is the authoritative location for project-level agent instructions. The agent reads CLAUDE.md on every session. Using a marker (`## Auto-Commit After Apply`) allows idempotent re-runs.

### D3: Apply skill Step 8 in both files

**Choice**: Add commit step to both `.claude/skills/openspec-apply-change/SKILL.md` and `.claude/commands/opsx/apply.md`.

**Rationale**: From memory — "OpenSpec has TWO separate file types per skill: SKILL.md (loaded when LLM calls Skill tool) and command .md (loaded when user types /opsx:<id>). Custom additions to SKILL.md are NOT reflected in command files — both must be edited." Note: `openspec update --force` will overwrite command files from npm templates, losing the commit step. CLAUDE.md serves as the stable fallback.

## Risks / Trade-offs

- **[Risk] openspec update --force overwrites command files** → CLAUDE.md auto-commit instruction serves as stable backup. Document this in the commit message.
- **[Risk] Old settings.json still references `.claude/hooks/activity-track.sh`** → `wt-deploy-hooks` already detects and upgrades existing configs. The stale downgrade path in lines ~260-275 handles PreToolUse re-creation.
- **[Risk] Agent commits too eagerly** → The instruction says "after apply finishes or pauses", scoped to skill-driven apply only. This matches existing wt-tools behavior.
