# Tasks: mobile-project-type

## 0. Core fix: MRO-aware template resolution

- [x] 0.1 Fix `get_template_dir()` in `lib/set_orch/profile_types.py` to walk `type(self).__mro__` instead of using `type(self)` directly — enables inherited templates to resolve to the parent module's directory [REQ: module-metadata-and-inheritance]
- [x] 0.2 Add unit test for MRO template resolution: `MobileProjectType.get_template_dir("nextjs")` resolves to `modules/web/` path [REQ: module-metadata-and-inheritance]

## 0b. Developer guide

- [x] 0b.1 Create `modules/dev-guide.md` documenting inheritance patterns, override strategies, template system, and new module checklist [REQ: module-dev-guide]

## 1. Module scaffold

- [x] 1.1 Create `modules/mobile/` directory structure: `set_project_mobile/__init__.py`, `project_type.py`, `gates.py`, `planning_rules.txt` [REQ: module-metadata-and-inheritance]
- [x] 1.2 Create `modules/mobile/pyproject.toml` with entry point `mobile = "set_project_mobile:MobileProjectType"` under `set_tools.project_types` [REQ: module-metadata-and-inheritance]
- [x] 1.3 Install module in editable mode: `pip install -e modules/mobile` [REQ: module-metadata-and-inheritance]

## 2. MobileProjectType class

- [x] 2.1 Create `MobileProjectType(WebProjectType)` with `info` property returning `name="mobile"`, `version="0.1.0"`, `parent="web"` [REQ: module-metadata-and-inheritance]
- [x] 2.2 Implement `get_templates()` returning `TemplateInfo(id="capacitor-nextjs", ...)` [REQ: template-registration]
- [x] 2.3 Implement `get_verification_rules()` — call `super().get_verification_rules()` + add Capacitor config consistency rule and plugin version tracking rule [REQ: capacitor-config-verification, REQ: capacitor-plugin-tracking]
- [x] 2.4 Implement `get_orchestration_directives()` — call `super().get_orchestration_directives()` + add `cap sync` post-merge directive and native config serialization directive [REQ: capacitor-sync-directive, REQ: native-config-serialization]
- [x] 2.5 Implement `detect_build_command()` — check for `ios/App/` and return combined web build + cap sync command, fall back to super() [REQ: ios-build-detection]
- [x] 2.6 Implement `detect_e2e_command()` — inherit from web (Playwright), no override needed [REQ: module-metadata-and-inheritance]
- [x] 2.7 Write `planning_rules.txt` with mobile-specific decomposition guidance (separate native vs web changes, platform testing, Capacitor plugin changes) [REQ: planning-rules-for-mobile]
- [x] 2.8 Implement `planning_rules()` — load from `planning_rules.txt` [REQ: planning-rules-for-mobile]
- [x] 2.9 Export `MobileProjectType` from `__init__.py` [REQ: module-metadata-and-inheritance]

## 3. Gates

- [x] 3.1 Create `gates.py` with `MobileXcodeBuildGate` — runs `xcodebuild build` for iOS projects when `ios/App/` is modified [REQ: ios-build-detection]
- [x] 3.2 Implement `register_gates()` — inherit web gates + add Xcode build gate [REQ: ios-build-detection]

## 4. Template: capacitor-nextjs

- [x] 4.1 Create `templates/capacitor-nextjs/` directory structure [REQ: template-registration]
- [x] 4.2 Create `manifest.yaml` — core files, protected files, optional modules [REQ: manifest-definition]
- [x] 4.3 Create `capacitor.config.ts` template with `webDir` pointing to Next.js output [REQ: capacitor-config-template]
- [x] 4.4 Create `rules/capacitor-conventions.md` — Capacitor plugin usage, native bridge patterns, platform-specific code organization [REQ: mobile-convention-rules]
- [x] 4.5 Create `rules/native-bridge.md` — guidelines for Capacitor ↔ native code communication [REQ: mobile-convention-rules]
- [x] 4.6 Create `project-knowledge.yaml` with mobile-specific context [REQ: template-registration]

## 5. Tests

- [x] 5.1 Create `tests/test_project_type.py` — test `info`, `get_templates()`, `get_verification_rules()`, `get_orchestration_directives()`, inheritance from WebProjectType [REQ: module-metadata-and-inheritance]
- [x] 5.2 Create `tests/test_integration.py` — test that all profile methods are callable without error [REQ: module-metadata-and-inheritance]
- [x] 5.3 Test template directory exists and contains required files [REQ: template-registration]
- [x] 5.4 Test `detect_build_command()` with and without `ios/App/` directory [REQ: ios-build-detection]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a project has `project-type.yaml` with `type: mobile` THEN `load_profile()` resolves to `MobileProjectType` [REQ: module-metadata-and-inheritance, scenario: profile-resolution]
- [x] AC-2: WHEN `get_verification_rules()` is called THEN result includes all WebProjectType rules plus mobile-specific rules [REQ: module-metadata-and-inheritance, scenario: inherited-web-rules-are-present]
- [x] AC-3: WHEN a project contains `capacitor.config.ts` THEN verification checks that `webDir` points to existing build output [REQ: capacitor-config-verification, scenario: capacitor-config-exists]
- [x] AC-4: WHEN a change modifies `capacitor.config.ts` THEN `npx cap sync` is triggered as post-merge action [REQ: capacitor-sync-directive, scenario: config-change-triggers-sync]
- [x] AC-5: WHEN `ios/App/App.xcodeproj` exists THEN `detect_build_command()` returns command including `npx cap sync ios` [REQ: ios-build-detection, scenario: ios-project-detected]
- [x] AC-6: WHEN no `ios/` directory exists THEN module falls back to web-only build detection [REQ: ios-build-detection, scenario: no-ios-project]
- [x] AC-7: WHEN two changes both modify files under `ios/App/` THEN directive serializes their execution [REQ: native-config-serialization, scenario: parallel-native-changes-serialized]
- [x] AC-8: WHEN `get_templates()` is called THEN result includes `TemplateInfo` with `id="capacitor-nextjs"` [REQ: template-registration, scenario: template-listed]
- [x] AC-9: WHEN template is deployed THEN `capacitor.config.ts` is created with correct `webDir` [REQ: capacitor-config-template, scenario: config-file-deployed]
- [x] AC-10: WHEN template is deployed THEN `.claude/rules/capacitor-conventions.md` exists [REQ: mobile-convention-rules, scenario: rules-deployed]
