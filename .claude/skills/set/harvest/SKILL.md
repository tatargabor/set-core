Harvest framework fixes from consumer project E2E runs.

**Input**: `--project <name>` (optional) — scan a single project. Without it, scans all registered consumer projects.

**You are a framework maintainer.** Your job is to review ISS fixes and template changes from consumer E2E runs and decide which ones should be adopted into set-core.

## Quick Start

Run the harvest CLI to see unadopted framework-relevant fixes:

```bash
set-harvest --dry-run              # preview what's pending
set-harvest --project craftbrew-run-20260320-1445  # scan single project
set-harvest                        # interactive review all
set-harvest --all                  # include project-specific fixes too
set-harvest --json                 # machine-readable output
```

## What It Scans

The harvest tool scans registered consumer projects (from `set-project list`) for:

1. **ISS registry** — unresolved issues from `.set/issues/registry.json` with diagnosed root causes. Framework-relevant issues (orchestrator bugs, gate failures, stall recovery) are surfaced even if no fix commit exists. This catches bugs that were **diagnosed but never fixed**.
2. **ISS fix commits** — commits with `fix:` or `fix-iss-` patterns that were created by the orchestration agent during E2E runs to resolve build/test/e2e gate failures
3. **Template divergences** — modifications to `.claude/rules/set-*.md` files that were deployed by `set-project init` but modified by agents during the run

Issues are classified by keyword analysis of root_cause and error_summary:
- **FRAMEWORK** — mentions orchestrator, engine, merger, gate, stall, redispatch, worktree
- **EXTERNAL** — rate limits, API issues
- **PROJECT-SPECIFIC** — app-level bugs (Suspense, Prisma, Stripe)

Commits are classified by files changed:
- **FRAMEWORK** — modifies config files (package.json, playwright.config.ts, middleware.ts) → should be reviewed for adoption into planning_rules.txt or templates
- **TEMPLATE** — modifies `.claude/` deployed files → diff against set-core templates
- **PROJECT-SPECIFIC** — only modifies app code → usually skip

## Interactive Review

**Issues** (shown first):
1. **View** the ISS ID, severity, state, summary, and root cause
2. **Investigate** (`i`) to read the full investigation report
3. **Skip** (`s`) to move on
4. **Dismiss** (`d`) to mark as not relevant

**Commits** (shown after issues):
1. **View** the commit message, files changed, and suggested adoption target
2. **View diff** (`v`) to see the actual code change
3. **Adopt** (`a`) to apply the learning to set-core (planning rules, templates, or core code)
4. **Skip** (`s`) to mark as reviewed and move on

## Adoption Targets

| Consumer file | Set-core target |
|--------------|-----------------|
| `package.json` build script | `modules/web/.../planning_rules.txt` |
| `playwright.config.ts` | `modules/web/.../templates/nextjs/playwright.config.ts` |
| `middleware.ts` patterns | `.claude/rules/web/set-auth-middleware.md` |
| `.claude/rules/set-*.md` | `templates/core/rules/` |

## After Harvesting

The harvest state (last reviewed SHA per project) is saved to `~/.local/share/set-core/harvest-state.json`. Future harvests only show new changes since the last review.

## Guardrails

- Never auto-adopt — always review the diff and confirm
- Framework fixes often need generalization before adoption (strip project-specific paths, entity names)
- If a fix appears in multiple runs, it's a strong signal for adoption
- Template divergences should be diffed against the current set-core template, not blindly copied
