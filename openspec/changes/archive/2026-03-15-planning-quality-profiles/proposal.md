## Why

### Problem 1: Quality patterns injected too late

E2E run #13 revealed that agents produce code requiring multiple review retries for security issues (IDOR on cart mutations, missing auth middleware). The review gate catches these issues, but agents need 2-3 retries to fix them — wasting tokens and time. The root cause: quality patterns (security, architecture, design) are injected too late (at review) instead of during planning and dispatch.

### Problem 2: Plugin system exists but engine doesn't use it

A **complete project-type plugin system already exists** across 3 repos:

```
set-project-base (pip package)           set-project-web (pip package)
├── ProjectType ABC                      ├── WebProjectType(BaseProjectType)
│   ├── info()                           │   ├── 11 verification rules (i18n, auth, prisma...)
│   ├── get_templates()                  │   ├── 7 orchestration directives
│   ├── get_verification_rules()         │   └── templates/nextjs/rules/
│   └── get_orchestration_directives()   │       ├── security.md (CSP, CORS, rate limiting)
├── BaseProjectType                      │       ├── auth-conventions.md (NextAuth, roles)
│   ├── 3 verification rules            │       ├── testing-conventions.md
│   └── 4 orchestration directives       │       └── ... (13 rule files total)
└── Python entry_points registration     └── extends base via inheritance
```

`set-project init --project-type web` correctly loads and deploys these. **But the orchestration engine ignores them entirely** and uses its own hardcoded web patterns:

| Engine file | What's hardcoded | Plugin equivalent (unused) |
|-------------|-----------------|---------------------------|
| `templates.py:244-344` | Playwright E2E, auth middleware, IDOR in `_PLANNING_RULES` | `set-project-web` security.md, auth-conventions.md, testing-conventions.md |
| `dispatcher.py:46-60` | `LOCKFILE_PM_MAP`, `pnpm install`, `GENERATED_FILE_PATTERNS` | `set-project-base` orchestration directives |
| `planner.py:164-195` | `_auto_detect_test_command()` reads `package.json` | Should be profile method |
| `verifier.py:136-174` | `_load_web_security_rules()` hardcoded to `rules/web/` | `set-project-web` verification rules |
| `builder.py:190-225` | `_detect_build_cmd()` reads `package.json` | Should be profile method |
| `merger.py:562-611` | `_install_post_merge_deps()` pnpm/yarn/npm only | `set-project-base` `install-deps-npm` directive |
| `milestone.py:353-376` | PM detection + install (duplicated) | Same — duplicated 5 times across engine |
| `config.py:560-619` | PM detection + test command (duplicated) | Same |
| `bin/wt-merge:47-59` | `GENERATED_FILE_PATTERNS` (Node.js only) | Should come from profile |
| `bin/wt-new:58-77` | PM detection + install (duplicated) | Same |
| `deploy.sh:175-196` | Deploys ALL rules to ALL projects | Should filter by project type |

**PM detection alone is duplicated 5 times** across dispatcher.py, planner.py, builder.py, config.py, milestone.py.

### Problem 3: Self-use vs consumer rules conflated

set-core is itself a web application (wt-control dashboard, API endpoints). Its own `.claude/rules/web/` are needed for self-development — but these same rules also get deployed to consumer projects via `deploy.sh`, even though consumer projects already get rules from `set-project-web` templates.

### Evidence from E2E runs

| Run | Issue | Root cause | Tokens wasted |
|-----|-------|------------|---------------|
| #13 | cart-feature IDOR not fixed after 2 retries | Security patterns not in planning context | ~200K |
| #13 | admin-auth missing middleware.ts | Auth middleware pattern not in dispatch context | ~180K |
| #13 | 5 sentinel interventions needed | Agents didn't know patterns upfront | — |
| #4 vs #13 | 0 interventions vs 5 | #4 had no review gate, but also no security issues | — |

### Research mandate

This change requires **research into industry standards and our own empirical data** before implementation:
- **OWASP Top 10** — which checks can be shifted left into planning prompts?
- **SANS CWE Top 25** — common weakness patterns applicable to AI code generation
- **Secure SDLC practices** — how do enterprise teams inject security into design phase?
- **AI code generation quality** — academic/industry research on prompt engineering for secure code
- **Framework-specific patterns** — Next.js, Django, FastAPI, Rails each have their own security idioms
- **Our own E2E data** — 13 runs of empirical data on what agents get wrong and what review catches

