## 1. IKP Bridge Module

- [x] 1.1 Create `lib/set_orch/ikp_bridge.py` with module docstring, logging setup, and `_ikp_available()` function that tries importing ikp and caches the result [REQ: graceful-degradation]
- [x] 1.2 Implement `IkpConfig` dataclass with `packs: list[str]`, `packs_dir: Path`, `language: str`, `ikp_version: str` fields [REQ: ikp-config-loading]
- [x] 1.3 Implement `load_ikp_config(project_path)` — reads `.ikp.yaml`, expands `~` in `packs_dir`, returns `IkpConfig` or None [REQ: ikp-config-loading]
- [x] 1.4 Implement `has_ikp_pipeline(project_path, directives)` — checks directive, package availability, and config presence [REQ: ikp-pipeline-detection]
- [x] 1.5 Implement `get_context_for_phase(phase, pack_names, ikp_config)` — loads appropriate layers per phase (decompose→L1+L2, dispatch→L1+L3, verify→L1+L4), returns markdown string [REQ: phase-based-context-loading]
- [x] 1.6 Implement `inject_rules_for_change(wt_path, pack_names, phase, language, packs_dir)` — writes `ikp-<pack>.md` files into `<wt>/.claude/rules/` [REQ: rule-file-injection]

## 2. Config Directive

- [x] 2.1 Add `"ikp_pipeline": "auto"` to `DIRECTIVE_DEFAULTS` in `lib/set_orch/config.py` [REQ: standalone-orchestration-config-file]
- [x] 2.2 Add `ikp_pipeline` validator to `_VALIDATORS` — accepts `"auto"` or `"none"` [REQ: standalone-orchestration-config-file]

## 3. Optional Dependency

- [x] 3.1 Add `ikp` to `[project.optional-dependencies]` in `pyproject.toml` [REQ: graceful-degradation]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `.ikp.yaml` exists with `packs`, `packs_dir`, and `language` fields THEN `load_ikp_config()` returns an `IkpConfig` with parsed values and expanded path [REQ: ikp-config-loading, scenario: valid-config-file]
- [x] AC-2: WHEN no `.ikp.yaml` exists THEN `load_ikp_config()` returns None without logging an error [REQ: ikp-config-loading, scenario: missing-config-file]
- [x] AC-3: WHEN `packs_dir` is `~/code2/ikp/packs` THEN the system expands to absolute path [REQ: ikp-config-loading, scenario: config-with-tilde-in-packs-dir]
- [x] AC-4: WHEN directive is `"auto"`, ikp installed, and `.ikp.yaml` has packs THEN `has_ikp_pipeline()` returns True [REQ: ikp-pipeline-detection, scenario: all-conditions-met]
- [x] AC-5: WHEN directive is `"none"` THEN `has_ikp_pipeline()` returns False without further checks [REQ: ikp-pipeline-detection, scenario: directive-disabled]
- [x] AC-6: WHEN ikp package not importable THEN `has_ikp_pipeline()` returns False with debug log [REQ: ikp-pipeline-detection, scenario: package-not-installed]
- [x] AC-7: WHEN phase is `"decompose"` THEN load L1+L2 and return per-pack markdown with capabilities and pitfalls [REQ: phase-based-context-loading, scenario: decompose-phase]
- [x] AC-8: WHEN phase is `"dispatch"` with language `"typescript"` THEN load L1+L3 filtered to typescript [REQ: phase-based-context-loading, scenario: dispatch-phase]
- [x] AC-9: WHEN phase is `"verify"` THEN load L4+L1 with sandbox setup and edge cases [REQ: phase-based-context-loading, scenario: verify-phase]
- [x] AC-10: WHEN requested pack not found in `packs_dir` THEN log warning and skip without exception [REQ: phase-based-context-loading, scenario: pack-not-found]
- [x] AC-11: WHEN `inject_rules_for_change()` called with pack `"billingo"` THEN create `<wt>/.claude/rules/ikp-billingo.md` with metadata and L3 content [REQ: rule-file-injection, scenario: single-pack-injection]
- [x] AC-12: WHEN ikp package raises ImportError during operation THEN function returns default value and logs WARNING [REQ: graceful-degradation, scenario: import-error-during-operation]
- [x] AC-13: WHEN a pack's `pack.yaml` is malformed THEN log warning, skip pack, continue with others [REQ: graceful-degradation, scenario: corrupted-pack-file]
