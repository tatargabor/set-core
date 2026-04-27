# Template Engine Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Safe variable escaping for prompt templates
The system SHALL provide `escape_for_prompt(text)` that neutralizes characters which would break shell heredoc expansion or corrupt structured text output: `$`, backtick, `EOF` markers, and unmatched quotes.

#### Scenario: Dollar signs in diff output
- **WHEN** `escape_for_prompt("function $foo() { return $bar; }")` is called
- **THEN** the output preserves the literal text without shell variable expansion

#### Scenario: Backticks in test output
- **WHEN** `escape_for_prompt("Error: `undefined` is not a function")` is called
- **THEN** the output preserves the literal backticks without command substitution

#### Scenario: EOF marker in content
- **WHEN** `escape_for_prompt("some text\nEOF\nmore text")` is called
- **THEN** the output does not prematurely terminate a heredoc boundary

#### Scenario: Plain text passes through unchanged
- **WHEN** `escape_for_prompt("simple text without special chars")` is called
- **THEN** the output equals the input exactly

### Requirement: Proposal template rendering
`render_proposal(change_name, scope, roadmap_item, memory_ctx, spec_ref)` SHALL generate the proposal.md content that dispatcher.sh currently builds with 3 concatenated heredocs (PROPOSAL_EOF, MEMORY_EOF, SPECREF_EOF).

#### Scenario: All fields provided
- **WHEN** `render_proposal` is called with all arguments populated
- **THEN** the output contains the proposal markdown with properly escaped variables in the correct sections

#### Scenario: Optional fields empty
- **WHEN** `render_proposal` is called with `memory_ctx=""` and `spec_ref=""`
- **THEN** the output omits the memory and spec reference sections cleanly (no empty headers or trailing whitespace)

### Requirement: Review prompt rendering
`render_review_prompt(scope, diff_output, req_section)` SHALL generate the code review prompt that verifier.sh currently builds with the `<<REVIEW_EOF` heredoc.

#### Scenario: Diff containing special characters
- **WHEN** `render_review_prompt` is called with a `diff_output` containing `$HOME`, backticks, and Unicode
- **THEN** the output contains the literal diff text without expansion or corruption

#### Scenario: Large diff truncation
- **WHEN** `diff_output` exceeds 50,000 characters
- **THEN** the output truncates the diff with a clear "... truncated ..." marker

### Requirement: Fix prompt rendering
`render_fix_prompt(change_name, scope, output_tail, smoke_cmd)` SHALL replace the `<<SMOKE_FIX_EOF` and `<<SCOPED_FIX_EOF` heredocs in merger.sh and verifier.sh.

#### Scenario: Test output with stack traces
- **WHEN** `render_fix_prompt` is called with `output_tail` containing Node.js stack traces with file paths and line numbers
- **THEN** the output preserves the stack trace formatting intact

### Requirement: Planning prompt rendering
`render_planning_prompt(input_content, specs, memory, replan_ctx)` SHALL replace the 200-line nested heredoc structure in planner.sh:882-1074 including the 5 nested sub-heredocs (MEM_CTX, REPLAN_CTX, ORCH_HIST, E2E_CTX).

#### Scenario: Replan mode with all contexts
- **WHEN** `render_planning_prompt` is called with replan context containing completed changes, cycle number, orchestration memory, and E2E failures
- **THEN** the output includes all context sections with proper escaping and no nested heredoc artifacts

#### Scenario: Initial plan (no replan context)
- **WHEN** `render_planning_prompt` is called with empty replan context
- **THEN** the replan sections are omitted entirely (no empty blocks)

### Requirement: CLI bridge for template operations
The `set-orch-core template` subcommand SHALL expose template rendering to bash scripts via stdout.

#### Scenario: Render proposal to stdout
- **WHEN** bash calls `set-orch-core template proposal --change "my-change" --scope "Add auth" --roadmap "Authentication system"`
- **THEN** stdout contains the rendered proposal markdown

#### Scenario: Long arguments via stdin
- **WHEN** template arguments contain multi-kilobyte text (diff output, test results)
- **THEN** the CLI accepts `--input-file -` to read the large argument from stdin instead of command-line argument
