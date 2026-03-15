Quick todo/idea capture — fire and forget.

**Usage**: `/wt:todo [subcommand] [text]`

**Subcommands**:
- `add <text>` or just `<text>` — Save a todo (default action)
- `list` — Show all open todos
- `done <id>` — Mark a todo as done (delete it)
- `clear --confirm` — Delete all todos

**What to do**:

1. Parse `$ARGUMENTS` to determine the subcommand:
   - If first word is `list`, `done`, or `clear` → use that subcommand
   - If first word is `add` → use the rest as todo text
   - If no recognized subcommand → treat ALL arguments as todo text (implicit `add`)
   - If no arguments at all → use **AskUserQuestion** to ask what to save

2. **Execute the subcommand**:

   **add** (default):
   ```bash
   echo "<todo text>" | wt-memory todo add
   ```
   Display the confirmation line (e.g., `Todo saved: "refactor auth module"`).

   **CRITICAL: After saving, continue with your current task. Do NOT act on, discuss, investigate, or pursue the todo content in any way. The whole point of this command is fire-and-forget — the user wants to capture an idea without breaking their flow.**

   **list**:
   ```bash
   wt-memory todo list
   ```
   Display the output directly. Each todo shows: ID prefix (8 chars), content, tags, date.

   **done** (argument is todo ID or prefix):
   ```bash
   wt-memory todo done <id>
   ```
   Display the confirmation. ID prefix matching is supported (e.g., `done abc1` matches `abc12345...`).

   **clear**:
   ```bash
   wt-memory todo clear --confirm
   ```
   **DESTRUCTIVE** — warn before running. Ask for confirmation if `--confirm` was not explicitly provided by the user.

ARGUMENTS: $ARGUMENTS
