## 1. Cache module

- [x] 1.1 Add `_compute_cache_key(prompt: str, model: str) -> str` helper at module level in `lib/set_orch/digest.py` returning `hashlib.sha256(prompt.encode("utf-8") + model.encode("utf-8")).hexdigest()` [REQ: cache-key-composition]
- [x] 1.2 Add `DIGEST_CACHE_DIR = Path.home() / ".cache" / "set-orch" / "digest-cache"` constant (mirrors `CLONE_CACHE_DIR` style in `modules/web/set_project_web/v0_importer.py:37`) [REQ: cache-layout]
- [x] 1.3 Add `_cache_path(key)` returning `DIGEST_CACHE_DIR/<first-2-chars>/<full-key>.json` [REQ: cache-layout]
- [x] 1.4 Add `_read_cache_entry(key) -> str | None` that returns the `raw_response` field on hit (returns None on miss/IO/JSON error) and updates mtime via `os.utime` on hit [REQ: cache-lookup-and-hit-short-circuits-the-api-call, REQ: lru-eviction-caps-the-cache-at-64-entries]
- [x] 1.5 Add `_write_cache_entry(key, raw_response, model)` that constructs the documented JSON shape (`version=1, key, model, created_at, raw_response`), writes to a temp file in the same dir, and `os.replace`s into place atomically [REQ: cache-write-is-atomic-and-only-on-parseable-response, REQ: cache-layout]
- [x] 1.6 Make `_write_cache_entry` invoke `parse_digest_response(raw)` first; on `ValueError`, return without writing [REQ: cache-write-is-atomic-and-only-on-parseable-response]
- [x] 1.7 Add `DIGEST_CACHE_MAX_ENTRIES = 64` constant and `_prune_cache_lru()` that keeps only the 64 most-recent (mtime) entries; called once after each successful write [REQ: lru-eviction-caps-the-cache-at-64-entries]
- [x] 1.8 Add `_clear_cache()` that removes all files under `DIGEST_CACHE_DIR` (idempotent if dir is missing) [REQ: --digest-cache-clear-flag-purges-the-cache-before-running]

## 2. call_digest_api integration

- [x] 2.1 Refactor `call_digest_api(prompt, model="opus", max_retries=3)` in `digest.py` to accept a new keyword-only `bypass_cache: bool = False`. The external return type stays `str`; no caller changes are needed for this kwarg's default value [REQ: python-digest-api-invocation]
- [x] 2.2 At function entry, compute `key = _compute_cache_key(prompt, model)` [REQ: cache-key-composition]
- [x] 2.3 If `bypass_cache is False`, attempt `_read_cache_entry(key)`; on hit return its raw string and emit `INFO digest cache hit (key=<8>, age=<N>m)` [REQ: cache-lookup-and-hit-short-circuits-the-api-call]
- [x] 2.4 On miss (or bypass), keep the existing retry loop. Emit `INFO digest cache miss → calling API` before the loop on miss; emit `INFO digest cache bypass (--no-digest-cache flag)` instead when bypass is true [REQ: cache-lookup-and-hit-short-circuits-the-api-call, REQ: --no-digest-cache-flag-skips-both-lookup-and-write]
- [x] 2.5 After a successful API attempt, if `bypass_cache is False`, call `_write_cache_entry(key, raw, model)` (which itself parses-or-skips per task 1.6); on a successful write, emit `INFO digest cache write (key=<8>)`. If `bypass_cache is True`, skip the write entirely [REQ: cache-write-is-atomic-and-only-on-parseable-response, REQ: --no-digest-cache-flag-skips-both-lookup-and-write]
- [x] 2.6 Update `call_digest_api`'s docstring to describe the cache contract, the `bypass_cache` kwarg, and that the function still returns a raw string (no return-type change) [REQ: python-digest-api-invocation]

## 3. CLI flag plumbing

- [x] 3.1 Add `--no-digest-cache` argparse flag to the `dig_run` parser at `lib/set_orch/cli.py:1826`; help text states "skip both cache lookup and cache write for this invocation" [REQ: --no-digest-cache-flag-skips-both-lookup-and-write]
- [x] 3.2 Add `--digest-cache-clear` argparse flag to the same `dig_run` parser; help text states "purge the digest cache before running"; the handler MUST invoke `_clear_cache()` before any digest pipeline call begins; log `INFO digest cache cleared (--digest-cache-clear flag)` [REQ: --digest-cache-clear-flag-purges-the-cache-before-running]
- [x] 3.3 Plumb `bypass_cache=args.no_digest_cache` through to `call_digest_api` via the existing `run_digest_pipeline` (or equivalent) call chain [REQ: --no-digest-cache-flag-skips-both-lookup-and-write]

