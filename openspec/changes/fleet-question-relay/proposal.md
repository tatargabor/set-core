## Why

When an agent asks a blocking question (`AskUserQuestion`: a question with an option list),
its terminal stops until somebody at this machine answers. Away from the desk, that is time
lost on every agent at once. The user asked (2026-10-10, confirmed 2026-10-11) for one switch
in the fleet: when it is on, every such question from a set-core-managed agent goes to a chat
channel, the answer comes back, and the agent continues. A second operator on another machine
must be able to use the same mechanism with their own channel, without the first operator's
tooling.

Measured on the current runtime before this proposal, in an interactive session:

- a `PreToolUse` hook on `AskUserQuestion` can answer the question — it returns the original
  input plus `answers`, and no picker appears; a hook waited 700 s and still delivered;
- a hook that exits 0 with no output, even after waiting, **releases**: the normal picker
  appears, and the question is then in the transcript like any other;
- while the hook waits, the session reads as `busy` and the question is NOT in the transcript,
  so nothing on the fleet can see a relayed question unless the relay reports it;
- headless (`-p`) sessions are not offered the tool at all, so they are out of scope.

## What Changes

- **A relay hook**, deployed as `PreToolUse` matcher `AskUserQuestion` to every project. When
  the switch is off it exits at once and nothing changes. When it is on, it hands the question
  to the operator's configured outbound and either waits for the answer or releases at once,
  depending on the outbound.
- **Two outbound kinds, chosen per machine in local config** (never in a repository):
  - **command (two-way):** a local command takes a question envelope on stdin and later
    delivers the answer as a file. The hook waits, re-checking the switch and a release
    marker, and answers the question when every answer has arrived. The envelope shape is the
    one an existing chat bridge on this machine already speaks.
  - **webhook (notify only):** a chat webhook gets a short notice and the question is released
    at once, so it is answered at the terminal. A webhook cannot carry an answer back.
- **Fail-open to the terminal.** Every failure (no configuration, a refused or failed
  hand-off, a timeout, the switch turned off, an explicit release) ends in the normal picker,
  never in a lost or invented answer.
- **The fleet header gets the switch**, its readiness (what configuration is missing), the
  count of questions waiting on the channel, and a per-question "answer here instead".

## Capabilities

### New Capabilities
- `agent-question-relay`: forwarding an interactive agent's blocking question to an
  operator-configured outbound and bringing the answer back — the hook, the per-machine
  configuration, the waiting record the fleet reads, and the fleet's switch and release.

### Modified Capabilities
<!-- none. `work-cycle-question-outbound` (open) covers questions a work cycle writes into a
     task file; this covers the interactive tool. Both use the same envelope field spelling —
     see design.md D2. -->

## Impact

- New: `bin/set-hook-question-relay`, `lib/set_orch/fleet/question_relay.py` (Layer 1 —
  domain-free), routes in `lib/set_orch/api/fleet.py`, `web/src/components/FleetRelay.tsx`,
  `web/src/lib/fleetRelay.ts`, the header in `web/src/pages/Fleet.tsx`.
- `bin/set-deploy-hooks`: a new `PreToolUse` entry (matcher `AskUserQuestion`, long timeout).
  Existing projects get it on their next `set-project init`.
- Local config keys under `question_relay.*`; runtime state under
  `~/.local/share/set-core/question-relay/`.
- Every interactive session in a deployed project runs the hook on every `AskUserQuestion`;
  with the switch off this is one config read.