The goal is not just to move existing rules earlier, but to **discover what patterns are most effective** at preventing issues when injected at planning time vs dispatch time vs review time.

## What Changes

### Phase 1: Research & Analysis
- Research OWASP/SANS/NIST standards for which security patterns are most effective as "shift-left" planning context
- Analyze all 13 E2E runs to categorize: what did agents get wrong, what did review catch, what could planning have prevented
- Audit `set-project-web` existing rules (13 rule files in templates/nextjs/rules/) for completeness vs our hardcoded patterns
- Design the bridge between existing plugin interface and orchestration engine

### Phase 2: Extend ProjectType Interface
The existing `ProjectType` ABC in `set-project-base` has `get_verification_rules()` and `get_orchestration_directives()`. It needs new methods for orchestration engine integration:

- `planning_rules() -> str` — quality patterns for the decompose prompt (security, architecture, testing)
- `security_rules() -> List[Path]` — rule files for review retry context
- `generated_file_patterns() -> List[str]` — patterns for merge conflict resolution
- `detect_package_manager(project_path) -> Optional[str]` — replaces 5 duplicated functions
- `detect_test_command(project_path) -> Optional[str]` — replaces hardcoded package.json parsing
- `detect_build_command(project_path) -> Optional[str]` — replaces hardcoded build detection
- `bootstrap_worktree(worktree_path) -> None` — dependency install for new worktrees
- `post_merge_install(project_path) -> None` — dependency install after merge
- `ignore_patterns() -> List[str]` — for digest generation (node_modules, venv, etc.)

### Phase 3: Connect Engine to Plugin System
- **New `lib/set_orch/profile_loader.py`** — loads the active profile from `wt/plugins/project-type.yaml` via Python entry_points (same mechanism `set-project init` uses)
- Replace hardcoded patterns in engine files with profile method calls:
  - `templates.py` — `_PLANNING_RULES` split into core + `profile.planning_rules()`
  - `dispatcher.py` — `LOCKFILE_PM_MAP`, `GENERATED_FILE_PATTERNS`, bootstrap → profile methods
  - `planner.py` — `_auto_detect_test_command()` → `profile.detect_test_command()`
  - `verifier.py` — `_load_web_security_rules()` → `profile.security_rules()`
  - `builder.py` — `_detect_pm()`, `_detect_build_cmd()` → profile methods
  - `merger.py` — `_install_post_merge_deps()` → `profile.post_merge_install()`
  - `milestone.py` — PM detection → profile method
  - `config.py` — PM + test + build detection → profile methods (single source of truth)
  - `bin/wt-merge` — `GENERATED_FILE_PATTERNS` → profile config file or env var
  - `bin/wt-new` — PM detection + install → profile bootstrap
  - `digest.py` — `_IGNORE_PATTERNS` → includes `profile.ignore_patterns()`
- **Graceful fallback**: if no profile loaded (plugin not installed), fall back to current hardcoded behavior

### Phase 4: Planning Quality Injection
- `render_planning_prompt()` calls `profile.planning_rules()` to get framework-specific quality patterns
- Profile planning rules include security design patterns (not just review rules):
  - "Every mutation endpoint MUST include ownership check in the WHERE clause"
  - "Protected routes MUST have middleware, not handler-level auth checks"
  - "Every new API route MUST have input validation schema"
- These patterns are injected BEFORE agents write code, not after review fails
- Research output determines which patterns go to planning vs dispatch vs review

### Phase 5: Dispatch Quality Injection
- `_build_proposal_content()` includes profile's security checklist in proposal.md
- Agent sees security requirements BEFORE writing code, not after review fails
- Profile provides dispatch-time context (relevant security rules, architecture patterns)

### Phase 6: Separate Self-Use vs Deploy Rules

**Critical distinction**: set-core' own `.claude/rules/web/` stay — they're for developing set-core itself (wt-control dashboard, API endpoints). Consumer rules come from `set-project-web` templates.

```
set-core/.claude/rules/web/        ← STAYS: set-core' own dev rules
                                      (auth-middleware.md, security-patterns.md, api-design.md)

set-project-web/templates/nextjs/   ← ALREADY EXISTS: consumer rules
  rules/security.md                   (CSP, CORS, rate limiting, input validation)
  rules/auth-conventions.md           (NextAuth, roles, middleware)
  rules/testing-conventions.md        (Playwright, Jest patterns)
  rules/...                           (13 rule files)
```

