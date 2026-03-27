# Tasks: docs-screenshot-pipeline

## 1. Web dashboard screenshots — expand coverage

- [ ] 1.1 Move output dir from `docs/images/web-dashboard/` to `docs/images/auto/web/`, update existing refs [REQ: web-dashboard-screenshot-capture]
- [ ] 1.2 Add Memory page screenshot (`/p/:name/memory`) [REQ: web-dashboard-screenshot-capture]
- [ ] 1.3 Add Settings page screenshot (`/p/:name/settings`) [REQ: web-dashboard-screenshot-capture]
- [ ] 1.4 Add Issues page screenshots — global (`/issues`) and project-level (`/p/:name/issues`) [REQ: web-dashboard-screenshot-capture]
- [ ] 1.5 Add Worktrees page screenshot (`/p/:name/orch/worktrees`) [REQ: web-dashboard-screenshot-capture]
- [ ] 1.6 Add Agent chat tab screenshot (`?tab=agent`) and Sentinel tab (`?tab=sentinel`) [REQ: web-dashboard-screenshot-capture]
- [ ] 1.7 Set viewport to 1280x720 in screenshot spec [REQ: web-dashboard-screenshot-capture]
- [ ] 1.8 Auto-detect latest "done" project from API when E2E_PROJECT not specified [REQ: web-dashboard-screenshot-capture]

## 2. CLI output screenshots (ansi2html + Playwright)

- [ ] 2.1 Create `scripts/capture-cli-screenshots.py` — reads ANSI output, renders via ansi2html + Playwright to PNG [REQ: cli-output-screenshot-capture]
- [ ] 2.2 Add CLI commands to capture: `set-list`, `openspec status`, `set-status`, `set-memory stats`, `set-audit scan` [REQ: cli-output-screenshot-capture]
- [ ] 2.3 Style terminal output with dark theme (Catppuccin Mocha), window decorations, monospace font [REQ: cli-output-screenshot-capture]
- [ ] 2.4 Save CLI screenshots to `docs/images/auto/cli/` [REQ: cli-output-screenshot-capture]
- [ ] 2.5 Document dependency: `pip install ansi2html` in script header and Makefile [REQ: cli-output-screenshot-capture]

## 3. Consumer app screenshots (extend existing capture-screenshots.ts)

- [ ] 3.1 Add route auto-discovery to `capture-screenshots.ts` — scan `src/app/` for `page.tsx` files, build route list [REQ: consumer-app-screenshot-capture]
- [ ] 3.2 Keep hardcoded fallback routes for known scaffolds (minishop, micro-web) when auto-discovery fails [REQ: consumer-app-screenshot-capture]
- [ ] 3.3 Accept `--project-dir` arg or auto-detect latest "done" E2E run from `~/.local/share/set-core/e2e-runs/` [REQ: consumer-app-screenshot-capture]
- [ ] 3.4 Handle Prisma setup (generate + db push + seed) before starting dev server [REQ: consumer-app-screenshot-capture]
- [ ] 3.5 Save app screenshots to `docs/images/auto/app/` [REQ: consumer-app-screenshot-capture]
- [ ] 3.6 Add `pnpm screenshot:app` script to `web/package.json` [REQ: consumer-app-screenshot-capture]

## 4. Unified entry point + docs

- [ ] 4.1 Create root `Makefile` with `screenshots` target calling web, cli, app in sequence [REQ: unified-screenshot-entry-point]
- [ ] 4.2 Update `docs/wt-web.md` — move image paths to `images/auto/web/`, add new page sections [REQ: docs-reference-auto-generated-images]
- [ ] 4.3 Update `docs/developer-memory.md` — reference auto-generated memory page screenshot [REQ: docs-reference-auto-generated-images]
- [ ] 4.4 Update `docs/cli-reference.md` — add CLI output screenshots [REQ: docs-reference-auto-generated-images]
- [ ] 4.5 Update `docs/worktrees.md` — add worktree page screenshot [REQ: docs-reference-auto-generated-images]
- [ ] 4.6 Update `docs/sentinel.md` — add sentinel/agent chat screenshot [REQ: docs-reference-auto-generated-images]
- [ ] 4.7 Write `docs/screenshot-pipeline.md` — full docs: dependencies, usage, what each command generates, how to add new screenshots [REQ: unified-screenshot-entry-point]
- [ ] 4.8 Move existing `docs/images/web-dashboard/` to `docs/images/auto/web/`, delete old dir [REQ: docs-reference-auto-generated-images]

## 5. Validation

- [ ] 5.1 Run `make screenshots` end-to-end — verify all expected files generated [REQ: unified-screenshot-entry-point]
- [ ] 5.2 Verify `pnpm test:e2e` still passes (screenshots don't interfere) [REQ: web-dashboard-screenshot-capture]
- [ ] 5.3 Verify docs render correctly with new image paths [REQ: docs-reference-auto-generated-images]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN `pnpm screenshot:docs` run with E2E_PROJECT THEN PNGs in `docs/images/auto/web/` for each visible tab [REQ: web-dashboard-screenshot-capture, scenario: all-dashboard-tabs-captured]
- [ ] AC-2: WHEN `pnpm screenshot:docs` run THEN secondary pages (Memory, Settings, Issues, Worktrees, Agent) also captured [REQ: web-dashboard-screenshot-capture, scenario: secondary-pages-captured]
- [ ] AC-3: WHEN conditional tab has no data THEN screenshot skipped without failure [REQ: web-dashboard-screenshot-capture, scenario: optional-tabs-gracefully-skipped]
- [ ] AC-4: WHEN `scripts/capture-cli-screenshots.py` run THEN CLI output saved as PNG in `docs/images/auto/cli/` [REQ: cli-output-screenshot-capture, scenario: cli-commands-rendered-as-images]
- [ ] AC-5: WHEN CLI output has ANSI colors THEN image preserves colors [REQ: cli-output-screenshot-capture, scenario: terminal-styling-preserved]
- [ ] AC-6: WHEN consumer project has dev server THEN app pages captured to `docs/images/auto/app/` [REQ: consumer-app-screenshot-capture, scenario: app-pages-captured-via-playwright]
- [ ] AC-7: WHEN no dev server THEN app screenshots skipped with warning [REQ: consumer-app-screenshot-capture, scenario: app-screenshot-skipped-if-no-server]
- [ ] AC-8: WHEN `make screenshots` run THEN all three categories regenerated [REQ: unified-screenshot-entry-point, scenario: top-level-command]
- [ ] AC-9: WHEN no E2E_PROJECT specified THEN uses latest "done" project automatically [REQ: web-dashboard-screenshot-capture, scenario: manager-page-with-multiple-projects]
