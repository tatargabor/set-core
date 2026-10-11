## Why

The question relay carries a question an agent asks with `AskUserQuestion`. But agents often
end a turn waiting on the user in prose instead — "Then tell me 'done'" after listing manual
steps — and that wait reaches nobody away from the terminal. The user asked (2026-10-11) for
such waits to be detected and to reach the chat channel too, answerable there, with options
offered where the question allows.

Measured before this proposal, in a real interactive session on the current runtime:

- the `Stop` hook input carries the final message text (`last_assistant_message`) and
  `stop_hook_active`;
- a `Stop` hook returning `decision: "block"` with a reason makes the model continue with the
  reason as its next instruction; told to re-ask with `AskUserQuestion`, it did — it wrote the
  steps into the question and built fitting options itself ("Done" / "There was a problem") —
  and the relay carried it, the answer came back, the agent continued;
- the continuation's own `Stop` carries `stop_hook_active: true`, so one conversion per turn
  cannot loop;
- a headless classifier call (`claude -p`, a small model, all hooks disabled, no session
  persisted) answered WAITING/DONE correctly in 3.6 s.

Anthropic's documentation has no recommendation to prefer `AskUserQuestion` over prose and no
setting that forces it; it calls instruction files advisory and hooks deterministic. A skill
is invoked at the model's discretion, so it would be as reliable as a rule; an external
watcher would see the wait late and still could not deliver the answer. A hook at the turn
end has both the moment and the text.

## What Changes

- **A `Stop` hook**, deployed like the relay hook. When the relay is off it exits at once.
  When it is on, a small model classifies the final message: is the agent waiting on the
  user (a question, a decision, a manual step to confirm)? If so, the hook blocks the stop
  once with an instruction to ask again with `AskUserQuestion` — with the context needed to
  answer from a phone, and short options that fit. The existing relay then carries it.
- **Never more than once per turn** (`stop_hook_active`), and every failure — classifier
  missing, slow, unparseable — lets the turn end as today.
- No new switch: it follows the relay's switch and readiness.

## Capabilities

### New Capabilities
- `agent-wait-detection`: turning an agent's prose wait into a structured question while
  the question relay is on.

### Modified Capabilities
<!-- none: the relay is consumed unchanged -->

## Impact

- New: `bin/set-hook-wait-detect`, `lib/set_orch/fleet/wait_detect.py` (Layer 1).
- `bin/set-deploy-hooks`: the hook joins the `Stop` matcher-"" entry; `install.sh` links it.
- While the relay is on, every turn end in a deployed project costs one small-model call
  (~4 s, inside the hook's timeout); a conversion costs one extra model turn.
