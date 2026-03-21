# Design: Web Route Completeness Rules

## Approach

Four coordinated additions — a new rule file, extended keyword mapping, acceptance criteria, and a verification rule.

### 1. New Rule: `route-completeness.md`

**Location**: `.claude/rules/web/route-completeness.md`
**Deployed to**: Consumer projects via `set-project init`
**Used by**: Code review gate (injected when scope matches keywords), agents during implementation

**Rule content covers four patterns:**

#### Pattern A: Category Listing Completeness
If the spec/schema defines multiple product categories (e.g., COFFEE, EQUIPMENT, MERCH, BUNDLE), and one category gets a listing page, ALL categories need listing pages.

```
Wrong: /coffees/page.tsx exists but /equipment/page.tsx, /merch/page.tsx, /bundles/page.tsx don't
Correct: Every category in the schema/spec has a corresponding listing page
```

Check: enumerate categories from Prisma enum or spec, verify each has `src/app/[locale]/<category>/page.tsx`.

#### Pattern B: Detail Page Implies Listing Page
If `[category]/[slug]/page.tsx` (detail) exists, then `[category]/page.tsx` (listing) MUST also exist. Users need to discover items before viewing details.

```
Wrong: /bundles/[slug]/page.tsx exists but /bundles/page.tsx doesn't
Correct: Both listing and detail pages exist
```

#### Pattern C: Task-File Correlation
If tasks.md marks a task as `[x]` done and the task description references creating a file (page, API route, component), that file MUST exist in the working tree. Don't mark tasks done without creating the referenced files.

This applies to ALL file types — page.tsx, route.ts, and component files.

```
Wrong (page): "- [x] Create /equipment listing page" but src/app/[locale]/equipment/page.tsx doesn't exist
Wrong (API): "- [x] Create return request API endpoint" but src/app/api/returns/route.ts doesn't exist
Correct: Task is only [x] when the described file/feature is actually implemented
```

**Note:** Pattern C is generic (not web-specific), but placing it in the web rule file is pragmatic — web projects are where this gap was observed. A future change may extract it to a core rule for all project types.

#### Pattern D: Admin Resource Completeness
If the spec mentions admin management for a resource (orders, returns, products, users), ALL mentioned admin resources need corresponding pages.

```
Wrong: Spec says "admin manages orders, returns, products" but /admin/returns/page.tsx doesn't exist
Correct: Every spec-mentioned admin resource has its admin page
```

### 2. Keyword Mapping Extension

**Location**: `lib/set_orch/profile_loader.py` — `NullProfile.rule_keyword_mapping()`

Add new category:
```python
"catalog": {
    "keywords": ["catalog", "listing", "category", "browse", "product list", "page.tsx", "grid"],
    "globs": ["web/route-completeness.md"],
}
```

This ensures the rule is injected into the agent's context when the change scope mentions catalog/listing/category concepts.

### 3. Acceptance Criteria Extension

**Location**: `WebProjectType.security_checklist()` in set-project-web only.

`NullProfile.security_checklist()` stays empty — route concepts are web-specific and belong exclusively in the web profile override.

Add to `WebProjectType.security_checklist()`:
```markdown
- [ ] Every spec-mentioned category has a listing page (page.tsx)
- [ ] Every [slug] detail route has a corresponding listing page
- [ ] Tasks marked [x] in tasks.md have their referenced files actually created
- [ ] i18n keys for new route names present in all locale files
```

### 4. Verification Rule: `route-listing-completeness`

**Location**: `set-project-web/verification-rules/route-listing-completeness.yaml`

The existing SCHEMA.md defines 6 check types. None can express "sibling file must exist." Two options:

**Option A (chosen):** Use `file-mentions` check type — scan for `[slug]/page.tsx` paths and verify each parent directory also contains `page.tsx`. This isn't a perfect semantic fit but `file-mentions` can be configured to check file existence by pattern.

**Option B (future):** Add a new `sibling-file-required` check type to the verifier. Deferred to avoid scope creep.

## Dependencies

None — additive changes only.

## Alternatives Considered

1. **Automated file-existence gate in verifier.py** — Rejected for now. The profile interface supports this via `gate_overrides()` but it requires parsing tasks.md for file references, which is fragile. Better to start with review rules (human-readable) and add automated verification rules later.

2. **Decomposer prompt change** — The decomposer creates change scopes correctly ("browse across categories"). The gap is in artifact creation (agent narrows to one example). The review rule catches this at verify time, which is the right layer.

3. **Pattern C as core rule** — Task-file correlation is framework-generic. Kept in web rule for now because web projects are where the gap was observed. Documented as a future extraction candidate for a core rule (`task-file-correlation.md`) applicable to all project types.

4. **Route AC in NullProfile** — Rejected. `NullProfile.security_checklist()` returns `""` and `WebProjectType` overrides it without calling `super()`. Route concepts are web-specific — AC belongs in `WebProjectType` only.
