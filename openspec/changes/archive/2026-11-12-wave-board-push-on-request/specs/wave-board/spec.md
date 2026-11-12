## MODIFIED Requirements

### Requirement: A Stop hook makes the agent push

`set-hook-waveboard` SHALL run on the Stop event and SHALL be OFF unless the machine opts in:
it SHALL exit 0 without output, without running sync, unless `SET_WAVEBOARD_PUSH` is `on`,
`1`, `true`, `yes` or `worktree`. An unset, empty or unrecognised value is off. When on, it
SHALL also exit 0 without output when `stop_hook_active` is true, outside a git repository, in
a linked git worktree (unless `SET_WAVEBOARD_PUSH=worktree`), or when `docs/waveboard/` does
not exist. Otherwise it SHALL run sync quietly and decide per job, from the push
class sync reports, whether to ask for the push now:

- `first` (no push recorded on this machine) or `milestone` (since the last push a wave has
  had every item `done` or `skipped`, or an item has turned `blocked`): ask, unless reminded
  within the backoff (default 30 minutes, `SET_WAVEBOARD_NAG_SECONDS`, timestamp in
  `.set/waveboard/<job>.nag`);
- `progress` (item statuses, titles, waves or dependencies changed, no milestone): ask only
  when the job's oldest pending target was last pushed at least
  `SET_WAVEBOARD_DEBOUNCE_SECONDS` ago (default 3600) and the job was not reminded within that
  time either;
- `notes` (only notes, `updated` / `by` stamps or evidence definitions changed): never ask.

A job's board document and its combined-board document SHALL be decided together, by the
strongest class among them, and asked for in the same block. When at least one job is due it
SHALL print one `{"decision":"block","reason":...}` whose reason is the exact push procedure:
the `ArtifactData` `set` call with the URL, `collection=board`, `doc_id=state`, the payload
path, and `if_version` (the last recorded version, or omitted when none is recorded), what to do
on a version conflict, and the `pushed` command to run after. It SHALL NOT use the network and
SHALL finish well inside its timeout.

`pushed` SHALL record, with the hash and version, the marks the next push is classed against
— the finished waves, the blocked items and a hash of the visible substance — but only when the
recorded hash is the current payload's own. A record without marks SHALL class the next change
as `progress`, never as `notes`.

#### Scenario: Off unless the machine opts in

- **WHEN** a repository has a job with a pending push and `SET_WAVEBOARD_PUSH` is unset
- **THEN** the hook prints nothing, exits 0, and does not run sync

#### Scenario: Opted in, the reminder works as before

- **WHEN** the same repository is stopped in with `SET_WAVEBOARD_PUSH=on`
- **THEN** the hook blocks with the push procedure

#### Scenario: The hook's own continuation does not loop

- **WHEN** the Stop event carries `stop_hook_active: true`
- **THEN** the hook prints nothing and exits 0

#### Scenario: A linked worktree is not the board's source

- **WHEN** the Stop event comes from a linked git worktree of a repository with a pending job
- **THEN** the hook prints nothing

#### Scenario: Backoff

- **WHEN** the hook blocked for a job and runs again within the backoff with the job still
  pending
- **THEN** it prints nothing

#### Scenario: Routine progress is batched

- **WHEN** a job was pushed less than `SET_WAVEBOARD_DEBOUNCE_SECONDS` ago and an item has
  since moved from `todo` to `doing`
- **THEN** the hook prints nothing, and `set-wave-board pending` still lists the job

#### Scenario: A milestone is asked for at once

- **WHEN** an item turned `blocked`, or the last open item of a wave became `done` or
  `skipped`, since the job's last push
- **THEN** the hook blocks with the push procedure without waiting for the debounce

#### Scenario: A notes-only change is never asked for

- **WHEN** only an item's note changed since the job's last push
- **THEN** the hook prints nothing, even with both backoffs at zero, and the change goes with
  the next push that is asked for

#### Scenario: The board and the combined document travel together

- **WHEN** a job's combined-board document has never been pushed and its board has only a
  notes change
- **THEN** one block asks for both pushes

### Requirement: The Stop hook asks for a review of a stale board

Under the same silence rules as the push reminder, `set-hook-waveboard` SHALL also evaluate each
job's staleness. The silence rules are: `SET_WAVEBOARD_PUSH` not opted in (unset or off), its own
continuation, no repository, a linked worktree, no `docs/waveboard/`, and any error.

For each stale job not reminded within the review backoff, it SHALL include a review reminder.
The backoff is `SET_WAVEBOARD_REVIEW_SECONDS`, default 14 400, with the timestamp in
`.set/waveboard/<job>.review-nag`. The reminder SHALL name:
- the number of commits since the board's last change;
- up to 20 manual open items, each with id, status and title, followed by the count of the rest;
- the `set-wave-board set <job> <item> <status>` command;
- the `set-wave-board reviewed <job>` command.

`SET_WAVEBOARD_REVIEW=off` SHALL silence only the review reminder.

The hook SHALL print at most one `{"decision":"block","reason":...}` per Stop. When a push and a
review are both due, one block SHALL carry the push procedure first and the review list after
it.

#### Scenario: A stale board blocks the stop with its items

- **WHEN** a stale job with no page URL has manual open items, and the hook runs in the main
  checkout
- **THEN** it prints one block whose reason names the commits since, each manual item's id, and
  both commands

#### Scenario: The review backs off on its own clock

- **WHEN** the hook gave a review reminder for a job and runs again within the review backoff
- **THEN** it prints nothing for that job's review

#### Scenario: Both due, one block

- **WHEN** a job is both pending a push and stale
- **THEN** the hook prints exactly one block, and its reason holds the push procedure before
  the review list

#### Scenario: The review alone can be switched off

- **WHEN** `SET_WAVEBOARD_REVIEW=off` and a job is stale but not pending
- **THEN** the hook prints nothing

#### Scenario: A worktree is still skipped

- **WHEN** the Stop event comes from a linked worktree of a repository with a stale job
- **THEN** the hook prints nothing
