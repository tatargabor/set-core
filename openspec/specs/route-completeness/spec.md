# Spec: Route Completeness Rule

## Requirements

### REQ-RC-001: Category Listing Completeness Rule
When a change scope covers product catalog pages across multiple categories, the review rule MUST flag if any category mentioned in the spec or defined in the database schema (e.g., Prisma enum) lacks a corresponding listing page (`page.tsx`).

**Acceptance Criteria:**
- [ ] Rule text covers the pattern with wrong/correct examples using generic names (e.g., `/coffees`, `/equipment`)
- [ ] Rule references checking Prisma enums or spec categories as the source of truth
- [ ] Example shows: if `/coffees/page.tsx` exists for COFFEE, then `/equipment/page.tsx` must exist for EQUIPMENT

### REQ-RC-002: Detail-Implies-Listing Rule
The review rule MUST flag when a dynamic detail page (`[slug]/page.tsx` or `[id]/page.tsx`) exists without a corresponding listing/index page in the same directory.

**Acceptance Criteria:**
- [ ] Rule text covers the pattern with wrong/correct examples
- [ ] Rule explains the UX reason (users must discover items before viewing details)

### REQ-RC-003: Task-File Correlation Rule
The review rule MUST flag when tasks.md marks a task `[x]` done that describes creating a file (page, API route, component) but the file doesn't exist in the working tree.

**Acceptance Criteria:**
- [ ] Rule text covers the pattern with wrong/correct examples for page.tsx files
- [ ] Rule includes a separate wrong/correct example for API route.ts files
- [ ] Rule applies to page.tsx, route.ts, and component files
- [ ] Rule explains: never mark a task done if the referenced output doesn't exist

### REQ-RC-004: Admin Resource Completeness Rule
The review rule MUST flag when the spec mentions admin management for a resource but the corresponding admin page doesn't exist.

**Acceptance Criteria:**
- [ ] Rule text covers the pattern with wrong/correct examples
- [ ] Rule references the spec's admin requirements as source of truth

### REQ-RC-005: Keyword Mapping Extension
`NullProfile.rule_keyword_mapping()` MUST include a "catalog" category that maps catalog/listing/category/browse keywords to the new `route-completeness.md` rule.

**Acceptance Criteria:**
- [ ] New "catalog" key in rule_keyword_mapping return dict
- [ ] Keywords include: catalog, listing, category, browse, product list, page.tsx, grid
- [ ] Globs point to: web/route-completeness.md

### REQ-RC-006: Acceptance Criteria Extension (WebProjectType only)
`WebProjectType.security_checklist()` in set-project-web MUST include route coverage acceptance criteria. `NullProfile` does NOT get route AC — route concepts are web-specific.

**Acceptance Criteria:**
- [ ] WebProjectType checklist includes: "Every spec-mentioned category has a listing page"
- [ ] WebProjectType checklist includes: "Every [slug] detail route has a corresponding listing page"
- [ ] WebProjectType checklist includes: "Tasks marked [x] have their referenced files created"
- [ ] WebProjectType checklist includes: "i18n keys for new route names present in all locale files"
- [ ] NullProfile.security_checklist() is NOT modified

### REQ-RC-007: Verification Rule in set-project-web
A new verification rule `route-listing-completeness` MUST be added to `WebProjectType.get_verification_rules()`.

**Acceptance Criteria:**
- [ ] YAML file created in `verification-rules/route-listing-completeness.yaml`
- [ ] Uses a valid check type from SCHEMA.md (file-mentions)
- [ ] Registered in `get_verification_rules()` method
- [ ] Severity: warning
