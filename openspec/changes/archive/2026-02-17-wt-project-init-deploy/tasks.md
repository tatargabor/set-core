## 1. Add deploy function to set-project

- [x] 1.1 Add `deploy_set_tools` helper function that copies `.claude/commands/wt/` and `.claude/skills/wt/` from the set-core repo to the target project, and calls `wt-deploy-hooks`
- [x] 1.2 Resolve set-core repo root from `BASH_SOURCE[0]` (follow symlinks to find the real bin dir, then go up one level)

## 2. Modify cmd_init for deploy-on-init

- [x] 2.1 Change the "already registered" path to skip registration but proceed to deploy (instead of `exit 0`)
- [x] 2.2 Call `deploy_set_tools` after successful registration (new project) and after skip (existing project)
- [x] 2.3 Print deployment summary showing what was deployed/updated

## 3. Update install.sh

- [x] 3.1 Remove global symlink creation from `install_skills()` (the `ln -sfn` for `commands/wt` and `skills/wt`)
- [x] 3.2 Change `install_project_hooks()` to call `set-project init` for each registered project instead of `wt-deploy-hooks` directly
