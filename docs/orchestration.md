# Orchestration Guide

`wt-orchestrate` is an autonomous multi-change execution engine. It reads a specification document, decomposes it into independent changes using an LLM, dispatches each to its own worktree with a Ralph loop, and monitors everything to completion — merging results back to main as they finish.

---

## Quick Start

```bash
# 1. Write your spec (any format — markdown, design doc, feature list)
cat docs/v3-release.md

# 2. Generate a plan
wt-orchestrate --spec docs/v3-release.md plan

# 3. Review the plan
wt-orchestrate plan --show

# 4. Execute
wt-orchestrate start

# 5. Monitor progress
wt-orchestrate status
```

That's it. The orchestrator creates worktrees, starts Ralph loops, monitors progress, merges completed work, and stops when everything is done.

---

## Example Walkthrough

Suppose you have a project with this spec document (`docs/v3-release.md`):

```markdown
# v3 Release Plan

## Authentication
- Add JWT-based auth middleware
- Add user roles (admin, editor, viewer)

## API
- Add REST endpoints for user management
- Add rate limiting middleware

## Infrastructure
- Add structured logging with correlation IDs
- Update CI pipeline for the new auth tests
```

### Step 1: Plan

```bash
wt-orchestrate --spec docs/v3-release.md plan
```

The orchestrator sends your spec to Claude, which decomposes it into sized, dependency-ordered changes:

```
[INFO] Reading input (spec): docs/v3-release.md
[INFO] Directives: {"max_parallel":2,"merge_policy":"checkpoint",...}
[INFO] Planning 6 changes from spec...
[INFO] Plan saved to orchestration-plan.json
```

### Step 2: Review

```bash
wt-orchestrate plan --show
```

```
═══ Orchestration Plan ═══

  add-jwt-auth [M] — Add JWT-based authentication middleware...
    depends_on: (none)
  add-user-roles [M] — Add user roles (admin, editor, viewer)...
    depends_on: add-jwt-auth
  add-user-api [M] — REST endpoints for user management...
    depends_on: add-jwt-auth
  add-rate-limiting [S] — Rate limiting middleware...
    depends_on: (none)
  add-structured-logging [S] — Structured logging with correlation IDs...
    depends_on: (none)
  update-ci-auth [S] — Update CI pipeline for auth tests...
    depends_on: add-jwt-auth

Dependency order:
  1. add-jwt-auth
  2. add-rate-limiting
  3. add-structured-logging
  4. add-user-roles
  5. add-user-api
  6. update-ci-auth
```

The orchestrator respects dependencies — `add-user-roles` won't start until `add-jwt-auth` is merged.

### Step 3: Execute

```bash
wt-orchestrate start
```

The orchestrator:
1. Creates worktrees for changes that have no unmet dependencies (up to `max_parallel`)
2. Runs `opsx:ff` in each worktree to generate OpenSpec artifacts
3. Starts a Ralph loop in each worktree to implement the change
4. Polls every 30 seconds for completion
5. When a change finishes, merges it to main and dispatches the next available change
6. Repeats until all changes are done

```
[INFO] Dispatching: add-jwt-auth (M)
[INFO] Dispatching: add-rate-limiting (S)
[INFO]   → Worktree created, Ralph loop started
[INFO]   → Worktree created, Ralph loop started
[INFO] Monitoring 2 active changes...
...
[INFO] add-rate-limiting completed → merging
[INFO] Merge successful: add-rate-limiting
[INFO] Dispatching: add-structured-logging (S)
...
[INFO] add-jwt-auth completed → merging
[INFO] Merge successful: add-jwt-auth
[INFO] Dispatching: add-user-roles (M)
[INFO] Dispatching: add-user-api (M)
```

### Step 4: Monitor

While the orchestrator runs, check status anytime from another terminal:

```bash
wt-orchestrate status
```

