# Input and Configuration

## Input Modes

The orchestrator accepts three types of input. These are mutually exclusive.

![Input modes and configuration resolution](diagrams/rendered/01-input-modes.png){width=90%}

### 1. Specification Mode (`--spec`)

Most projects work with specification documents:

```bash
wt-orchestrate --spec docs/v3.md plan
wt-orchestrate --spec v12 plan          # shortname: wt/orchestration/specs/v12.md
wt-orchestrate --spec docs/ plan         # entire directory
```

`--spec` can point to a file or directory. For directories, the system processes all `.md` files, and the `scan_spec_directory()` function builds the complete picture.

**Phase filtering**: The `--phase` option narrows to a specific phase:

```bash
wt-orchestrate --spec docs/v3.md --phase 2 plan    # phase 2 only
wt-orchestrate --spec docs/v3.md --phase "Security" plan  # text filter
```

### 2. Brief Mode (`--brief`)

The earlier, simpler format uses a `### Next` section to list roadmap items:

```markdown
## Feature Roadmap
### Next
- Auth system: JWT-based authentication
- User profile: Profile editing and avatar
### Later
- Admin panel: User management
```

### 3. Auto-detect

If neither `--spec` nor `--brief` is specified, the system searches automatically:

1. `openspec/project-brief.md` — if it contains `### Next` items
2. `openspec/project.md` — fallback
3. Error if neither is found

## Configuration

Behavior can be configured at three levels. Higher levels override lower ones:

```
CLI flag  >  orchestration.yaml  >  document directives  >  defaults
```

### orchestration.yaml

The main configuration file is `.claude/orchestration.yaml` (or `wt/orchestration.yaml`):

```yaml
# Execution
max_parallel: 3               # max parallel changes
merge_policy: checkpoint       # eager | checkpoint | manual
checkpoint_every: 3            # checkpoint after N changes

# Testing
test_command: "pnpm test"      # test command
test_timeout: 300              # test timeout (seconds)
smoke_command: "pnpm build"    # smoke test command
smoke_blocking: true           # does smoke fail block merge

# Models
default_model: opus            # implementation model
review_model: sonnet           # review model
summarize_model: haiku         # summarization model

# Review
review_before_merge: true      # LLM review before merge
max_verify_retries: 2          # verify retry limit

# Automation
auto_replan: true              # auto-plan for next phase
context_pruning: true          # context window optimization
model_routing: "off"           # model routing strategy

# Safety
token_budget: 5000000          # soft limit (warning)
token_hard_limit: 20000000     # hard limit (human approval)
time_limit: "5h"               # runtime limit

# Hooks
post_merge_command: "pnpm db:generate"
hook_pre_dispatch: ""
hook_post_verify: ""
hook_pre_merge: ""
hook_post_merge: ""
hook_on_fail: ""
```

### Document Directives

Directives can also be specified within the specification itself:

```markdown
## Orchestrator Directives
- max_parallel: 4
- merge_policy: eager
- token_budget: 100000
```

The system reads these values using the `parse_directives()` function.

\begin{keypoint}
CLI flags always win. If \texttt{--max-parallel 5} is on the command line, it overrides both YAML and document directives.
\end{keypoint}

## Directive Reference

| Directive | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_parallel` | number | 3 | Max parallel worktrees |
| `merge_policy` | enum | checkpoint | eager/checkpoint/manual |
| `checkpoint_every` | number | 3 | Checkpoint frequency |
| `test_command` | string | "" | Test command |
| `test_timeout` | number | 300 | Test timeout (seconds) |
| `smoke_command` | string | "" | Smoke test command |
| `smoke_blocking` | bool | true | Does smoke fail block merge |
| `smoke_fix_max_retries` | number | 3 | Smoke fix retry limit |
| `e2e_command` | string | "" | E2E test command |
| `e2e_mode` | enum | per_change | per_change/phase_end |
| `default_model` | string | opus | Implementation model |
| `review_model` | string | sonnet | Review model |
| `review_before_merge` | bool | false | LLM review enabled |
| `max_verify_retries` | number | 2 | Verify retry limit |
| `auto_replan` | bool | false | Auto-replan at phase end |
| `token_budget` | number | 0 | Soft token limit |
| `token_hard_limit` | number | 20M | Hard token limit |
| `time_limit` | string | 5h | Runtime limit |
| `watchdog_timeout` | number | 600 | Watchdog timeout (seconds) |
| `context_pruning` | bool | true | Context optimization |
| `model_routing` | string | off | Model routing strategy |
| `post_merge_command` | string | "" | Post-merge command |
