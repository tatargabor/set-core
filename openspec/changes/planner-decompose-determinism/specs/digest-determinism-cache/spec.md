## ADDED Requirements

### Requirement: Cache key composition

The cache key SHALL be `hashlib.sha256(prompt.encode("utf-8") + model.encode("utf-8")).hexdigest()`, where `prompt` is the exact string passed to `call_digest_api` and `model` is the model-name string. The key MUST NOT depend on wall-clock time, machine identifiers, project paths, environment variables, run identifiers, or any separately-versioned constants.

#### Scenario: Identical prompt and model produce identical key

- **GIVEN** two invocations of the cache-key helper with the same `prompt` bytes and the same `model` string
- **WHEN** the keys are computed
- **THEN** both keys are byte-identical SHA256 hex strings

#### Scenario: Spec edit changes the prompt and invalidates the key

- **GIVEN** a spec file `S` whose digest is cached under key `K1`
- **WHEN** the operator modifies `S` (any byte change), `build_digest_prompt` is re-run, and the resulting prompt feeds `call_digest_api`
- **THEN** the computed key `K2` differs from `K1`
- **AND** the run is a cache miss

#### Scenario: Model name change invalidates key

- **GIVEN** a digest cached under key `K_opus` for `model="opus"`
- **WHEN** the same prompt is digested with `model="sonnet"`
- **THEN** the computed key differs and the run is a cache miss

#### Scenario: Prompt template change invalidates key

- **GIVEN** cached entries created by an earlier version of `build_digest_prompt`
- **WHEN** a maintainer modifies the prompt template wording and the new prompt feeds `call_digest_api` against any spec
- **THEN** the new run is a cache miss for every spec (because the prompt bytes differ)

### Requirement: Cache lookup and hit short-circuits the API call

When `call_digest_api` is invoked and a valid cache entry exists for the computed key (and `bypass_cache` is false), the function SHALL return the cached raw response string and MUST NOT invoke the Claude CLI. The hit MUST be logged at INFO level naming a short prefix of the key and the entry's age in minutes.

#### Scenario: Cache hit returns cached raw response

- **GIVEN** a cache entry exists for key `K` with `raw_response` `R`
- **WHEN** `call_digest_api` is invoked with input that hashes to `K`
- **THEN** the function returns `R` byte-for-byte
- **AND** no Claude CLI subprocess is spawned
- **AND** an INFO log line `digest cache hit (key=<short>, age=<N>m)` is emitted

#### Scenario: Cache miss invokes API and writes entry

- **GIVEN** no cache entry exists for key `K`
- **WHEN** `call_digest_api` is invoked
- **THEN** the Claude CLI is invoked as today
- **AND** on a successful response that parses with `parse_digest_response`, a cache entry is written under key `K`
- **AND** an INFO log line `digest cache miss → calling API` precedes the call
- **AND** an INFO log line `digest cache write (key=<short>)` is emitted after success

### Requirement: Cache write is atomic and only on parseable response

A cache entry MUST be written only after the cache write helper verifies that `parse_digest_response` succeeds against the raw response. On parse failure, no cache entry SHALL be created. The write MUST be atomic (write to a temporary file in the same directory, then `os.replace` into place) so a partially-written entry is never visible to subsequent readers.

#### Scenario: Parse failure does not cache

- **GIVEN** the Claude CLI returns a response that `parse_digest_response` raises `ValueError` on
- **WHEN** `call_digest_api` returns
- **THEN** no file is created under `~/.cache/set-orch/digest-cache/`
- **AND** the raw response is still returned to the caller (which will encounter the same parse failure and surface it)

#### Scenario: Crash mid-write leaves no partial entry

- **GIVEN** the cache write is killed via SIGKILL between opening the temp file and `os.replace`-ing it
- **WHEN** a subsequent `call_digest_api` runs with the same key
- **THEN** the only artifact found is either (a) a complete valid entry or (b) no entry at all — no half-written or empty file is treated as a hit

### Requirement: Cache layout

