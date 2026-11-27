## Context

`continuation.continue_turn` posts after a DONE verdict, with a summary and up to three
`NEXT:` suggestions from one headless model call that sees only the final message. An agent's
"done" is usually local: a board empty, a step finished, a release out. The session was
started for something larger, and that reason lives only in its opening prompt.

## Goals / Non-Goals

**Goals:** remind the owner of the original goal in the post, and make "keep going" a one-tap
answer that sends the agent back to its goal rather than to the last thing it said.

**Non-Goals:** deciding by itself whether the goal is met (the owner, or the auto-answer under
its existing rules, decides), persisting goals, and changing when a continuation posts.

## Decisions

**D1 — The opening prompt is the goal source, read from the transcript head.** It is the one
place that says why the session exists, and it is already on disk. The transcript is read from
its start (bounded to 400 lines), and the first user entry whose content is the user's own text
is taken. Tool results, `<command-…>` / `<local-command-…>` wrappers, caveat blocks and
task notifications are skipped. Alternative considered: the handoff file of the thread. Rejected
here because not every session has one; a session started by an automatic `/clear` gets the
auto-continue text as its opening prompt, which names the handoff, and the model reads that.

**D2 — The model states the goal; the code does not summarise.** The suggester already runs
once per continuation. One extra `GOAL:` line costs nothing extra and keeps the code
domain-free.

**D3 — A fixed first option, not a model suggestion.** "Keep going" must be present every time,
including when the suggester fails, because the owner's complaint is exactly the stop that has
nothing better to offer. Its wake instruction makes the agent re-check the goal itself and stop
with a one-line reason when it no longer holds. So a wrong tap costs one turn, not an unwanted
change.

## Risks / Trade-offs

- [The opening prompt is about something that has since been settled] → The instruction makes
  the agent check that the goal still holds before continuing, and the post asks the owner the
  same thing.
- [Prompt text reaches the headless call] → Same boundary as the final message today: it goes
  to the one headless call and the outbound envelope only, and is never logged.

- [A session started by an automatic `/clear` has the auto-continue text as its opening prompt,
  measured on a real transcript the day this shipped: the goal itself is in the reloaded
  handoff, not in the prompt] → The post then often has no `Started for:` line. The keep-going
  instruction still sends the agent to re-read the handoff it loaded, so the one-tap answer
  works. Reading the handoff's goal into the post is a possible follow-up.

## Migration Plan

Additive; rollback by revert. No stored state.
