## 1. Layer 1 — ProjectType ABC hooks

- [x] 1.1 Add seven new ABC method signatures with no-op defaults on `ProjectType` in `lib/set_orch/profile_types.py`:
   - `detect_project_categories(project_path) -> set[str]` (default: `{"general"}`)
   - `detect_scope_categories(scope: str) -> set[str]` (default: `set()`)
   - `categories_from_paths(paths: list[str]) -> set[str]` (default: `set()`)
   - `categories_from_change_type(change_type: str) -> set[str]` (default: `set()`)
   - `categories_from_requirements(req_ids: list[str]) -> set[str]` (default: `set()`)
   - `category_taxonomy() -> list[str]` (default: `["general"]`)
   - `project_summary_for_classifier(project_path) -> str` (default: `""`)
   - Property `llm_classifier_model -> str | None` (default: `"claude-sonnet-4-6"`)
- [x] 1.2 Document each method with full docstring covering: purpose, inputs, return shape, example return for a typical web project, no-op default rationale.
- [x] 1.3 Verify `set_project_base` shim re-exports stay valid (existing plugins that subclass `ProjectType` directly inherit the new no-op defaults — no breakage).
- [x] 1.4 Add unit test `tests/unit/test_profile_types_category_hooks.py` that asserts NullProfile and CoreProfile return the documented defaults.

## 2. Layer 1 — Path constants and persistence helpers

- [x] 2.1 In `lib/set_orch/paths.py`, add `LineagePaths.category_classifications` returning `<state_dir>/category-classifications.jsonl` and `LineagePaths.project_insights` returning `<state_dir>/project-insights.json`.
- [x] 2.2 Add a small JSONL append helper that opens with `"a"` + line-flush + atomic write semantics; reuse the existing event-bus append pattern if available.
- [x] 2.3 Add the two path constants to the gitignore deploy template under `.set/state/`.
- [x] 2.4 Test path resolution against a tmp_path fixture.

## 3. Layer 1 — `lib/set_orch/category_resolver.py` (new file)

- [x] 3.1 Define module docstring summarizing the six-layer + LLM design and pointing at design.md.
- [x] 3.2 Implement `resolve_change_categories(change, profile, project_path, manifest_paths, project_insights=None) -> ResolverResult` that:
   - runs the five primary deterministic layers in order
   - invokes `detect_project_categories` only when primary union has ≤ 2 categories
   - applies project-insights bias from `by_change_type[change.change_type].common_categories` if present
   - computes `cache_key = sha256(scope || sorted(req_ids) || sorted(deps)).hexdigest()`
   - looks up cache by walking `category-classifications.jsonl` for matching `cache_key`
   - on cache miss: calls the LLM via the helper from §3.5
   - on LLM result: filters categories against `profile.category_taxonomy()`; routes unknowns to `uncovered_categories`
   - returns final union plus a structured audit record
- [x] 3.3 Define `ResolverResult` dataclass with: `final_categories: set[str]`, `deterministic: dict`, `llm: dict`, `cache_hit: bool`, `delta: dict`, `uncovered_categories: list[str]`, `audit_record: dict` (JSONL-serializable).
- [x] 3.4 Implement `_build_audit_record(...)` that produces the exact JSONL schema documented in design.md D7.
- [x] 3.5 Implement `_call_sonnet(prompt_inputs, profile) -> tuple[set[str], dict]`:
   - reads `profile.llm_classifier_model` (skip call if None/empty)
   - composes system prompt with `category_taxonomy()` and `project_summary_for_classifier()`
   - composes user prompt with scope, change_type, requirements, paths, deps, insights summary
   - 8s timeout, single-shot retry on 5xx/timeout
   - returns parsed JSON `{categories, confidence, reasoning}`
   - on error: returns `(set(), {"error": "...", "duration_ms": ...})` for graceful degradation
- [x] 3.6 Append the audit record to `category-classifications.jsonl` (line-atomic).
- [x] 3.7 Tests in `tests/unit/test_category_resolver.py` covering each spec scenario:
   - all five primary layers contribute
   - project-state fallback engages when primary ≤ 2 cats
   - LLM-only categories union with deterministic
   - LLM cannot remove deterministic categories
   - non-taxonomy LLM category filtered + recorded
   - cache hit on identical inputs (replan)
   - cache miss on edited scope
   - LLM timeout → graceful fallback to deterministic
   - malformed JSON → graceful fallback
   - LLM disabled (model None) → skip call
   - audit record schema matches design.md D7
   - concurrent appends produce well-formed JSONL

