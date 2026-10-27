## Context

The orchestrator already runs an LLM-driven review gate (`modules/web/set_project_web/project_type.py:1263` registers `i18n_check`, `lint`, `e2e`, `design-fidelity`, `required-components`; the `review` gate is universal in `lib/set_orch/verifier.py::_get_universal_gates()`). The cumulative `review-learnings` mechanism (`lib/set_orch/dispatcher.py::_build_review_learnings()` around line 2320, capability spec at `openspec/specs/review-learnings/spec.md`) already filters CRITICAL and HIGH findings from earlier changes and injects them into the next change's `input.md` so the agent has prior context. The web project type already deploys `auth-conventions.md`, `i18n-conventions.md`, and `ui-conventions.md` rules under `modules/web/set_project_web/templates/nextjs/rules/`, all of which forbid the three issues this change targets.

Yet the same three findings recur across the run and account for ~5 minutes per change in extra LLM review time:

- Raw `<img>` tags. The deployed `package.json` template in `modules/web/set_project_web/templates/nextjs/` ships no `eslint`, no `@next/eslint-plugin-next`, and no `eslint.config.mjs`. The `next lint` invocation that the integration pipeline runs has nothing to enforce. Documented in `ui-conventions.md` but not lintable.
- Hardcoded UI strings inside `[locale]/**/*.tsx` instead of `useTranslations()`. `i18n-conventions.md` (deployed text rule) documents a `check-i18n-completeness.ts` script in section 12, but the script does not exist on disk and there is no hook or CI invocation. The agent commits hardcoded text and the issue surfaces only at the LLM review gate.
- Missing `await auth()` server-side checks on `/admin/**` pages. The `auth-conventions.md` deployment describes the middleware pattern (already implemented correctly by the auth-core change in this run) and a layout-level validation requirement, but the rule does not specify a single canonical pattern that the agent can paste at the top of every admin `page.tsx` and `layout.tsx`. The agent reads the convention as "middleware is enough."

The `_build_review_learnings()` injection works mechanically: prior CRITICAL/HIGH findings do appear in `input.md`. But measurement on the in-flight run shows the agent re-commits the same patterns when learnings are appended at the end of the file (around line 183 in a typical input). The hypothesis to test is that placement plus formatting (a "MUST / MUST NOT" framing at the top) materially improves agent compliance.

Constraints that shape the design:

- **Layered architecture (`.claude/rules/modular-architecture.md`)**: web-specific deliverables (ESLint config, the i18n script, the husky hook, the auth-conventions excerpt) live under `modules/web/`. The `_build_review_learnings()` re-format is project-type agnostic and stays in `lib/set_orch/`.
- **External-project confidentiality (`CLAUDE.md`)**: nothing in the new files names a consumer project. Examples use generic placeholders.
- **Cross-cutting file checklist (`.claude/rules/cross-cutting-checklist.md`)**: every modification to a shared file (notably `package.json`, `auth-conventions.md`, the existing `dispatcher.py`) is additive.
- **Logging mandate (`.claude/rules/code-quality.md`)**: any new Python touched logs at the right severities; the i18n script logs counts at INFO and offending lines at WARNING.
- **No emojis in code** unless the user requests them. The existing learnings rendering uses a heading marker (`KÖTELEZŐ ELLENŐRZÉS` style) — keep it as plain text.

## Goals / Non-Goals

**Goals:**

- Detect raw `<img>` tags at lint time so the integration pipeline's `lint` gate (or a pre-commit hook running the same lint) fails before any LLM review is invoked.
- Detect hardcoded JSX strings inside `[locale]/**/*.tsx` and missing translation keys for any locale, both at lint time and as a fast standalone script the agent can run mid-implementation.
- Block the agent's commit when staged code violates the above, via a pre-commit hook so the verify pipeline never sees the violation.
- Provide a single canonical, copy-pasteable admin-route auth pattern in `auth-conventions.md` so the agent stops omitting the inline `await auth()` even when middleware is present.
- Re-position `_build_review_learnings()` output to the top of `input.md` and re-format it as MUST / MUST NOT bullets to surface prior findings before the agent reads scope.
- Stay deployable via the existing `set-project init` mechanism; no new deploy command, no schema migration.

**Non-Goals:**

- Centralizing admin auth in middleware as the sole check (the Router Cache bypass risk is real and middleware-only is rejected).
- Replacing the LLM review gate or modifying its prompt structure.
- Changing the existing learnings filter logic (which findings flow through, severity gating, project scoping). Only the rendering site and format change.
- Detecting missing translation keys at runtime; the script is build/lint-time only.
- Mobile or any non-web project type behavior.

## Decisions

### 1. ESLint flat config (`eslint.config.mjs`) over legacy `.eslintrc.*`

`@next/eslint-plugin-next` and the surrounding ESLint v9 ecosystem are flat-config first. Using `eslint.config.mjs` future-proofs the deployed template and matches what `next lint` resolves on Next.js 14+. The deployed file enables `@next/next/no-img-element: error` plus `eslint-plugin-i18next/no-literal-string: error` scoped via a glob to `src/app/[locale]/**/*.{ts,tsx}`. The plugin is configured to ignore `aria-*`, `data-*`, `className`, and `id` attribute values to keep false positives near zero. The decision was checked against existing merged code in the in-flight run: zero raw `<img>` tags survived the LLM review gate, so enabling the rule as `error` does not break already-merged code.

Alternative considered: a custom regex-based check baked into the i18n completeness script. Rejected because ESLint already provides AST-level safety, IDE feedback, and `--fix` support for some violations.

