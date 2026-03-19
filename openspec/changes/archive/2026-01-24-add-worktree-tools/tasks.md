## 1. Project Management
- [x] 1.1 Create `bin/set-project` - project registry management (add/list/remove/default)
- [x] 1.2 Config file management (`~/.config/set-core/projects.json`)

## 2. Core Scripts
- [x] 2.1 Create `bin/wt-open` - create worktree based on change-id
- [x] 2.2 Create `bin/wt-edit` - launch Zed editor for worktree
- [x] 2.3 Create `bin/wt-list` - list active worktrees
- [x] 2.4 Create `bin/wt-close` - delete worktree

## 3. Installation
- [x] 3.1 Create `install.sh` - Linux/macOS installer
- [x] 3.2 Create `install.ps1` - Windows PowerShell installer
- [ ] 3.3 Create `install.bat` - Windows CMD installer (optional, skipped)
- [x] 3.4 Claude Code CLI installation (npm i -g @anthropic-ai/claude-code)
- [x] 3.5 OpenSpec CLI installation
- [x] 3.6 Zed editor installation (platform-specific)

## 4. Cross-Platform Support
- [x] 4.1 Platform detection in scripts
- [x] 4.2 Zed path handling per platform
- [ ] 4.3 Windows Git Bash compatibility testing (requires Windows environment)
- [x] 4.4 Config path handling per platform

## 5. Documentation
- [x] 5.1 README.md with usage guide
- [x] 5.2 Examples for typical workflows
