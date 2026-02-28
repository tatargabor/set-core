## ADDED Requirements

### Requirement: Manual task checkbox syntax
Tasks requiring human intervention use `- [?]` checkbox syntax in tasks.md, distinct from `- [ ]` (pending auto) and `- [x]` (complete).

#### Scenario: Parser recognizes manual tasks
- **WHEN** tasks.md contains `- [?] 3.3 Configure Stripe API keys`
- **THEN** the task is classified as "manual/human" and NOT counted as a pending auto-task

#### Scenario: Manual tasks are not counted as incomplete auto-tasks
- **WHEN** `check_tasks_done()` runs on a tasks.md with only `[?]` tasks remaining (no `[ ]`)
- **THEN** auto-tasks are considered complete (return 0) — manual tasks are tracked separately

#### Scenario: Completed manual tasks
- **WHEN** a user or tool marks a manual task as `- [x]`
- **THEN** it is treated identically to any other completed task

### Requirement: Manual task type annotations
Manual tasks may include an inline type annotation in square brackets after the description.

#### Scenario: Input-type manual task
- **WHEN** a task reads `- [?] 3.3 Configure Stripe keys [input:STRIPE_SECRET_KEY]`
- **THEN** the parser extracts type=`input` and key=`STRIPE_SECRET_KEY`

#### Scenario: Confirm-type manual task
- **WHEN** a task reads `- [?] 4.1 Create Firebase project [confirm]`
- **THEN** the parser extracts type=`confirm` (no key)

#### Scenario: Manual task without annotation
- **WHEN** a task reads `- [?] 5.2 Get client approval`
- **THEN** the parser defaults to type=`confirm`

### Requirement: Manual instruction sections
Detailed human-readable instructions for manual tasks are provided in `### Manual:` sections within tasks.md.

#### Scenario: Instruction section present
- **WHEN** tasks.md contains `### Manual: 3.3 — Configure Stripe API Keys` followed by markdown content
- **THEN** `wt-manual show` displays this content as instructions for task 3.3

#### Scenario: Instruction section missing
- **WHEN** a `[?]` task has no corresponding `### Manual:` section
- **THEN** `wt-manual show` displays the task description only, with a note that no detailed instructions were provided

#### Scenario: Instruction section structure
- **WHEN** a `### Manual:` section exists
- **THEN** it may contain: `**What to do:**` steps, `**Input:**` key name, `**Format:**` expected format, `**Target:**` where the value will be stored, and freeform markdown (links, notes)