## 4. Planner force_strategy knob

- [x] 4.1 Add a helper near `lib/set_orch/planner.py:2475` that reads `planner.force_strategy` from the orchestration config (handle missing key, missing section, missing file — default `"auto"`) [REQ: planner-force_strategy-knob]
- [x] 4.2 Validate the value: only `flat`, `domain-parallel`, `auto` are accepted; on any other string, log WARN and treat as `auto` [REQ: planner-force_strategy-knob]
- [x] 4.3 At the `if req_count >= DOMAIN_PARALLEL_MIN_REQS:` decision (line ~2475), branch on `force_strategy`: when `flat` skip the threshold and force the single-call path; when `domain-parallel` skip the threshold and force `_try_domain_parallel_decompose`; when `auto` keep today's path [REQ: planner-force_strategy-knob]
- [x] 4.4 Emit one INFO log line per strategy decision in digest mode with the documented format `decompose strategy=<flat|domain-parallel>, source=<threshold|force_strategy>, req_count=<N>, threshold=<T>` — on BOTH branches and BOTH source variants [REQ: strategy-decision-logging-is-symmetric]

## 5. Tests

- [x] 5.1 Unit test for `_compute_cache_key` — same `(prompt, model)` → same key, any prompt byte change → different key, model change → different key [REQ: cache-key-composition]
- [x] 5.2 Unit test that `build_digest_prompt(spec_path, scan)` is byte-deterministic on a fixed input scan (asserts the precondition for cache key stability) [REQ: cache-key-composition]
- [x] 5.3 Unit test for read/write round-trip — write an entry, read it back, raw response is byte-equal [REQ: cache-layout]
- [x] 5.4 Unit test for atomic write — assert tempfile is created in the same dir as final, then renamed via `os.replace`; assert no orphan tempfile remains on success [REQ: cache-write-is-atomic-and-only-on-parseable-response]
- [x] 5.5 Unit test for parse-failure path — feed a response that raises `ValueError` from `parse_digest_response`; assert no cache file is written but the raw string is still returned to the caller [REQ: cache-write-is-atomic-and-only-on-parseable-response]
- [x] 5.6 Unit test for LRU prune — populate 64 entries with distinct mtimes, write a 65th, assert oldest is gone and exactly 64 remain [REQ: lru-eviction-caps-the-cache-at-64-entries]
- [x] 5.7 Unit test for hit refreshes mtime — read an entry whose mtime was set far in the past; after read, mtime is within seconds of `time.time()` [REQ: lru-eviction-caps-the-cache-at-64-entries]
- [x] 5.8 Unit test for `bypass_cache=True` — pre-seed a cache entry, call with bypass, assert API path is taken (use a stub for `run_claude_logged`) AND assert cache entry is unchanged after the call [REQ: --no-digest-cache-flag-skips-both-lookup-and-write]
- [x] 5.9 Unit test for `_clear_cache()` — populate dir with 17 files, call clear, assert 0 files remain; call again on empty dir, assert no error [REQ: --digest-cache-clear-flag-purges-the-cache-before-running]
- [x] 5.10 Unit test for `force_strategy` — table-driven cases: `flat`/`domain-parallel`/`auto`/`""`/`"aggressive"`; assert correct branch is taken; assert correct log line emitted; assert WARN on invalid value [REQ: planner-force_strategy-knob, REQ: strategy-decision-logging-is-symmetric]

## 6. Validation procedure (4 scaffolds × 2 runs)

- [x] 6.1 Document a `tools/validate-digest-determinism.sh` script that for each of `tests/e2e/scaffolds/{nano,micro-web,minishop,craftbrew}` runs the digest twice (cache cleared at the start of the procedure) and asserts byte equality between run-1 and run-2 raw responses [REQ: cache-lookup-and-hit-short-circuits-the-api-call]
- [ ] 6.2 Validation step for `nano` scaffold: `--digest-cache-clear` once, then run digest, capture raw response as `nano.run1.raw`; run digest again WITHOUT clearing, capture as `nano.run2.raw`; assert `diff -q nano.run1.raw nano.run2.raw` is empty (live LLM run; deferred to next E2E session) [REQ: cache-lookup-and-hit-short-circuits-the-api-call]
- [ ] 6.3 Repeat 6.2 for `micro-web` scaffold; capture both raw responses; assert byte equality (live LLM run; deferred) [REQ: cache-lookup-and-hit-short-circuits-the-api-call]
- [ ] 6.4 Repeat 6.2 for `minishop` scaffold; capture both responses; assert byte equality (live LLM run; deferred) [REQ: cache-lookup-and-hit-short-circuits-the-api-call]
- [ ] 6.5 Repeat 6.2 for `craftbrew` scaffold; capture both responses; assert byte equality (live LLM run; deferred) [REQ: cache-lookup-and-hit-short-circuits-the-api-call]
- [ ] 6.6 Strategy routing observation: capture the planner's `decompose strategy=…` log line for each scaffold under default threshold=30 and record in a results table. The strategy chosen per scaffold is **observed**, not asserted — a follow-up may revisit threshold tuning if results land surprisingly (live LLM run; deferred) [REQ: strategy-decision-logging-is-symmetric]
- [ ] 6.7 Sanity check: between runs, confirm `events.jsonl` for run-2 contains NO `LLM_CALL` event with `purpose="digest"` for that scaffold (proof the cache hit short-circuited the API) (live LLM run; deferred) [REQ: cache-lookup-and-hit-short-circuits-the-api-call]
- [ ] 6.8 Force-strategy spot check: pick `nano` scaffold, set `planner.force_strategy: domain-parallel` in its `orchestration.yaml`, run planner, assert log line names `source=force_strategy` and `_try_domain_parallel_decompose` was invoked (live LLM run; deferred) [REQ: planner-force_strategy-knob]

