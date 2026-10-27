## Why

Three classes of recurring agent mistakes — raw `<img>` tags, hardcoded JSX strings instead of i18n calls, and missing server-side `await auth()` checks on admin routes — are caught only by the LLM review gate today, costing roughly 5 minutes of LLM review time per change in retry cycles. Run-level evidence: across four merged changes the same three findings reappeared even though earlier findings were injected into the next change's `input.md` via the existing learnings mechanism, indicating the agent does not consistently honor learnings when they land deep in the prompt. Shifting these checks left to ESLint, a pre-commit hook, and a re-positioned learnings section eliminates the LLM round-trips for issues that have a deterministic answer.

## What Changes

- **NEW** ESLint configuration deployed by the web project type with `@next/next/no-img-element: error` and an i18n hardcoded-string rule scoped to locale-routed pages, so build/lint surfaces these errors before the verify gate fires.
- **NEW** `scripts/check-i18n-completeness.ts` deployed by the web project type, re-runnable via `pnpm check:i18n`, that asserts every namespace referenced by `useTranslations()` exists in every configured locale and every key is non-empty.
- **NEW** Husky pre-commit hook deployed by the web project type that runs `pnpm lint --max-warnings=0` and `pnpm check:i18n` against staged files, blocking the agent from committing locale-route code that would fail the same checks during integration.
- **NEW** explicit `/admin/**` server-side auth-check pattern documented in the web project type's `auth-conventions.md` rule deployment, mandating `const session = await auth(); if (!session?.user || session.user.role !== "ADMIN") redirect(...)` at the top of every admin `page.tsx` and `layout.tsx`. Middleware-only enforcement is rejected because of the documented Next.js Router Cache bypass risk.
- **MODIFIED** `review-learnings` — the learnings section emitted into `input.md` moves to the top of the file (before scope/requirements), is rendered as a MUST/MUST NOT bullet list with concrete examples per finding type, and is surrounded by an unmistakable header so the agent does not skip it.
- **NEW** capability `web-build-time-quality-gates` documenting the prevention pipeline as a whole (lint config, i18n script, pre-commit hook, admin-auth pattern) so future web project type extensions consume it as a single contract.

## Capabilities

### New Capabilities

- `web-build-time-quality-gates`: deployed lint, i18n-completeness, and pre-commit prevention pipeline for the web project type. Defines the rule severities ESLint enforces, the contract of the i18n completeness script, and the pre-commit hook composition. Includes the explicit admin-route server-side auth pattern.

### Modified Capabilities

- `review-learnings`: prior-change findings render at the top of `input.md` as a MUST/MUST NOT block instead of appended at the end, so the agent honors them before drafting code.

## Impact

- **Web project type (`modules/web/set_project_web/templates/nextjs/`)**: new `eslint.config.mjs`, new `scripts/check-i18n-completeness.ts`, new `.husky/pre-commit`, additions to `package.json` (`eslint`, `@next/eslint-plugin-next`, `eslint-plugin-i18next`, `husky`, `lint-staged`, scripts: `lint`, `check:i18n`, `prepare`).
- **Web project type rules (`modules/web/set_project_web/templates/nextjs/rules/auth-conventions.md`)**: new section with the mandatory admin-route auth-check pattern and example.
- **Engine (`lib/set_orch/dispatcher.py::_build_review_learnings`)**: re-formats and re-positions the learnings output. No change to upstream learnings collection or filtering. Output remains a single string assembled into `input.md`; only the section template and call site (top vs. bottom) change.
- **Tests**: new unit test for `check-i18n-completeness.ts` (passes/fails fixtures); new ESLint fixture asserting the config catches `<img>` and a hardcoded string in a locale-routed page; regression test on `_build_review_learnings()` output position and MUST/MUST NOT formatting.
- **No layer crossing**: web-specific deliverables stay in `modules/web/`. The `_build_review_learnings()` re-format is project-type agnostic and remains in Layer 1, in line with the modular architecture rule.
- **Backwards compatibility**: existing consumer projects without the new files keep working — `set-project init` re-deploys to add them. The learnings re-format is additive (same content, different position/format).
- **Deployment**: shipped via `set-project init`. Mid-run consumer projects pick up the new template by re-running `set-project init <name>`; in-flight worktrees keep their old config until next dispatch.