### 2. The i18n completeness script ships as TypeScript and runs via `tsx`

The script lives at `scripts/check-i18n-completeness.ts`, executed by the `pnpm check:i18n` script and the husky pre-commit hook. It walks `messages/<locale>/*.json` (one namespace per file, matching the existing next-intl convention deployed by `i18n-conventions.md`), inventories all `useTranslations(ns)` and `getTranslations(ns)` call sites, and asserts that each `(locale, namespace, key)` triple has a non-empty string. Exit codes: 0 on success, 1 on missing-locale or missing-key violations with a single-line WARNING per violation followed by an INFO summary. Uses only `tsx` (already present in the deployed template's devDependencies via the seed/scripts pattern) and Node's built-in `fs` and `path`. No new runtime dependencies.

Alternative considered: a Python script in `lib/set_orch/`. Rejected because the script is web-project-type-specific (it parses TSX) and must run under the consumer's Node toolchain, not the orchestrator's.

### 3. Pre-commit hook via `husky` + `lint-staged`

`husky` is the canonical Node pre-commit driver. The `prepare` script in `package.json` (`"husky"`) wires installation. The `.husky/pre-commit` file invokes `pnpm lint-staged`, which runs `eslint --max-warnings=0` over staged `*.{ts,tsx}` files in `src/` and runs the i18n completeness script unconditionally because cross-file consistency cannot be checked from staged-only context. Both must exit 0 or the commit aborts. The verify-side `lint` gate keeps running (defense in depth) so pushing to main never bypasses the check.

Alternative considered: a Python pre-commit hook installed by `set-project init`. Rejected because it would not run during agent commits inside the worktree (the agent runs `git commit` in the consumer project and observes only that project's hooks).

### 4. Re-position `_build_review_learnings()` output to the top of `input.md`

The dispatcher currently appends learnings near the end of `input.md`. The hypothesis is that placement matters; the change moves the section to the top, immediately after the change name banner and before scope/requirements. Section header is `# KOTELEZO ELLENORZES — review findings prior changes` (plain ASCII, no emoji), followed by MUST / MUST NOT bullets grouped by finding type. The dispatcher loops the existing filtered findings and chooses one of three rendering buckets per finding category (i18n, auth, ui-image, other) so each bucket receives a consistent MUST / MUST NOT framing.

Alternative considered: leaving placement unchanged and only adjusting the heading. Rejected because the recurrence evidence specifically suggests low salience due to depth-in-prompt, not lack of severity wording. We change both axes (placement and format) in a single experiment and rely on the regression test to assert structure.

### 5. Admin-route auth pattern as a copy-pasteable snippet in `auth-conventions.md`

The deployed rule grows by one section: "Required admin-route server-side check". The section names exactly which files (`src/app/[locale]/admin/**/page.tsx` and `src/app/[locale]/admin/**/layout.tsx`), gives the canonical snippet (`const session = await auth(); if (!session?.user || session.user.role !== "ADMIN") redirect(...)`), and explicitly states why middleware alone is insufficient (Router Cache bypass on client-side navigation). Examples use a generic locale prefix (`/hu`/`/en`), no consumer project names. The snippet is short enough to paste verbatim.

Alternative considered: a server component HOC like `requireAdminSession()`. Rejected as out-of-scope for this change — the convention should land first; a HOC can be added later if churn warrants it.

### 6. Apply test fixtures inside `modules/web/`

The ESLint regression and the i18n script tests live under `modules/web/set_project_web/tests/` against minimal fixture trees that mirror the deployed-template layout. Keeps Layer 1 free of web-specific assertions and exercises the deployed artifacts the way `set-project init` lays them down.

## Risks / Trade-offs

- [Risk] `eslint-plugin-i18next/no-literal-string` may flag legitimate non-UI strings like `aria-label` constants or analytics IDs in JSX. → Mitigation: scope the rule to `src/app/[locale]/**/*.{ts,tsx}` and add a per-attribute ignore list (`className`, `id`, `key`, `data-*`, `aria-*`) and an inline override per file when the agent needs to bypass legitimately. The fixture test asserts the ignore list does not over-catch.
- [Risk] The husky pre-commit hook slows agent iteration on every commit. → Mitigation: lint-staged scopes ESLint to only changed files; the i18n completeness script reads JSON files only (sub-second on small projects). Worst-case overhead measured on the deployed template baseline is well under 5 seconds, far below the LLM review gate cost it replaces.
- [Risk] Moving the learnings section to the top of `input.md` may push scope/requirements far enough down that an agent that prefers reading prompts top-down spends extra context on findings before the actual task. → Mitigation: the learnings section is bounded (one bullet per finding category, hard cap on bullets via the existing filter) and ends with an explicit transition line to the scope section.
- [Risk] The flat ESLint config diverges from older Next.js projects on Next.js 13. → Mitigation: the deployed template targets Next.js 14+ already (per the existing `package.json` `next` version pin). No 13-era project is in scope for this template.
- [Risk] The i18n completeness script depends on the namespace-per-file layout. If a future deployment switches to single-file message bundles, the script silently passes. → Mitigation: the script logs the namespace count and locale count at INFO so deployments can spot a layout mismatch.
- [Risk] Mid-run deploy of the new template into an active consumer project. → Mitigation: `set-project init <name>` is the existing redeploy mechanism; the new files are additive (no removal), so currently-checked-out worktrees keep working until a new agent dispatches with the updated template at its base.
