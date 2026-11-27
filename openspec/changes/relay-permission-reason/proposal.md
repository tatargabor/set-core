## Why

A permission prompt that a PreToolUse hook raised with `ask` reaches the relay channel as an
Allow / Deny post, but the post carries only the tool summary cut at 160 characters. It never
says WHY the hook asked, because the runtime's `PermissionRequest` payload holds `tool_name`,
`tool_input` and `permission_suggestions` and nothing from the asking hook (measured, B-188).
Measured again on 2026-11-27 on the real channel: a guard's `ask` waited 22 minutes on the
phone with a truncated command and no reason, and the owner finally answered it in the
terminal. The reason was the one thing needed to decide, and in that case it would also have
shown that the guard had misfired. The owner asked for the decision to be possible from the
channel, and chose "the reason in the post" over automatic answers.

## What Changes

- A new carrier mode, `set-hook-notify-relay --ask-reason`. A guard hook calls it beside its
  `ask` return, piping its own PreToolUse input plus its reason (`reason`, `source`) on stdin.
  The carrier stores the reason in the relay's state directory, keyed by the session and a hash
  of the tool name and canonical tool input. It acts only while the relay switch is on, has no
  answer path, always exits 0, and never logs the command or the reason text.
- The permission post built by `permission_question` gains a `Why it asks (<source>): <reason>`
  line when a matching, fresh reason exists. Matching is exact on session, tool and input;
  fresh means at most 10 minutes old; each reason is used once.
- The permission post shows the command up to a bounded length (1200 characters) with an
  explicit cut marker, instead of the 160-character summary. This applies with or without a
  reason.
- A reason is removed when its permission call ends, and reasons older than the freshness
  window are pruned on the next write or read.
- Unchanged: the auto-answer never writes a permission; the terminal stays live; the
  `--text` notification mode keeps working as before.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `agent-question-relay`: ADDED requirements. A hook-raised confirmation can hand its reason to
  the relay, and the permission post shows that reason and a bounded full command. These are
  added rather than modified because the permission-post requirement itself still lives in the
  unarchived `relay-answerable-blocking-points` change.

## Impact

- `bin/set-hook-notify-relay`: new `--ask-reason` mode.
- `lib/set_orch/fleet/question_relay.py`: reason store (write, match, consume, prune), and
  `permission_question` / `permission` using it.
- `tests/unit/`: new tests for the store, the matching, and the post text.
- Adoption: the family plugin's guard hooks call the carrier. That is the plugin owner's change;
  set-core announces the carrier and its stdin shape on the agent bus.
- Bug register: closes B-188 (a) once a real guarded command shows its reason on the channel.
