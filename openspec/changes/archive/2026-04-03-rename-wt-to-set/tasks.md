# Tasks: Rename wt/ to set/

## 1. Template Directory Rename
- [x] 1.1 Rename templates/nextjs/wt/ → set/ [REQ: project-config-directory-naming]
- [x] 1.2 Rename templates/spa/wt/ → set/ [REQ: project-config-directory-naming]
- [x] 1.3 Update manifest.yaml files [REQ: project-config-directory-naming]

## 2. bin/set-project
- [x] 2.1 Rename function scaffold_wt_directory → scaffold_set_directory [REQ: project-config-directory-naming]
- [x] 2.2 Bulk replace all wt/ path references [REQ: project-config-directory-naming]
- [x] 2.3 Add migration: wt/ → set/ rename [REQ: project-config-directory-naming]
- [x] 2.4 Update .gitignore scaffold [REQ: project-config-directory-naming]

## 3. Python Code
- [x] 3.1 Bulk replace "wt/" → "set/" in lib/set_orch/ [REQ: project-config-directory-naming]
- [x] 3.2 Add backwards compat fallback in merger.py [REQ: project-config-directory-naming]
- [x] 3.3 Update modules/web Python files [REQ: project-config-directory-naming]

## 4. Shell Scripts
- [x] 4.1 Update all lib/*.sh files [REQ: project-config-directory-naming]

## 5. Claude Skills & Commands
- [x] 5.1 Update decompose and harvest skills [REQ: project-config-directory-naming]
- [x] 5.2 Update decompose command [REQ: project-config-directory-naming]

## 6. Tests
- [x] 6.1 Update unit test files [REQ: project-config-directory-naming]
- [x] 6.2 Update integration test scripts [REQ: project-config-directory-naming]
- [x] 6.3 Update E2E runner scripts [REQ: project-config-directory-naming]

## 7. Verify
- [x] 7.1 Python import check — 0 errors [REQ: project-config-directory-naming]
- [x] 7.2 Grep verify: 0 remaining wt/ in active code [REQ: project-config-directory-naming]
- [x] 7.3 Web build succeeds [REQ: project-config-directory-naming]

## Acceptance Criteria
- [x] AC-1: set-project init creates set/ dir [REQ: project-config-directory-naming]
- [x] AC-2: Legacy wt/ auto-migrated to set/ [REQ: project-config-directory-naming]
- [x] AC-3: Backwards compat fallback to wt/ [REQ: project-config-directory-naming]
