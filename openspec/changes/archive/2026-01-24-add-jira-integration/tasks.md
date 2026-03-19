## 1. MCP Setup (mcp-atlassian)
- [x] 1.1 Create `.mcp.template.json` with mcp-atlassian config (credentials placeholders)
- [x] 1.2 Add `.mcp.json` to `.gitignore`
- [x] 1.3 Document mcp-atlassian installation (`uvx mcp-atlassian` or `pip install mcp-atlassian`)

## 2. Configuration Management
- [x] 2.1 Define JSON schema for global config `~/.config/set-core/jira.json`
- [x] 2.2 Define JSON schema for project config `.set-core/jira.json`
- [x] 2.3 Implement config file reader with platform-specific paths
- [x] 2.4 Implement config merging (global + project, project takes precedence)
- [x] 2.5 Implement environment variable override logic
- [x] 2.6 Add file permission check/set (600) on global config creation
- [x] 2.7 Implement titlePrefix handling for issue creation

## 3. CLI Tool (wt-jira)
- [x] 3.1 Create `bin/wt-jira` bash script skeleton (source wt-common.sh)
- [x] 3.2 Implement `wt-jira init` interactive credentials setup
- [x] 3.3 Implement `wt-jira test` connection tester
- [x] 3.4 Implement `wt-jira show` config display (masked password)
- [x] 3.5 Implement `wt-jira fields` to discover JIRA fields (Epic Link field ID)
- [x] 3.6 Implement `wt-jira log [key] <duration> [comment]` worklog command
- [x] 3.7 Implement automatic ticket resolution from proposal.md `JIRA Key:` line
- [x] 3.8 Detect current worktree/change context for automatic ticket lookup
- [x] 3.9 Implement duration parser (2h, 30m, 1h 30m, 1d → JIRA format)
- [x] 3.10 Implement `wt-jira sync` batch sync command
- [x] 3.11 Integrate with `wt-list` to iterate through worktrees
- [x] 3.12 Parse proposal.md files for JIRA Key extraction
- [x] 3.13 Implement --dry-run flag for sync
- [x] 3.14 Implement -p/--project flag for sync
- [x] 3.15 Implement -y/--yes flag for non-interactive sync
- [x] 3.16 Implement summary report after sync
- [x] 3.17 Implement `wt-jira audit` to find misconfigured Tasks (orphans, missing Epic)
- [x] 3.18 Add conversion links and suggested parents to audit output
- [x] 3.19 Implement `wt-jira rename-prefix` to update prefix in all issue summaries
- [x] 3.20 Implement `wt-jira rename-story` to rename Story summary (preserves prefix)
- [x] 3.21 Implement `wt-jira move-subtask` to move Sub-Task to different parent (uses Playwright browser automation - REST API doesn't support parent changes)

## 4. OpenSpec-JIRA Integration
- [x] 4.1 Create prompt for parent Story selection (new vs existing vs skip)
- [x] 4.2 Implement "Create new Story" flow with summary input
- [x] 4.3 Implement "Use existing Story" flow with key input or list selection
- [x] 4.4 Query and display existing Stories with project prefix for selection
- [x] 4.5 Extract proposal title from `# Change:` or `# Proposal:` line in proposal.md
- [x] 4.6 Create Sub-Task with `[prefix] proposal title` as summary
- [x] 4.7 Add `JIRA Key:` and `Story:` lines to proposal.md after creation
- [x] 4.8 Handle "Skip JIRA sync" option gracefully
- [x] 4.9 Add `parentEpic` to project config (required for Story creation)
- [x] 4.10 Link new Stories to Epic automatically
- [x] 4.11 Verify and add missing Epic links to existing Stories during sync

## 5. Installation & Integration (extends add-worktree-tools)
- [x] 5.1 Add mcp-atlassian install to `install.sh` (pip or uvx)
- [x] 5.2 Add wt-jira symlink to `install.sh` → `~/.local/bin/wt-jira`
- [ ] 5.3 Add mcp-atlassian install to `install.ps1` for Windows
- [x] 5.4 Create `.mcp.template.json` in project root
- [ ] 5.5 Document setup in README

## 6. Testing & Validation
- [x] 6.1 Test credentials flow with real JIRA server (jira.example.com) - Connected successfully
- [ ] 6.2 Test mcp-atlassian tools via Claude Code
- [ ] 6.3 Test environment variable override
- [ ] 6.4 Test error scenarios (invalid creds, network issues, invalid JQL)
- [x] 6.5 Verify cross-worktree credential sharing works - worktrees work with global creds
- [x] 6.6 Test OpenSpec-JIRA auto-sync flow (proposal → Sub-Task) - dry-run works, lists all 5 proposals
- [x] 6.7 Test worklog CLI with automatic ticket resolution - tested with EXAMPLE-513
- [x] 6.8 Test audit command - lists orphan Tasks with conversion links
- [x] 6.9 Test rename-prefix command - dry-run shows 43 issues to update
