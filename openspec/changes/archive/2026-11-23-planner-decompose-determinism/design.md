## Context

Today's planner has two co-conspiring sources of non-determinism that together produce dramatically different plans for the same input spec:

1. **Digest extraction LLM jitter.** `call_digest_api` (`lib/set_orch/digest.py:245`) invokes the Claude CLI without a temperature setting (the CLI does not expose one). Claude's default sampling produces semantically equivalent but **structurally different** outputs across runs — different counts of extracted requirements, different boundary decisions, different ambiguity flagging. We have observed two recent E2E runs of the same micro-web scaffold against an identical brief (matching `brief_hash`) producing 25 vs 34 requirements respectively.

2. **Step-function strategy threshold.** `lib/set_orch/planner.py:2461` toggles between flat single-call decompose and 3-phase domain-parallel decompose at exactly `req_count >= 30`. A 1-req delta crossing the threshold flips between a 6-change and a 14-change plan — the granularity discontinuity is enormous.

Combined, ANY repeated run of ANY spec near the threshold has a meaningful chance of producing a fundamentally different plan. This breaks reproducibility, breaks A/B comparison of planner changes, and inflates cost on the high side of the threshold.

The Claude CLI does not expose `temperature`, `top_p`, or `seed`, so we cannot determinize the API call at the API layer. We must determinize at the **caching layer**: same input → same cached output.

A separate ergonomic concern — operators sometimes know the right strategy for their project (e.g. "this is a tiny scaffold, force flat regardless of req count") — is not a determinism question but a control question, and is solved by an explicit override knob.

