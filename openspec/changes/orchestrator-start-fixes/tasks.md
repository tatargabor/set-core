# Tasks: orchestrator-start-fixes

## 1. Add default_model to resolve_directives

- [x] 1.1 Add `default_model` case to `resolve_directives()` case statement (after `review_model`, ~line 415) — validate `^(haiku|sonnet|opus)$`, default `$DEFAULT_IMPL_MODEL`
- [x] 1.2 Add `default_model` local variable init (`local default_model="$DEFAULT_IMPL_MODEL"`) with the other defaults (~line 295)
- [x] 1.3 Add `default_model` to the JSON output object in `resolve_directives()` (~line 466)

## 2. Fix sentinel restart args

- [x] 2.1 In `.claude/commands/wt/sentinel.md` Step 3 crash recovery restart command, change `wt-orchestrate start &` to `wt-orchestrate start $ARGUMENTS &`
