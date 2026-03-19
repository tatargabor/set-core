# Tasks: Add Row Context Menu & Improve New Dialog

## 1. New Worktree Dialog
- [x] 1.1 Create NewWorktreeDialog class
- [x] 1.2 Add project dropdown (load from projects.json)
- [x] 1.3 Add change ID input field
- [x] 1.4 Add preview labels (full path, branch name)
- [x] 1.5 Update preview on input change
- [x] 1.6 Replace old QInputDialog with new dialog
- [x] 1.7 Remove Base Branch (wt-new doesn't support it)

## 2. Context Menu Setup
- [x] 2.1 Enable context menu on QTableWidget
- [x] 2.2 Create show_row_context_menu method
- [x] 2.3 Get clicked row and worktree data

## 3. Top-Level Menu Actions
- [x] 3.1 Add "Focus Window" menu item
- [x] 3.2 Add "Open in Terminal" menu item
- [x] 3.3 Add "Open in File Manager" menu item
- [x] 3.4 Add "Copy Path" menu item
- [x] 3.5 Add "+ New Worktree..." menu item (pre-fills project)

## 4. Git Submenu
- [x] 4.1 Create Git submenu
- [x] 4.2 Add "Merge to..." with MergeDialog (stash, keep-branch options)
- [x] 4.3 Add "Merge from..." to pull changes from other branches
- [x] 4.4 Add "Push" (`git push`)
- [x] 4.5 Add "Pull" (`git pull`)
- [x] 4.6 Add "Fetch" (`git fetch`)

## 5. JIRA Submenu
- [x] 5.1 Create JIRA submenu (conditional on config)
- [x] 5.2 Add "Open Story" menu item
- [x] 5.3 Add "Log Work..." menu item
- [x] 5.4 Add "Sync Worklog" (`wt-jira auto --dry-run`)

## 6. Worktree Submenu
- [x] 6.1 Create Worktree submenu
- [x] 6.2 Add "Close" menu item
- [x] 6.3 Add "Push Branch" (`wt-push`)

## 7. Worktree Config Dialog
- [x] 7.1 Create WorktreeConfigDialog class
- [x] 7.2 Load .set-core/*.json config files
- [x] 7.3 Display configs in tabs (Jira, Confluence, etc.)
- [x] 7.4 Make config values editable (QLineEdit)
- [x] 7.5 Add Save button to persist changes

## 8. Platform Support
- [x] 8.1 Implement open_in_terminal (Linux/macOS/Windows)
- [x] 8.2 Implement open_in_file_manager (xdg-open/open/explorer)
- [x] 8.3 Implement copy_to_clipboard

## 9. State Persistence
- [x] 9.1 Add STATE_FILE constant for gui-state.json
- [x] 9.2 Implement save_state (needs_attention, previous_statuses)
- [x] 9.3 Implement load_state
- [x] 9.4 Call load_state on startup
- [x] 9.5 Call save_state when needs_attention changes

## 10. Command Output Dialog
- [x] 10.1 Create CommandOutputDialog class
- [x] 10.2 Show command string and real-time output
- [x] 10.3 Display success/failure status
- [x] 10.4 Close button always enabled (don't wait for process)
- [x] 10.5 Update all commands to use dialog (git, wt-new, wt-close, wt-work)

## 11. Merge Dialog
- [x] 11.1 Create MergeDialog class
- [x] 11.2 Target branch dropdown
- [x] 11.3 Stash checkbox (auto-checked if uncommitted changes)
- [x] 11.4 Keep source branch checkbox (default: checked)
- [x] 11.5 Auto-stash before merge, pop after
