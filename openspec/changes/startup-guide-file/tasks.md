## 1. Profile ABC

- [x] 1.1 Add `generate_startup_file(self, project_path: str) -> str` method to `ProjectType` ABC in `lib/set_orch/profile_types.py` [REQ: profile-abc-defines-startup-file-generation]
- [x] 1.2 Add default empty-string implementation in `CoreProfile` [REQ: profile-abc-defines-startup-file-generation]

## 2. Web Profile Implementation

- [x] 2.1 Add `generate_startup_file()` to `WebProjectType` in `modules/web/set_project_web/project_type.py` — move detection logic from `dispatcher.py:generate_startup_guide()` [REQ: web-profile-detects-project-stack-for-start-md]
- [x] 2.2 Use `##` section headings (Install, Dev Server, Database, Tests, E2E Tests) with bash code blocks [REQ: start-md-has-stable-section-structure]
- [x] 2.3 Add auto-generated header comment to START.md output [REQ: start-md-has-stable-section-structure]

## 3. Dispatcher Update

- [x] 3.1 Replace `generate_startup_guide()` call with `profile.generate_startup_file()` in dispatcher dispatch flow [REQ: dispatcher-appends-startup-guide-to-worktree-claude-md]
- [x] 3.2 Write result to `START.md` instead of appending to CLAUDE.md [REQ: dispatcher-appends-startup-guide-to-worktree-claude-md]
- [x] 3.3 Delete old `generate_startup_guide()` and `append_startup_guide_to_claudemd()` from `dispatcher.py` [REQ: startup-guide-content-detection]

## 4. Merger Post-Merge Regeneration

- [x] 4.1 After successful merge in `merger.py`, load profile and call `generate_startup_file()` on main project path [REQ: post-merge-regeneration]
- [x] 4.2 Write result to `START.md` in project root (overwrite) [REQ: post-merge-regeneration]
- [x] 4.3 Handle profile-not-loadable gracefully (skip without error) [REQ: post-merge-regeneration]

## 5. Deploy CLAUDE.md Reference

- [x] 5.1 Add `## Getting Started` managed section to `_deploy_memory()` in `deploy.sh` that references START.md [REQ: claude-md-references-start-md]
- [x] 5.2 Idempotent: skip if section already exists [REQ: claude-md-references-start-md]

## 6. Cleanup

- [x] 6.1 Remove `_detect_package_manager()` from `dispatcher.py` if no other callers remain (check for other usages first) [REQ: startup-guide-content-detection]
  - NOTE: Still used by `_sync_deps_after_main_merge()` (line 201) and legacy bootstrap (line 382). Kept.

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `generate_startup_file()` called on WebProjectType with `package.json` dev script THEN returns markdown with install and dev server sections [REQ: profile-abc-defines-startup-file-generation, scenario: web-profile-generates-startup-file]
- [x] AC-2: WHEN `generate_startup_file()` called on CoreProfile THEN returns empty string [REQ: profile-abc-defines-startup-file-generation, scenario: unknown-project-type-returns-empty]
- [x] AC-3: WHEN project has pnpm + next + prisma + playwright THEN START.md has Install, Dev Server, Database, Tests, E2E Tests sections [REQ: web-profile-detects-project-stack-for-start-md, scenario: full-stack-nextjs-project]
- [x] AC-4: WHEN dispatcher dispatches and no START.md exists THEN profile generates and writes START.md [REQ: dispatcher-appends-startup-guide-to-worktree-claude-md, scenario: claude-md-has-no-startup-section]
- [x] AC-5: WHEN set-project init runs and CLAUDE.md has no Getting Started section THEN managed reference section is appended [REQ: claude-md-references-start-md, scenario: claude-md-gets-reference-on-init]
- [x] AC-6: WHEN a change merges to main THEN merger regenerates START.md with current profile [REQ: post-merge-regeneration, scenario: merge-adds-prisma-start-md-updated]
