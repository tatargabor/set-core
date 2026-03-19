Interact with the project's cognitive memory system (shodh-memory).

**Usage**: `/set:memory [subcommand] [args]`

**Subcommands**:

Core:
- `status [--json]` — Show config, health, and memory count
- `recall <query> [--limit N] [--mode MODE] [--tags t1,t2] [--tags-only] [--min-importance F]` — Semantic search
- `proactive <context> [--limit N]` — Context-aware retrieval with relevance scores
- `remember --type TYPE [--tags t1,t2] [--metadata JSON] [--failure] [--anomaly]` — Save a new memory (stdin)
- `list [--type TYPE] [--limit N]` — List all memories (JSON)
- `browse` (default) — Show summary grouped by type
- `projects` — List all projects with memory counts

Forget / Cleanup:
- `forget <id>` — Delete a single memory by ID
- `forget --all --confirm` — Delete ALL memories
- `forget --older-than <days>` — Delete memories older than N days
- `forget --tags <t1,t2>` — Delete memories matching tags
- `forget --pattern <regex>` — Delete memories matching regex

Diagnostics:
- `stats [--json]` — Memory quality diagnostics (types, tags, importance)
- `cleanup [--threshold F] [--dry-run]` — Remove low-value memories (default threshold 0.2)
- `audit [--threshold F] [--json]` — Duplicate detection report (default threshold 0.75)
- `dedup [--threshold F] [--dry-run] [--interactive]` — Remove duplicate memories

Introspection:
- `get <id>` — Get a single memory by ID (JSON)
- `context [topic]` — Condensed summary by category
- `brain` — 3-tier memory visualization

Export / Import:
- `export [--output FILE]` — Export all memories to JSON
- `import FILE [--dry-run]` — Import memories from JSON (skip duplicates)

Sync (team sharing via git):
- `sync` — Push + pull in one step
- `sync push` — Export and push to git remote
- `sync pull [--from user/machine]` — Pull and import from git remote
- `sync status` — Show sync state and remote sources

Maintenance:
- `health` — Check if shodh-memory is available
- `health --index` — Check index health (JSON)
- `repair` — Repair index integrity
- `migrate` — Run pending memory migrations
- `migrate --status` — Show migration history

**What to do**:

1. Parse `$ARGUMENTS` to determine the subcommand (first word). If no arguments, default to `browse`. If unrecognized subcommand, pass through to `set-memory` directly.

2. **Check health first**:
   ```bash
   set-memory health
   ```
   If this fails (exit code non-zero), display:
   > "Memory system not available — shodh-memory is not running. Check with `set-memory health`."
   Then STOP.

3. **Execute the subcommand**:

   **status**:
   ```bash
   set-memory status $REMAINING_ARGS
   ```
   Display the output directly.

   **recall** (rest of arguments is the query and flags):
   ```bash
   set-memory recall "<query>" --limit 5 $REMAINING_FLAGS
   ```
   Recall modes (`--mode`): `semantic` (default), `temporal`, `hybrid`, `causal`, `associative`.
   Parse the JSON output. For each memory, display:
   - Type and tags
   - Content (truncated to 200 chars if long)
   - Creation date
   If no results, say "No matching memories found."

   **proactive** (rest of arguments is context string):
   ```bash
   set-memory proactive "<context>" --limit 5
   ```
   Parse JSON and display results like recall.

   **remember** (rest of arguments is the content):
   - Use the **AskUserQuestion tool** to ask which memory type to use:
     - Options: `Decision`, `Learning`, `Context`
   - Optionally ask for comma-separated tags (or skip)
   - Then run:
     ```bash
     echo "<content>" | set-memory remember --type <type> --tags <tags>
     ```
   - Confirm: "Memory saved."

   **list**:
   ```bash
   set-memory list $REMAINING_ARGS
   ```
   Parse JSON and display in a readable table format.

   **browse** (default):
   ```bash
   set-memory status
   set-memory list
   ```
   Display status summary, then group memories by type (Decision, Learning, Context) and show counts + recent entries.

   **forget** (pass all remaining args through):
   ```bash
   set-memory forget $REMAINING_ARGS
   ```
   **DESTRUCTIVE** — warn user before running without `--dry-run`. Display output directly.

   **stats / cleanup / audit / dedup** (pass all remaining args through):
   ```bash
   set-memory <subcommand> $REMAINING_ARGS
   ```
   Display the output directly. For `dedup` without `--dry-run` or `--interactive`, warn about destructive operation.

   **get** (argument is memory ID):
   ```bash
   set-memory get <id>
   ```
   Parse JSON and display the memory content, type, tags, and metadata.

   **context / brain** (pass through):
   ```bash
   set-memory context|brain $REMAINING_ARGS
   ```
   Display the output directly.

   **export / import** (pass through):
   ```bash
   set-memory export|import $REMAINING_ARGS
   ```
   Display the output directly. For `import` without `--dry-run`, warn that it will add memories.

   **sync** (pass subcommand through):
   ```bash
   set-memory sync $REMAINING_ARGS
   ```
   Display the output directly.

   **health / repair / migrate** (pass through):
   ```bash
   set-memory <subcommand> $REMAINING_ARGS
   ```
   Display the output directly.

   **projects**:
   ```bash
   set-memory projects
   ```
   Display the output directly.

**Important**:
- All `set-memory` commands auto-detect the project from git root
- Override with `--project NAME`
- If shodh-memory is not installed, all commands exit silently (exit 0)
- Memory types: `Decision` (architectural choices), `Learning` (patterns/gotchas), `Context` (background info, events, notes)
- Legacy aliases: `Observation` maps to `Learning`, `Event` maps to `Context` (with deprecation warning)

ARGUMENTS: $ARGUMENTS