```
Orchestration Status: running
  Elapsed: 1h23m | Changes: 4/6 done | Active: 2

  add-jwt-auth        ✅ done     (merged)
  add-rate-limiting    ✅ done     (merged)
  add-structured-log   ✅ done     (merged)
  add-user-roles       🔄 running  (ralph: iteration 3)
  add-user-api         🔄 running  (ralph: iteration 2)
  update-ci-auth       ⏳ waiting  (blocked by: add-jwt-auth ✅)
```

---

## Input Modes

### Spec mode (recommended)

Pass any document — the orchestrator uses Claude to extract actionable changes:

```bash
wt-orchestrate --spec docs/release-plan.md plan
wt-orchestrate --spec docs/design-doc.md plan
```

For large specs, use `--phase` to focus on a subset:

```bash
wt-orchestrate --spec docs/v3-release.md --phase 1 plan        # plan phase 1
wt-orchestrate --spec docs/v3-release.md --phase "Security" plan # plan by name
```

### Brief mode (legacy)

Create `openspec/project-brief.md` with a `### Next` section:

```markdown
### Next
- Add JWT authentication
- Add rate limiting
- Update CI pipeline
```

```bash
wt-orchestrate plan    # auto-detects project-brief.md
```

---

## Configuration

### In-document directives

Add an `## Orchestrator Directives` section to your spec:

```markdown
## Orchestrator Directives
- max_parallel: 3
- merge_policy: eager
- test_command: npm test
- auto_replan: true
```

### Config file

Create `.claude/orchestration.yaml`:

```yaml
max_parallel: 3
merge_policy: checkpoint    # eager | checkpoint | manual
checkpoint_every: 3         # merge-checkpoint after every N changes
test_command: npm test       # run after each merge
auto_replan: true            # auto-advance to next phase
pause_on_exit: false         # pause running changes on Ctrl+C
```

### CLI flags

CLI flags override config and directives:

```bash
wt-orchestrate --max-parallel 4 --time-limit 2h start
```

### Precedence

Settings are resolved in order (highest wins):

1. CLI flags (`--max-parallel`, `--time-limit`)
2. Config file (`.claude/orchestration.yaml`)
3. In-document directives (`## Orchestrator Directives`)
4. Defaults

---

## Merge Policies

| Policy | Behavior |
|--------|----------|
| `eager` | Merge each change immediately when done |
| `checkpoint` | Batch merges every N completed changes, wait for approval |
| `manual` | Queue merges, only flush on `wt-orchestrate approve --merge` |

---

## Pause, Resume, Replan

```bash
# Pause one change
wt-orchestrate pause add-user-roles

# Pause everything
wt-orchestrate pause --all

# Resume
wt-orchestrate resume add-user-roles
wt-orchestrate resume --all

# Update your spec, then re-plan (preserves completed work)
wt-orchestrate replan
```

---

## Safety

- **Time limit**: default 5 hours. Override with `--time-limit 2h` or `--time-limit none`
- **Crash recovery**: state is persisted to `orchestration-state.json`. Run `wt-orchestrate start` again to resume
- **Ctrl+C**: saves state and optionally pauses running changes (`pause_on_exit: true`)
- **Test verification**: if `test_command` is set, tests run after each merge — failures block further merges

---

## Files

| File | Purpose |
|------|---------|
| `orchestration-plan.json` | LLM-generated change plan with dependency graph |
| `orchestration-state.json` | Runtime state (change statuses, merge queue) |
| `orchestration-summary.md` | Human-readable summary (generated on completion) |
| `.claude/orchestration.yaml` | Optional configuration |
| `.claude/orchestration.log` | Debug log (auto-rotated at 100KB) |

---

## CLI Reference

```
wt-orchestrate [options] <command>

Options:
  --spec <path>          Specification document
  --brief <path>         Structured brief (legacy)
  --phase <hint>         Phase filter (number or text)
  --max-parallel <N>     Max concurrent changes
  --time-limit <dur>     Stop after duration (default: 5h)

Commands:
  plan [--show]          Generate or show plan
  start                  Execute the plan
  status                 Show progress
  pause <name|--all>     Pause changes
  resume <name|--all>    Resume changes
  replan                 Re-plan from updated spec
  approve [--merge]      Approve checkpoint / flush merge queue
```
