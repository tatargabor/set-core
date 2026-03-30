# Design: post-run-template-hardening

## Decisions

### D1: Add sections to existing rules rather than creating many new rule files
The web module already has 15 rule files. Rather than creating separate files for each gap, we add sections to existing rules where they topically belong. Only i18n gets a new file because no existing rule covers it.

### D2: i18n rule is always deployed (not conditional)
Considered: only loading i18n-conventions.md when next-intl/react-i18next is detected in deps. Decided against — the rule is small, the patterns are universally good practice (translation keys, sidecar resilience), and conditional rule loading adds complexity. If the project doesn't use i18n, the agent will simply not encounter situations where the rule applies.

### D3: Template code changes are additive
The playwright.config.ts and global-setup.ts templates already exist. Changes add dotenv loading, env vars, and cache cleanup — all additive. Existing functionality is preserved.

### D4: Engine fixes are independent of template changes
The 3 engine fixes (sidecar merge, redispatch branch, issue timeout) are in `lib/set_orch/` and can be implemented/tested independently of the template rule changes. They address different root causes (framework behavior vs agent guidance).

### D5: Merger sidecar strategy — try/catch in request.ts, not auto-merge content
Considered: having the merger auto-merge sidecar JSON content into base files during archive. This is complex (deep-merge JSON, handle conflicts) and fragile. Instead: the rule instructs agents to always wrap sidecar imports in try/catch from the start. The merger's archive step already deletes sidecar files — the app just needs to survive the deletion.

### D6: Redispatch branch preservation — cherry-pick, not rebase
When redispatching, the new worktree branches from the change's existing branch tip. If that branch has diverged from main, the first thing the new agent does is merge main into it (existing behavior). This is simpler and safer than rebasing.

## File Map

### Template Rules (modules/web/set_project_web/templates/nextjs/rules/)
| File | Action | Sections Added |
|------|--------|----------------|
| testing-conventions.md | Modify | Post-merge cache cleanup, dotenv in global-setup, Playwright config hardening, strict selectors, data-testid mandatory, test user seeding, NODE_ENV guards, hydration race handling |
| auth-conventions.md | Modify | No secret fallbacks, layout-level JWT validation, auto-login after registration |
| auth-middleware.md (framework-rules/web/) | Modify | Exclude all /api routes from middleware |
| security.md | Modify | No fallback values for secret env vars |
| functional-conventions.md | Modify | ASCII-safe slugs, filter delimiter encoding, render consistency |
| ui-conventions.md | Modify | No placeholder content, navigation link integrity |
| i18n-conventions.md | **New** | Translation keys, sidecar resilience, Link-based switcher, dynamic route format, E2E locale, middleware API exclusion |

### Template Code (modules/web/set_project_web/templates/nextjs/)
| File | Action | Changes |
|------|--------|---------|
| tests/e2e/global-setup.ts | Modify | Add dotenv/config import, add .next cache cleanup |
| playwright.config.ts (if exists as template) | Modify or document in rule | dotenv, env spread, NEXTAUTH vars, locale, retry |

### Engine Code (lib/set_orch/)
| File | Action | Changes |
|------|--------|---------|
| merger.py or engine.py | Modify | Sidecar import resilience check during archive |
| dispatcher.py | Modify | Redispatch from change branch instead of main |
| dispatcher.py | Modify | Issue ownership timeout in resume_stalled_changes |
