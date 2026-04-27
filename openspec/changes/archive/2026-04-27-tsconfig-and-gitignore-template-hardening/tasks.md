## 1. tsconfig patcher implementation

- [x] 1.1 Add module-level `REQUIRED_TSCONFIG_EXCLUDES = ("v0-export", "v0-export.*", "*.bak", "*.bak.*")` constant in `design_import_cli.py` [REQ: set-design-import-patches-tsconfig-exclude-on-every-run]
- [x] 1.2 Implement `_patch_tsconfig_excludes(scaffold: Path) -> list[str]` that reads `tsconfig.json`, computes missing patterns, appends them, and writes back with `json.dumps(..., indent=2)` + trailing newline when additions are non-empty; returns the list of added patterns [REQ: set-design-import-patches-tsconfig-exclude-on-every-run]
- [x] 1.3 Preserve order of pre-existing exclude entries (append new entries to the end) [REQ: set-design-import-patches-tsconfig-exclude-on-every-run]
- [x] 1.4 Emit INFO log listing the added patterns when the file is modified [REQ: set-design-import-patches-tsconfig-exclude-on-every-run]
- [x] 1.5 Emit DEBUG log when no patch is needed (idempotent path) [REQ: set-design-import-patches-tsconfig-exclude-on-every-run]
- [x] 1.6 Wrap the whole patcher in try/except so parse errors log a WARNING with file path + exception and do NOT raise [REQ: set-design-import-degrades-gracefully-on-malformed-tsconfig]
- [x] 1.7 When `tsconfig.json` is missing, log DEBUG and return an empty list without raising [REQ: set-design-import-degrades-gracefully-on-malformed-tsconfig]

## 2. CLI wiring

- [x] 2.1 Call `_patch_tsconfig_excludes(scaffold)` from `main()` in the `--regenerate-manifest` branch after the manifest is written [REQ: set-design-import-patches-tsconfig-exclude-on-every-run]
- [x] 2.2 Call `_patch_tsconfig_excludes(scaffold)` from `main()` in the full-import branch after `import_v0_git` / `import_v0_zip` returns (before the quality validator) [REQ: set-design-import-patches-tsconfig-exclude-on-every-run]

## 3. Gitignore template

- [x] 3.1 Add "Orchestration runtime journals" section to `modules/web/set_project_web/templates/nextjs/.gitignore` with the five entries (`journals/`, `orchestration-events-*.jsonl`, `set/orchestration/activity-detail-*.jsonl`, `set/orchestration/spec-coverage-history.jsonl`, `set/orchestration/e2e-manifest-history.jsonl`) [REQ: gitignore-covers-orchestration-runtime-journal-files]
- [x] 3.2 Verify the five entries do NOT overlap with `/.set/` already present in the gitignore (they sit at the project root, not inside `/.set/`) [REQ: gitignore-covers-orchestration-runtime-journal-files]

## 4. Tests

- [x] 4.1 New file `tests/unit/test_tsconfig_patcher.py` — stub scaffold with a minimal `tsconfig.json`, assert post-run exclude contains all four patterns [REQ: set-design-import-patches-tsconfig-exclude-on-every-run]
- [x] 4.2 Add test: pre-existing excludes preserved in order [REQ: set-design-import-patches-tsconfig-exclude-on-every-run]
- [x] 4.3 Add test: idempotent no-op when all patterns already present (file byte-identical before/after) [REQ: set-design-import-patches-tsconfig-exclude-on-every-run]
- [x] 4.4 Add test: partial pre-existing state ("v0-export" present, others missing) — only missing entries added [REQ: set-design-import-patches-tsconfig-exclude-on-every-run]
- [x] 4.5 Add test: malformed tsconfig (JSON5 comments) → WARNING logged, file unchanged, return value empty [REQ: set-design-import-degrades-gracefully-on-malformed-tsconfig]
- [x] 4.6 Add test: missing tsconfig.json → DEBUG logged, return value empty, no raise [REQ: set-design-import-degrades-gracefully-on-malformed-tsconfig]
- [x] 4.7 New file `tests/unit/test_nextjs_template_gitignore.py` — assert the five runtime-journal patterns are present in the template `.gitignore` [REQ: gitignore-covers-orchestration-runtime-journal-files]

## Acceptance Criteria (from spec scenarios)

### v0-design-import

- [x] AC-1: WHEN full import runs against stale tsconfig THEN exclude list contains the four v0-export patterns + INFO log names additions [REQ: set-design-import-patches-tsconfig-exclude-on-every-run, scenario: full-import-on-a-stale-tsconfig-patches-exclude]
- [x] AC-2: WHEN `--regenerate-manifest` runs against stale tsconfig THEN exclude list contains the four v0-export patterns + INFO log names additions [REQ: set-design-import-patches-tsconfig-exclude-on-every-run, scenario: regenerate-manifest-on-a-stale-tsconfig-patches-exclude]
- [x] AC-3: WHEN tsconfig already covers all patterns THEN file is byte-identical before/after and DEBUG log records no-op [REQ: set-design-import-patches-tsconfig-exclude-on-every-run, scenario: patch-is-idempotent-when-excludes-already-cover-the-patterns]
- [x] AC-4: WHEN pre-existing exclude is ["node_modules", "dist", "v0-export"] THEN post-patch preserves that order and appends missing patterns [REQ: set-design-import-patches-tsconfig-exclude-on-every-run, scenario: patch-preserves-the-order-of-pre-existing-exclude-entries]
- [x] AC-5: WHEN tsconfig has JSON5 comments THEN WARNING logged + file unchanged + rest of import continues [REQ: set-design-import-degrades-gracefully-on-malformed-tsconfig, scenario: tsconfig-with-json5-comments-triggers-warning]
- [x] AC-6: WHEN tsconfig.json missing THEN DEBUG logged + rest of import continues [REQ: set-design-import-degrades-gracefully-on-malformed-tsconfig, scenario: missing-tsconfig-is-tolerated]

### web-template-gitignore

- [x] AC-7: WHEN dispatcher writes journals/<change>.jsonl THEN git status does not list it [REQ: gitignore-covers-orchestration-runtime-journal-files, scenario: per-change-journal-directory-is-gitignored]
- [x] AC-8: WHEN event bus rotates cycle file THEN git status does not list it [REQ: gitignore-covers-orchestration-runtime-journal-files, scenario: rotated-orchestration-event-logs-are-gitignored]
- [x] AC-9: WHEN activity-detail writes cache jsonl THEN git status does not list it [REQ: gitignore-covers-orchestration-runtime-journal-files, scenario: activity-detail-cache-files-are-gitignored]
- [x] AC-10: WHEN coverage-history / e2e-manifest-history is appended THEN git status does not list those files [REQ: gitignore-covers-orchestration-runtime-journal-files, scenario: coverage-and-e2e-manifest-history-are-gitignored]
- [x] AC-11: WHEN consumer authors a hand-written file under set/orchestration/ THEN it is NOT automatically gitignored [REQ: gitignore-covers-orchestration-runtime-journal-files, scenario: other-files-under-set-orchestration-remain-tracked]
- [x] AC-12: WHEN `set-project init --project-type web --template nextjs` runs post-update THEN deployed .gitignore contains the new patterns [REQ: gitignore-covers-orchestration-runtime-journal-files, scenario: additions-ship-via-set-project-init]
