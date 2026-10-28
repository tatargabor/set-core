## Why

A wave board is shared by people who split the work between them, but it cannot say who owns an
item. What it shows instead, on every row and on the sync line, is the hostname of the machine
that last touched it (`szluka-ASUS-TUF-Gaming-A15-FA507UV-FA507UV` on one board, 31 times). The
user's verdict (2026-10-28): it "doesn't carry information"; the board should offer **choosable
assignees**, and every board of this kind should carry the same structure.

The hostname also lands in the tracked job file (`by`), so a public repository leaks a machine
name for no reader's benefit.

## What Changes

- **No machine names on the board.** Items no longer get a `by` field; a legacy `by` is dropped
  from the job file on the next write and never reaches the payload. The page shows neither an
  item's nor the sync's machine. (`pushed.json` keeps its local `by`: it is per-machine state,
  gitignored, never shown.)
- **Assignees, one structure for every board.** The job file gains a board-level `assignees` list
  (the names the page offers) and an optional item-level `assignee` (the default owner). CLI:
  `init --assignees A,B`, `assignees <job> A,B`, `add --assignee`, `assign <job> <item> <name|->`.
- **The page lets a viewer pick the assignee.** Each row gets a select with the board's names. A
  choice is written to the `board/assignees` document (one field per item id), which the agent's
  push of `board/state` never touches; the page shows that choice over the job file's default. This
  is the page's only write.
- **The skill says how to read it back**: `ArtifactData get board/assignees`, and `assign` to make
  a choice part of the tracked file.
