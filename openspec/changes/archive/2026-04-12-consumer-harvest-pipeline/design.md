# Design: consumer-harvest-pipeline

## Context

Consumer projects accumulate valuable fixes during E2E runs — ISS fixes (build gate DB init, smoke_blocking config), template divergences (middleware rules, i18n patterns), and planning rule gaps. The existing harvest skill only diffs `.claude/rules/`, missing ISS commits and framework-level fixes entirely. Over months of runs, dozens of fixes have gone unreviewed.

The key insight: **this runs from set-core, not from the consumer project**. The developer sits in set-core and reviews what consumer projects discovered.

## Goals / Non-Goals

**Goals:**
- Scan all registered projects for unadopted ISS fixes and `.claude/` changes
- Present chronologically, per-project, per-commit — user reviews one by one
- Track what's been reviewed so harvests are incremental
- Make adoption easy — suggest target file, show diff, write on confirm

**Non-Goals:**
- Auto-adopting anything (always requires user confirmation)
- LLM-based classification (heuristics are sufficient and deterministic)
- Replacing the learnings-to-rules pipeline (that handles review findings, this handles commits)

## Decisions

### D1: Git log scanning with pattern matching

**Choice:** Scan `git log --oneline --after=<last_harvested_sha>` for each registered project. Classify commits by:
- `fix-iss-*` or `fix:` in message → ISS fix candidate
- `--diff-filter=M -- '.claude/'` → template divergence candidate
- Everything else → skip (feature implementation, not framework-relevant)

**Why:** Simple, fast, no external dependencies. The commit message conventions are already enforced by the orchestration system.

### D2: Classification heuristics (no LLM)

**Choice:** Classify by files changed:
- Modifies `package.json` scripts, `*config.ts`, `middleware.ts`, `.env*` → framework-relevant
- Modifies only `src/app/`, `src/components/`, `prisma/` with business logic → project-specific  
- Modifies `.claude/rules/set-*.md` → template divergence (diff against set-core source)

**Why:** Deterministic, instant. The file paths tell you the scope — no ambiguity.

### D3: Adoption targets mapped by file type

| Consumer file modified | Set-core adoption target |
|----------------------|--------------------------|
| `package.json` build script | `modules/web/.../planning_rules.txt` |
| `playwright.config.ts` | `modules/web/.../templates/playwright.config.ts` |
| `middleware.ts` patterns | `.claude/rules/web/set-auth-middleware.md` |
| `.claude/rules/set-*.md` | `templates/core/rules/` or `modules/web/.../templates/rules/` |
| `vitest.config.ts` | `modules/web/.../templates/vitest.config.ts` |
| Other | User chooses target |

### D4: Harvest state in project registry

**Choice:** Add `last_harvested_sha` to `set-project` registry (the same JSON that stores project paths). Not a separate file.

**Why:** Atomic with project registration. If a project is removed, its harvest state goes with it.

### D5: CLI tool (`bin/set-harvest`), not just a skill

**Choice:** Python CLI in `bin/set-harvest` + `lib/set_orch/harvest.py`. The `/set:harvest` skill calls the CLI.

**Why:** The CLI can be run outside Claude sessions (e.g., in CI, by the developer directly). The skill wraps it for interactive use.

### D6: Chronological order across projects

**Choice:** All commits from all projects are sorted by date, not grouped by project. This shows the true timeline — which fix came first, which fix was repeated across projects.

**Why:** If the same build gate fix appears in minishop-run14 AND craftbrew-run22, the chronological view reveals it immediately. Project-grouped would hide the pattern.

## Risks / Trade-offs

- **[Risk] Too many commits to review** → Mitigation: ISS fix + `.claude/` filters reduce to ~5-10 commits per run. Chronological + skip makes it fast.
- **[Risk] Heuristic misclassifies a commit** → Mitigation: User always reviews. "View diff" shows full context. No auto-adoption.
- **[Risk] Stale projects in registry inflate scan** → Mitigation: Skip projects where git dir is missing. Warn about unregistered projects.
