## Purpose

Migrate `lib/loop/tasks.sh` (235 LOC) to `lib/set_orch/loop_tasks.py`. Task file discovery, completion checking, manual task detection, and done criteria.

## Requirements

### TASKS-01: Task File Discovery
- `find_tasks_file(wt_path)` searches for tasks.md
- Priority: root → subdirectories (maxdepth 4)
- Exclude: `archive/`, `node_modules/`
- Return path or None

### TASKS-02: Completion Checking
- `check_completion(tasks_path)` parses markdown checkboxes
- Count: `- [x]` (done), `- [ ]` (pending), `- [?]` (manual/blocked)
- Return `TaskStatus(total, done, pending, manual, percent_complete)`
- 100% complete when all non-manual tasks are checked

### TASKS-03: Manual Task Detection
- `find_manual_tasks(tasks_path)` returns list of `- [?]` tasks
- Each manual task: `ManualTask(id, title, type_annotation, instructions)`
- Type annotations: `[input:KEY_NAME]`, `[confirm]`

### TASKS-04: Done Criteria
- `is_done(wt_path, target_change)` comprehensive done check
- All tasks checked OR change archived OR "done" marker present
- Return `DoneResult(done, reason)`

### TASKS-05: Unit Tests
- Test discovery with mock directory structures
- Test completion parsing with various checkbox states
- Test manual task detection and annotation parsing
