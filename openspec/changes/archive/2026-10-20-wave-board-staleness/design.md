## Context

A wave board has three layers (`wave-board` spec):
- the tracked job file;
- `sync`, which derives status from evidence and runs on every Stop;
- the agent's own `set`.

The third layer is the only one that can move an item with no evidence, or a `blocked` item.
Nothing asks for it. The Stop hook prompts only for a push, and a push is due only when the
payload hash changed.

Measured 2026-10-20 over 8 boards in 7 projects (B-165):
- `sync` would move 0 items on every board;
- 70 of 168 unfinished items have no evidence;
- 14 of those are `blocked`, plus 2 `blocked` items with evidence that cannot override them;
- the repositories had 1 to 438 commits on `HEAD` since each board's newest item `updated`.

The board with 1 commit since was current. Its one commit was the commit that recorded the
board's own change.

## Goals / Non-Goals

**Goals:**
- An agent working in a project is asked to update the items only it can move, when the
  repository has clearly moved on since the board did.
- A board that is correct but quiet can say so, and stops being flagged.
- The fleet shows a stale board as stale, on the closed chip and in its row.

**Non-Goals:**
- **New evidence types**, such as a git tag closing a release item. This was option 3 in the
  discussion and is a follow-up.
- **Deciding statuses for the agent.** The reminder lists items; it never sets one.
- **Writing into a project tree from set-core.** The fleet stays read-only. The only files the
  hook writes are machine-local stamps under the already-ignored `.set/waveboard/`.
- **Pushing the `reviewed` stamp to the board page.**

## Decisions

### D1 — "manual open" is what `sync` cannot move

An item is manual open when its status is neither `done` nor `skipped`, and either it has no
evidence or its status is `blocked`.

Those are exactly the items for which `sync_job` either skips evaluation (no evidence) or keeps
the status whatever evidence says (`blocked`, which is sticky). An item whose evidence gives no
verdict is not counted: its evidence will move it when the work appears, so asking a person
about it is noise. That was 43 items in the measurement, and 42 of them named work that existed
nowhere yet.

### D2 — the board's last change

The board's last change is the newest of these:
- every item's `updated`;
- the job file's `reviewed.at`;
- failing both, `created`, read as midnight UTC.

If none of them parses, the staleness is not measurable: `commits_since_change` is null and the
board is not stale. A gap is not a zero, so it is never reported as "0 commits".

### D3 — staleness is counted in commits on `HEAD`, not in hours

`git rev-list --count --since=<last change> HEAD` runs in the board's repository root, using the
committer date.

- **Why commits rather than hours:** a board in a quiet project is not stale, whatever its age.
  The screenshot's 292 h board and its 32 h board differ in commits since (80 against 1), not
  in how wrong they look.
- **Why `HEAD` rather than `--all`:** evidence is evaluated on `HEAD`, and a board describes the
  branch it lives on. Work on another branch is not yet this board's business.

### D4 — the threshold is 3 commits, and both sides read the same default

A board is stale when `manual_open > 0` and `commits_since_change >= 3`. The threshold is
`SET_WAVEBOARD_STALE_COMMITS`, default 3.

**Why not 1:** the commit that records a `set` or a `reviewed` is itself newer than the stamp it
records. Measured: the one current board had exactly that one commit. With a threshold of 1,
every board would be stale the moment its own change was committed. 3 leaves room for that
commit plus one ordinary follow-up.

### D5 — `reviewed` lives in the tracked job file, outside the pushed content

`set-wave-board reviewed <job>` sets `"reviewed": {"at": <iso>, "by": <host>}` at the top level
of the job file.

- **Outside the pushed content:** `content_of()`, and therefore the content hash and the push
  payload, keeps exactly `schema, job, title, waves`. A review never causes a push reminder.
- **Machine-local was rejected.** The fleet, and a session on another machine, would keep
  flagging a board that someone has already confirmed. "Someone confirmed this board current
  at T" is a fact about the board, so it travels with the board.

### D6 — the review reminder has its own backoff and its own off switch

- **Backoff:** `SET_WAVEBOARD_REVIEW_SECONDS`, default 14 400 (4 h). The stamp is
  `.set/waveboard/<job>.review-nag`.
- **Off switch:** `SET_WAVEBOARD_REVIEW=off` silences only the review reminder.
  `SET_WAVEBOARD_PUSH=off` still silences the whole hook, as before.

A review asks for judgement, so it is rarer than a push, which is a mechanical copy. The push
reminder keeps its 30 minutes. The rules that keep the hook silent stay in force: its own
continuation, a linked worktree, no board, no repository, and any error.

### D7 — one block when both reminders are due

The hook prints at most one `{"decision":"block"}` per Stop. When both reminders are due, the
reason carries the push procedure first, then the review list. The order matters because the
review may change the payload, and the next Stop will then ask for that push.

### D8 — what the reminder shows, and what the fleet does not

The review reason names, for each due job:
- the number of commits since the board's last change;
- up to 20 manual open items as `id`, status and title, then "+N more";
- the two commands, `set-wave-board set <job> <item> <status>` and
  `set-wave-board reviewed <job>`.

Titles reach only the project's own agent, inside its own repository. The fleet summary keeps
its rule of counts only (`fleet-wave-overview`): it gains `manual_open` as a number, and no
title.

### D9 — the rule is written twice, and a test holds the two together

`bin/set-wave-board` and `bin/set-hook-waveboard` are standalone scripts that do not import
`set_orch`, because they run from a consumer's hooks with whatever Python is on `PATH`. So:
- `lib/set_orch/fleet/waveboards.py` keeps its own copy of D1, D2 and D4, about 25 lines;
- a test runs both implementations on the same fixture repository and asserts the same
  `manual_open`, `commits_since_change` and `stale`.

The same pattern already holds the media suffix lists together.

### D10 — the fleet reads git under a timeout, and failure is visible as null

There is one `git rev-list` per readable board, with a 5 s timeout. A failure leaves
`commits_since_change` null, which the row shows as "not measured" in its age tooltip, and is
logged at DEBUG with the reason. It is not a WARNING, because the route is polled every 60 s
and a project without git would otherwise fill the journal (B-162). The null is what makes the
failure visible.

### D11 — the row and the chip

- **Row:** a stale row gets an amber marker after its age, "⟳ N commits since", whose tooltip
  says how many manual open items only an agent can move.
- **Chip:** the closed chip gains an amber count of stale boards, beside the blocked and
  unreadable counts.

A non-stale row is unchanged, which keeps the list as quiet as it is now.

## Risks / Trade-offs

- **An agent can run `reviewed` reflexively to silence the reminder.** → The reason lists the
  items and asks for each to be checked. The stamp records `by`. A reflexive stamp only buys
  the next 3 commits.
- **Noise in a busy repository.** → At most one review reminder per job per 4 h, only in the
  main checkout (worktrees are skipped as now), and only while manual open items exist.
- **The `reviewed` stamp edits a tracked file**, so it needs a commit like any `set` does. →
  This is the same cost the agent already pays for `set`, and that commit is accounted for in
  D4.
- **Duplicated rule (D9).** → The cross-check test fails on any drift.
