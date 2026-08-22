## IN SCOPE
- The hook event the framework registers to learn that a session finished, and why it is `SessionEnd` rather than `Stop`
- What the hook writes: one queue entry per finished session, and nothing else
- What the hook is forbidden to do in-process
- How a queue entry is retired, and what happens to one that fails repeatedly

## OUT OF SCOPE
- What a distillation reads out of the transcript and what it may write (see `session-distillation`)
- Any hook that fires per assistant turn, per tool call, or per prompt
- Scheduling policy for the distiller itself (when it runs, how often)

## ADDED Requirements

### Requirement: The framework registers SessionEnd, never Stop, for this purpose
The framework SHALL learn that a session finished through the `SessionEnd` hook event. It SHALL NOT use `Stop` for this purpose, because `Stop` fires at the end of every assistant turn and therefore observes prompts still in flight — the measured cause of the removed subsystem's 89.8 % noise rate.

#### Scenario: A session ends
- **WHEN** a session in a project where the framework is installed ends
- **THEN** exactly one queue entry is created for that session

#### Scenario: An assistant turn ends mid-session
- **WHEN** the assistant finishes a turn while the session continues
- **THEN** no queue entry is created

### Requirement: The hook enqueues and does nothing else
The `SessionEnd` hook SHALL write one queue entry containing the transcript path, the project slug and a timestamp, and SHALL NOT read the transcript, call a model, write a memory file, or take any action whose duration depends on session size.

#### Scenario: A long session ends
- **WHEN** a session with a very large transcript ends
- **THEN** the hook's work is bounded by writing one small entry, and it does not read the transcript

#### Scenario: The hook cannot write its entry
- **WHEN** the queue directory is unwritable
- **THEN** the hook fails visibly rather than silently, and the session's end is not recorded as processed

### Requirement: A queue entry is retired only against evidence
A queue entry SHALL be retired only when the distillation run's trace exists and names that entry's transcript. A run's own report of success SHALL NOT retire an entry.

#### Scenario: A distiller reports done with no trace
- **WHEN** a distillation subprocess exits zero but leaves no trace naming the transcript
- **THEN** the entry stays queued and the failure is recorded

#### Scenario: A repeatedly failing entry
- **WHEN** an entry has failed distillation a bounded number of times
- **THEN** it is moved aside with its failure reasons preserved, rather than retried forever or deleted silently
