## 1. Config Directive

- [ ] 1.1 Add `"design_source_path": None` to `DIRECTIVE_DEFAULTS` in `lib/set_orch/config.py` [REQ: standalone-orchestration-config-file]
- [ ] 1.2 Add `design_source_path` string validator to `_VALIDATORS` in `lib/set_orch/config.py` [REQ: standalone-orchestration-config-file]

## 2. Design Source Detection

- [ ] 2.1 Modify `detect_design_source()` in `modules/web/set_project_web/base.py` to check `design_source_path` directive first, returning `"v0-external"` if the external path exists [REQ: external-design-directory-mounting]
- [ ] 2.2 Add `_resolve_design_source_path(project_path, directives)` helper that reads the directive, expands `~`, validates existence, and returns resolved Path or None [REQ: external-design-directory-mounting]

## 3. Worktree Mounting

- [ ] 3.1 Modify `_deploy_v0_export_to_worktree()` in `lib/set_orch/dispatcher.py` to accept an optional `source_path` parameter instead of hardcoding `project_path / "v0-export"` [REQ: external-design-directory-mounting]
- [ ] 3.2 Update the dispatcher's `dispatch_change()` to resolve the design source path from directives and pass it to the deploy function [REQ: external-design-directory-mounting]

## 4. Design Token Extraction

- [ ] 4.1 Implement `_extract_css_tokens(globals_css_path)` that parses `:root { }`, `.dark { }`, and `@theme { }` blocks and extracts `--variable: value` pairs [REQ: design-token-extraction]
- [ ] 4.2 Implement `_format_design_tokens(tokens)` that renders extracted tokens as a markdown `## Design Tokens` section grouped by light/dark theme [REQ: design-token-extraction]
- [ ] 4.3 Wire token extraction into `get_design_dispatch_context()` in `modules/web/set_project_web/base.py` — call extraction when design source is `"v0-external"` [REQ: design-token-extraction]

## 5. Design Rule Injection

- [ ] 5.1 Implement `_inject_external_design_rules(external_path, wt_path)` that symlinks `.set-designer/design-rules/*.md` files into `<wt>/.claude/rules/design-<filename>` [REQ: design-rule-injection]
- [ ] 5.2 Call `_inject_external_design_rules()` from `dispatch_change()` after design source deployment when source is `"v0-external"` [REQ: design-rule-injection]

## 6. Design Bridge Rule Update

- [ ] 6.1 Update `templates/core/rules/set-design-bridge.md` to add a scenario for external design sources — reference `v0-export` symlink and injected design rules [REQ: design-bridge-rule-for-agents]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN `design_source_path` is set to `~/projects/consumer-app-design` and directory exists THEN dispatcher creates symlink `<wt>/v0-export → <resolved-path>` [REQ: external-design-directory-mounting, scenario: external-design-path-configured-and-exists]
- [ ] AC-2: WHEN `design_source_path` is set but directory missing THEN log WARNING and fall back to in-project detection [REQ: external-design-directory-mounting, scenario: external-design-path-configured-but-missing]
- [ ] AC-3: WHEN `design_source_path` not set THEN use existing in-project v0-export logic unchanged [REQ: external-design-directory-mounting, scenario: no-external-path-configured]
- [ ] AC-4: WHEN `globals.css` contains `:root` and `.dark` blocks with CSS custom properties THEN extract all `--variable: value` pairs grouped by theme [REQ: design-token-extraction, scenario: standard-shadcn-ui-globals-css]
- [ ] AC-5: WHEN `globals.css` not found in external design directory THEN return empty string with debug log [REQ: design-token-extraction, scenario: globals-css-not-found]
- [ ] AC-6: WHEN external design repo has `.set-designer/design-rules/` with `.md` files THEN symlink each into `<wt>/.claude/rules/design-<filename>` [REQ: design-rule-injection, scenario: design-rules-directory-exists]
- [ ] AC-7: WHEN external design repo has no `.set-designer/design-rules/` THEN skip silently with debug log [REQ: design-rule-injection, scenario: design-rules-directory-missing]
- [ ] AC-8: WHEN a design rule file name conflicts with existing rule THEN prefix with `design-` and log warning [REQ: design-rule-injection, scenario: rule-file-name-collision]
