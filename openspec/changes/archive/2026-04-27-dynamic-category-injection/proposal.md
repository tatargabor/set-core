## Why

Every change's `input.md` ships with 13.9 KB of auth/IDOR/Prisma/NextAuth review-learnings even when the project has no auth, DB, or API surface. Witnessed in `micro-web-run-20260426-1302`: 28 KB input.md per change, 45–65 % irrelevant. Two upstream bugs cause it:

1. `classify_diff_content(scope)` in `lib/set_orch/templates.py` looks for diff markers (`+++`/`---`) and code patterns (`prisma.`/`app.get(`) — it gets called with **scope text** which contains none of those, returns `set()`, and the consuming code treats empty as "no signal → include all learnings".
2. `WebProjectType.rule_keyword_mapping` uses substring matches; `"token"` matches "design tokens" and `"route"` matches "page routes", so every web scope activates the auth and api categories.

The bloat dilutes agent attention (`blog-list-and-data` regression: agent rebuilt v0's vertical list as a 3-column grid partly because IDOR/auth context tugged it off-task), eats the 1 M context window faster (latency +20–40 s per turn even with cache), and makes new project types (Python, Go) inherit the same noise blindly.

## What Changes

- **Replace** the buggy single-pass `classify_diff_content(scope)` injection trigger with a deterministic multi-layer per-change resolver plus an additive Sonnet 4.6 LLM classifier.
- **Add** seven new `ProjectType` ABC hooks (no-op defaults) so project-type plugins contribute their own patterns without touching core. **BREAKING** for plugins that subclass `ProjectType` directly without `CoreProfile` — those need to opt into the new defaults (covered by backwards-compatibility shim already in place via `set_project_base`).
- **Add** `lib/set_orch/category_resolver.py` orchestrating six deterministic detection layers + Sonnet escalation, with `sha256(scope)` cache and graceful fallback.
- **Add** `lib/set_orch/insights.py` post-merge aggregator that distills `category-classifications.jsonl` into `project-insights.json`, fed back as bias to subsequent dispatches.
- **Move** all web-specific patterns (next-auth/prisma/drizzle deps, REQ-domain mapping, file-path classifiers, scope-intent regexes, web phase defaults, web taxonomy, project-summary) into `WebProjectType` overrides — `lib/set_orch/` stays project-agnostic.
- **Drop** polysemous keywords (`token`, `middleware`, `route`) from `WebProjectType.rule_keyword_mapping` to stop "design tokens" / "page routes" from triggering auth/api injection.
- **Update** `lib/set_orch/dispatcher.py:_build_input_content` and `_build_review_learnings` callers to consume the new resolver instead of `classify_diff_content(scope)`.

## Capabilities

### New Capabilities

- `change-category-resolver`: Per-change category determination with six-layer deterministic detector (change_type, REQ-prefix, manifest paths, scope intent regex, depends_on transitive closure, project-state fallback) plus an additive Sonnet 4.6 LLM classifier with persistent audit log.
- `project-insights-aggregator`: Post-merge aggregation of per-change classification records into a project-scoped `project-insights.json` that biases subsequent deterministic detection and provides project context to the LLM classifier prompt.

### Modified Capabilities

- `learnings-scope-filter`: Replace the empty-set-fallthrough rule (when the legacy classifier returned `set()` it was treated as "no signal → include all"). New rule: empty deterministic + LLM result is a positive signal that the change has no domain surface, and only `general`-tagged learnings are injected. Profiles drive the categorization, not a single dispatch-time text classifier.

## Impact

**Affected code:**

- `lib/set_orch/profile_types.py` — seven new ABC methods on `ProjectType` (no-op defaults).
- `lib/set_orch/dispatcher.py` — `_build_input_content` and surrounding callers consume `category_resolver.resolve_change_categories(...)` instead of `classify_diff_content(scope)`. Old function stays for diff-time use (verifier still uses it correctly on actual diffs).
- `lib/set_orch/category_resolver.py` (new) — 6-layer deterministic orchestration + Sonnet call + cache + JSONL writer.
- `lib/set_orch/insights.py` (new) — post-merge aggregator.
- `lib/set_orch/paths.py` — `category_classifications`, `project_insights` path constants under `.set/state/`.
- `modules/web/set_project_web/project_type.py` — seven `WebProjectType` overrides; `rule_keyword_mapping` drops three polysemous keywords.

**Affected runtime data (per-project, gitignored under `.set/state/`):**

- `category-classifications.jsonl` — append-only audit log, one record per Sonnet call.
- `project-insights.json` — aggregated bias, rewritten after each merge.

**Affected gates / engine flow:**

- Dispatcher: +1 LLM call per change (cache-backed), worst-case +1–4 s latency, ~$0.005 cost. Cache hits free on retries/replans.
- Verifier: unaffected — `classify_diff_content` keeps its diff-time use case.

**Cost projection:**

| Run shape | Sonnet calls | Cache hit | Total cost |
|-----------|--------------|-----------|------------|
| 11-change micro-web | 11 | 50 % (retries/replans) | ~$0.03 |
| 30-change craftbrew | 30 | 60 % | ~$0.06 |

Compared to the bloat-induced extra context per turn (~$1–3/run wasted in cached re-reads), this is a clear net positive.

**Project-independence:**

A future Python plugin (`set-project-django`) supplies its own seven overrides — file detectors for `manage.py`, dependency detectors for `django-rest-framework`, REQ-prefix map for `VIEW`/`MODEL`/`MIGRATION`, scope intent regex for Django-specific keywords. Core dispatcher unchanged.

**Backwards compatibility:**

- Plugins using `set_project_base` shim get the new ABC defaults (no-op `set()`) automatically.
- The dispatcher gracefully degrades when the LLM call fails or times out — the deterministic layers provide a safe baseline.
- `category-classifications.jsonl` and `project-insights.json` are additive; absent files are treated as "no prior signal" and the resolver runs cold.
