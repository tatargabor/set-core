# Token Efficiency Rules

Every tool call adds to context cost. These rules reduce wasted turns.

## Subagent discipline

Do NOT spawn an Agent/subagent for tasks that can be done with direct tool calls:
- Reading a few files → use Read directly
- Searching for a pattern → use Grep directly
- Finding files → use Glob directly
- Checking if something exists → use Glob or Bash `ls`

Only spawn Agent when the task requires multi-step exploration across many files, or you genuinely need an independent context (e.g., code review).

## Do not re-read files

If you already Read a file earlier in this session, refer to the earlier result. Do not Read it again unless:
- You edited the file since the last read (and need to verify)
- The conversation context was compacted and you lost the content

CLAUDE.md and START.md are already in your system prompt — never Read them with the Read tool.

## TodoWrite sparingly

Only update your todo list at meaningful milestones:
- After completing a logical group of tasks
- When priorities change

Do NOT call TodoWrite after every single file edit. Batch your status updates.

## Prefer Edit over Write

When modifying existing files, use Edit (sends only the diff) instead of Write (sends the entire file content). Write is only for creating new files or complete rewrites.

## Bash: use dedicated tools

Use the dedicated tools instead of shell equivalents:
- `cat/head/tail file` → Read tool (with offset/limit for partial reads)
- `grep/rg pattern` → Grep tool
- `find . -name` → Glob tool
- `sed/awk` for edits → Edit tool

Reserve Bash for commands that genuinely need shell execution: git, npm/pnpm, build tools, test runners, process management.

## Parallel tool calls

When you need multiple independent pieces of information, make all calls in a single message. For example, if you need to read 3 files, send 3 Read calls in parallel — not sequentially.
