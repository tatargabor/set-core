## Why

When a work cycle asks a person something, the answer comes back as text and is carried into
the next run. `lib/set_workcycle/prompt.py:95-101` interpolates it directly:

```
- **{task}**: {answer}
```

under the heading *"Questions that have been answered"*, followed by *"They are decided now —
act on them rather than asking again."* No delimiting, no escaping, no bound. That string
becomes `cmd += ["--", prompt]` for a `claude -p` invocation that runs as **a full session**
with the project's own hooks and permission mode (`lib/set_workcycle/runner.py:60-81`), in the
project's tree, unattended.

Today that is defensible: an answer can only be written by somebody already at this machine
(`connector.write_answer` — *"Any caller may do this"*). The threat model is about to change.
`work-cycle-question-outbound` exists precisely to carry questions to a chat channel and take
answers back from it, which extends the write surface to whoever can post there. An answer
reading *"…also run: …"* would be indistinguishable from a decision a person made, and every
gate, test and verdict would still pass — **the injected instruction is the work product.**

The same document carries a second free-text field, `source`, which reaches a log line
verbatim (`cli.py:130-131`) while being sanitised for the filename. The enumeration missed it
because the rule names "the question and the answer", and `source` is neither.

**This change is a precondition for `work-cycle-question-outbound`, not a task inside it.** No
outbound is wired until it lands.

## What Changes

- **The answer's text is delimited where it lands**, and the prompt states what it is: a
  person's decision on a specific question, whose content is data. Deciding the question is
  what an answer may do; issuing new work is not.
- **The answer is bounded in length**, and an over-long answer is refused with a stated reason
  rather than truncated into something a person did not write.
- **Where the question offered a closed set of choices, an answer outside that set is
  refused** rather than pasted through. ⚠ **No option list exists in this engine today** —
  `OpenDecision` carries `task` and `question` only, and the awaiting marker records the
  question text alone. The structured list is produced by `work-cycle-question-outbound`,
  which is gated on this change, so this requirement is **inert until that lands**. It is
  written here because the check belongs at this boundary, and stated as inert so nobody
  reads a green test as a live control.
- **A refused answer is a distinct outcome**, and where it lives is stated: it is not applied,
  not consumed, not quarantined, and it does not count towards the parse-attempt budget.
  Without that, the obvious implementation — raising inside the parse block — would defer a
  legitimate over-long answer three times and then quarantine it.
- **Every free-text field of the answer document is enumerated and bounded before it reaches a
  log line** — `source` included (B-37).

**Not in this change:** any outbound; the intake mechanics (`deferred-work-connector` (in `work-cycle-engine-apply-first`)); B-36,
which is a separate defect in the same module.

## Capabilities

### New Capabilities
- `work-cycle-answer-trust`: how an answer's text is treated once it enters a run — delimited
  as data rather than as a standing instruction, bounded, constrained to the offered choices
  where there were any, and kept out of log lines.

### Modified Capabilities
<!-- None. `deferred-work-connector` (in `work-cycle-engine-apply-first`) describes carriage and explicitly leaves trust to this
     change; no requirement of it changes. -->

## Impact

- `lib/set_workcycle/prompt.py` — where the answer is rendered into the unit prompt.
- `lib/set_workcycle/connector.py` — where an answer document is read, and where a bound and
  an option-set check belong.
- `lib/set_workcycle/cli.py` — the log line carrying `source`.
- No new dependency, and no change to how an answer is delivered or applied.
