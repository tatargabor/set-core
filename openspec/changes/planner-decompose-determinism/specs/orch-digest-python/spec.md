## MODIFIED Requirements

### Requirement: Python digest API invocation
The system SHALL provide `call_digest_api()` in `digest.py` that calls Claude via `subprocess_utils.run_claude()` with the digest prompt and returns the raw response string. The function SHALL consult a content-addressed local cache (defined in capability `digest-determinism-cache`) before invoking the Claude CLI: on cache hit it MUST return the cached raw response without spawning the Claude subprocess; on cache miss it MUST invoke the CLI as today and write the response to the cache on successful parse. The cache layer MUST NOT alter the function's external return type — `call_digest_api` continues to return a raw string, and the caller continues to invoke `parse_digest_response` against that string. Cache lookup AND write MAY be skipped via the `--no-digest-cache` flag (pure pass-through), and the entire cache MAY be purged before the run via `--digest-cache-clear`.

#### Scenario: Successful API call (cache miss path)
- **WHEN** `call_digest_api()` is invoked with no cached entry for the input
- **AND** Claude CLI returns a response that `parse_digest_response` accepts
- **THEN** the function returns the raw response string
- **AND** an entry is written to `~/.cache/set-orch/digest-cache/` keyed by `sha256(prompt + model)`
- **AND** an INFO log line names the cache miss before the API call and the cache write after

#### Scenario: Cache hit avoids API call
- **WHEN** `call_digest_api()` is invoked with input that matches an existing cache entry
- **THEN** the function returns the cached raw response string (the caller will parse it)
- **AND** no Claude subprocess is spawned
- **AND** the events.jsonl `LLM_CALL` event for `purpose="digest"` is NOT emitted (since no LLM call occurred)
- **AND** an INFO log line names the cache hit with key prefix and entry age

#### Scenario: Retry semantics preserved on cache miss
- **WHEN** the Claude CLI fails on the first attempt during a cache miss
- **THEN** the existing retry loop (`max_retries=3`) executes as today
- **AND** the cache is written only after a successful attempt whose response parses; failed attempts MUST NOT poison the cache

#### Scenario: --no-digest-cache forces a fresh call AND skips write
- **WHEN** `call_digest_api()` is invoked with `bypass_cache=True` (set by the `--no-digest-cache` flag)
- **THEN** any matching cache entry is ignored and the Claude CLI is invoked
- **AND** the resulting raw response is returned to the caller
- **AND** no cache entry is written for this invocation
