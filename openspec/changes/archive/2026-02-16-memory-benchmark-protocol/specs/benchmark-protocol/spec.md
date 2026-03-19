## ADDED Requirements

### Requirement: Benchmark directory structure
The benchmark protocol SHALL be organized in a `benchmark/` directory at the project root with the following structure:
- `README.md` — overview, purpose, and quick start
- `project-spec.md` — full CraftBazaar specification (agent input)
- `changes/` — per-change definitions (01 through 06)
- `run-guide.md` — step-by-step execution instructions
- `scoring-rubric.md` — evaluation criteria and scoring methodology
- `diagnostic-framework.md` — gap analysis methodology for memory improvements
- `claude-md/baseline.md` — CLAUDE.md for Run A (no memory)
- `claude-md/with-memory.md` — CLAUDE.md for Run B (with memory)
- `templates/` — session annotation, metrics, and report templates

#### Scenario: Complete directory created
- **WHEN** all benchmark files are created
- **THEN** the `benchmark/` directory contains all listed files and subdirectories

### Requirement: Run guide with full toolchain bootstrap
The run guide SHALL include exact, copy-pasteable commands for setting up the test project from scratch. The bootstrap sequence SHALL cover: repository creation, `openspec init --tools claude`, `wt-deploy-hooks .` (Claude Code hooks), CLAUDE.md placement, and copying agent-only change definitions to `docs/benchmark/`. For Run B additionally: `set-memory-hooks install`. Prerequisites SHALL be listed: set-core installed and on PATH, Node.js, Claude Code CLI.

#### Scenario: Evaluator follows run guide for baseline run
- **WHEN** an evaluator follows the run guide step by step for Run A
- **THEN** a fresh CraftBazaar repository is created at `~/benchmark/run-a/craftbazaar/`
- **THEN** openspec is configured, Claude Code hooks are deployed, `baseline.md` is copied as CLAUDE.md
- **THEN** agent-only change definitions are in `docs/benchmark/01-*.md` through `06-*.md`
- **THEN** `set-memory-hooks` is NOT installed (no memory in skills)
- **THEN** the repository is ready to start `wt-loop`

#### Scenario: Evaluator follows run guide for memory run
- **WHEN** an evaluator follows the run guide step by step for Run B
- **THEN** a fresh CraftBazaar repository is created at `~/benchmark/run-b/craftbazaar/`
- **THEN** openspec is configured, Claude Code hooks are deployed, `with-memory.md` is copied as CLAUDE.md
- **THEN** `set-memory-hooks install` has been run (memory hooks in skills)
- **THEN** agent-only change definitions are in `docs/benchmark/01-*.md` through `06-*.md`
- **THEN** the memory store is empty (fresh start)
- **THEN** the repository is ready to start `wt-loop`

### Requirement: Two CLAUDE.md variants with single-variable difference
The benchmark SHALL provide two CLAUDE.md files that share a common base (project setup, testing commands, OpenSpec workflow guidance, self-directing benchmark task section, dev server port config) and differ only in memory-related content. The `baseline.md` SHALL NOT contain memory hooks or proactive memory instructions. The `with-memory.md` SHALL contain everything in baseline plus the proactive memory section (recall before work, save on insights, agent self-reflection). Both SHALL include the self-directing "Benchmark Task" section.

#### Scenario: Comparing the two CLAUDE.md files
- **WHEN** the two CLAUDE.md files are diff'd
- **THEN** the only differences are the presence/absence of memory-related sections
- **THEN** project setup, testing, OpenSpec workflow, and benchmark task sections are identical
- **THEN** PORT configuration differs (3000 for baseline, 3001 for with-memory)

### Requirement: Self-directing agent via CLAUDE.md
The CLAUDE.md variants SHALL include a "Benchmark Task" section that instructs the agent to self-direct through changes 01-06. The agent SHALL check `openspec list` to determine which changes are complete, read the next change definition from `docs/benchmark/0N-*.md` inside the project repo, and implement it using OpenSpec workflows (`/opsx:ff` → `/opsx:apply`). After completing a change, the agent SHALL write a status file to `results/change-0N.json`.

#### Scenario: Agent self-directs to next change
- **WHEN** a wt-loop iteration starts with fresh context
- **THEN** the agent reads CLAUDE.md and checks `openspec list`
- **THEN** the agent identifies the next incomplete change (lowest number not yet done)
- **THEN** the agent reads `docs/benchmark/0N-*.md` for task requirements
- **THEN** the agent uses `/opsx:ff` → `/opsx:apply` to implement the change

#### Scenario: Agent completes all changes
- **WHEN** the agent checks `openspec list` and all 6 changes are complete
- **THEN** the agent reports completion and the wt-loop terminates

### Requirement: Autonomous execution via wt-loop
Both runs SHALL execute via `wt-loop start` with no human intervention. Each wt-loop iteration provides fresh context (no conversation history from previous iterations). The wt-loop SHALL be configured with `--max 20` iterations and `--stall-threshold 3` to prevent infinite loops.

#### Scenario: Fully autonomous benchmark run
- **WHEN** the evaluator runs `wt-loop start "Build CraftBazaar changes 01-06"`
- **THEN** the agent autonomously works through all 6 changes across multiple iterations
- **THEN** no human input is required until the loop completes or stalls

#### Scenario: Agent stalls on a change
- **WHEN** the agent makes no commits for 3 consecutive iterations
- **THEN** the wt-loop stops automatically due to stall detection
- **THEN** the stall is recorded as data (agent could not solve the problem)