- `deploy.sh` stops deploying set-core' own `.claude/rules/web/` to consumer projects
- Consumer rules come exclusively from `set-project-web` templates (already working via `set-project init`)
- Engine loads security rules from profile path, not hardcoded `rules/web/`

### Phase 7: Implement in set-project-web
- Add new methods to `WebProjectType`:
  - `planning_rules()` — based on research output + existing templates/nextjs/rules/ content
  - `security_rules()` — points to templates/nextjs/rules/security.md + auth-conventions.md
  - `detect_package_manager()` — consolidates the 5 duplicated implementations
  - `detect_test_command()` — from package.json scripts
  - `detect_build_command()` — from package.json scripts
  - `generated_file_patterns()` — `.tsbuildinfo`, lock files, `.next/`, `dist/`
  - `bootstrap_worktree()` — `pnpm install --frozen-lockfile`
  - `post_merge_install()` — `pnpm install --no-frozen-lockfile`
  - `ignore_patterns()` — `node_modules`, `.next`, `dist`

## Capabilities

### New Capabilities
- `profile-engine-bridge`: Orchestration engine loads and uses project-type plugins for all framework-specific behavior
- `planning-quality-injection`: Security and architecture patterns from profile injected at decomposition time
- `dispatch-security-checklist`: Per-change security requirements from profile included in agent's proposal.md
- `unified-pm-detection`: Single source of truth for package manager detection via profile (replaces 5 duplications)

### Modified Capabilities
- `orchestration-planning`: `render_planning_prompt()` loads profile-specific planning rules
- `change-dispatch`: `dispatch_change()` uses profile for PM detection, bootstrap, security context
- `code-review-verification`: `_load_web_security_rules()` uses profile's `security_rules()` instead of hardcoded path
- `merge-pipeline`: Post-merge install uses profile's `post_merge_install()`
- `project-deployment`: `deploy.sh` stops deploying set-core' own rules to consumer projects
- `worktree-bootstrap`: `bin/wt-new` uses profile's `bootstrap_worktree()` instead of hardcoded PM detection

## Impact

### set-core (this repo)
- **New**: `lib/set_orch/profile_loader.py` — loads active profile from `wt/plugins/project-type.yaml`
- **Modified**: `lib/set_orch/templates.py` — split `_PLANNING_RULES` into core + `profile.planning_rules()`
- **Modified**: `lib/set_orch/dispatcher.py` — PM detection, bootstrap, proposal enrichment → profile methods
- **Modified**: `lib/set_orch/planner.py` — test command detection → profile method
- **Modified**: `lib/set_orch/verifier.py` — security rules → profile method
- **Modified**: `lib/set_orch/builder.py` — build command detection → profile method
- **Modified**: `lib/set_orch/merger.py` — post-merge install → profile method
- **Modified**: `lib/set_orch/milestone.py` — PM detection → profile method
- **Modified**: `lib/set_orch/config.py` — PM + test + build detection → profile methods
- **Modified**: `lib/set_orch/digest.py` — ignore patterns → includes profile patterns
- **Modified**: `bin/wt-merge` — generated file patterns → profile config
- **Modified**: `bin/wt-new` — bootstrap → profile method
- **Modified**: `lib/project/deploy.sh` — stop deploying own rules, only profile rules
- **Kept**: `.claude/rules/web/*.md` — set-core' own dev rules stay (set-core is itself a web app)

### set-project-base (separate repo)
- **Modified**: `base.py` — add new abstract methods to `ProjectType` ABC (with default no-op implementations for backward compat)

### set-project-web (separate repo)
- **Modified**: `project_type.py` — implement new methods in `WebProjectType`
- **Research output**: Document which OWASP/SANS patterns are most effective in planning vs dispatch vs review, backed by E2E run data

### Risk & backward compatibility
- **No breaking changes**: All new methods have default no-op implementations in base class
- **Graceful degradation**: If profile not installed, engine falls back to current hardcoded behavior
- **Cross-repo coordination**: Changes span 3 repos — must be versioned together
- **E2E validation**: Run #14 should test the full flow with profile-based quality injection
