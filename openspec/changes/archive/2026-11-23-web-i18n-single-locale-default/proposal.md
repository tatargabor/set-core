> **Superseded 2026-11-23 — closed without implementing the open tasks.** This change extends the
> orchestration engine (E2E gates, decompose/planner, fix-iss, the web project template and the
> run dashboards), which `fleet-era-consolidation` retires (stages 4-5: `retire-orchestration-cli`,
> `retire-orchestration-engine`). Archived with `--skip-specs` semantics: no delta reached
> `openspec/specs/`. Tasks ticked here were shipped; unticked ones were not.

## Why

The web template currently bootstraps every new project with the full multi-locale i18n pipeline (next-intl, two-language seed files, completeness gate, sidecar pattern, parity rule, serialization directive, ~200 lines of i18n agent rules). For multi-locale shops this is necessary; for single-locale projects (info sites, landing pages, designer portfolios, internal tools, MVP webshops) it is pure overhead — and worse, it actively misleads agents into generating cross-locale scaffolding that nobody asked for.

Industry consensus is unambiguous: single-locale apps ship without i18n libraries (cf. Vercel/shadcn/Tailwind UI starters, next-intl's own README, react-i18next FAQ). They still avoid hardcoded strings — by routing UI text through a centralized typed copy module — but they pay none of the locale-machinery cost. The framework today gives consumer projects no way to express that choice; every web project is opted into the most expensive mode.

This change introduces an explicit `i18n.mode` axis on the web template, with single-locale being the default for new projects, and preserves the entire current pipeline for projects that opt into multi.

## What Changes

- **NEW** `--i18n single|multi` flag on `set-project init` (web template). Default: `single`.
- **NEW** manifest module `i18n-multi` in `modules/web/set_project_web/templates/nextjs/manifest.yaml` containing: `messages/en.json`, `messages/hu.json`, `scripts/check-i18n-completeness.ts`, `rules/i18n-conventions.md`. These move out of `core:` into the optional module.
- **NEW** rule file `modules/web/set_project_web/templates/nextjs/rules/copy-module-conventions.md` (~40 lines) documenting the centralized typed-copy pattern (`src/copy/index.ts` + `src/copy/locale.ts`) for single-mode projects.
- **NEW** behavior in `set-project init`: when mode is `single`, write `set/plugins/project-type.yaml` with an overlay that disables i18n-specific verification rules and orchestration directives via the existing `ProjectTypeResolver` overlay mechanism.
- `lib/set_orch/design_manifest.py` "i18n leakage" hygiene check becomes mode-aware (in single mode, the equivalent check tests "is this string in `src/copy/`?", not "is it in `messages/*.json`?").
- `package.json` template keeps `next-intl` and `eslint-plugin-i18next` deps even in single mode (cosmetic — unused but harmless; cleaning them up is deferred to a v2 to keep this change minimal).
- **BREAKING for runner scripts that produce multi-locale apps**: any `tests/e2e/runners/run-*.sh` that bootstraps a multi-locale fixture (currently the craftbrew runner and any future webshop scaffold) MUST pass `--i18n multi` explicitly. Default flip means single-locale runners (designer portfolios, info-site fixtures) get the lighter setup automatically.
- **Backwards-compatible for existing projects**: any project without `i18n.mode` in its `set/plugins/project-type.yaml` gets the existing rule + directive set unchanged. The overlay mechanism is purely additive opt-out, never opt-in.

## Capabilities

### New Capabilities

- `web-template-i18n-modes`: the contract for the `i18n.mode` axis on the web template — what each mode seeds, what each mode's overlay disables, the default-mode policy at `set-project init`, and the mode-detection rules at runtime.

### Modified Capabilities

- `i18n-conventions`: scope all existing requirements (`REQ-I18N-TRANSLATION-KEYS`, `REQ-I18N-SIDECAR-RESILIENCE`, `REQ-I18N-LANGUAGE-SWITCHER`, `REQ-I18N-DYNAMIC-ROUTES`, `REQ-I18N-E2E-LOCALE`, `REQ-I18N-MIDDLEWARE`) to projects in multi-mode. Add a single new requirement governing single-mode (translation discipline through the typed copy module instead of `t('key')`).
- `cross-cutting-file-strategy`: scope the i18n sidecar requirements (sidecar pattern for parallel agents, post-merge i18n combination, namespace assignment) to multi-mode. The cross-cutting-file ownership requirements for `layout.tsx`, `middleware.ts`, etc. remain mode-agnostic.
- `design-source-hygiene`: scope rule #2 ("Hardcoded UI strings — i18n leakage") and rule #9 ("Locale-prefix inconsistency") so they fire against the appropriate target per mode (multi-mode: `messages/*.json` membership; single-mode: `src/copy/` membership).

## Impact

**Code (Layer 1, core):**
- `lib/set_project_base/cli.py` — new `--i18n` argparse arg (~15 lines)
- `lib/set_orch/profile_deploy.py` — overlay-emission step in `deploy_templates()` (~30 lines)
- `lib/set_orch/design_manifest.py` — mode-aware "i18n leakage" check (~10 lines)

**Code (Layer 2, web module):**
- `modules/web/set_project_web/templates/nextjs/manifest.yaml` — re-arrangement (move 4 entries from `core:` to a new `modules.i18n-multi:` block)
- `modules/web/set_project_web/templates/nextjs/rules/copy-module-conventions.md` — NEW (~40 lines)
- `modules/web/set_project_web/templates/nextjs/src/copy/index.ts` — NEW seed file (~20 lines, single mode only — placed in `core:` alongside other src files; multi mode keeps using `messages/`)
- `modules/web/set_project_web/templates/nextjs/src/copy/locale.ts` — NEW seed file (~5 lines, single mode primary-locale constant)

**Tests:**
- `tests/unit/test_web_template_i18n_modes.py` — NEW (~80 lines): asserts what is seeded / overlay-written per mode, verifies dispatcher sidecar instruction emission per mode, verifies design hygiene mode-awareness.
- `modules/web/tests/test_i18n_check_gate.py`, `modules/web/tests/test_i18n_checker_scope.py` — minor updates to assert the gate's existing skip path is still hit in single mode (no behavior change, just regression coverage).

**Runner scripts (operations, not framework):**
- `tests/e2e/runners/run-craftbrew.sh` — add explicit `--i18n multi` to the `set-project init` invocation. Document this in `tests/e2e/README.md`.
- Any future runner script for a multi-locale fixture must pass `--i18n multi` explicitly.

**Specs:**
- New: `openspec/specs/web-template-i18n-modes/spec.md`
- Modified: `openspec/specs/i18n-conventions/spec.md`, `openspec/specs/cross-cutting-file-strategy/spec.md`, `openspec/specs/design-source-hygiene/spec.md`

**Dependencies:**
- No new Python or JS dependencies. The `next-intl` dep stays in `package.json` even in single mode (cosmetic-only cost, deferred cleanup).

**Out of scope (explicit non-goals for this change):**
- Codemod for migrating an existing single-mode project to multi-mode (or vice versa). Mode is set at `set-project init` time; mid-project flips are manual.
- Stripping `next-intl` and `eslint-plugin-i18next` from `package.json` in single mode. Defer to a follow-up.
- A `none` mode where hardcoded strings are allowed. Not designed in this change.
- Auto-detecting mode from the spec text. Mode is explicit at init time only.
- Changing the runtime gate `i18n_check` (it already gracefully skips when no `useTranslations` usage is detected — no change needed).
- Changing the ESLint `no-literal-string` configuration (already scoped to `src/app/[locale]/**` paths, which don't exist in single mode — no change needed).
