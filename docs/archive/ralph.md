[< Back to README](../README.md)

# Ralph Loop

Ralph runs Claude Code autonomously through task lists. Start a loop, let the agent work through tasks, and come back to review the results. Each iteration starts a fresh Claude Code session, checks task completion, and continues until done.

## Commands

| Command | Description |
|---------|-------------|
| `set-loop start [change-id]` | Start autonomous Claude Code loop |
| `set-loop stop [change-id]` | Stop running loop |
| `set-loop status [change-id]` | Show loop status |
| `set-loop list` | List all active loops |
| `set-loop history [change-id]` | Show iteration history |
| `set-loop monitor [change-id]` | Watch loop progress live |

Claude Code skill: `/set:loop`

## How It Works

1. Ralph starts Claude Code with a task prompt
2. Claude works until it finishes or hits the context limit
3. Ralph checks task completion (reads `tasks.md` checkboxes)
4. If tasks remain, starts a new Claude Code iteration
5. Repeats until all tasks are done or max iterations reached

The GUI shows progress in real-time:

```
│  add-user-auth  │ running │ ralph:apply │ 45% │ 3/10 │
```

## Let the Agent Work Overnight

You have a well-defined task list. Start a Ralph loop and let Claude work through it:

```bash
set-loop start add-user-auth --task "Implement all tasks in tasks.md"
```

Come back in the morning:

```bash
set-loop history add-user-auth   # what happened?
set-loop monitor add-user-auth   # watch live if still running
set-loop stop add-user-auth      # stop if needed
```

## When to Use Ralph

**Good fit:**
- Well-scoped tasks with clear completion criteria (task lists, test suites, migrations)
- Implementation work after specs and design are done
- Repetitive changes across many files

**Not ideal for:**
- Exploratory or design-heavy work
- Tasks requiring frequent human judgment calls
- Work that needs real-time feedback

## Ralph in Orchestration

The orchestrator uses Ralph loops internally — each dispatched change gets its own Ralph loop. You don't interact with Ralph directly during orchestration; the orchestrator manages the loops.

---

*See also: [Sentinel & Orchestration](sentinel.md) · [Worktree Management](worktrees.md) · [Control Center GUI](gui.md)*
