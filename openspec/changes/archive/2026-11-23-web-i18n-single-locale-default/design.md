## Context

The web template (`modules/web/set_project_web/templates/nextjs/`) is the single bootstrap surface for every consumer project of project-type `web`. Today it deploys a uniform full-i18n stack regardless of whether the consumer needs one language or many:

```
                       ┌──────────────────────────────────────────┐
                       │   Web template (nextjs/) — current       │
                       └──────────────────────────────────────────┘
                                          │
            ┌─────────────────────────────┼──────────────────────────────┐
            │                             │                              │
        SEEDS                       ENFORCES                       ORCHESTRATES
            │                             │                              │
   messages/en.json              i18n-completeness              no-parallel-i18n
   messages/hu.json                (verifier rule,                (directive,
   scripts/check-i18n…             cross-file parity)              serializes locale
   rules/i18n-conventions.md     i18n_check gate                   modifications)
                                  (verify pipeline)              consolidate-i18n
   eslint-plugin-i18next         design-fidelity                   (warn directive)
   next-intl in deps             "i18n leakage"                  i18n_namespace
                                                                   assignment
                                                                   (planner)
                                                                 sidecar instructions
                                                                   (dispatcher)
                                                                 sidecar combiner
                                                                   (post-merge)
```

Several of these components already include defensive skip-paths that single-locale projects accidentally benefit from:

- `lib/set_orch/dispatcher.py:1782` — `_detect_i18n_sidecar` skips if no `messages/` directory.
- `modules/web/set_project_web/gates.py:1989` — `i18n_check` gate skips if `useTranslations`/`getTranslations` is not used in source.
- `modules/web/set_project_web/templates/nextjs/eslint.config.mjs:47` — `i18next/no-literal-string` is path-scoped to `src/app/[locale]/**` (no `[locale]` segment → never fires).

These skip-paths are *runtime* protections; they do not prevent agents from being seeded with the i18n-conventions rule, the locale files, or the sidecar instructions. The dispatch context still tells agents to write sidecar files; the verify rule still scans `messages/*.json`; the `i18n-conventions.md` rule still consumes ~200 lines of agent prompt context.

There is also an existing extension point that we can lean on: `lib/set_orch/profile_resolver.py` already supports a `set/plugins/project-type.yaml` overlay with `disabled_rules`, `disabled_directives`, `rule_overrides`, and `custom_rules`. This overlay is consumed by `verifier.py` and the engine. Today, no consumer project's overlay is auto-populated by `set-project init` — it is created empty and operators edit it manually if they need overrides. This change leverages that overlay to express the mode choice declaratively.

## Goals / Non-Goals

**Goals:**

1. Add an explicit `i18n.mode` axis to the web template with two values: `single` and `multi`.
2. Make `single` the default mode for new web projects via `set-project init`.
3. Ensure single-mode projects do not have `messages/*.json`, do not have `i18n-conventions.md` in their rule set, do not run the `i18n-completeness` verification rule, and do not have the `no-parallel-i18n` / `consolidate-i18n` orchestration directives applied to their plan.
4. Provide an idiomatic single-mode replacement for the `t('key')` pattern: a centralized typed copy module (`src/copy/index.ts`) with a primary-locale constant (`src/copy/locale.ts`) for `Intl.*` formatting calls.
5. Keep multi-mode behavior bit-identical for projects that opt in.
6. Keep existing consumer projects (initialized before this change) in their current behavior with no migration step required.
7. Keep the change implementation small (~150 LOC + 1 rule file + 1 test file) and the architectural surface confined to the bootstrap path.

**Non-Goals:**

- Mid-project mode switching. Mode is set at `set-project init` time. Operators can manually edit the overlay later, but no codemod or automated transition is provided.
- Stripping `next-intl` and `eslint-plugin-i18next` from `package.json` in single mode. They remain as unused dependencies (~1 MB in `node_modules`, zero runtime cost). Cleaning them up is a follow-up if the cost is ever shown to matter.
- A `none` mode permitting hardcoded JSX strings without any centralized copy discipline. Single-mode still enforces "no hardcoded user-visible strings outside `src/copy/`" — just via a different mechanism than `t('key')`.
- Auto-detecting mode from the spec text. Mode is explicit at init.
- Changing runtime gates (`i18n_check`) or runtime ESLint scoping. Both already skip correctly under single-mode conditions; no further work needed.
- Refactoring `WebProjectType.get_verification_rules()` or `get_orchestration_directives()`. The methods stay as today; mode-awareness is layered on via the overlay, not by mutating the profile class.
- Changing the planner's `i18n_namespace` assignment logic. The planner already only writes `i18n_namespace` for changes that explicitly touch i18n keys; in single mode, no change touches `messages/*.json` (it does not exist), so the assignment is a no-op. Confirmed in code review of `lib/set_orch/planner.py:2075-2078` — no defensive change required.
- Changing the post-merge sidecar combiner (`lib/set_orch/merger.py:2835`, `modules/web/set_project_web/post_merge.py:30`). Both iterate `messages/*` directories that don't exist in single mode and are no-ops by construction.