## 7. Docs

- [x] 7.1 Update orchestration config docs (or `docs/orchestration-yaml-reference.md` if present, otherwise wherever the schema is documented) to describe `planner.force_strategy` enum and default [REQ: planner-force_strategy-knob]
- [x] 7.2 Add a one-line note to `tests/e2e/README.md` describing that digest output is now content-addressed cached at `~/.cache/set-orch/digest-cache/`, and that `--digest-cache-clear` purges it [REQ: cache-layout]

## Acceptance Criteria (from spec scenarios)

### Capability: digest-determinism-cache

- [ ] AC-1: WHEN two cache-key computations use the same `prompt` bytes and `model` string THEN the keys are byte-identical [REQ: cache-key-composition, scenario: identical-prompt-and-model-produce-identical-key]
- [ ] AC-2: WHEN the operator modifies a spec file by any byte AND `build_digest_prompt` is re-run THEN the new prompt yields a different key and the run is a cache miss [REQ: cache-key-composition, scenario: spec-edit-changes-the-prompt-and-invalidates-the-key]
- [ ] AC-3: WHEN the same prompt is digested with `model="sonnet"` after a cached `model="opus"` run THEN the run is a cache miss [REQ: cache-key-composition, scenario: model-name-change-invalidates-key]
- [ ] AC-4: WHEN a maintainer modifies the prompt template wording THEN the next run for any spec is a cache miss [REQ: cache-key-composition, scenario: prompt-template-change-invalidates-key]
- [ ] AC-5: WHEN `call_digest_api` finds a valid cache entry THEN it returns the cached raw response AND no Claude subprocess is spawned AND a `digest cache hit` INFO log is emitted [REQ: cache-lookup-and-hit-short-circuits-the-api-call, scenario: cache-hit-returns-cached-raw-response]
- [ ] AC-6: WHEN `call_digest_api` has no matching cache entry THEN the Claude CLI is invoked AND on parse-OK a fresh entry is written AND `digest cache miss` and `digest cache write` logs are emitted [REQ: cache-lookup-and-hit-short-circuits-the-api-call, scenario: cache-miss-invokes-api-and-writes-entry]
- [ ] AC-7: WHEN `parse_digest_response` raises ValueError on the response THEN no cache file is written AND the raw response is still returned to the caller [REQ: cache-write-is-atomic-and-only-on-parseable-response, scenario: parse-failure-does-not-cache]
- [ ] AC-8: WHEN the cache write is killed mid-rename THEN the next call sees either a complete entry or no entry — never a half-written file [REQ: cache-write-is-atomic-and-only-on-parseable-response, scenario: crash-mid-write-leaves-no-partial-entry]
- [ ] AC-9: WHEN a cache key starts with `7b663f3…` THEN the file path is `~/.cache/set-orch/digest-cache/7b/7b663f3….json` [REQ: cache-layout, scenario: two-level-directory-layout]
- [ ] AC-10: WHEN a fresh cache entry is read THEN its `raw_response` field is the unmodified Claude CLI stdout [REQ: cache-layout, scenario: entry-includes-raw-response-for-forensic-replay]
- [ ] AC-11: WHEN the cache holds 64 entries and a 65th is written THEN the oldest-mtime entry is deleted and exactly 64 remain [REQ: lru-eviction-caps-the-cache-at-64-entries, scenario: adding-the-65th-entry-evicts-the-lru]
- [ ] AC-12: WHEN a cache hit is served on an entry with old mtime THEN the file's mtime is updated to roughly current wall-clock [REQ: lru-eviction-caps-the-cache-at-64-entries, scenario: cache-hit-refreshes-mtime]
- [ ] AC-13: WHEN the operator runs with `--no-digest-cache` AND a matching entry exists THEN the API is invoked AND the entry under that key is unchanged AND the bypass log names `--no-digest-cache flag` [REQ: --no-digest-cache-flag-skips-both-lookup-and-write, scenario: --no-digest-cache-neither-reads-nor-writes-the-cache]
- [ ] AC-14: WHEN `--no-digest-cache` is passed and the cache is cold THEN the API is invoked, its response is returned, AND no entry is written [REQ: --no-digest-cache-flag-skips-both-lookup-and-write, scenario: --no-digest-cache-on-cold-cache-leaves-cache-empty]
- [ ] AC-15: WHEN the operator runs with `--digest-cache-clear` and the cache had 17 entries THEN the directory has 0 entries before any API call begins AND the run repopulates one entry [REQ: --digest-cache-clear-flag-purges-the-cache-before-running, scenario: --digest-cache-clear-empties-the-cache-before-the-run]
- [ ] AC-16: WHEN `--digest-cache-clear` is passed and the cache dir is missing or empty THEN the run proceeds with no error [REQ: --digest-cache-clear-flag-purges-the-cache-before-running, scenario: --digest-cache-clear-is-idempotent-on-an-empty-cache]
- [ ] AC-17: WHEN both `--digest-cache-clear` and `--no-digest-cache` are passed THEN the cache is purged, API runs, and no fresh entry is written; the dir is empty after the run [REQ: --digest-cache-clear-flag-purges-the-cache-before-running, scenario: --digest-cache-clear-combined-with---no-digest-cache]