Constraints:
- Cannot bypass or reimplement the digest LLM call (we depend on Claude's extraction quality).
- Cannot pin Claude model output bit-for-bit (no API surface).
- Must keep the cache transparent: a fresh checkout / new machine should still work, just at API-call cost on first run.
- Must not break existing `brief` / `spec` input modes — they bypass digest entirely.
- Must compose with the existing `--regenerate-manifest` and `set-design-import` flows that may invalidate digests upstream.
- Must not change the `call_digest_api` external API. The function's signature is `(prompt, model, max_retries) -> str` and is called from `digest.py:1250`; downstream code parses that raw string with `parse_digest_response`. Caching must intercept internally and preserve the raw-string return.

Stakeholders: planner, digest pipeline, operators iterating on specs, E2E runners that re-execute the same spec across runs.

## Goals / Non-Goals

**Goals:**
- Same `(prompt, model)` → same digest output, every run, every machine.
- Same digest output → same strategy decision (flat vs domain-parallel) → same plan.
- Cache transparently — operator does not need to know it exists for normal flows.
- Provide escape hatches: pass-through (`--no-digest-cache`), full purge (`--digest-cache-clear`), force strategy (`planner.force_strategy`).
- Cheap validation: prove determinism on 4 different-sized scaffolds with 8 total digest invocations.

**Non-Goals:**
- Determinism of agent dispatch, build, test, or any phase downstream of the plan.
- Removing the threshold or smoothing it (the threshold itself is fine once its input is stable; if we later want a softer routing function, that is a separate change).
- Caching downstream artifacts (decompose results, change plans). Out of scope; only the `call_digest_api` step is cached.
- Caching the parsed `DigestResult` post-parse (we cache the raw response so parser improvements upgrade older cached entries automatically).
- Any change to digest prompt content or extraction logic. We treat the LLM as a black box and cache around it.
- Cross-machine cache sharing (e.g. centralized cache server). Local-disk cache is sufficient; team determinism comes from the prompt being the cache key, not the cache being shared.
- Caching for non-Claude models. Cache key includes model name; non-Claude usage just generates separate entries.

## Decisions

### D1 — Cache the raw LLM response, not the parsed result

The cache stores the **raw response string** that `call_digest_api` returns today, not a post-parse `DigestResult`. The caller continues to invoke `parse_digest_response` on the cache hit's payload exactly as it does on a fresh API call (`digest.py:1264`). Rationale:

- The current `call_digest_api(prompt, model, max_retries) -> str` API returns a raw string. Caching at this layer is a pure interception — no caller code changes, no API bump.
- `parse_digest_response` is deterministic (regex + JSON parse, no LLM). Running it on every hit is fast and produces identical output every time.
- Parser improvements **upgrade** older cached entries automatically — a fixed regex turns a previously-malformed-but-cached raw string into correct output. Caching post-parse would freeze the parser version implicitly, requiring deliberate cache invalidation on every parser tweak.
- Storing the raw response is also the strongest forensic artifact: we can replay the parser at any time against the original LLM output.

Alternative considered: cache the parsed `DigestResult`. Rejected — would require changing `call_digest_api`'s return type or wrapping the cache at a higher level (the `run_digest_pipeline` boundary), both more invasive than necessary.

### D2 — Cache key composition: `sha256(prompt + model)`

The key SHALL be `hashlib.sha256(prompt.encode("utf-8") + model.encode("utf-8")).hexdigest()`. The `prompt` argument already encapsulates everything that determines the LLM's task: the spec content (assembled by `build_digest_prompt`, `digest.py:1245`) plus the prompt template wording. Any change to either — operator edits the spec, or a maintainer rewrites the digest prompt template — produces a different `prompt` string, a different hash, and a forced cache miss.

The key MUST NOT include:
- Wall-clock time, machine ID, run ID, project path — those are non-determinism we are trying to avoid.
- Environment variables — would cause spurious cache misses.
- Any separately-versioned "prompt template version" constant. An earlier draft proposed `DIGEST_PROMPT_VERSION` as a manually-bumped invariant; **rejected** because the prompt itself is part of the key, so any prompt change invalidates organically. A version constant would either duplicate that signal or risk being forgotten on prompt edits.

#### Note on prompt determinism

`build_digest_prompt(spec_path, scan)` must itself produce the same output bytes for the same inputs. Today it does (concatenates file contents in deterministic order). If a future change introduces non-determinism into prompt assembly (e.g. relying on dict iteration order in a Python <3.7 environment), the cache will silently miss. We add a unit test asserting prompt determinism on a fixed scan to lock this in.

### D3 — Cache layout: `~/.cache/set-orch/digest-cache/<key-prefix>/<full-key>.json`

Two-level directory structure (first 2 chars of hash → directory) prevents thousands of files in one directory. JSON content. Symmetric with `~/.cache/set-orch/v0-clones/` (already a precedent in the codebase, `modules/web/set_project_web/v0_importer.py:37`).

Each cache entry includes the raw response and metadata for forensic inspection. Schema:
```json
{
  "version": 1,
  "key": "<full-sha256-hex>",
  "model": "opus",
  "created_at": "<ISO 8601>",
  "raw_response": "<verbatim Claude CLI stdout>"
}
```

We deliberately do NOT store the `prompt` itself in the cache file — it would inflate disk and is reconstructable from the source spec at any time if forensic replay is needed.

### D4 — Eviction: LRU on read, capped at 64 entries

Each cache hit `os.utime`s the file (mtime → now). Periodic prune (lazy, on cache write) drops the oldest beyond the cap. 64 entries is generous (a typical operator works on far fewer specs); each entry is a few KB of JSON; total bound is well under 1 MB.

We chose LRU on read instead of a TTL because cache entries don't go stale by clock — they go stale because the spec or prompt template changes (which produces a new key, not a hit on an old entry).

Alternative considered: no eviction. Rejected for hygiene; over years a directory of stale digests accumulates with no benefit.

### D5 — Cache write happens after the response parses, never before

After a fresh API call returns, the cache write helper SHALL parse the response (with the same `parse_digest_response` the caller would use) BEFORE writing the cache entry. If parse raises `ValueError`, no cache entry is created. The write helper discards its parsed result; the raw string flows back to the caller, which re-parses (paying a tiny duplicate-parse cost only on cold paths but keeping the cache module a single coherent concern).

This prevents cache-poisoning by an LLM response that happened to look like JSON but wasn't valid. The next call for the same key will re-invoke the API, giving the LLM another chance.

### D6 — `--no-digest-cache` semantics: skip lookup AND skip write

`--no-digest-cache` is a pure pass-through: the cache is neither consulted nor populated for this invocation. The flag's name matches its behavior literally — "no cache for this run." Use case: CI environments running prompt-template tests that should not pollute the developer cache.

If an operator wants "force fresh + cache the result" (a refresh), the canonical sequence is `--digest-cache-clear` (purges the entry) followed by a normal run (cache miss → API call → cache write). This avoids a third flag for an edge case.

Alternative considered: `--no-digest-cache` skips lookup but still writes. Rejected — flag-name confusion. The pass-through semantics is clearer and the refresh use case is composable from existing flags.

### D7 — `planner.force_strategy: flat | domain-parallel | auto`

A simple enum read at `lib/set_orch/planner.py:2475` (just before the `if req_count >= DOMAIN_PARALLEL_MIN_REQS:` check, inside the `if input_mode == "digest":` block). When `flat` → skip the threshold check, force single-call decompose. When `domain-parallel` → skip the threshold check, force the 3-phase pipeline. When `auto` (default) → today's behavior.

Validation: when `force_strategy` is set to a non-`auto` value, the planner emits an INFO log naming the source so forensic review distinguishes "operator forced" from "threshold triggered."

The knob applies only in `digest` input mode (which is where the strategy decision exists). `brief` and `spec` modes bypass the strategy decision entirely.

Alternative considered: a numeric `domain_parallel_min_reqs` knob. Rejected — exposes the brittle internal threshold and pushes the brittleness onto operators. The strategy enum is at the right semantic level.

### D8 — Validation: 4 scaffolds × 2 digest runs

The change ships with a documented validation procedure (in `tasks.md`) that runs `set-orch-core digest run` twice on each of `tests/e2e/scaffolds/{nano,micro-web,minishop,craftbrew}/`. Expected:

| Scaffold | Run 1 | Run 2 | Strategy under threshold=30 |
|---|---|---|---|
| nano | API call, store cache | cache hit, byte-identical raw | observed and logged |
| micro-web | API call, store cache | cache hit, byte-identical | observed and logged |
| minishop | API call, store cache | cache hit, byte-identical | observed and logged |
| craftbrew | API call, store cache | cache hit, byte-identical | observed and logged |

The validation does NOT prescribe what req-count each scaffold should produce — that is the LLM's call. It DOES require run-1 vs run-2 byte equality of the cached raw response, AND that the routed strategy is **logged** for each scaffold. The chosen strategy per scaffold is a record of the current threshold's behavior, not a pass/fail criterion of this change. Mismatches between run-1 and run-2 of the same scaffold are a hard failure of the change — that means cache key composition is wrong.

## Risks / Trade-offs

- [**Risk**] Cache key collision (two different prompts hash to the same SHA256). → **Mitigation:** SHA256 collision probability is negligible at our scale (64 entries vs 2^256 keyspace). Not a real concern.

- [**Risk**] Operator manually edits a spec, expects a fresh digest, gets a stale cache hit. → **Mitigation:** The `prompt` is built fresh from spec content on every call (`build_digest_prompt` reads the spec files), so any spec edit produces a different prompt and a cache miss. The risk only materializes if `build_digest_prompt` itself becomes non-deterministic for the same spec; D2's note covers this with a unit test.

- [**Risk**] Cold-start race: two parallel processes invoke `call_digest_api` on the same spec concurrently before any cache exists. Each gets a fresh (and possibly different) LLM response. → **Mitigation:** First-process-to-rename wins; the cache then records that one response. Future runs are deterministic. The two concurrent processes themselves see different responses — this is a known limitation of the no-locking approach. Acceptable trade-off: file locking would slow every cache write, parallel cold-starts are rare in practice (one orchestration per spec at a time), and the second start (any time after the first completes) sees a deterministic hit.

- [**Risk**] Cache write race (two processes finishing API calls at the same instant for the same key). → **Mitigation:** Filesystem-level rename-write is atomic on POSIX; whichever process renames last wins. Both wrote valid (parse-OK) entries, so the result is correct from the cache's perspective.

- [**Risk**] Disk fills up if eviction breaks. → **Mitigation:** 64 entries × ~few KB = ~1 MB upper bound. Even total eviction failure is harmless. We add a unit test asserting the LRU prune executes on cache write.

- [**Risk**] `force_strategy` misuse — operator forces `flat` on a 100-req spec and gets a monolithic plan. → **Mitigation:** This is the documented intent of the knob. Logging makes the choice visible. We do not add guardrails — explicit operator intent is respected.

- [**Trade-off**] Caching makes digest invocations less observable in cost/timing data. → **Mitigation:** Cache hits log a distinct INFO line (`digest cache hit`) so dashboards can distinguish hits from API calls. The events.jsonl `LLM_CALL` event is naturally absent on hits, which is the correct signal.

- [**Trade-off**] We accept that two operators on different machines paying API cost for the same first-run spec is fine. A shared/team cache is a future enhancement, not a v1 requirement.

- [**Trade-off**] The 64-entry LRU cap is a guess. If telemetry shows working sets exceed it, raising the cap is a one-line follow-up. We do not over-engineer to a configurable cap today.

## Migration Plan

1. Land code on a feature branch.
2. Run validation procedure (D8): 4 scaffolds × 2 runs, capture cached raw responses.
3. If run-1 vs run-2 raw-response bytes diverge for ANY scaffold, the change is broken — investigate (likely cache key composition bug or write/read symmetry issue).
4. Manually delete `~/.cache/set-orch/digest-cache/` once before merging to confirm cold-start path works (no errors when cache dir doesn't exist).
5. Update release notes calling out the new cache location and the two new flags.

Rollback: revert the proposal commit. Cached files remain on disk but are simply unused by the reverted code. No corruption risk.

## Open Questions

- **Q1**: Should the cache also be controllable via `orchestration.yaml::digest.cache_enabled: false` for projects that want to never cache (e.g. CI environments testing digest-prompt changes)? **Decision:** defer to follow-up. The two CLI flags cover the immediate use cases; a YAML-level switch can land later if telemetry shows it's needed.

- **Q2**: Should we surface the cache state in the activity dashboard (cache hit/miss banner per run)? **Decision:** out of scope for this change; the INFO log is sufficient. Track as a follow-up if operators ask.

- **Q3**: The planner has a separate `decompose_brief` LLM call for Phase 1 of the domain-parallel pipeline (`lib/set_orch/planner.py:2076`). Should THAT be cached too? **Decision:** not in this change. Phase-1 brief output is hash-deterministic *given* a deterministic digest input — once we fix the root non-determinism (the digest), downstream LLM calls become identical inputs → near-identical outputs. We measure first; if Phase-1 jitter still produces plan divergence after digest is cached, we extend the cache scope in a follow-up.
