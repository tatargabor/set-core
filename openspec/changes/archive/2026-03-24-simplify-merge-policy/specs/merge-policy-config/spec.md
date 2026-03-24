# Merge Policy Config

## MODIFIED Requirements

### Requirement: Merge queue always receives done changes
When a change passes all verify gates and reaches "done" status, it SHALL always be added to the merge queue. The previous guard `if merge_policy in ("eager", "checkpoint")` is removed — there is no policy where done changes skip the merge queue.

#### Scenario: Done change auto-queued regardless of config
- **WHEN** a change completes verify gates and status becomes "done"
- **THEN** it is added to the merge queue without checking merge_policy

### Requirement: Default merge policy is eager
The default `merge_policy` in Directives SHALL be "eager". The config validator SHALL accept "eager" and "checkpoint" as valid values. "manual" is removed.

#### Scenario: No merge_policy in config uses eager
- **WHEN** `wt/orchestration/config.yaml` does not specify `merge_policy`
- **THEN** the orchestrator uses "eager" (merge immediately when gates pass)

#### Scenario: Manual policy rejected
- **WHEN** config specifies `merge_policy: manual`
- **THEN** config validation warns and falls back to "eager"

### Requirement: Template config omits checkpoint settings
The web template `config.yaml` SHALL NOT include `merge_policy`, `checkpoint_auto_approve`, or `checkpoint_every`. These are advanced settings for production use — the default (eager) is correct for most projects.

#### Scenario: Fresh project has no checkpoint config
- **WHEN** `set-project init --project-type web --template nextjs` creates a project
- **THEN** `wt/orchestration/config.yaml` does not contain checkpoint-related keys