Cache entries SHALL be stored under `~/.cache/set-orch/digest-cache/<first-2-hex-chars-of-key>/<full-key>.json`. Each file SHALL contain a JSON object with at minimum: `version` (integer), `key` (full hash), `model` (string), `created_at` (ISO 8601), `raw_response` (string).

#### Scenario: Two-level directory layout

- **GIVEN** a cache key starting with `7b663f3…`
- **WHEN** the cache writes the entry
- **THEN** the file path is `~/.cache/set-orch/digest-cache/7b/7b663f3….json`

#### Scenario: Entry includes raw response for forensic replay

- **GIVEN** a fresh cache entry was written
- **WHEN** the JSON file is read back
- **THEN** the object's `raw_response` field is the unmodified Claude CLI stdout that produced this entry

### Requirement: LRU eviction caps the cache at 64 entries

On each successful cache write, the cache module SHALL prune entries beyond a configured cap (default `DIGEST_CACHE_MAX_ENTRIES = 64`). Eviction order is LRU — oldest mtime first. Every cache hit SHALL `os.utime` the entry to refresh its mtime. The cap and eviction policy MUST mirror the existing `~/.cache/set-orch/v0-clones/` LRU prune in style.

#### Scenario: Adding the 65th entry evicts the LRU

- **GIVEN** the cache contains exactly 64 entries with distinct mtimes
- **WHEN** a 65th entry is written
- **THEN** the entry with the oldest mtime is deleted
- **AND** the cache contains exactly 64 entries after the prune

#### Scenario: Cache hit refreshes mtime

- **GIVEN** an existing cache entry with mtime `T0` (set far in the past)
- **WHEN** a hit returns the entry
- **THEN** the file's mtime is updated to roughly the current wall-clock time

### Requirement: --no-digest-cache flag skips both lookup and write

The CLI flag `--no-digest-cache` SHALL cause `call_digest_api` to bypass cache lookup AND skip writing the response to the cache for that invocation. The flag is a pure pass-through to the API call. The flag SHALL be accepted on the `set-orch-core digest run` parser (`dig_run` at `lib/set_orch/cli.py:1826`).

#### Scenario: --no-digest-cache neither reads nor writes the cache

- **GIVEN** a valid cache entry exists for key `K`
- **WHEN** the operator runs `set-orch-core digest run --no-digest-cache`
- **THEN** the Claude CLI is invoked (no hit short-circuit)
- **AND** the entry under key `K` is unchanged after the run (whatever was there stays)
- **AND** an INFO log line names `--no-digest-cache flag` as the reason for the bypass

#### Scenario: --no-digest-cache on cold cache leaves cache empty

- **GIVEN** no cache entry exists for key `K`
- **WHEN** the operator runs with `--no-digest-cache`
- **THEN** the Claude CLI is invoked and its response is returned
- **AND** no entry is written under key `K`

### Requirement: --digest-cache-clear flag purges the cache before running

The CLI flag `--digest-cache-clear` SHALL delete every file under `~/.cache/set-orch/digest-cache/` before any digest call begins. The directory itself MAY be removed and recreated, or its contents emptied. After purge, the digest run proceeds normally (so the same invocation will be a cache miss and repopulate the entry, unless `--no-digest-cache` is also set).

#### Scenario: --digest-cache-clear empties the cache before the run

- **GIVEN** the cache contains 17 entries
- **WHEN** the operator runs the digest command with `--digest-cache-clear`
- **THEN** before any API call begins the directory contains 0 entries
- **AND** the run that follows writes 1 fresh entry (cache miss → write)

#### Scenario: --digest-cache-clear is idempotent on an empty cache

- **GIVEN** the cache directory does not exist or is empty
- **WHEN** `--digest-cache-clear` is passed
- **THEN** the run proceeds normally (no error)

#### Scenario: --digest-cache-clear combined with --no-digest-cache

- **GIVEN** the cache contains entries
- **WHEN** the operator runs with both `--digest-cache-clear --no-digest-cache`
- **THEN** the cache is purged before the run, the API call runs, and no fresh entry is written
- **AND** the cache directory is empty after the run