## 4. Layer 1 — `lib/set_orch/insights.py` (new file)

- [x] 4.1 Implement `update_insights(project_path)` that reads all records from `category-classifications.jsonl`, computes aggregates per design.md, and writes `project-insights.json` atomically (write to tmp then rename).
- [x] 4.2 Compute `by_change_type[ct]`:
   - `category_frequency`: `{cat: count/total}` for each category appearing in records of this change_type
   - `common_categories`: list of categories with frequency ≥ 0.5
   - `rare_categories`: list of categories with 0 < frequency < 0.5
- [x] 4.3 Compute `deterministic_vs_llm`:
   - `agreement_rate`: fraction of records where `set(deterministic.categories) == set(llm.categories)`, EXCLUDING cache_hit records
   - `llm_added_categories`: count map of categories added by LLM beyond deterministic, summed across records
- [x] 4.4 Compute `scope_keyword_categories`: for each change, tokenize scope on whitespace, take top-10 non-stopword tokens, map each token to the union of categories that appeared in classifications using that token. Threshold: token must appear in ≥ 2 changes to be counted.
- [x] 4.5 Compute `uncovered_categories`: count map summed across all records' `uncovered_categories` field. Persist across runs.
- [x] 4.6 Hook the aggregator into the merge pipeline — `OrchestrationEngine` or `engine.merge_change` callsite (whichever owns the merge transition). Wrap in try/except with WARNING log so aggregator failure never blocks merge.
- [x] 4.7 Tests in `tests/unit/test_project_insights.py`:
   - first merge populates with `samples_n: 1`
   - subsequent merges recompute from full record set
   - empty change_type bucket omitted
   - common/rare categories computed at the 0.5 threshold
   - cache-hit records excluded from agreement metric
   - aggregator failure does not raise (logs and returns)
   - uncovered_categories preserved across taxonomy expansion

## 5. Layer 1 — Dispatcher integration

- [x] 5.1 In `lib/set_orch/dispatcher.py:_build_input_content`, replace the `from .templates import classify_diff_content; _content_categories = classify_diff_content(scope)` block with a call to `category_resolver.resolve_change_categories(...)`.
- [x] 5.2 Pass `change_requirements` (already in scope) and the `digest_dir`-derived manifest paths into the resolver call.
- [x] 5.3 Read `project-insights.json` once per dispatch and pass into the resolver to enable bias.
- [x] 5.4 Audit-log the resolver result via the resolver's own JSONL write — no extra dispatcher logging needed.
- [x] 5.5 Update `_build_review_learnings(content_categories=...)` callers to pass the resolver's `final_categories` set. Note that empty set is now a positive "no domain surface" signal per modified spec.
- [x] 5.6 Leave `lib/set_orch/templates.py:classify_diff_content` untouched — verifier still uses it correctly on actual diffs.
- [x] 5.7 Tests in `tests/unit/test_dispatcher_resolver_integration.py`:
   - dispatcher invokes resolver with correct inputs
   - dispatcher does NOT call classify_diff_content(scope) at dispatch time
   - empty resolver result narrows learnings to general only
   - non-empty resolver result filters learnings appropriately
   - resolver exception falls through to legacy include-all (defensive, not the happy path)

## 6. Layer 2 — `WebProjectType` overrides

- [x] 6.1 Override `detect_project_categories(project_path)` in `modules/web/set_project_web/project_type.py`:
   - Always include `general`, `frontend`
   - Add `auth` if `middleware.ts` exists at root or `src/middleware.ts`
   - Add `auth` if any of `next-auth`, `@auth/core`, `lucia`, `iron-session`, `@clerk/nextjs` in `package.json` deps
   - Add `database` if any of `@prisma/client`, `drizzle-orm`, `kysely`, `@libsql/client`, `mongoose` in deps
   - Add `api` if `app/api/`, `src/app/api/`, `pages/api/`, or `src/pages/api/` directory exists
- [x] 6.2 Override `detect_scope_categories(scope)`:
   - Word-boundary regex `\b(auth|login|signup|signin|password|session|cookie|jwt|oauth|nextauth|clerk|lucia)\b` → `auth`
   - `\b(api endpoint|API route|webhook|REST|POST /|GET /|PUT /|DELETE /|app\.get\(|router\.(get|post|put|delete))\b` → `api`
   - `\b(prisma|drizzle|migration|table|column|relation|schema)\b` → `database`
   - `\b(payment|checkout|cart|order|invoice|stripe|paypal|billing)\b` → `payment`