### Capability: planner-force-strategy

- [ ] AC-18: WHEN `orchestration.yaml` has no `planner.force_strategy` key THEN the threshold check runs as today [REQ: planner-force_strategy-knob, scenario: default-is-auto]
- [ ] AC-19: WHEN `force_strategy: flat` is set AND req_count=100 THEN the single-call branch is taken AND `_try_domain_parallel_decompose` is NOT called AND log records `source=force_strategy` [REQ: planner-force_strategy-knob, scenario: force_strategy-flat-overrides-the-threshold]
- [ ] AC-20: WHEN `force_strategy: domain-parallel` is set AND req_count=12 THEN the 3-phase pipeline is invoked AND log records `source=force_strategy` [REQ: planner-force_strategy-knob, scenario: force_strategy-domain-parallel-overrides-the-threshold]
- [ ] AC-21: WHEN `force_strategy` has any other string value THEN a WARN log is emitted AND the planner falls back to auto behavior [REQ: planner-force_strategy-knob, scenario: unknown-value-falls-back-to-auto-with-a-warning]
- [ ] AC-22: WHEN req_count=12 AND force_strategy=auto THEN the planner emits `decompose strategy=flat, source=threshold, req_count=12, threshold=30` [REQ: strategy-decision-logging-is-symmetric, scenario: flat-branch-logs-symmetrically]
- [ ] AC-23: WHEN req_count=42 AND force_strategy=auto THEN the planner emits `decompose strategy=domain-parallel, source=threshold, req_count=42, threshold=30` [REQ: strategy-decision-logging-is-symmetric, scenario: domain-parallel-branch-logs-symmetrically]
- [ ] AC-24: WHEN any digest mode run forces a strategy THEN the `source=` field on the strategy log line is `force_strategy` [REQ: strategy-decision-logging-is-symmetric, scenario: forced-branch-names-force_strategy-as-source]

### Capability: orch-digest-python (modified)

- [ ] AC-25: WHEN `call_digest_api` runs with no cached entry AND Claude returns a parseable response THEN it returns the raw response AND an entry is written to `~/.cache/set-orch/digest-cache/` AND miss+write INFO logs are emitted [REQ: python-digest-api-invocation, scenario: successful-api-call-cache-miss-path]
- [ ] AC-26: WHEN `call_digest_api` runs with a matching cache entry THEN it returns the cached raw response AND no Claude subprocess is spawned AND no `LLM_CALL` event with `purpose="digest"` is emitted [REQ: python-digest-api-invocation, scenario: cache-hit-avoids-api-call]
- [ ] AC-27: WHEN the Claude CLI fails on the first attempt during a cache miss THEN the existing `max_retries=3` loop runs AND the cache is populated only after a successful parseable attempt [REQ: python-digest-api-invocation, scenario: retry-semantics-preserved-on-cache-miss]
- [ ] AC-28: WHEN `call_digest_api` is invoked with `bypass_cache=True` AND a matching entry exists THEN the entry is ignored, the CLI is invoked, AND no cache write occurs [REQ: python-digest-api-invocation, scenario: --no-digest-cache-forces-a-fresh-call-and-skips-write]
