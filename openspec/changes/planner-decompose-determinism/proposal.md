## Why

The planner's choice between **flat** (single-call decompose) and **3-phase domain-parallel** decompose is gated by a hard step function: `req_count >= DOMAIN_PARALLEL_MIN_REQS (=30)` in `lib/set_orch/planner.py:2461`. The INPUT to that step function — the requirement count — comes from a non-deterministic Claude CLI call (`call_digest_api` in `lib/set_orch/digest.py`). The Claude CLI does not expose a temperature flag, so successive runs of the same spec routinely return different requirement counts.

Observed in two recent E2E runs of the same micro-web scaffold against an identical brief (matching `brief_hash`): the digest extracted **25** requirements one time (flat → 6 changes) and **34** on a later run (domain-parallel → 14 changes). That's a 2.3× change-count blowup with no spec edit, just digest jitter. Costs: extra worktrees × build/test/e2e/verify cycles, ~10 extra LLM planning calls (Phase 1 brief + per-domain decomposes + Phase 3 merge), and merge-conflict surface on shared layout/CSS that should have been bundled.

The bug is **not the threshold value** (raising 30→50 or scaffold-aware knobs only shifts the discontinuity to a new req-count band where the same jitter still flips the outcome). The bug is that the step function's input is jittery. We need to determinize the input.

## What Changes

- **NEW** `digest_cache`: a content-addressed cache for the **raw** digest LLM response. Cache key = `sha256(prompt_bytes + model_bytes)` where `prompt_bytes` is the entire prompt string passed to `call_digest_api` (already encapsulates spec content + prompt template, since `build_digest_prompt` produces the full prompt) and `model_bytes` is the model name. Cache value = the raw Claude CLI stdout.
- **NEW** Cache hit path: `call_digest_api` returns the cached raw response string without invoking the Claude CLI; the caller continues to invoke `parse_digest_response` against the result, exactly as today. Cache miss path: invoke as today, then store the response. Eviction: LRU-style with a configurable max-entry count (default 64 entries, ~few MB).
- **NEW** Cache location: `~/.cache/set-orch/digest-cache/<hash-prefix>/<full-hash>.json`. Symmetric with the existing `~/.cache/set-orch/v0-clones/` cache layout.
- **NEW** CLI flags on `set-orch-core digest run` (the `dig_run` parser at `lib/set_orch/cli.py:1826`): `--no-digest-cache` (skip BOTH lookup and write — pure pass-through to the API for that invocation), `--digest-cache-clear` (purge cache before running). Symmetric with how other set-core caches expose escape hatches.
- **NEW** Operator escape hatch on the strategy decision itself: `orchestration.yaml::planner.force_strategy: flat | domain-parallel | auto` (default `auto`). When set to `flat` or `domain-parallel`, the planner skips the threshold check and takes the named branch unconditionally. `auto` preserves today's threshold behavior.
- **NEW** INFO-level logging that names the cache state on every digest call: `digest cache hit (key=<short-hash>, age=<minutes>)` or `digest cache miss → calling API`.
- **NEW** Logging on the strategy decision: `decompose strategy=<flat|domain-parallel>, source=<threshold|force_strategy>, req_count=<N>, threshold=<T>`. The current path only logs the small-spec branch — symmetric logging covers both.
- **NEW** Validation procedure documented in `tasks.md`: run digest twice on each of `nano`, `micro-web`, `minishop`, `craftbrew` scaffolds; first run is a cache miss + API call, second run is a cache hit. Raw responses MUST match byte-for-byte between runs of the same scaffold. Strategy routing per-scaffold is **observed and logged**, not asserted (we surface what each scaffold lands on under threshold=30; threshold tuning is out of scope here).

## Capabilities

### New Capabilities

- `digest-determinism-cache`: defines content-addressed caching of the digest LLM raw response keyed by prompt+model hash. Covers cache layout, hit/miss semantics, eviction, escape hatches.
- `planner-force-strategy`: defines the `orchestration.yaml::planner.force_strategy` config knob and its observable effect on the decompose-strategy decision.

### Modified Capabilities

- `orch-digest-python`: extend the `call_digest_api` contract so that cache hits short-circuit the Claude CLI invocation while preserving the existing raw-string return type, and cache-state appears in the run log.

## Impact

- **Code**:
  - `lib/set_orch/digest.py` — `call_digest_api` gains internal cache lookup/store; new module-level helpers for keying, reading, writing, evicting. The function's external API (`(prompt, model, max_retries) -> str`) is unchanged — caching is purely internal.
  - `lib/set_orch/planner.py` — read `planner.force_strategy` from orchestration config near the `DOMAIN_PARALLEL_MIN_REQS` decision (line ~2475); add structured log of the chosen strategy.
  - `lib/set_orch/cli.py` — `--no-digest-cache` and `--digest-cache-clear` flags on the `dig_run` parser at line 1826.
- **Configs**: `orchestration.yaml` schema gains optional `planner.force_strategy: flat|domain-parallel|auto`.
- **Behavior**: every project sees one extra disk write per fresh spec (cache file). On second+ runs of the same spec, the digest LLM call is **skipped entirely** — saves ~$0.50–$1 and 30–120 seconds per run. Strategy decision becomes deterministic across runs of the same prompt+model.
- **Risk surface**: cache-poisoning if a corrupt response gets stored. Mitigated by validating that `parse_digest_response` succeeds against the response BEFORE writing the cache entry (same parser the caller uses; if parse fails we don't cache).
- **No impact** on planning paths that don't go through `call_digest_api` (brief/spec input modes) — they remain unchanged.
- **Validation cost**: 4 scaffolds × 2 digest runs = 8 invocations (4 of which are cache hits and free). One-time validation budget.
