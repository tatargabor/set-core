## Context

The question relay already has a two-way outbound contract, used today by one external bridge:

- **Out:** the relay (or the auto-answer outbound in front of it) runs the configured command and
  pipes `{"questions": [{id, key, question, optionsList, multi, audience, source, valasz_tar}]}` to
  its stdin. `SET_RELAY_KIND` (`ask`, `permission`, `continuation`), `SET_RELAY_SESSION` and
  `SET_RELAY_CWD` are in its environment. Exit 0 means "posted". Anything else makes the relay
  release the question to the terminal.
- **Back:** the relay polls `<valasz_tar>/<id>__<key>.json` for `{"valasz": text}`.
- **Still waiting?** While a call waits, `<state>/waiting/<session>.json` carries its `id`. The
  record disappears when the call is answered, released or timed out.
- The auto-answer worker appends its proposal to the question text before forwarding, so a post
  shows it with no extra field.

Every machine without that external bridge can only notify (the `webhook` target, one-way). This
change gives set-core its own bridge, with the same answer rules the external one has proven in
daily use: numbered reactions, reply text, "number + note", ❌ to defer, ✅ to close a multi-select,
an acknowledgement, and closing a post whose question no longer waits.

## Goals / Non-Goals

**Goals:**
- Any machine can relay questions to a Discord channel and take the answer back, with set-core
  alone and one bot token.
- The answer rules match the ones the operator already knows, so a teammate's channel behaves the
  same way.
- Fail toward today: a bridge failure releases the question to the terminal and never invents an
  answer.

**Non-Goals:**
- A gateway connection, slash commands or buttons (interactions need a public endpoint or a
  long-lived gateway process).
- Scheduled re-posts, content masking, per-audience routing beyond the envelope's `audience` field.
- Migrating the owner's existing bridge.

## Decisions

**D1 — REST polling on a one-minute timer, no gateway.** A gateway client is a long-lived
websocket process with heartbeats, reconnects and a third-party library. The relay already
tolerates minute-scale latency: the hook polls every 3 s, but the human answers from a phone.
A oneshot `poll` each minute is restartable, has no state in memory, and the timer pattern
already exists (`idle_close.install_timer`). *Alternative:* the gateway gives instant answers;
rejected for the dependency and the always-on process.

**D2 — stdlib `urllib` against Discord REST v10.** set-core's core has no HTTP client
dependency, and the relay's webhook path already uses `urllib`. Rate limits: a 429 is retried
once after `retry_after`; anything else counts as a failure for that call. The `User-Agent` is the
generic `DiscordBot (set-core, <version>)` form Discord requires, with no personal data.

**D3 — reactions for choice, replies for text.** Number reactions 1️⃣–5️⃣ are the one-tap path from
a phone. Replies (a message whose `message_reference.message_id` is the post) carry free text and
notes. Reading reply content needs the bot's **Message Content** intent, which is a toggle in the
developer portal. `setup` says so, and `test` detects an empty-content reply and names the toggle.
Reactions are read per emoji (`GET …/reactions/<emoji>`), which returns the user ids. That is what
the allowed-user check needs; the message's reaction counts alone cannot tell who reacted.

**D4 — the answer rules are one pure function.** `decide(post, reactions_by_user, replies)`
returns `answer | defer | wait | unclear` with the text. Tests drive it directly, and `poll` only
gathers inputs and acts on the result. This is the same split the proven bridge uses, and for the
same reason: the rule is measured where no network is involved.

**D5 — allowed users are required.** Anyone who can read the channel could otherwise answer a
permission prompt. An empty list blocks both `post` and `poll`, so a half-configured machine
releases to the terminal instead of exposing questions.

**D6 — state lives under the relay's state dir.** Post records go to
`<question-relay state>/discord/posts/<id>__<key>.json` (mode 600), next to `waiting/` and
`answers/`. They hold the message id, the options and the timestamps. The question text is kept
only in the record, because the acknowledgement needs the option labels. It is never logged.
Seven days after answered or closed, records are pruned, matching the answer store's retention.

**D7 — where setup wires itself.** If `question_relay.command` is the auto-answer outbound
(`set-auto-answer`), the bridge goes into `auto_answer.forward_command`, so the decider still runs
first. Otherwise it goes into `question_relay.command`, and `question_relay.target` is set to
`command`. An existing different command is replaced only with `--replace`, and the old value is
printed so it can be restored.

**D8 — token outside config.json.** `set-config` writes `config.json`, which is a settings file
people cat and copy. The token goes to its own 600 file
(`~/.config/set-core/relay-discord.token`), read only by the bridge. `--token-stdin` keeps it out
of shell history.

**D9 — Discord copy in English.** set-core's product language is English. The question text
itself is whatever the agent asked, untouched.

## Risks / Trade-offs

- [The Message Content intent is off] → replies arrive empty. `test` posts a probe and reports
  the missing intent; reactions still work without it.
- [A minute of latency per answer] → acceptable for a phone answer. The hook's own timeout
  (55 min) is far longer.
- [Discord rate limits on a burst of posts] → the envelope is at most a few questions. One retry
  on 429, otherwise exit non-zero, and the relay releases the question to the terminal.
- [Two bridges configured on one machine] → setup refuses to replace without `--replace`, and
  `status` names the configured command.
- [Live verification needs a real bot] → the pure rules and the HTTP layer are tested with a fake
  transport. The end-to-end check needs a token and a channel from the operator, or runs on the
  teammate's machine. The task says so and stays open until it is done.

## Migration Plan

Opt-in per machine: `set-relay-discord setup …`. Rollback: `set-relay-discord setup --remove`
(stops the timer, restores the previous command it recorded), or set the command back by hand. The
owner's machine is not touched.

## Open Questions

- None blocking. Which channel and bot the teammate uses is theirs to choose at setup.
