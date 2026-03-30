# Proposal: post-run-template-hardening

## Why

After every orchestration run on consumer projects, a significant number of manual fix commits are needed — 18 fixes in one run, 16 in another. Analysis of 34 post-merge fix commits across two independent consumer projects reveals that **~80% are preventable** with better template rules and template code. The fixes cluster into 5 categories: E2E test instability (14 fixes), i18n/locale handling (6), auth/security gaps (4), UI/UX incompleteness (3), and framework engine issues (5). Most share a common root cause: the agent lacks explicit guidance in template rules for patterns that are obvious to experienced developers but not to an AI agent working from specs alone.

## What Changes

### Template Rule Updates (existing files)

- **testing-conventions.md** — Add sections: post-merge .next cache cleanup in global-setup, dotenv loading in global-setup and playwright.config, Playwright locale/env/retry configuration, strict mode heading selectors, data-testid MUST (not SHOULD), test user seeding requirement, NODE_ENV guards for test endpoints, networkidle for hydration-dependent interactions
- **auth-conventions.md** — Add sections: no hardcoded secret fallbacks, layout-level JWT/session validation (not just middleware), auto-login after registration
- **auth-middleware.md** — Strengthen: middleware matcher must exclude ALL /api routes, not just auth
- **security.md** — Add: never use fallback values for secret env vars
- **functional-conventions.md** — Add: slug generation must strip accented characters, URL filter encoding (pipe not comma when values contain commas), saved/cached views must use same components as live views
- **ui-conventions.md** — Add: no placeholder divs/content — use real components with real data, every navigation link must point to an existing route

### New Template Rule

- **i18n-conventions.md** — Comprehensive i18n rule for projects using next-intl or react-i18next: all user-facing strings must use translation keys, unit/measurement translation, sidecar imports with try/catch, language switcher via Link not hydration-dependent button, next-intl dynamic route object format `{pathname, params}`, E2E tests must set browser locale

### Template Code Updates

- **playwright.config.ts** template — Add dotenv loading, process.env spread to webServer.env, NEXTAUTH_SECRET/NEXTAUTH_URL in env, locale setting, retry=1 for dev flakes
- **global-setup.ts** template — Add dotenv loading, .next cache cleanup before test run

### Framework Engine Fixes

- **Merger sidecar handling** — After archiving a change that added i18n sidecar files, the merger must ensure remaining code handles missing sidecars (or merge sidecar content into base files during archive)
- **Dispatcher redispatch branch preservation** — When redispatching a stalled/dead agent, branch from the change's existing branch (preserving committed artifacts) instead of fresh from main
- **Issue ownership stall timeout** — Add configurable timeout (default 30min) so issue pipeline ownership doesn't block stall recovery indefinitely

## Capabilities

### New Capabilities
- `i18n-conventions`: Template rule for i18n-aware consumer projects — translation keys, sidecar resilience, locale-aware E2E tests
- `stall-recovery-timeout`: Issue pipeline ownership timeout for stall recovery

### Modified Capabilities
- `testing-conventions`: E2E stability patterns — cache cleanup, dotenv, selectors, retry, locale, test users
- `auth-conventions`: Layout-level validation, no secret fallbacks, post-registration auto-login
- `auth-middleware`: API route exclusion from i18n/auth middleware
- `security-patterns`: Secret env var handling
- `functional-conventions`: Slug encoding, filter delimiters, rendering consistency
- `ui-conventions`: No placeholder content, navigation integrity
- `playwright-template`: Hardened config template with env, locale, retry
- `global-setup-template`: Dotenv + cache cleanup
- `merger-sidecar-handling`: Resilient sidecar file management during archive
- `dispatcher-redispatch`: Branch preservation on agent redispatch

## Impact

- **Template rules** (8 files modified, 1 new): Pure documentation — zero code risk, immediately deployable via `set-project init`
- **Template code** (2 files): playwright.config.ts and global-setup.ts templates — low risk, only affects new projects/reinit
- **Engine code** (3 areas): merger, dispatcher, engine — medium risk, needs E2E validation
- **Dependencies**: None
