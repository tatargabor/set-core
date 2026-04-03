## 1. Create templates/core/rules/ directory

- [x] 1.1 Create `templates/core/rules/` directory [REQ: deploy-rules-to-project]
- [x] 1.2 Copy `cross-cutting-checklist.md` from `.claude/rules/` to `templates/core/rules/` [REQ: deploy-rules-to-project]
- [x] 1.3 Copy `design-bridge.md` from `.claude/rules/` to `templates/core/rules/` [REQ: deploy-rules-to-project]
- [x] 1.4 Copy `sentinel-autonomy.md` from `.claude/rules/` to `templates/core/rules/` [REQ: deploy-rules-to-project]
- [x] 1.5 Copy `readme-updates.md` from `.claude/rules/` to `templates/core/rules/` [REQ: deploy-rules-to-project]

## 2. Update deploy.sh rules section

- [x] 2.1 In `_deploy_skills()` (line 175), change `src_rules` from `$SET_TOOLS_ROOT/.claude/rules` to `$SET_TOOLS_ROOT/templates/core/rules` [REQ: deploy-rules-to-project]
- [x] 2.2 Replace `find "$src_rules" -maxdepth 1 -name '*.md' -print0` with `find "$src_rules" -name '*.md' -print0` (remove maxdepth hack) [REQ: deploy-rules-to-project]
- [x] 2.3 Remove the self-deploy guard (`is_self` check, lines 178-181) — `templates/core/rules/` will never equal the target `.claude/rules/` so the check is unnecessary. Or keep it as safety — decide at implementation. [REQ: deploy-rules-to-project]
- [x] 2.4 Update the comment on line 184 to reflect new source path [REQ: deploy-rules-to-project]

## 3. Remove old cross-cutting-checklist special deploy

- [x] 3.1 Remove `templates/cross-cutting-checklist.md` file (superseded by `templates/core/rules/cross-cutting-checklist.md`) [REQ: deploy-rules-to-project]
- [x] 3.2 Remove lines 111-121 in `bin/set-project` `scaffold_wt_directory()` that special-case deploy `cross-cutting-checklist.md` without prefix [REQ: deploy-rules-to-project]

## 4. Verify

- [x] 4.1 Run `set-project init` on a test project and confirm exactly 4 `set-*.md` files appear in `.claude/rules/` [REQ: deploy-rules-to-project]
- [x] 4.2 Confirm `modular-architecture.md` and `openspec-artifacts.md` do NOT appear in consumer `.claude/rules/` [REQ: only-template-core-rules-are-deployed]
- [x] 4.3 Confirm set-core self-deploy (`set-project init` in set-core dir) does not copy rules [REQ: deploy-rules-to-project]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `set-project init` runs on a new project THEN `.claude/rules/` is created with `set-*.md` files from `templates/core/rules/` [REQ: deploy-rules-to-project, scenario: first-init-deploys-core-rules-from-templates]
- [x] AC-2: WHEN `set-project init` runs on existing project with custom rules THEN only `set-*` files are overwritten, custom rules untouched [REQ: deploy-rules-to-project, scenario: re-init-updates-rules-without-touching-project-rules]
- [x] AC-3: WHEN `set-project init` runs in set-core repo THEN rules are NOT copied [REQ: deploy-rules-to-project, scenario: self-deploy-skips-rules]
- [x] AC-4: WHEN `.claude/rules/` has `modular-architecture.md` THEN it is NOT deployed to consumer project [REQ: deploy-rules-to-project, scenario: only-template-core-rules-are-deployed]