- [x] 6.3 Override `categories_from_paths(paths)`:
   - any path containing `/app/api/` or `/pages/api/` → `api`
   - any path containing `prisma/` or `drizzle/` → `database`
   - any path matching `middleware.ts$` → `auth`
   - any `.tsx`/`.jsx`/`.css`/`.scss` extension → `frontend`
- [x] 6.4 Override `categories_from_change_type(change_type)`:
   - `foundational` → `{frontend, scaffolding}`
   - `infrastructure` → `{ci-build-test}`
   - `schema` → `{database}`
   - `feature` → `{frontend}`
   - `cleanup-before`, `cleanup-after` → `{refactor}`
- [x] 6.5 Override `categories_from_requirements(req_ids)` — REQ-prefix map:
   - `AUTH/LOGIN/SESSION/RBAC` → `auth`
   - `API/ENDPOINT/WEBHOOK` → `api`
   - `DB/DATA/SCHEMA/MIGRATION` → `database`
   - `PAY/CHECKOUT/CART/ORDER/INVOICE` → `payment`
   - `TEST/CI/BUILD` → `ci-build-test`
   - `NAV/PAGE/UI/FORM/FOOT/LAYOUT/COMPONENT` → `frontend`
- [x] 6.6 Override `category_taxonomy()` returning `["general", "frontend", "auth", "api", "database", "payment", "scaffolding", "ci-build-test", "refactor", "schema", "i18n"]`.
- [x] 6.7 Override `project_summary_for_classifier(project_path)` returning a one-line string identifying framework (Next.js / generic-web), inferred from `package.json` deps (`next`, `react-router`, `vite`).
- [x] 6.8 Drop polysemous keywords from `rule_keyword_mapping` (Bug #2): remove `token`, `middleware` from `auth.keywords`; remove `route` from `api.keywords`. Add inline comment explaining why each was removed.

## 7. Layer 2 — Tests

- [x] 7.1 `modules/web/tests/test_web_categories.py` exercising each override:
   - middleware.ts → auth
   - prisma dep → database
   - app/api/ dir → api
   - scope "checkout flow" → payment
   - REQ-AUTH-001 → auth
   - foundational → scaffolding+frontend
   - .tsx path → frontend
   - micro-web fixture (no auth/api/db) → only general+frontend
   - craftbrew-shaped fixture (auth+db+api) → all five
- [x] 7.2 `modules/web/tests/test_rule_keyword_mapping_polysemous.py` regression test:
   - scope "design tokens" does NOT activate auth
   - scope "page routes" does NOT activate api
   - scope "Next.js middleware for routing" does NOT activate auth
   - scope "session cookie" DOES activate auth (kept keyword)
   - scope "API endpoint" DOES activate api (kept keyword)

## 8. Layer 1 + 2 — Live verification

- [x] 8.1 Generate input.md for the foundation-shell-and-navigation scope from `micro-web-run-20260426-1302` using the new resolver. Expect `final_categories ⊆ {general, frontend, scaffolding, ci-build-test}`. Verify the rendered input.md has NO auth/IDOR/Prisma sections.
- [x] 8.2 Generate input.md for a craftbrew-style "POST /api/admin/users mutation" scope using a fixture project state with auth+db+api. Expect `final_categories` to include `auth`, `api`, `database`, `frontend`. Verify those sections are present.
- [x] 8.3 Compare input.md sizes before and after for both fixtures. Target: ≥ 60 % reduction for micro-web foundation. Document actual measurement in commit message.
- [x] 8.4 Run the full dispatcher test suite (`pytest tests/unit/test_dispatcher*.py modules/web/tests/`) — all green except pre-existing failures unrelated to this change.

## 9. Documentation + commit

- [x] 9.1 Update `lib/set_orch/dispatcher.py` callsite comment to reference `category_resolver` and remove the comment about `classify_diff_content(scope)` being safe-fallthrough (it's no longer invoked at dispatch).
- [x] 9.2 Add a short note in `templates/core/rules/code-quality.md` under "Logging — mandatory" explaining that `category_resolver` audits go to `category-classifications.jsonl` and how to inspect.
- [ ] 9.3 Single commit per phase (Layer 1 ABC + paths + resolver + insights + dispatcher integration; Layer 2 overrides + bug-fix; tests; live-verification artifacts). Keep commits revertible per design.md D9 migration plan.
- [ ] 9.4 Open a follow-up ticket for: (a) Haiku/Sonnet cascade on low-confidence, (b) cross-project insight export via `set-harvest`, (c) lazy LRU truncation of `category-classifications.jsonl` past 1000 entries.
