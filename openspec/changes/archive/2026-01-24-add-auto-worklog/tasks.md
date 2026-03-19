# Tasks: Add Automatic JIRA Worklog Generation

## 1. Core Activity Detection

- [x] 1.1 Implement `get_commits_for_date()` function - git log with --since/--until filters
- [x] 1.2 Implement `get_all_worktree_commits()` - collect commits across all worktrees
- [x] 1.3 Implement `fetch_remote_branches()` - git fetch --all for multi-machine support
- [x] 1.4 Implement date parsing for relative dates ("yesterday", "2 days ago")

## 2. Time Calculation Engine

- [x] 2.1 Implement `group_commits_into_blocks()` - gap-based grouping algorithm
- [x] 2.2 Implement `calculate_block_duration()` - with buffer time
- [x] 2.3 Implement `detect_overlaps()` - find overlapping intervals across worktrees
- [x] 2.4 Implement `allocate_time_proportionally()` - fair distribution for overlaps
- [x] 2.5 Implement `calculate_gap_to_target()` - compare activity to daily target

## 3. Configuration

- [x] 3.1 Extend `.set-core/jira.json` schema with `autoWorklog` section
- [x] 3.2 Implement config loading and defaults (dailyTarget, roundTo, minActivityGap)
- [x] 3.3 Implement config validation

## 4. CLI Interface

- [x] 4.1 Add `auto` subcommand to `wt-jira`
- [x] 4.2 Implement `--date` parameter with date parsing
- [x] 4.3 Implement `--dry-run` mode with detailed output
- [x] 4.4 Implement `--fetch` flag for remote sync
- [x] 4.5 Implement `--project` filter
- [x] 4.6 Implement `--interactive` mode for per-task confirmation
- [x] 4.7 Implement `--yes` flag for non-interactive submission

## 5. Structured Worklog Comments

- [x] 5.1 Implement `format_worklog_comment()` - generate structured comment with [wt-auto] marker
- [x] 5.2 Implement `parse_worklog_comment()` - extract sessions from existing worklog
- [x] 5.3 Implement location hint detection from hostname/git remote
- [x] 5.4 Include abbreviated commit hashes in session details

## 6. JIRA Integration

- [x] 6.1 Extend existing worklog submission to support `started` timestamp
- [x] 6.2 Implement batch worklog submission for multiple tasks
- [x] 6.3 Add duplicate detection - find existing `[wt-auto]` worklogs for same date
- [x] 6.4 Implement incremental update - add session to existing worklog via PUT
- [x] 6.5 Handle JIRA API errors gracefully

## 7. Output and Reporting

- [x] 7.1 Implement summary output format (as shown in design.md)
- [x] 7.2 Add color coding for different statuses
- [x] 7.3 Implement warnings for anomalies (>10h, no activity, etc.)
- [x] 7.4 Add verbose mode for debugging

## 8. Testing and Documentation

- [ ] 8.1 Add unit tests for time calculation functions
- [ ] 8.2 Add integration tests with mock git repos
- [ ] 8.3 Update README with auto worklog usage
- [ ] 8.4 Add example configurations

## Dependencies

- Task 2.* depends on 1.*
- Task 4.* depends on 2.* and 3.*
- Task 5.* (Structured Comments) can be parallelized with 4.*
- Task 6.* (JIRA Integration) depends on 4.* and 5.*
- Task 7.* (Output) can be parallelized with 6.*
- Task 8.* (Testing) should be done last

## Notes

- The existing `wt-jira log` command remains unchanged
- The `auto` command is new functionality, doesn't modify existing behavior
- The config extension is backward compatible (new section, not required)
