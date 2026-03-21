# Tasks: web-route-completeness-rules

## set-core tasks

### 1. Create route completeness rule file

- [x] 1.1 Create `.claude/rules/web/route-completeness.md` with Pattern A: Category Listing Completeness — wrong/correct examples using generic names (coffees/equipment, not project-specific), reference Prisma enums as source of truth
- [x] 1.2 Add Pattern B: Detail-Implies-Listing — wrong/correct examples for `[slug]/page.tsx` requiring sibling `page.tsx`
- [x] 1.3 Add Pattern C: Task-File Correlation — wrong/correct examples for `[x]` tasks requiring referenced files to exist. Include BOTH a page.tsx example AND a route.ts (API) example
- [x] 1.4 Add Pattern D: Admin Resource Completeness — wrong/correct examples for spec-mentioned admin CRUD pages
- [x] 1.5 Add "The rule" summary line for each pattern (consistent with existing rule files like `security-patterns.md`)

### 2. Extend keyword mapping (NullProfile defaults)

- [x] 2.1 Add "catalog" category to `NullProfile.rule_keyword_mapping()` in `lib/set_orch/profile_loader.py` with keywords: catalog, listing, category, browse, product list, page.tsx, grid — globs: web/route-completeness.md

### 3. Update run-7 findings

- [x] 3.1 Update `tests/e2e/craftbrew/run-7.md` — add observations for: (a) decomposer narrowing scope to one category example, (b) phantom task completion on returns flow, (c) reference this change as the fix

## set-project-web tasks (repo: /home/tg/code2/set-project-web)

### 4. Extend WebProjectType.security_checklist()

- [x] 4.1 Add four route coverage AC lines to `security_checklist()` in `project_type.py`: listing page per category, listing per detail route, task-file correlation, i18n keys for new routes

### 5. Override WebProjectType.rule_keyword_mapping()

- [x] 5.1 Override `rule_keyword_mapping()` in `WebProjectType` — call `super()` for NullProfile defaults + add "catalog" category (same keywords as 2.1) + add "payment" category mapping to transaction-patterns.md

### 6. New verification rule: route-listing-completeness

- [x] 6.1 Create `verification-rules/route-listing-completeness.yaml` — use `file-mentions` check type, scan `[slug]/page.tsx` paths, verify parent directory listing page exists, severity: warning
- [x] 6.2 Add the VerificationRule entry to `WebProjectType.get_verification_rules()` in `project_type.py`

### 7. Tests

- [x] 7.1 Verify rule file deploys: `.claude/rules/web/route-completeness.md` exists in set-core
- [x] 7.2 Verify verification rule: `route-listing-completeness` registered in project_type.py line 193
- [x] 7.3 Verify keyword mapping: `rule_keyword_mapping()` override at project_type.py line 438 with "catalog" key
- [x] 7.4 Verify security checklist: "listing page" text at project_type.py line 294
