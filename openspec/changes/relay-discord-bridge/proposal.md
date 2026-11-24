## Why

The question relay hands every blocking point (a question, a permission prompt, a finished turn's
"what next?") to a configured command, and reads the answer back from its answer store. set-core
ships no command that talks to a chat channel both ways. The only working two-way bridge lives in
one operator's private assistant repository, so on any other machine the relay can only notify
(the webhook target), and an answer still needs the terminal or the fleet panel.

Measured 2026-11-24: a teammate's machine got the full set-core update, but the relay could not reach
Discord the way it does on the owner's machine, because the forward command there points into that
private repository. The owner asked for the bridge to be built into set-core, so every machine
works the same way.

## What Changes

- A new tool, `set-relay-discord`, speaks the relay's existing outbound contract with Discord. It
  uses the Discord REST API with a bot token and the standard library only.
  - `post` is the forward command. It reads the relay envelope on stdin, posts one message per
    question with its options as numbered reactions, and exits 0 only when every post landed.
  - `poll` runs every minute from a user timer. It reads the reactions and replies of allowed users
    only, decides the answer, writes it into the relay's answer store, and acknowledges it on the
    post. It closes a post whose question no longer waits, so an answer typed there is not lost
    silently.
  - `setup` stores the token in a private file outside every repository and the channel and allowed
    users in machine-local config. It checks access, wires the relay to the bridge, and installs the
    timer. `status` and `test` report and probe.
- Nothing in the relay itself changes. The envelope, the answer-file shape and the waiting record
  are the contract the bridge reads, exactly as an external bridge reads them today.
- An operator who already uses another bridge keeps it. The bridge is opt-in per machine.

## Capabilities

### New Capabilities
- `relay-discord-bridge`: a two-way Discord bridge for the question relay. It covers the post, the
  answer rules (reactions, replies, defer, multi-select close), allowed users, the acknowledgement,
  closing stale posts, and the setup that wires it.

### Modified Capabilities
(none — the relay's outbound contract is read, not changed)

## Impact

- New: `lib/set_orch/fleet/relay_discord.py` (core, domain-free) and `bin/set-relay-discord`, plus
  a systemd user timer and service it installs.
- Config (machine-local, never committed): `relay_discord.channel_id`,
  `relay_discord.allowed_users`, and the token file `~/.config/set-core/relay-discord.token`
  (mode 600).
- Uses `question_relay.command`, or `auto_answer.forward_command` when the relay command is the
  auto-answer outbound, as the place it wires itself.
- Network: outbound HTTPS to the Discord API only, from the posting command and the timer.
- Discord side: a bot application with the Message Content intent enabled, invited to one channel.
