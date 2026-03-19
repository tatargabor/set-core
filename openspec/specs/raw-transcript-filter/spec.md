## Requirements

### Requirement: Rule-based transcript filter replaces Haiku LLM extraction
The Stop handler SHALL process the full JSONL transcript using rule-based filters instead of calling Claude Haiku LLM. The filter SHALL run as a background process (disowned) and complete in under 500ms for a typical session transcript.

**The filter SHALL sanitize all string content after `json.loads()` to replace lone surrogate codepoints with U+FFFD (REPLACEMENT CHARACTER).** This prevents `UnicodeEncodeError` when content is later passed to `set-memory remember` via `subprocess.run(..., text=True)`.

**The filter SHALL NOT silently swallow exceptions.** The `except Exception: pass` block around `subprocess.run` SHALL be replaced with specific `UnicodeEncodeError` handling that logs the error to stderr (which flows to `$STOP_LOG_FILE`) and continues processing remaining entries.

#### Scenario: Normal session end with meaningful conversation
- **WHEN** the Stop event fires with a valid transcript path
- **AND** the transcript contains 30 user+assistant turns
- **THEN** the filter SHALL parse ALL entries (not just last 80)
- **AND** SHALL apply word-count and pattern filters
- **AND** SHALL save filtered turns directly via `set-memory remember`
- **AND** SHALL NOT call Claude Haiku or any LLM

#### Scenario: Transcript with Hungarian content and lone surrogates
- **WHEN** a JSONL transcript line contains `\ud800` (lone high surrogate from Node.js)
- **AND** the line also contains valid Hungarian text "Ez a Prisma config működik"
- **THEN** the surrogate SHALL be replaced with `�`
- **AND** the valid Hungarian text SHALL be preserved
- **AND** the filtered entry SHALL be saved successfully to memory

#### Scenario: UnicodeEncodeError logged instead of swallowed
- **WHEN** `subprocess.run(['set-memory', ...], input=content, text=True)` raises `UnicodeEncodeError`
- **THEN** the error SHALL be logged with the entry index and a content preview
- **AND** processing SHALL continue with the next entry
- **AND** the final `saved=N/M` count SHALL reflect the skip

#### Scenario: Empty or trivial session
- **WHEN** the Stop event fires
- **AND** all conversation turns are below filter thresholds
- **THEN** no memories SHALL be saved
- **AND** the filter SHALL exit cleanly

### Requirement: Filter rules for discarding low-value turns
The filter SHALL discard turns matching any of these criteria:

- User turns with content < 15 characters
- Assistant turns with text content < 50 characters
- Entries that are purely system-reminder content
- Entries that are tool call results with no assistant text
- Repeated file-read entries (same file path appearing 3+ times — keep first 2 only)

#### Scenario: Short user acknowledgment filtered
- **WHEN** a user turn contains only "ok" (2 chars)
- **THEN** that turn SHALL be discarded

#### Scenario: Short assistant acknowledgment filtered
- **WHEN** an assistant turn contains only "Done." (5 chars)
- **THEN** that turn SHALL be discarded

#### Scenario: Substantive user question kept
- **WHEN** a user turn contains "miért nem működik a PreToolUse hook?" (38 chars)
- **THEN** that turn SHALL be kept

#### Scenario: System-reminder entries filtered
- **WHEN** a JSONL entry contains only system-reminder content (no user/assistant text)
- **THEN** that entry SHALL be discarded

#### Scenario: Repeated file reads deduplicated
- **WHEN** the transcript contains 5 Read tool calls for `/home/user/src/config.py`
- **THEN** only the first 2 occurrences SHALL be kept

### Requirement: Context prefix on saved memories
Each saved raw memory SHALL be prefixed with session context in the format: `[session:<change-name>, turn <N>/<total>] <content>`

Where `<change-name>` is extracted from opsx/openspec skill invocations in the transcript (or "unknown" if none found), `<N>` is the turn number among filtered turns, and `<total>` is the total filtered turn count.

#### Scenario: Memory with change context
- **WHEN** the session used skill `opsx:apply` for change `fix-auth-bug`
- **AND** a user turn "a config.py-ban az X pattern bugos" passes the filter as turn 3 of 18
- **THEN** the saved memory content SHALL be: `[session:fix-auth-bug, turn 3/18] a config.py-ban az X pattern bugos`

#### Scenario: Memory without change context
- **WHEN** the session did not invoke any opsx/openspec skills
- **AND** a turn passes the filter
- **THEN** the prefix SHALL use `unknown` as the change name

### Requirement: Raw tag on all ingested memories
All memories saved by the raw filter SHALL include the tag `raw` along with standard auto-extract tags.

The full tag set SHALL be: `raw,phase:auto-extract,source:hook,change:<name>`

#### Scenario: Tag verification
- **WHEN** a raw memory is saved
- **THEN** calling `set-memory recall --tags raw` SHALL return it
- **AND** the memory tags SHALL include `raw`, `phase:auto-extract`, `source:hook`

### Requirement: User and assistant turns saved as separate memories
Each filtered user turn and each filtered assistant turn SHALL be saved as separate memory entries. User turns SHALL be saved with type `Context`. Assistant turns SHALL be saved with type `Learning`.

#### Scenario: User question saved
- **WHEN** a user turn passes the filter
- **THEN** it SHALL be saved via `set-memory remember --type Context`

#### Scenario: Assistant explanation saved
- **WHEN** an assistant text turn passes the filter
- **THEN** it SHALL be saved via `set-memory remember --type Learning`

### Requirement: Background execution
The raw filter SHALL run as a disowned background process, same as the current Haiku extraction. It SHALL NOT block the session exit.

#### Scenario: Session exit not blocked
- **WHEN** the Stop handler launches the raw filter
- **THEN** the handler SHALL return immediately after launching the background process
- **AND** the synchronous Stop handler SHALL complete its metrics flush and cache cleanup without waiting