### Requirement: Parallel execution support
The benchmark SHALL support running Run A and Run B simultaneously in separate directories. Each run SHALL use a different dev server port (PORT=3000 for Run A, PORT=3001 for Run B), configured in the respective CLAUDE.md. Each run SHALL have its own independent git repo, openspec config, and memory store.

#### Scenario: Running both benchmarks in parallel
- **WHEN** the evaluator starts wt-loop in both `~/benchmark/run-a/craftbazaar/` and `~/benchmark/run-b/craftbazaar/`
- **THEN** both agents work independently without interference
- **THEN** no port conflicts occur between dev servers

### Requirement: Scoring rubric with quantitative and qualitative metrics
The scoring rubric SHALL define per-change metrics: dead ends (0-5 scale), repeated mistakes (0-3 scale), design rework (0-3 scale), first-try test pass (yes/no), and session length (turn count). For Run B, additional metrics SHALL include: memory recalls (count), useful recalls (count), and memories saved (count).

#### Scenario: Evaluator scores a completed change
- **WHEN** a change session is complete
- **THEN** the evaluator fills out the session annotation template with all required metrics
- **THEN** the evaluator records the metrics in the JSON template
- **THEN** both qualitative notes and quantitative scores are captured

### Requirement: Comparison report template
The benchmark SHALL provide a comparison report template that aggregates per-change metrics from both runs into a side-by-side table, with delta calculations (absolute and percentage) for each metric. The report SHALL include a narrative section for overall findings.

#### Scenario: Generating comparison report
- **WHEN** both Run A and Run B are complete with all changes scored
- **THEN** the evaluator fills the comparison report template with aggregated data
- **THEN** the report shows per-change and total deltas for dead ends, repeated mistakes, design rework, test pass rate, and session length

### Requirement: Diagnostic framework for memory gap analysis
The benchmark SHALL include a diagnostic framework that categorizes memory system failures. Categories SHALL include: missed recall opportunities (relevant memory existed but wasn't recalled), low-quality saves (memory was saved but too vague to be useful), missing memory types (an event should have triggered a save but didn't), timing issues (saved too late to help the current or next change), and recall relevance problems (recalled but irrelevant to the current task).

#### Scenario: Analyzing memory gaps after Run B
- **WHEN** Run B is complete and all changes are annotated
- **THEN** the evaluator reviews each change for memory gap categories
- **THEN** each gap instance is documented with: the change where it occurred, the category, what should have happened, and a suggested improvement

#### Scenario: Identifying efficiency improvement opportunities
- **WHEN** the diagnostic analysis is complete
- **THEN** the evaluator can identify which memory system components need improvement
- **THEN** the analysis produces actionable recommendations (e.g., "add automatic environment learning", "improve recall relevance ranking")

### Requirement: Automatic data collection during runs
The benchmark SHALL automatically collect data during execution without human intervention. Automatic data sources SHALL include: wt-loop state file (per-iteration timing, tokens, commits, stall events), ralph-loop.log (full session transcript), git log (commit history with timestamps), openspec status (change completion), and agent-written `results/change-0N.json` status files.

#### Scenario: Data available after autonomous run
- **WHEN** a wt-loop run completes (or stalls)
- **THEN** `.claude/ralph-loop.log` contains the full session transcript
- **THEN** `wt-loop history` shows per-iteration metrics (time, tokens, commits)
- **THEN** `git log` shows all commits with timestamps
- **THEN** `openspec list --json` shows which changes completed
- **THEN** `results/change-0N.json` files exist for each completed change

### Requirement: Memory event logging for Run B
During Run B (with memory), memory events are automatically captured in the session transcript (ralph-loop.log) because `set-memory recall` and `set-memory remember` commands appear in the log output. After the run, the evaluator SHALL review the transcript to extract and annotate memory events.

#### Scenario: Extracting memory events from Run B transcript
- **WHEN** Run B completes and the evaluator reviews `.claude/ralph-loop.log`
- **THEN** all `set-memory recall` invocations and their results are visible in the log
- **THEN** all `set-memory remember` invocations and what was saved are visible in the log
- **THEN** the evaluator annotates which recalls directly influenced agent behavior

### Requirement: Post-run results collection guide
The benchmark SHALL include a results collection guide that documents how to extract, organize, and compare data from both completed runs. The guide SHALL cover: copying logs and status files to a results directory, running `wt-loop history` and `set-memory list --json` (Run B), and using the comparison report template.

#### Scenario: Evaluator collects results after both runs
- **WHEN** both Run A and Run B have completed
- **THEN** the evaluator follows the results collection guide to gather all data
- **THEN** automatic metrics (iterations, time, tokens, commits) are tabulated
- **THEN** the evaluator reviews transcripts and fills qualitative annotations
- **THEN** a comparison report is generated using the template

### Requirement: Change definition file splitting
Each change definition file in `benchmark/changes/` SHALL have two clearly separated sections: "Agent Input" (task description and acceptance criteria, delimited by a marker) and "Evaluator Notes" (trap documentation, memory predictions, scoring focus). The run guide SHALL include instructions for extracting only the "Agent Input" sections into the project repo at `docs/benchmark/0N-*.md`.

#### Scenario: Bootstrap extracts agent-only files
- **WHEN** the evaluator runs the bootstrap steps from the run guide
- **THEN** `docs/benchmark/0N-*.md` files contain ONLY the "Agent Input" sections
- **THEN** trap documentation and evaluator notes are NOT present in the project repo
- **THEN** the agent cannot access evaluator notes during execution
