# Tasks: web-template-test-configs

## 1. Add playwright.config.ts template
- [x] 1.1 Create `modules/web/set_project_web/templates/nextjs/playwright.config.ts` with PW_PORT env var, chromium project, screenshot on, webServer with next dev
- [x] 1.2 Add `playwright.config.ts` to `manifest.yaml` core list

## 2. Replace jest with vitest
- [x] 2.1 Create `modules/web/set_project_web/templates/nextjs/vitest.config.ts` excluding tests/e2e/**
- [x] 2.2 Remove `modules/web/set_project_web/templates/nextjs/jest.config.ts`
- [x] 2.3 Update `manifest.yaml`: replace `jest.config.ts` with `vitest.config.ts`

## 3. Remove tailwind.config.ts
- [x] 3.1 Remove `modules/web/set_project_web/templates/nextjs/tailwind.config.ts`
- [x] 3.2 Remove `tailwind.config.ts` from `manifest.yaml`

## 4. Discord config
- [x] 4.1 N/A — config.yaml is user-authored, not template-generated. E2E runners already include discord section. No change needed.

## 5. Verify
- [ ] 5.1 Run `set-project init` on a test dir and verify correct files deployed

## Acceptance Criteria
- [ ] `playwright.config.ts` deployed with PW_PORT env var
- [ ] `vitest.config.ts` deployed instead of jest.config.ts
- [ ] `tailwind.config.ts` NOT deployed
- [ ] Discord section present in orchestration config
