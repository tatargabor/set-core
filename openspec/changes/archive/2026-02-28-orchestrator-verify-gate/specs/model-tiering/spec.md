# Model Tiering

Model selection per orchestration task — cheaper models for summarization and review, expensive models for planning and implementation.

## Requirements

### MT-1: run_claude model parameter
- `run_claude()` accepts an optional second parameter for model selection
- Valid values: `haiku`, `sonnet`, `opus`, or empty (system default)
- Maps to `claude -p --model <model-id>` flag
- Model IDs: `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`, `claude-opus-4-6`
- If model parameter is empty/unset, omit `--model` flag (use Claude CLI default)

### MT-2: Summarization uses cheap model
- `summarize_spec()` uses the model from `summarize_model` directive
- Default: `haiku` (cheapest, sufficient for text summarization)
- Configurable in `orchestration.yaml`: `summarize_model: haiku|sonnet|opus`

### MT-3: Plan decomposition always uses Opus
- `cmd_plan()` LLM call always uses Opus regardless of directives
- Planning requires complex reasoning about dependencies, file overlap, phasing
- Not configurable — hardcoded to Opus

### MT-4: Review and fix use configurable model
- Code review gate (VG-4) uses `review_model` directive
- Test failure fix (Ralph retry prompt) uses `review_model` for the retry instruction generation
- Default: `sonnet` (good balance of quality and cost)
- Configurable: `review_model: haiku|sonnet|opus`

### MT-5: New directives
- `summarize_model`: model for spec summarization (default: `haiku`)
- `review_model`: model for code review and fix instructions (default: `sonnet`)
- Parsed in `resolve_directives()` alongside existing directives
- Validated: must be one of `haiku`, `sonnet`, `opus`
- Passed through directives JSON to monitor_loop and handle_change_done
