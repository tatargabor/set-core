## 1. Safety checks in wt-close

- [ ] 1.1 Remove `--force` flag parsing and all related code paths from `bin/wt-close`
- [ ] 1.2 Make uncommitted changes check unconditional (always block, no bypass)
- [ ] 1.3 Add unmerged/unpushed commit detection function: check if branch has commits not in master (`git log master..branch`) and not on remote (`git log origin/branch..branch`)
- [ ] 1.4 Integrate unmerged commit detection into interactive branch deletion flow — show warning with commit count, require explicit "yes" confirmation

## 2. Non-interactive flags

- [ ] 2.1 Add `--keep-branch` flag — close worktree without prompts, keep branch
- [ ] 2.2 Add `--delete-branch` flag — close worktree and delete branch, but fail with error if branch has unprotected commits (not in master AND not on remote)
- [ ] 2.3 Ensure `--keep-branch` and `--delete-branch` are mutually exclusive
- [ ] 2.4 Keep `--delete-remote` flag working with both interactive delete and `--delete-branch`

## 3. Update callers

- [ ] 3.1 Update GUI handler in `gui/control_center/mixins/handlers.py` to use `--keep-branch` instead of `--force`
- [ ] 3.2 Search for any other callers of `wt-close --force` in the codebase and update them

## 4. Shell completions and docs

- [ ] 4.1 Update `bin/wt-completions.bash` — remove `--force`, add `--keep-branch` and `--delete-branch`
- [ ] 4.2 Update `bin/wt-completions.zsh` — remove `--force`, add `--keep-branch` and `--delete-branch`
- [ ] 4.3 Update usage/help text in `wt-close` to document new flags and removed `--force`