## Decisions

### Decision 1 — Default mode is `single`

**Choice:** `set-project init` defaults to `--i18n single` for the web template. Multi-mode is opt-in via `--i18n multi`.

**Rationale:** Empirical observation across recent runs of various consumer projects shows the majority are single-locale (info sites, designer portfolios, internal tools, MVP shops). Defaulting to multi means the framework opts every consumer into the most expensive mode by default — a 70%+ tax-on-the-common-case. Defaulting to single inverts the cost: only consumers who actually need multi pay for it.

**Alternatives considered:**

- **Default to `multi` (preserve today's behavior).** Zero risk to existing E2E runners but defeats the purpose. Most new projects continue paying the i18n cost they don't need; nothing improves for the common case. Rejected.
- **Default to auto-detect from spec text.** Parse `docs/spec.md` for "supports English and Hungarian", "multi-language", etc. Brittle (false positives on phrases like "supports JSON and XML"), silent (operator can't see the decision was made), and would need a fallback flag anyway. Rejected for v1; could be revisited later as a planner heuristic, but not in this change.
- **No default; require explicit flag.** Forces every operator to think about it, which is honest but creates friction for the 70% case. Rejected.

**Consequence:** `tests/e2e/runners/run-craftbrew.sh` (and any other runner that bootstraps a multi-locale fixture) MUST explicitly pass `--i18n multi`. This is a required runner-script update, treated as part of this change. We document the requirement in `tests/e2e/README.md`.

### Decision 2 — Implementation via overlay write at init time, not via runtime conditionals in `WebProjectType`

**Choice:** `set-project init` writes a `set/plugins/project-type.yaml` overlay containing the `i18n.mode` value AND the corresponding `disabled_rules` / `disabled_directives` lists. The `WebProjectType` Python class itself remains unchanged.

```yaml
# set/plugins/project-type.yaml — single mode
type: web
template: nextjs
i18n:
  mode: single
  primary_locale: en        # or whatever the user passes; see Decision 7
  copy_root: src/copy
disabled_rules:
  - i18n-completeness
disabled_directives:
  - no-parallel-i18n
  - consolidate-i18n
  - cross-cutting-review     # only the i18n part — see Decision 6
```

**Rationale:** Two architectural advantages:

1. **No refactor of `WebProjectType`.** The `ProjectTypeResolver` (`profile_resolver.py:48-145`) already consumes overlay `disabled_rules` / `disabled_directives`. We get mode-awareness for free at every call site that goes through the resolver — verifier, engine, merger, dispatcher.
2. **Self-documenting overlay.** Operators reading `set/plugins/project-type.yaml` see exactly which rules are off and why. This is far more transparent than a hidden `if mode == 'single':` branch in `WebProjectType.get_verification_rules()`.

**Alternatives considered:**

- **Refactor profile methods to read mode and conditionally return rules/directives.** Requires injecting a project path or `i18n.mode` value into the constructor or the method calls. The methods are called from many places (`profile_resolver.py:64`, `dispatcher.py:3533`, `engine.py:1057`, `merger.py:3064`, `verifier.py:1796`); each call site would need updating. Higher blast radius. Rejected.
- **Add `mode` runtime conditional to each rule/gate/directive consumer.** Spreads the conditional logic across many files. Hard to audit. Rejected.
- **Two profile classes (`WebSingleProjectType`, `WebMultiProjectType`) registered as separate types.** Forces the operator to pick the type at init, but doubles the maintenance burden — every change to web behavior must update two classes. Rejected.

**Consequence:** The exact list of rules/directives to disable in each mode lives in two places: in this design doc (for review) and in the deploy code (`profile_deploy.py`'s overlay-emission step). Drift between the two is possible but small — mitigated by a unit test that asserts the overlay contents per mode.

### Decision 3 — Mode flag stored in `set/plugins/project-type.yaml`, not in `project-knowledge.yaml`

**Choice:** The `i18n.mode` key lives under the top-level `i18n:` block of `set/plugins/project-type.yaml`.

**Rationale:** `project-type.yaml` is the canonical place for **profile-resolver-time** decisions (which type, which template, which rules to disable). `project-knowledge.yaml` is for **planner/dispatcher-time** semantic context (cross-cutting files, route patterns, framework conventions). Mode is a profile-resolution-level decision: it determines which rules and directives load. Storing it in `project-type.yaml` puts it next to the related overlay keys (`disabled_rules`, `disabled_directives`), which is structurally correct.

**Alternatives considered:**

- **`project-knowledge.yaml`.** Splits mode metadata across two files (mode in one file, the disabled-rules consequence in another), creating drift risk. Rejected.
- **A new top-level file like `i18n.yaml`.** Adds a new file type for one flag. Rejected as gratuitous.

**Consequence:** Code paths that need to read mode (the dispatcher's `_detect_i18n_sidecar`, the design-source-hygiene check) must load `set/plugins/project-type.yaml`. We provide a single helper `lib/set_orch/profile_loader.py:get_i18n_mode(project_path)` that reads this file (cached) and returns `"single" | "multi"`, defaulting to `"multi"` if the file is missing or the key is absent — preserving current behavior for projects that predate this change.

### Decision 4 — Manifest module split, no separate template directory

**Choice:** Keep one `templates/nextjs/` directory. Use the manifest's existing `core:` / `modules:` split to designate i18n-multi-only files as belonging to the optional `i18n-multi` module. `set-project init --i18n multi` adds `i18n-multi` to the modules list passed into `deploy_templates()`.

```yaml
# templates/nextjs/manifest.yaml — proposed shape
core:
  - .gitignore
  - path: package.json
    protected: true
  - project-knowledge.yaml
  - rules/ui-conventions.md
  # ... other always-deployed files ...
  - rules/copy-module-conventions.md   # NEW — single + multi both get this
  - src/copy/index.ts                   # NEW — typed copy module (single mode only)
  - src/copy/locale.ts                  # NEW — primary-locale constant
  # ... rest of core ...

modules:
  i18n-multi:
    description: "Multi-locale i18n machinery (next-intl + sidecar pattern)"
    files:
      - rules/i18n-conventions.md
      - messages/en.json
      - messages/hu.json
      - scripts/check-i18n-completeness.ts

  integrations:
    description: "External API patterns (webhooks, retry, rate limiting)"
    files:
      - rules/integrations.md
```

Wait — `src/copy/index.ts` and `src/copy/locale.ts` need to be single-mode-only, not always-on. They will collide with `next-intl` patterns in multi mode (multi mode users wouldn't have a typed copy module; they'd have `messages/*.json`). So we add a second module:

```yaml
modules:
  i18n-multi: { ... as above ... }
  i18n-single:
    description: "Single-locale typed copy module"
    files:
      - src/copy/index.ts
      - src/copy/locale.ts
```

And `set-project init` selects exactly one of the two based on `--i18n`. The `rules/copy-module-conventions.md` file stays in `core:` because both modes benefit from it (multi-mode also has cases where strings live in `src/copy/` rather than `messages/` — e.g., system-internal strings, log messages — and the rule documents that boundary).

Actually re-thinking: in multi mode, the centralized copy module is irrelevant — multi mode uses `t('key')` and `messages/*.json`. The `copy-module-conventions.md` rule should ALSO be in the `i18n-single` module, not in core. We end up with:

```yaml
modules:
  i18n-multi:
    files:
      - rules/i18n-conventions.md
      - messages/en.json
      - messages/hu.json
      - scripts/check-i18n-completeness.ts
  i18n-single:
    files:
      - rules/copy-module-conventions.md
      - src/copy/index.ts
      - src/copy/locale.ts
  integrations: { ... unchanged ... }
```

`set-project init` always selects exactly one of `i18n-multi` / `i18n-single`. (The CLI translates `--i18n single` to `--modules i18n-single` and `--i18n multi` to `--modules i18n-multi`, alongside any user-supplied `--modules` list.)

**Rationale:** Manifest's `modules:` mechanism already supports this exact pattern (`integrations` module). No new deploy infrastructure needed. The split is explicit in the manifest and easy to audit.

**Alternatives considered:**

- **Two separate template directories (`templates/nextjs-single/`, `templates/nextjs-multi/`).** Forces 90% of files to be duplicated. Maintenance nightmare. Rejected.
- **Single core, post-deploy script that strips i18n files in single mode.** Adds a deploy phase, asymmetric ("we deploy then un-deploy"). Rejected.
- **All files in `core:`, with overlay marking some as "delete in single mode".** Inverts the natural flow; `core:` becomes a maximal list with subtractive overrides. Less readable than the additive `modules:` approach. Rejected.

### Decision 5 — Single-mode pattern: typed copy module with `as const`

**Choice:** Single-mode projects place all user-visible strings in `src/copy/index.ts` exported as a deeply-nested `as const` literal:

```typescript
// src/copy/index.ts — seeded in single mode
export const copy = {
  home: {
    title: "Welcome",
    subtitle: "Explore our offering",
    cta: "Get started",
  },
  nav: { home: "Home", about: "About", login: "Log in" },
  common: { loading: "Loading…", error: "Something went wrong" },
  // ... organized by feature/page ...
} as const;

export type Copy = typeof copy;
```

```typescript
// src/copy/locale.ts — primary-locale constant for Intl.* calls
export const PRIMARY_LOCALE = "en-US";
// Components needing locale-aware formatting:
//   import { PRIMARY_LOCALE } from "@/copy/locale";
//   date.toLocaleDateString(PRIMARY_LOCALE)
```

Components import and use:
```tsx
import { copy } from "@/copy";
<h1>{copy.home.title}</h1>
<button>{copy.common.retry}</button>
```

**Rationale:** Five properties matter:

1. **Type-safe references.** Typo-on-key fails at compile time (`copy.home.titlle` → tsc error). Equivalent guarantee to `t('home.title')` would require typegen from JSON, which next-intl provides but plain message files don't.
2. **Single source of truth for designers/copywriters.** One file to grep, edit, and review. The original i18n promise without the routing/parity machinery.
3. **No runtime overhead.** Direct property access, no library, no React context, no SSR locale negotiation.
4. **Migration-ready.** A future `single → multi` transition is a one-shot codemod: serialize the `as const` object to `messages/<primary_locale>.json`, replace each `copy.x.y` usage with `t('x.y')`. Trivially tractable because the structure is already a 1:1 dictionary.
5. **Compatible with `Intl.*` rules.** The existing rule "use a locale value with `Intl.*`/`toLocale*`" applies — single mode satisfies it via the `PRIMARY_LOCALE` constant rather than a `useLocale()` call.

**Alternatives considered:**

- **next-intl with a single locale.** Keeps the `t('key')` ergonomics but retains all the next-intl machinery (middleware, locale routing, `[locale]` segment in App Router). Defeats the purpose of single mode. Rejected.
- **Plain `export const HOME_TITLE = "Welcome";` flat constants.** Lacks the namespace structure that makes large copy files navigable. Rejected.
- **JSON file (e.g., `src/copy.json`).** Loses TypeScript type-safety. Rejected.
- **Tagged template literal pattern (`copy.home.title()` as a function).** Adds runtime indirection without typed-key benefit. Rejected.

### Decision 6 — `cross-cutting-review` directive partial scoping

**Choice:** The `cross-cutting-review` directive (currently `change-modifies-any(cross_cutting_files.sidebar, cross_cutting_files.i18n, cross_cutting_files.route_labels)`) is NOT disabled in single mode. Instead, the `cross_cutting_files.i18n` reference in the directive's trigger evaluates against the project-knowledge file: in single mode, `cross_cutting_files.i18n` is set to `["src/copy/index.ts"]` rather than `["messages/*.json"]`.

**Rationale:** The directive is mode-agnostic in spirit — it flags edits to files that many features share. The `src/copy/index.ts` IS such a shared file in single mode. We adjust *what* the directive points at, not whether it runs.

**Implementation:** `set-project init` writes the appropriate `cross_cutting_files.i18n` list into `project-knowledge.yaml` based on mode:
- single mode: `i18n: [src/copy/index.ts, src/copy/locale.ts]`
- multi mode: `i18n: [messages/*.json]` (today's value)

**Alternatives considered:**

- Disable the directive entirely in single mode. Loses a useful flag. Rejected.
- Keep the directive but make the `i18n` slot empty in single mode. The directive then quietly does nothing for an i18n-touch in single mode. Rejected — silent under-coverage is worse than an explicit re-pointing.

### Decision 7 — `primary_locale` capture and use

**Choice:** `set-project init --i18n single --primary-locale <BCP-47>` accepts an optional locale string, default `"en-US"`. Stored in `set/plugins/project-type.yaml` under `i18n.primary_locale` and ALSO seeded into `src/copy/locale.ts` as `PRIMARY_LOCALE`.

**Rationale:** The framework currently has implicit Hungarian assumptions in places (e.g., the `messages/hu.json` seed exists). Single mode forces the question: "which language?" Operators need a way to say "Hungarian-only single-locale shop" → `--primary-locale hu-HU`. The locale flows into:
- `src/copy/locale.ts` (Intl.* calls)
- Playwright `use.locale` if we seed a config
- Default `<html lang="...">` if we touch the layout (we don't — out of scope)

**Default `en-US`:** chosen for parity with most Vercel/shadcn starter conventions. Operators who want Hungarian or another primary locale pass `--primary-locale hu-HU` (or whichever) explicitly. The runner scripts that today target Hungarian fixtures will pass this flag explicitly as part of their multi/single declaration.

**Alternatives considered:**

- **Mandatory flag, no default.** Friction for the common case. Rejected.
- **Default `hu-HU` because the framework was developed with Hungarian fixtures.** Bakes in a project-specific assumption. Rejected — and reinforced by the CLAUDE.md "External Project Confidentiality" rule.
- **Read the locale from `LANG` env var.** Surprising. Rejected.

### Decision 8 — `next-intl` and `eslint-plugin-i18next` stay in `package.json` even in single mode

**Choice:** The `package.json` template is shared across modes. `next-intl` and `eslint-plugin-i18next` remain as devDependencies / dependencies in both single and multi mode.

**Rationale:** Splitting `package.json` is non-trivial because it's marked `protected: true` in the manifest (changes to it after init are preserved). Having two variants would mean either: (a) two `package.json` template files with a deploy-time swap, or (b) a post-deploy filter step that strips deps in single mode. Both add asymmetry. The cost of leaving the deps in is ~1 MB in `node_modules` (zero runtime cost — they're tree-shaken from the bundle if unused).

**Alternatives considered:**

- **Two package.json templates.** Deploy-time selection. Maintainable but more code. Defer.
- **Post-deploy strip step.** A `pnpm remove next-intl eslint-plugin-i18next` after init for single mode. Adds an installation phase. Defer.

**Consequence:** A follow-up change can revisit this if the dep cost is ever measured to matter. For now, declared explicitly out of scope.

### Decision 9 — `design_manifest.py` mode-aware "i18n leakage" check

**Choice:** The hygiene check at `lib/set_orch/design_manifest.py` (rule #2 "Hardcoded UI strings — i18n leakage" per the `design-source-hygiene` spec) reads `i18n.mode` from `set/plugins/project-type.yaml` and changes its target:

- multi mode: a string is "leaked" if it does not appear in any `messages/*.json` file. (Today's behavior.)
- single mode: a string is "leaked" if it does not appear in `src/copy/index.ts`.
- mode missing / file missing: fall back to multi behavior. (Preserves existing projects.)

**Rationale:** The hygiene check's intent is "user-visible strings should live in a centralized location, not hardcoded in JSX." That intent is mode-agnostic; only the centralized location differs.

**Implementation:** The check uses the same `get_i18n_mode(project_path)` helper introduced in Decision 3. It reads `src/copy/index.ts` once per scan in single mode (parsing the `as const` literal with a forgiving regex — the structure is predictable). Performance impact: one extra file read per hygiene scan. Negligible.

**Alternatives considered:**

- **Disable the rule in single mode.** Loses the hygiene benefit. Rejected.
- **Run the check against both targets in single mode.** Confusing false positives ("string appears in src/copy/ but is missing from messages/en.json") for projects that don't have `messages/`. Rejected.

### Decision 10 — Backwards compatibility via "missing flag = multi" semantics

**Choice:** Any code path that reads `i18n.mode` from `set/plugins/project-type.yaml` defaults to `"multi"` if:
- the file is missing,
- the file exists but `i18n` block is absent,
- the file has `i18n.mode` but the value is not `"single"`.

**Rationale:** Existing consumer projects (initialized before this change) have `set/plugins/project-type.yaml` files with no `i18n.mode` key. Defaulting to `"multi"` for them preserves their current behavior bit-identically — they continue running with `messages/*.json`, the i18n-completeness rule, the `no-parallel-i18n` directive, and so on. No migration, no surprise.

**Alternatives considered:**

- **Default to `single`.** Would silently flip existing projects' behavior. Catastrophic. Rejected with prejudice.
- **Error on missing flag.** Forces a migration before any future orchestration runs. Operationally unfriendly. Rejected.

## Risks / Trade-offs

**[Risk] Default flip silently breaks runner scripts that produce multi-locale apps.**
→ Mitigation: Audit `tests/e2e/runners/*` as part of this change (one task). Any runner that bootstraps a multi-locale fixture must pass `--i18n multi` explicitly. Document the requirement in `tests/e2e/README.md`. Add a one-shot grep check in CI: any runner that does NOT pass `--i18n` should fail review (operators must be explicit). For this change, we update the known runner(s) ourselves.

**[Risk] Operators in single mode hand-edit `package.json` to remove `next-intl`, then start using `useTranslations` somewhere later, breaking at runtime.**
→ Mitigation: this is operator error; documenting "next-intl is unused in single mode but present" in `copy-module-conventions.md` is sufficient. The decision to leave the dep in (Decision 8) explicitly accepts this trade-off.

**[Risk] The `as const` typed copy module grows unwieldy at scale (~1000s of strings).**
→ Mitigation: consumers can split into `src/copy/<feature>.ts` files re-exported from `src/copy/index.ts`. The pattern is conventional in TypeScript codebases at scale. Document the pattern in `copy-module-conventions.md`. No code change needed; the mechanism is just `import * as feature from "./feature"`.

**[Risk] Two copies of the disabled-rules list — one in this design doc, one in `profile_deploy.py`'s overlay-emission code — drift over time.**
→ Mitigation: a unit test (`tests/unit/test_web_template_i18n_modes.py`) asserts exact overlay contents per mode. If the deploy code changes, the test fails. If the design doc says something different from the test, code review catches it.

**[Risk] In multi mode, an agent inadvertently writes a string into `src/copy/index.ts` instead of `messages/*.json`.**
→ Mitigation: in multi mode, `src/copy/index.ts` is NOT seeded (Decision 4 puts it in the `i18n-single` module). Multi-mode agents have no `src/copy/` directory; the path doesn't exist for them to write to. The `i18n-conventions.md` rule already commands them to use `t('key')`.

**[Risk] An existing project's operator wants to migrate from multi to single (or vice versa) after init.**
→ Mitigation: explicitly out of scope (Non-Goal). Operator can edit `set/plugins/project-type.yaml` overlay manually; the framework will respect it on the next run. Codemod for the source code (replacing `t()` with `copy.x.y` references or vice versa) is left to the operator. Document this in the rule file.

**[Risk] The dispatcher's `_detect_i18n_sidecar` heuristic (looks for `next-intl` in `package.json` AND a `messages/` directory) misfires if a single-mode project has `next-intl` in deps but no `messages/` dir → already returns `""` per current code (`dispatcher.py:1782`). The defensive skip works.**
→ Mitigation: Confirmed by reading the code. No change needed. Add a regression test that asserts single mode produces no sidecar instructions.

**[Risk] The `i18n-conventions` capability spec changes might invalidate workflows that depend on it being unconditional.**
→ Mitigation: the modification scopes existing requirements to multi-mode but preserves them. Anything that was true is still true *for multi-mode projects*. Any rule consumer that doesn't check mode reads the old behavior — that's fine because their projects are multi-mode (default for legacy, explicit for new).

**[Trade-off] Mode is set once at init. Mid-project switches require manual edits and a copy migration.**
→ Accepted (Non-Goal). The marginal benefit of automated switching is small — projects don't typically toggle this axis.

**[Trade-off] `package.json` carries unused deps in single mode.**
→ Accepted (Decision 8). Cosmetic, ~1 MB on disk.

**[Trade-off] `i18n-conventions` spec becomes mode-conditional, slightly more complex to read.**
→ Accepted. The spec gets a "Applicability" preamble: "These requirements apply to projects with `i18n.mode: multi`. Single-mode projects use the typed copy module pattern; see `web-template-i18n-modes`." Readers always know which set applies to them.

## Migration Plan

**Step 1 — Implementation order.** Implement bottom-up to keep the system in a consistent state at each commit:
1. Add `get_i18n_mode(project_path)` helper to `profile_loader.py`. Default-multi behavior. Tested.
2. Seed the new files: `rules/copy-module-conventions.md`, `src/copy/index.ts`, `src/copy/locale.ts`.
3. Update `manifest.yaml` to move i18n-multi files into the `i18n-multi` module and add the `i18n-single` module.
4. Update `set-project init` (`lib/set_project_base/cli.py` + `lib/set_orch/profile_deploy.py`) to: (a) accept `--i18n` and `--primary-locale`, (b) translate `--i18n single` to `--modules i18n-single` and `--i18n multi` to `--modules i18n-multi`, (c) write the `i18n.mode` block + `disabled_rules` + `disabled_directives` into `set/plugins/project-type.yaml`, (d) write the `i18n.primary_locale` value into `src/copy/locale.ts` as a search-and-replace if mode=single.
5. Update `dispatcher.py:_detect_i18n_sidecar` to return `""` immediately if `get_i18n_mode() == "single"` (defense-in-depth — current code already short-circuits via the `messages/` dir check, but explicit is clearer).
6. Update `design_manifest.py` "i18n leakage" check to be mode-aware.
7. Update modified specs (`i18n-conventions`, `cross-cutting-file-strategy`, `design-source-hygiene`) and add new spec (`web-template-i18n-modes`).
8. Update runner scripts that need `--i18n multi` explicitly.
9. Add the unit test.

**Step 2 — Verification.** Run two end-to-end orchestration runs back-to-back:
- a single-mode fixture (e.g., scaffold a designer-portfolio-style spec with `--i18n single`)
- a multi-mode fixture (run the existing craftbrew runner with `--i18n multi` added)

Compare:
- Single-mode run: assert no `messages/` directory created, no `i18n_check` gate fired, no `no-parallel-i18n` directive applied to the plan, no sidecar instructions in dispatch contexts. Assert `src/copy/index.ts` exists.
- Multi-mode run: assert behavior is identical to today's craftbrew runs (no regressions in gate count, directive count, dispatch context shape).

**Step 3 — Rollout.** No staged rollout. The change is behind explicit init flags; existing projects are unaffected (Decision 10). Merging is safe.

**Step 4 — Rollback.** If the change causes an unexpected regression, the rollback is a single revert: existing projects' overlays don't reference the new behavior, so reverting the deploy code returns the system to today's state. New single-mode projects created during the broken window may need manual cleanup (run `set-project init --i18n multi --force` or hand-edit the overlay), but the impact is contained.

## Open Questions

1. **Should `set-project init` accept a `--copy-root` flag to override `src/copy/`?** Current proposal hardcodes `src/copy/`. Some projects might want `app/_copy/` or `src/locales/copy/`. Defer — easy to add later if requested.

2. **Is the typed-copy pattern compatible with React Server Components everywhere?** The `as const` object is a serializable literal, so it works in both client and server contexts. Confirmed; no RSC-specific handling needed.

3. **Should `copy-module-conventions.md` include a section on "string keys for analytics/tracking"?** Some teams use `t('key')` calls as implicit string IDs for analytics. In single-mode `copy.feature.action` paths can serve the same role. Document briefly; not a blocker.

4. **Do we need a runtime warning if a single-mode project starts importing from `next-intl`?** Could be a lint rule or a startup check. Probably YAGNI — the symptom (no provider, runtime error) is loud. Defer.

5. **What happens if an external plugin (not `WebProjectType`) wants to participate in the `i18n.mode` axis?** Out of scope for this change. The mechanism (overlay-driven `disabled_rules`) is general; external plugins can adopt the same flag if they like, with their own rule IDs. No core abstraction change needed.

6. **Should the planner `i18n_namespace` assignment in `lib/set_orch/planner.py:2075-2078` be made mode-aware as defense-in-depth?** Currently it just sets the namespace on every change. In single mode, no change touches `messages/*.json`, so the field is set but never used. Harmless. Adding a mode check costs a file read in the planner. Probably not worth it; rely on the natural skip path. Defer unless verification surfaces an actual issue.
