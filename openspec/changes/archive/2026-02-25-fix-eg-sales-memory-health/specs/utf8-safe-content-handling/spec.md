## ADDED Requirements

### Requirement: Character-safe truncation for all user prompt content
All truncation of user prompt content in `wt-hook-memory` SHALL use character-level operations (`cut -c1-N`) instead of byte-level operations (`head -c N`). This prevents splitting multi-byte UTF-8 sequences (e.g., Hungarian á=0xc3 0xa1, é=0xc3 0xa9, emoji, CJK characters).

#### Scenario: Hungarian text truncated at character boundary
- **WHEN** UserPromptSubmit fires with prompt "Ez a projekt Prisma 7-et használ és Railway-en fut, az ékezetes karakterek működnek" (89 chars, multi-byte)
- **AND** the emotion detection saves the prompt with 500-char limit
- **THEN** the saved content SHALL NOT contain orphaned bytes or surrogate characters
- **AND** the truncation SHALL occur at a character boundary, not a byte boundary

#### Scenario: Emoji in prompt truncated safely
- **WHEN** a prompt contains "Fix the 🔴 error in config" and is truncated
- **THEN** the emoji (4-byte UTF-8 sequence) SHALL be either fully included or fully excluded — never split

#### Scenario: ASCII-only text unaffected
- **WHEN** a prompt contains only ASCII characters
- **THEN** `cut -c1-N` SHALL produce identical output to the previous `head -c N`

### Requirement: Defense-in-depth surrogate sanitization in wt-memory remember
The `cmd_remember` function in `wt-memory` SHALL sanitize content before passing it to the Rust/PyO3 `m.remember()` call. Surrogate codepoints SHALL be replaced with U+FFFD (REPLACEMENT CHARACTER) using `content.encode('utf-8', errors='replace').decode('utf-8')`.

#### Scenario: Surrogate content from external caller
- **WHEN** any caller pipes content containing surrogate codepoint `\udcc3` to `wt-memory remember`
- **THEN** the memory SHALL be saved successfully with `\udcc3` replaced by `�` (U+FFFD)
- **AND** no `UnicodeEncodeError` SHALL be raised

#### Scenario: Valid UTF-8 content passes through unchanged
- **WHEN** content containing valid Hungarian text "működik az ékezet" is piped to `wt-memory remember`
- **THEN** the content SHALL be stored exactly as provided, with no replacement characters

### Requirement: Transcript JSON surrogate sanitization
The `_stop_raw_filter()` function in `wt-hook-memory` SHALL sanitize all string content extracted from JSONL transcript entries after `json.loads()`. Lone surrogates from Node.js JSON output SHALL be replaced with U+FFFD before further processing.

#### Scenario: Node.js lone surrogate in transcript
- **WHEN** a JSONL line contains an unpaired surrogate escape (e.g., `\ud83c` without matching low surrogate)
- **AND** `json.loads()` decodes it into a Python string with surrogate codepoint
- **THEN** the sanitization SHALL replace the surrogate with `�`
- **AND** the rest of the content SHALL be preserved intact

#### Scenario: Valid Unicode in transcript preserved
- **WHEN** a JSONL line contains properly paired surrogates or direct UTF-8
- **THEN** the content SHALL pass through sanitization unchanged

### Requirement: UTF-8 locale fallback in hook
The `wt-hook-memory` SHALL ensure a UTF-8 locale is active for `cut -c` operations. If `LANG` and `LC_CTYPE` are both unset or non-UTF-8, the hook SHALL export `LC_ALL=C.UTF-8` as a fallback.

#### Scenario: No locale set
- **WHEN** the hook runs in an environment where `LANG` is unset
- **THEN** `LC_ALL=C.UTF-8` SHALL be set before any `cut -c` operation
- **AND** character-level truncation SHALL work correctly for multi-byte characters
