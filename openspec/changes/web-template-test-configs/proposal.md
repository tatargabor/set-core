# Proposal: web-template-test-configs

## Why

The web project template (`modules/web/`) deploys outdated config files during `set-project init`. Agents waste iterations creating configs that should ship with the template. Key gaps found in micro-web E2E runs:

1. **No `playwright.config.ts`** — agents create it ad-hoc, sometimes without `PW_PORT` env var, causing port collisions in parallel worktrees
2. **`jest.config.ts` instead of `vitest.config.ts`** — Next.js 14+ ecosystem moved to Vitest; agents override with Vitest anyway
3. **No `tailwind.config.ts` needed** — Tailwind CSS v4 uses CSS-based config, the v3 JS config is dead weight
4. **No Discord notification config** — orchestration config template doesn't include Discord webhook setup
5. **Integration e2e gate fails on port 3000** — parallel agents and gates all compete for the same port

## What Changes

- **Replace** `jest.config.ts` with `vitest.config.ts` in web template
- **Add** `playwright.config.ts` with `PW_PORT` env var for port isolation
- **Remove** `tailwind.config.ts` (Tailwind v4 doesn't need it)
- **Add** Discord webhook config to orchestration config template
- **Update** `manifest.yaml` to reflect new file list

## Capabilities

### New Capabilities
- `web-template-configs`: Template config files for web projects (playwright, vitest, discord)

### Modified Capabilities
(none — this is a template-only change, no runtime behavior changes)

## Impact

- `modules/web/set_project_web/templates/nextjs/` — config files and manifest
- `lib/set_orch/` — orchestration config template (discord section)
- All future `set-project init --project-type web` deployments get correct configs
