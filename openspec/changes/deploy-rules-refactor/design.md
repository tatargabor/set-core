## Context

Currently `deploy.sh:_deploy_skills()` (lines 174-197) deploys rules to consumer projects by running `find .claude/rules -maxdepth 1 -name '*.md'`. This implicitly deploys ALL top-level `.md` files, including set-core internal docs like `modular-architecture.md` and `openspec-artifacts.md` that have no value in consumer projects. Internal rules must be hidden in subdirectories (`gui/`, `dev/`) as a workaround.

The web template rules (deployed via `profile_deploy.py`) are unaffected — they already use an explicit manifest system.

## Goals / Non-Goals

**Goals:**
- Explicit control over which rules deploy to consumer projects
- `.claude/rules/` becomes set-core's own space (can add files freely)
- No behavior change for consumer projects (same `set-*.md` files)

**Non-Goals:**
- Changing the web template deployment (profile_deploy.py — stays as-is)
- Changing the `set-` prefix convention
- Changing agent or command deployment

## Decisions

### 1. New source: `templates/core/rules/`
Core rules that deploy to every project live in `templates/core/rules/`. This is a flat directory with `.md` files.
**Why:** Matches the existing `templates/` directory (already has `cross-cutting-checklist.md`, `memory-seed.yaml`, `systemd/`). The `core/rules/` nesting makes it clear these are the universally-deployed rules, distinct from project-type templates in `modules/`.
**Alternative considered:** Manifest file listing which `.claude/rules/` files to deploy — rejected because it's one more indirection. Having the actual files in `templates/core/rules/` is self-documenting: what you see is what gets deployed.

### 2. Files are independent copies, not symlinks
The files in `templates/core/rules/` are standalone copies, not symlinks to `.claude/rules/`.
**Why:** The set-core version of a rule may evolve differently from the consumer version. For example, `sentinel-autonomy.md` in set-core has internal context about merge testing that consumers don't need. Over time these may diverge, which is fine — they serve different audiences.

### 3. deploy.sh reads `templates/core/rules/*.md` with simple find
```bash
local src_rules="$SET_TOOLS_ROOT/templates/core/rules"
find "$src_rules" -name '*.md' -print0
```
No `-maxdepth 1` needed — everything in `templates/core/rules/` is meant to be deployed.
**Why:** Simpler than the current code. No manifest parsing, no hack.

### 4. Remove old `templates/cross-cutting-checklist.md`
There's an existing `templates/cross-cutting-checklist.md` deployed by a separate mechanism in `bin/set-project` (lines 111-121). This is superseded by `templates/core/rules/cross-cutting-checklist.md` and the unified rules deploy path.
**Why:** Single deployment path for all core rules. No special cases.

### 5. Which rules go to `templates/core/rules/`

| Rule | Deploy? | Reason |
|------|---------|--------|
| `cross-cutting-checklist.md` | YES | Universal parallel-worktree safety |
| `design-bridge.md` | YES | Design snapshot integration |
| `sentinel-autonomy.md` | YES | Sentinel behavior rules |
| `readme-updates.md` | YES | README generation conventions |
| `modular-architecture.md` | NO | set-core internal architecture |
| `openspec-artifacts.md` | NO | set-core monorepo-specific |
| `gui/*.md` | NO | set-core GUI development |

## Risks / Trade-offs

[Risk] Content drift between `.claude/rules/` and `templates/core/rules/` versions → Mitigation: acceptable. They serve different audiences. If exact sync is needed, a CI check can diff them.

[Risk] Forgetting to add a new universal rule to `templates/core/rules/` → Mitigation: explicit is better than implicit. The old behavior (deploy everything) was the real risk.

[Risk] Old `templates/cross-cutting-checklist.md` removal breaks something → Mitigation: check all callers in `bin/set-project` before removing.

## Migration Plan

1. Create `templates/core/rules/` with 4 rule files
2. Update `deploy.sh` to read from `templates/core/rules/`
3. Remove old `templates/cross-cutting-checklist.md` and its special-case deploy in `bin/set-project`
4. No consumer-facing migration needed — same files deployed with same names
