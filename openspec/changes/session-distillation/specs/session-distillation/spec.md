## IN SCOPE
- Reading one finished session transcript and proposing candidate facts from it
- The admissibility gate that refuses a candidate (state claims, harness artifacts, repo-derivable facts, session-local detail)
- The confidentiality gate that runs BEFORE any write, using a runtime-resolved private-slug list
- Writing an admitted fact as one file in the native per-repository memory directory, plus exactly one index line
- The index budget, enforced as a refusal to append rather than as a warning
- The trace a distillation run must leave, and how a run is judged complete

## OUT OF SCOPE
- The `SessionEnd` hook and the queue it writes (see `session-end-queue`)
- Semantic search, tag filtering, temporal queries, full-text search, cross-device sync, version history — the six capabilities `remove-shodh-memory` deliberately did not replace
- Any second memory store, index, or database beside the native directory
- Distilling anything other than a completed transcript (live sessions, partial turns, in-flight prompts)

## ADDED Requirements

### Requirement: A distillation reads only a completed transcript
The distiller SHALL operate on a session transcript that the runtime has finished writing, identified by a queue entry, and SHALL NOT read the prompt currently in flight in any live session.

#### Scenario: A queued transcript is distilled
- **WHEN** the distiller processes a queue entry naming an existing transcript file
- **THEN** it reads that file end-to-end and produces zero or more candidate facts

#### Scenario: The named transcript no longer exists
- **WHEN** a queue entry names a transcript file that is absent
- **THEN** the distiller retires the entry with a recorded reason and writes no memory file

#### Scenario: A live session is never a source
- **WHEN** a transcript belongs to a session the runtime still holds open
- **THEN** the distiller leaves the entry queued rather than reading a partial file

### Requirement: A candidate that claims something about the user's state is refused
The distiller SHALL refuse any candidate whose content is an inferred emotion, a sentiment label, or any other claim about the user's state that the source text does not literally support. This is a refusal, not a downgrade or a flag for later review.

#### Scenario: An exclamation mark is not anger
- **WHEN** a candidate is derived from a user message such as `szuper!!!` or `pont így akartam!!!`
- **THEN** no memory file is written, and the refusal names the rule it applied

#### Scenario: A stated preference is admissible
- **WHEN** the user states a working preference in their own words and the candidate records that preference as a fact
- **THEN** the candidate passes this gate

### Requirement: A harness artifact is never stored verbatim
The distiller SHALL refuse any candidate whose body reproduces a harness artifact — a task notification, a cross-session message, another agent's system prompt, a system reminder, or a raw transcript fragment.

#### Scenario: A task notification reaches the distiller
- **WHEN** a candidate's body is the text of a task notification or system reminder
- **THEN** the candidate is refused and no file is written

#### Scenario: A fact learned from a notification survives
- **WHEN** the candidate states a durable fact that happened to be learned while a notification was on screen, in the distiller's own words
- **THEN** the candidate passes this gate

### Requirement: A candidate the repository already records is refused
The distiller SHALL refuse a candidate that is derivable from the repository itself — code structure, commit history, a documented past fix, or content already present in the project's instruction files.

#### Scenario: A fact already in the rule book
- **WHEN** a candidate restates something the project's `CLAUDE.md` already carries
- **THEN** the candidate is refused, because a second copy drifts

### Requirement: Confidentiality is enforced before the write, not after
The distiller SHALL check every candidate against the private-slug list resolved at run time from the framework's project registry and its allowlist, and SHALL refuse a matching candidate. The matched value SHALL NOT be echoed into the refusal, any log, or any diagnostic output.

#### Scenario: A consumer project name appears in a candidate
- **WHEN** a candidate's body or index line contains a private consumer slug, a partner name, or a personal name
- **THEN** no file is written, and the refusal names the rule without reproducing the matched text

#### Scenario: The list is never committed to this repository
- **WHEN** the confidentiality gate needs its pattern list
- **THEN** it resolves the list at run time from the registry and allowlist, and no pattern file naming a consumer exists in this repository

#### Scenario: The registry is unreadable
- **WHEN** the private-slug list cannot be resolved
- **THEN** the distiller writes nothing and reports the failure, rather than proceeding with an empty list

### Requirement: An admitted fact becomes one file plus one index line
The distiller SHALL write each admitted fact as a single Markdown file in the project's native memory directory with the required frontmatter (`name`, `description`, `metadata.type` of `user`, `feedback`, `project`, or `reference`), and SHALL add exactly one pointer line to `MEMORY.md`. It SHALL NOT create any store, index, or database beside these.

#### Scenario: One fact, one file, one line
- **WHEN** a candidate is admitted
- **THEN** exactly one new memory file exists and `MEMORY.md` grew by exactly one line

#### Scenario: An equivalent memory already exists
- **WHEN** an admitted fact is already covered by an existing memory file
- **THEN** the distiller updates that file instead of creating a duplicate, and `MEMORY.md` does not grow

### Requirement: The index budget is a refusal
Because only the first 200 lines or 25 KB of `MEMORY.md` are injected and nothing warns past that cut, the distiller SHALL refuse to append once the index would exceed 150 lines or 20 KB, and SHALL report the refusal with the measured size.

#### Scenario: The index is at the budget
- **WHEN** appending an index line would take `MEMORY.md` past 150 lines or 20 KB
- **THEN** no line is appended, no memory file is written, and the report states the measured line count and byte size

#### Scenario: The index is below the budget
- **WHEN** the index is within budget
- **THEN** the pointer line is appended and the measured size is recorded in the run's trace

### Requirement: A run is judged by its trace, not by its report
A distillation run SHALL leave a machine-readable trace naming the transcript consumed, each candidate's disposition and the rule that decided it, and the path of every file written. A run whose trace is absent SHALL be treated as not having run, whatever it reported.

#### Scenario: The distiller reports success but wrote nothing
- **WHEN** a run returns success and its trace names no written file and no refusal
- **THEN** the queue entry is not retired and the run is recorded as failed

#### Scenario: Every refusal is attributable
- **WHEN** a candidate is refused
- **THEN** the trace names which rule refused it, without reproducing any matched confidential value
