# Tasks: design-brief-dispatch

## 1. FigmaMakePromptParser — design_parser.py

- [x] 1.1 Add `FigmaMakePromptParser(DesignParser)` class to `lib/set_orch/design_parser.py` — parse `## N. TITLE` + fenced code block structure, extract page name from title (normalize "HOMEPAGE — DESKTOP (1280px)" → "Home"), skip instructional sections [REQ: parse-figma-make-prompt-files]
- [x] 1.2 Implement section merging — combine desktop+mobile sections for same page into one `PageSpec` with subsections [REQ: parse-figma-make-prompt-files]
- [x] 1.3 Extract tokens from prompt content — color hex values, font names, spacing values into `DesignSystem.tokens` with deduplication [REQ: parse-figma-make-prompt-files]
- [x] 1.4 Update `get_parser()` factory — detect figma.md format (has `## \d+\.` numbered sections with fenced code blocks), return `FigmaMakePromptParser` [REQ: parse-figma-make-prompt-files]

## 2. Design Brief Output — design_parser.py

- [x] 2.1 Add `to_brief_markdown()` method to `DesignSystem` dataclass — generate `## Page: <name>` sections with condensed visual descriptions, preserving actionable detail (dimensions, hex codes, CTA text, component counts), removing Figma meta-instructions [REQ: generate-design-brief-output]
- [x] 2.2 Update `main()` CLI — when parser produces pages with visual descriptions, write `design-brief.md` alongside `design-system.md`; print summary with brief line count [REQ: set-design-sync-outputs-both-files]

## 3. Per-Change Design File — dispatcher.py

- [x] 3.1 Add `_find_design_brief()` helper to `dispatcher.py` — search standard paths (`docs/design-brief.md`, `design-brief.md`, `docs/design/design-brief.md`), return path or None [REQ: generate-per-change-design-file-at-dispatch]
- [x] 3.2 Add `_build_per_change_design()` to `dispatcher.py` — call bridge.sh `design_brief_for_dispatch()` with scope text, write result + tokens + components to `openspec/changes/<name>/design.md` [REQ: generate-per-change-design-file-at-dispatch]
- [x] 3.3 Integrate into `dispatch_single_change()` — after worktree setup, call `_build_per_change_design()` if design-brief.md exists; falls back to existing inline injection if not [REQ: dispatch-without-design-brief-backwards-compatible]
- [x] 3.4 Update `_build_input_content()` — when per-change design.md exists, include tokens inline + "Read design.md for visual specs" instruction instead of full inline Design Context [REQ: input-md-references-per-change-design-file]

## 4. Bridge.sh — scope matching

- [x] 4.1 Add `design_brief_for_dispatch()` function to `lib/design/bridge.sh` — read design-brief.md, match `## Page: <name>` sections against scope using page-name + alias matching, output matched sections to stdout [REQ: page-matching-uses-precise-page-name-keywords]
- [x] 4.2 Define default page alias map in bridge.sh — dict of page name → list of phrase aliases (e.g., Home → "homepage,hero banner,featured coffees", Login → "login,register,belepes,regisztracio") [REQ: aliases-provide-additional-matching]
- [x] 4.3 Add profile hook for custom aliases — `design_page_aliases()` method on `ProjectType` ABC in `profile_types.py`, default returns empty (use bridge.sh defaults); WebProjectType can override for domain-specific terms [REQ: abstract-dispatch-mechanism-supports-profile-customization]

## 5. Scaffold & Runner Updates

- [x] 5.1 Generate `design-brief.md` for craftbrew scaffold — run `set-design-sync --input figma.md` or manually create from figma.md content with `## Page: <name>` sections, commit to `tests/e2e/scaffolds/craftbrew/docs/` [REQ: generate-design-brief-output]
- [x] 5.2 Clean up craftbrew `design-system.md` — remove skeletal Page Layouts bullet lists (now in design-brief.md), keep Design Tokens + Components index + Raw Theme CSS [REQ: generate-design-brief-output]
- [x] 5.3 Update `run-craftbrew.sh` — add `set-design-sync` call after spec copy to generate design-brief.md if not already present in scaffold [REQ: set-design-sync-outputs-both-files]

## 6. Documentation & Rules

- [x] 6.1 Update `.claude/rules/design-bridge.md` — add reference to `design-brief.md` and per-change `design.md`, update agent instructions to read these files before implementing UI [REQ: dispatch-without-design-brief-backwards-compatible]
- [x] 6.2 Update design pipeline docs — document new file structure (design-system.md for tokens, design-brief.md for visuals, per-change design.md for agents), update examples [REQ: dispatch-without-design-brief-backwards-compatible]

## 7. Tests

- [x] 7.1 Unit test `FigmaMakePromptParser` — test parsing numbered sections, page name normalization, desktop+mobile merging, token extraction, instructional section skipping [REQ: parse-figma-make-prompt-files]
- [x] 7.2 Unit test `to_brief_markdown()` — test page section generation, actionable detail preservation, meta-instruction removal [REQ: generate-design-brief-output]
- [x] 7.3 Unit test `design_brief_for_dispatch()` — test page matching with precise aliases, false positive avoidance, backwards compatibility when no brief exists [REQ: page-matching-uses-precise-page-name-keywords]
- [x] 7.4 Unit test per-change design.md generation — test file writing, input.md reference, fallback to inline when no brief [REQ: generate-per-change-design-file-at-dispatch]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `FigmaMakePromptParser.parse()` is called with a figma.md file THEN each numbered section with code block is parsed into a PageSpec [REQ: parse-figma-make-prompt-files, scenario: parse-well-structured-figma-md]
- [x] AC-2: WHEN prompt sections contain color/font/spacing values THEN they are extracted into DesignSystem.tokens with deduplication [REQ: parse-figma-make-prompt-files, scenario: extract-design-tokens-from-prompt-content]
- [x] AC-3: WHEN desktop and mobile sections exist for same page THEN they are merged into one PageSpec [REQ: parse-figma-make-prompt-files, scenario: handle-combined-desktop-mobile-sections]
- [x] AC-4: WHEN `to_brief_markdown()` is called THEN output has `## Page: <name>` sections with concrete design values [REQ: generate-design-brief-output, scenario: generate-brief-with-page-sections]
- [x] AC-5: WHEN `set-design-sync --input figma.md` is run THEN both design-system.md and design-brief.md are generated [REQ: generate-design-brief-output, scenario: set-design-sync-outputs-both-files]
- [x] AC-6: WHEN dispatch runs with design-brief.md present THEN per-change design.md is written with tokens + matched pages [REQ: generate-per-change-design-file-at-dispatch, scenario: dispatch-with-design-brief-present]
- [x] AC-7: WHEN dispatch runs without design-brief.md THEN existing inline injection works unchanged [REQ: generate-per-change-design-file-at-dispatch, scenario: dispatch-without-design-brief-backwards-compatible]
- [x] AC-8: WHEN scope contains "product reviews rating" THEN AdminProducts page is NOT matched [REQ: page-matching-uses-precise-page-name-keywords, scenario: precise-matching-avoids-over-matching]
- [x] AC-9: WHEN per-change design.md exists THEN input.md contains tokens inline + file reference [REQ: generate-per-change-design-file-at-dispatch, scenario: input-md-references-per-change-design-file]
- [x] AC-10: WHEN profile implements design_page_aliases() THEN dispatcher uses profile aliases [REQ: abstract-dispatch-mechanism-supports-profile-customization, scenario: profile-can-override-matching-logic]
