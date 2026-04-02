## 1. SpecSection Dataclass + ABC Method

- [ ] 1.1 Add `SpecSection` dataclass to `profile_types.py` with fields: `id`, `title`, `description`, `required`, `phase`, `output_path`, `prompt_hint` [REQ: projecttype-abc-has-spec-sections-method]
- [ ] 1.2 Add `spec_sections()` method to `ProjectType` ABC returning `list[SpecSection]` [REQ: projecttype-abc-has-spec-sections-method]
- [ ] 1.3 Implement `CoreProfile.spec_sections()` returning 4 core sections: overview, requirements (project-type agnostic: "What are the main features?"), orchestrator_directives, verification_checklist [REQ: projecttype-abc-has-spec-sections-method]

## 2. Web Module Spec Sections

- [ ] 2.1 Implement `WebProjectType.spec_sections()` extending core with 7 web sections: data_model, seed_catalog, pages_routes, auth_roles, i18n, design_tokens, test_strategy [REQ: projecttype-abc-has-spec-sections-method]
- [ ] 2.2 Set `required=True` for `data_model` and `pages_routes` [REQ: projecttype-abc-has-spec-sections-method]
- [ ] 2.3 Set appropriate `prompt_hint` for each web section (Prisma-aware for data_model, realistic names for seed) [REQ: projecttype-abc-has-spec-sections-method]

## 3. Write-Spec Skill Rewrite

- [ ] 3.1 In Phase 0, add profile detection: call `profile.spec_sections()` to get section list, fall back to hardcoded core sections if `python3 -c "from set_orch..."` fails [REQ: projecttype-abc-has-spec-sections-method]
- [ ] 3.2 Replace hardcoded Phases 1-10 with dynamic iteration over section list ordered by `phase` [REQ: projecttype-abc-has-spec-sections-method]
- [ ] 3.3 For each section, use `prompt_hint` as the question and `description` as guidance [REQ: projecttype-abc-has-spec-sections-method]

## 4. Modular Output Generation

- [ ] 4.1 In Phase 11 (assembly), detect feature count: if 3+ features on web → modular output [REQ: write-spec-generates-modular-output]
- [ ] 4.2 Generate `docs/spec.md` with overview, conventions, directives, checklist, and relative links to feature files [REQ: write-spec-generates-modular-output]
- [ ] 4.2b If `docs/spec.md` already exists, ask user: overwrite / update in-place / create as docs/spec-v2.md [REQ: write-spec-generates-modular-output]
- [ ] 4.3 Generate `docs/features/<feature>.md` per feature with REQ-IDs and scenarios [REQ: write-spec-generates-modular-output]
- [ ] 4.4 Generate `docs/catalog/*.md` for structured seed data when Prisma detected [REQ: write-spec-generates-modular-output]
- [ ] 4.5 For small projects (1-2 features), generate single `docs/spec.md` with all sections inline [REQ: write-spec-generates-modular-output]

## 5. Anti-Pattern Detection

- [ ] 5.1 Before assembly, scan all requirement sections for fenced code blocks — warn user [REQ: anti-pattern-detection-before-assembly]
- [ ] 5.2 Scan for file paths (`src/`, `lib/`, `.ts`, `.tsx`, `.py` extensions) in requirement sections — warn user [REQ: anti-pattern-detection-before-assembly]
- [ ] 5.3 Scan for placeholder seed data ("Product 1", "Test Item", "Lorem ipsum") — warn user [REQ: anti-pattern-detection-before-assembly]
- [ ] 5.4 Block assembly if any requirement lacks a WHEN/THEN scenario — prompt user to add one [REQ: anti-pattern-detection-before-assembly]

## 6. REQ-ID and Scenario Enforcement

- [ ] 6.1 Auto-generate REQ-IDs in format `REQ-<DOMAIN>-<NN>` from feature name + requirement order (compatible with decomposer's `REQ-*` regex in templates.py) [REQ: req-id-and-scenario-enforcement]
- [ ] 6.2 Ensure every requirement has `### Requirement:` header with REQ-ID [REQ: req-id-and-scenario-enforcement]
- [ ] 6.3 Ensure every requirement has at least one `#### Scenario:` with WHEN/THEN format [REQ: req-id-and-scenario-enforcement]

## 7. Verification Checklist

- [ ] 7.1 Auto-generate `## Verification Checklist` section from requirements [REQ: verification-checklist-auto-generation]
- [ ] 7.2 Group checklist items by feature/domain [REQ: verification-checklist-auto-generation]
- [ ] 7.3 Each requirement → at least one `- [ ]` checkbox item [REQ: verification-checklist-auto-generation]

## 8. Orchestrator Directives

- [ ] 8.1 Add `## Orchestrator Directives` section to spec output with yaml block [REQ: orchestrator-directives-section]
- [ ] 8.2 Ask user for max_parallel, review_before_merge, e2e_mode (or use defaults: 3, true, per_change) [REQ: orchestrator-directives-section]

## 9. Documentation Update

- [ ] 9.1 Update `docs/guide/writing-specs.md` with new modular structure and anti-pattern guidance [REQ: write-spec-generates-modular-output]
- [ ] 9.2 Add the E2E scaffold spec (tests/e2e/scaffolds/craftbrew/) as reference example in the guide [REQ: write-spec-generates-modular-output]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN CoreProfile.spec_sections() called THEN returns 4 core sections [REQ: projecttype-abc-has-spec-sections-method, scenario: core-profile-returns-core-sections]
- [ ] AC-2: WHEN WebProjectType.spec_sections() called THEN returns core + 7 web sections [REQ: projecttype-abc-has-spec-sections-method, scenario: web-profile-extends-core-sections]
- [ ] AC-3: WHEN user describes 3+ features on web project THEN modular output generated [REQ: write-spec-generates-modular-output, scenario: web-project-with-multiple-features]
- [ ] AC-4: WHEN requirement has code block THEN warning shown [REQ: anti-pattern-detection-before-assembly, scenario: code-block-detected-in-requirement]
- [ ] AC-5: WHEN requirement has no scenario THEN assembly blocked [REQ: anti-pattern-detection-before-assembly, scenario: requirement-without-scenario]
- [ ] AC-6: WHEN spec assembled THEN verification checklist present grouped by domain [REQ: verification-checklist-auto-generation, scenario: checklist-generated-from-requirements]
