# E2E Infrastructure — Tier 1 Hardening

This page documents the Tier 1 shipment of the `fix-e2e-infra-systematic`
OpenSpec change. It is the short, practical summary; for the full design
context see `openspec/changes/fix-e2e-infra-systematic/`.

## What landed in Tier 1

| # | Area | Outcome |
|---|---|---|
| 1 | i18n baseline | `messages/{hu,en}.json` ship with `home.*`, `nav.*`, `footer.*`, `common.*` mirrored; `i18n_check` gate runs pre-e2e (~1–2s). Missing keys fail fast instead of cascading into Playwright hydration errors. |
| 2 | Playwright env alignment | `playwright.config.ts` honors `PW_TIMEOUT`, `PW_PORT`, `PW_FRESH_SERVER`. The gate runner passes `PW_TIMEOUT=e2e_timeout` so Playwright's `globalTimeout` matches the outer gate budget. |
| 3 | Stale build + zombie guard | `global-setup.ts` kills any process bound to `PW_PORT` before webServer starts, and maintains a `.next/BUILD_COMMIT` marker. Stale `.next/` is invalidated only when HEAD changed (previous behavior always wiped it — ~30s saved on unchanged worktrees). |
| 4 | Prisma schema-hash cache | `global-setup.ts` skips `npx prisma db push --force-reset` when `prisma/schema.prisma` is byte-identical to the last run (SHA-256 cached in `.set/seed-schema-hash`). Opt-out: `PRISMA_FORCE_RESEED=1`. |
| 5 | Deterministic port allocation | `change.extras.assigned_e2e_port` is persisted at dispatch time using `hash(change.name) % 1000 + 3100`. The e2e gate reads from extras first and falls back to `profile.worktree_port` for legacy changes. |
| 6 | Convention docs | New `rules/web-conventions.md`: bans `navigator.sendBeacon` for cart/order mutations, documents upsert unique-key pattern, testid naming, admin `storageState` via `lib/auth/storage-state.ts` helper, REQ-id comment convention on e2e specs. |
| 7 | Config drift warning | Engine emits `CONFIG_DRIFT` (event + WARNING) when `set/orchestration/config.yaml` is newer than the parsed `directives.json` — surfaces the "I edited config.yaml but nothing changed" footgun. |

## Consuming the hardened defaults

**New projects** — `set-project init --project-type web --template nextjs`
deploys the hardened templates automatically.

**Existing projects** — re-run `set-project init --name <project>` to pull
the updated template files. The project's `.claude/` rules, `messages/`
baseline, `scripts/check-i18n-completeness.ts`, `tests/e2e/global-setup.ts`,
and `src/lib/auth/storage-state.ts` will be synchronized. `playwright.config.ts`
is in `manifest.yaml` as `protected: true` — re-init will NOT overwrite a
consumer's customized config. If you want the new env-driven config, copy
the diff manually from `modules/web/set_project_web/templates/nextjs/playwright.config.ts`.

## What did NOT change

- Gate ordering (build → test_files → test → lint → e2e → spec_verify → review)
  is unchanged. Full e2e still runs before spec_verify / review.
- Retry flow is unchanged. Single `verify_retry_count`, full-pipeline re-run on fail.
- `verdict.json` schema unchanged (findings structure lands in Tier 2).
- Existing running projects see no behavior change — only newly-initialized /
  re-initialized projects pick up the template changes.

## Rollout & rollback

- The `i18n_check` gate defaults to non-blocking (`warn`) on first rollout.
  Flip to blocking via `set/orchestration/config.yaml`:
  ```yaml
  gate_overrides:
    i18n_check: run  # or: skip to disable entirely
  ```
- To roll back an individual template change in a consumer project, edit the
  file in place — `set-project init` will not overwrite protected paths or
  files you've diverged.

## Gate flow — updated order

```
build → test_files → test → lint → i18n_check → e2e → spec_verify → review
                                   ^^^^^^^^^^ new (warn)
```

## Where Tier 2 picks up

Tier 2 is scheduled after Tier 1 proves out on a fresh orchestrated run.
It adds:

- Structured `findings` blocks in `verdict.json` so reviewer FIX instructions
  survive across retries.
- `CROSS_CHANGE_REGRESSION` event at the integration gate when a failing test
  belongs to an already-merged change (with prescriptive `retry_context` that
  tells the agent "do NOT modify that other change's code").

See `openspec/changes/fix-e2e-infra-systematic/` for the full task list and
design notes.
