## 1. The price table

- [x] 1.1 Add a pricing module holding the cache multipliers (read 0.1×, 5-minute write 1.25×, one-hour write 2×) and per-model input prices, each carrying the date its figures were verified against platform.claude.com [REQ: prices-come-from-one-dated-table-and-a-missing-price-degrades-to-tokens]
- [x] 1.2 Return no price — never a fabricated one — for a model absent from the table, so callers can degrade to tokens [REQ: prices-come-from-one-dated-table-and-a-missing-price-degrades-to-tokens]
- [x] 1.3 Unit-test both paths: a known model yields a cost, an unknown model yields none [REQ: prices-come-from-one-dated-table-and-a-missing-price-degrades-to-tokens]

## 2. Reading the cache state

- [x] 2.1 Add a reader that takes a transcript path and returns the last assistant record's cache state — request start timestamp, size (`cache_read_input_tokens` + `cache_creation_input_tokens`), and the lifetime from whichever `cache_creation.ephemeral_*` bucket holds tokens [REQ: a-sessions-prompt-cache-state-is-read-from-the-transcript-it-already-writes]
- [x] 2.2 Scan BACKWARD from the end of the file and stop at the first usage block, so cost does not scale with transcript size [REQ: a-sessions-prompt-cache-state-is-read-from-the-transcript-it-already-writes]
- [x] 2.3 Return absent — not a zero-valued state — for a missing transcript, a transcript with no usage record, and an unreadable or malformed file [REQ: a-session-with-no-measurement-is-representable-and-is-not-a-cold-one]
- [x] 2.4 Unit-test with fixtures covering: a 1h record, a 5m record, no transcript, a transcript with no usage block, and a truncated final line [REQ: a-session-with-no-measurement-is-representable-and-is-not-a-cold-one]
- [x] 2.5 Prove the lifetime is read rather than assumed: a fixture writing the 5-minute bucket must yield 5 minutes, and the test must fail if the value is hard-coded [REQ: a-sessions-prompt-cache-state-is-read-from-the-transcript-it-already-writes]

## 3. Carrying it to the surface

- [x] 3.1 Give the fleet `Agent` record an optional cache field, populated from the reader via the transcript path `_session_log_for` already resolves [REQ: a-sessions-prompt-cache-state-is-read-from-the-transcript-it-already-writes]
- [x] 3.2 Serialize it into the fleet API payload as an optional object, omitted entirely when unmeasured [REQ: a-session-with-no-measurement-is-representable-and-is-not-a-cold-one]
- [x] 3.3 Confirm by inspection that no code path writes cache state to disk — no cache file, no log line carrying size or cost, no debug dump [REQ: nothing-measured-from-a-session-is-written-down]
- [x] 3.4 Test that a fleet payload for an agent with no transcript carries no cache object at all [REQ: a-session-with-no-measurement-is-representable-and-is-not-a-cold-one]

## 4. The mark on the tab

- [x] 4.1 Compute, per tab, one cooled fraction (0 when the request just started, 1 at the lifetime) and ONE `cold` boolean derived from it [REQ: a-cold-tab-says-so-in-more-than-one-way-and-the-ways-cannot-disagree]
- [x] 4.2 Render the bar filling from the leading edge with the cooled fraction, staying fully drawn past expiry [REQ: the-tab-marks-how-far-its-cache-has-cooled]
- [x] 4.3 Colour the bar in three bands by that same fraction [REQ: the-tab-marks-how-far-its-cache-has-cooled]
- [x] 4.4 Scale the bar's thickness with cache size against a fixed ceiling [REQ: the-mark-carries-the-stake-as-well-as-the-time]
- [x] 4.5 Drive the name's cold styling and the price's appearance from the SAME `cold` boolean as the full bar — no second computation [REQ: a-cold-tab-says-so-in-more-than-one-way-and-the-ways-cannot-disagree]
- [x] 4.6 Render the unmeasured mark — distinct from live and cold, with no bar and no price [REQ: a-tab-with-no-measurement-is-marked-unknown-never-cold]
- [x] 4.7 Put the remaining minutes, the token count and the cost in the hover title, for every state including unmeasured [REQ: the-exact-figures-are-reachable-without-acting]

## 5. Proving the marks

- [x] 5.1 Unit-test the fresh / partway / expired renderings, asserting the bar's fill and that it persists past expiry [REQ: the-tab-marks-how-far-its-cache-has-cooled]
- [x] 5.2 Unit-test that two tabs at equal cooling but different sizes render different thicknesses [REQ: the-mark-carries-the-stake-as-well-as-the-time]
- [x] 5.3 Unit-test that cold name, full bar and price appear and disappear together — and that no input makes them disagree [REQ: a-cold-tab-says-so-in-more-than-one-way-and-the-ways-cannot-disagree]
- [x] 5.4 Unit-test that an unmeasured tab renders neither as cold nor as live [REQ: a-tab-with-no-measurement-is-marked-unknown-never-cold]
- [x] 5.5 Unit-test that an unknown model shows tokens and no monetary figure [REQ: prices-come-from-one-dated-table-and-a-missing-price-degrades-to-tokens]
- [x] 5.6 Mutation-check the new tests: break the cooled fraction, the thickness scale and the `cold` condition in turn, confirm each break fails a test, and restore each with a verified diff [REQ: a-cold-tab-says-so-in-more-than-one-way-and-the-ways-cannot-disagree]

## 6. PM mode ordering

- [x] 6.1 Replace the freshness sort key in `attention.py` with recoverable money — size × (rewrite − read) while live, zero once cold [REQ: the-queue-is-ordered-by-freshness-of-the-blockage-not-by-arrival]
- [x] 6.2 Keep freshness as the ranking for items whose cache state was not measured, without assuming a size or age for them [REQ: the-queue-is-ordered-by-freshness-of-the-blockage-not-by-arrival]
- [x] 6.3 Preserve project exhaustion and demotion exactly as they are — this task changes the key, not the queue's other rules [REQ: the-queue-is-ordered-by-freshness-of-the-blockage-not-by-arrival]
- [x] 6.4 Unit-test: equal freshness with unequal stakes, live outranking cold regardless of blockage time, and unmeasured items still ordered by freshness [REQ: the-queue-is-ordered-by-freshness-of-the-blockage-not-by-arrival]
- [x] 6.5 Update `attention.py`'s docstring — it currently states the module asserts no cache lifetime, which this change makes false [REQ: the-queue-is-ordered-by-freshness-of-the-blockage-not-by-arrival]

## 7. Verification

- [x] 7.1 Run the Python unit suite and the web unit suite; compare failures against a baseline built per the `regression-baseline` skill, not against a remembered number [REQ: the-tab-marks-how-far-its-cache-has-cooled]
- [x] 7.2 `tsc -b --force` in `web/` and `pnpm build`, so port 7400 serves the change [REQ: the-tab-marks-how-far-its-cache-has-cooled]
- [x] 7.3 **MANDATORY VISUAL CHECK — DONE 2026-08-27, on the running dashboard at port 7400.** All four states seen, across two projects, because no single project held them all:
  - `set-core` (3 seats): two **live** tabs, `fill 0.002` and `0.006`, emerald fill ~0.8 px of a 135 px track — a bar the eye correctly does not notice yet — and the **unmeasured** `?` on `consumer-c-1`.
  - `consumer-a` (3 seats): two **cold** tabs (`fill 1.000`, full-width `bg-red-400`, red name, `$1.95` / `$2.87`) either side of one live tab (`fill 0.013`, emerald, no price). The cold/live difference is legible without reading a word.
  - `consumer-b` (2 seats): both cold, `$.83` and `$1.00`.
  - Thickness varies on the real data: 4 px at 487 557 tokens vs 3 px at 101 211 in the same strip, at equal cooling — AC-8 rendered live, not only in a fixture.
  - Hover titles carry the figures for every state, e.g. `prompt cache warm for 1h 0m — 487 557 tokens, then $4.88 to rewrite` and `prompt cache expired — 287 204 tokens, $2.87 to rewrite`.
  - **This check found a defect two green suites did not — see 7.6.** [REQ: a-cold-tab-says-so-in-more-than-one-way-and-the-ways-cannot-disagree]
- [x] 7.4 **DONE — the accepted risk judged in situ, and it holds.** Counted on the real strips: **4 red names** (2 of 3 on `consumer-a`, 2 of 2 on `consumer-b`). Red does NOT read as "failed" there, and the reason is structural rather than a matter of taste: `TAB_DOT` (`Fleet.tsx:822`) maps every state to emerald / sky / grey / amber and has **no red value and no red fallback**, and the tab's two other markers (unconfirmed binding, refuted declaration) are amber. **Red is unused on this strip except for a cold cache**, so it carries no second meaning to be confused with. The price rendered beside the name reinforces it — `consumer-b-2030 $.83` reads as a cost, not a crash. Not changed unilaterally; reported.
  - **One finding to report rather than fix here:** the unmeasured mark and the unconfirmed-binding marker are **the same glyph in the same colour** — an amber `?` — and render adjacent. Only the tooltip separates them. No tab currently shows both (the one seat holding both, `chrome`, is alone on its project so no strip renders), so this is a latent collision, not a live defect. Out of this change's scope; raise it before a seat lands in both states. [REQ: a-cold-tab-says-so-in-more-than-one-way-and-the-ways-cannot-disagree]
- [x] 7.5 **DONE — the unmeasured mark seen live.** `consumer-c-1` on `set-core`'s three-tab strip renders `data-fleet-tab-cache="unmeasured"`: an amber `?`, **no bar element at all** (not a zero-length one), **no price**, and the title `prompt cache not measured — this seat has no transcript to read`. It is beside two live tabs, so the three-way distinction is visible in one glance, and nothing about it reads as cold. [REQ: a-tab-with-no-measurement-is-marked-unknown-never-cold]

## 7b. What the visual check found

- [x] 7.6 **A price of $1.00 rendered as `$.00`.** Measured on the running dashboard: `consumer-b-1`, 99 685 tokens at `rewrite_usd = 0.9969`, drew `$.00` on its tab. `money()` asked `usd < 1` of the **raw** value and then sliced the leading character off the **rounded** string, and the two disagree across `[0.995, 1)`: `(0.9969).toFixed(2)` is `"1.00"`, and `.slice(1)` ate the `1`. The fail direction is why it mattered — a dollar of stake read as nothing, on a strip whose only job is to say what a cold cache costs. Fixed by deciding the branch on the rounded string it actually cuts. Proven by a test run against the UNFIXED source first (`expected '$.00' to be '$1.00'`), then green; re-verified on the running screen after `pnpm build` — the tab now reads `consumer-b-1 $1.00` [REQ: prices-come-from-one-dated-table-and-a-missing-price-degrades-to-tokens]
- [x] 7.7 Not asserted, and said out loud rather than left implicit: `money(0.995)` yields `$.99`, because 0.995's binary representation sits just below the decimal it is written as. That is IEEE-754, not this formatter, and a test asserting otherwise would be a test about floats [REQ: prices-come-from-one-dated-table-and-a-missing-price-degrades-to-tokens]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the last assistant record of a session's transcript carries a usage block with cache figures THEN the session's cache state names that record's timestamp, the sum of its cache read and cache creation tokens, and the lifetime that record wrote [REQ: a-sessions-prompt-cache-state-is-read-from-the-transcript-it-already-writes, scenario: a-session-that-has-made-a-request]
- [x] AC-2: WHEN a record's `cache_creation` reports tokens written under the one-hour lifetime and none under the five-minute one THEN the state names one hour, and the framework does not substitute a lifetime of its own [REQ: a-sessions-prompt-cache-state-is-read-from-the-transcript-it-already-writes, scenario: the-lifetime-is-read-never-assumed]
- [x] AC-3: WHEN a discovered agent has no transcript on disk THEN its record carries no cache state, rather than a cache state with zero size [REQ: a-session-with-no-measurement-is-representable-and-is-not-a-cold-one, scenario: a-seat-that-has-never-run]
- [x] AC-4: WHEN a transcript exists but holds no assistant record carrying cache figures THEN its record carries no cache state [REQ: a-session-with-no-measurement-is-representable-and-is-not-a-cold-one, scenario: a-transcript-with-no-usage-records]
- [x] AC-5: WHEN a session's last request started moments ago THEN its tab's bar is empty [REQ: the-tab-marks-how-far-its-cache-has-cooled, scenario: a-freshly-used-session]
- [x] AC-6: WHEN half of a session's cache lifetime has elapsed THEN its tab's bar is drawn to about half its width, in the band that fraction falls in [REQ: the-tab-marks-how-far-its-cache-has-cooled, scenario: a-session-partway-through-its-lifetime]
- [x] AC-7: WHEN more time has passed than the session's cache lifetime THEN the bar is fully drawn and stays drawn, in the final band [REQ: the-tab-marks-how-far-its-cache-has-cooled, scenario: a-session-past-its-lifetime]
- [x] AC-8: WHEN two sessions are equally far through their lifetimes but one holds several times the tokens of the other THEN the larger session's bar is drawn thicker [REQ: the-mark-carries-the-stake-as-well-as-the-time, scenario: two-tabs-same-age-different-caches]
- [x] AC-9: WHEN a session's cache lifetime has elapsed THEN the tab's name is marked as cold, its bar is fully drawn, and the rewrite cost is shown beside the name [REQ: a-cold-tab-says-so-in-more-than-one-way-and-the-ways-cannot-disagree, scenario: a-cold-tab]
- [x] AC-10: WHEN a session's cache is still within its lifetime THEN the tab's name carries no cold marking and no cost is shown [REQ: a-cold-tab-says-so-in-more-than-one-way-and-the-ways-cannot-disagree, scenario: a-live-tab]
- [x] AC-11: WHEN an agent's record carries no cache state THEN its tab shows an unmeasured marking, with no bar and no cost [REQ: a-tab-with-no-measurement-is-marked-unknown-never-cold, scenario: an-unmeasured-seat]
- [x] AC-12: WHEN the reader hovers a tab whose cache is still live THEN the remaining minutes, the cache size, and the rewrite cost are stated [REQ: the-exact-figures-are-reachable-without-acting, scenario: hovering-a-live-tab]
- [x] AC-13: WHEN the reader hovers a tab with no cache state THEN it states that the cache was not measured, and offers no figure [REQ: the-exact-figures-are-reachable-without-acting, scenario: hovering-an-unmeasured-tab]
- [x] AC-14: WHEN a session's model has no entry in the price table THEN the tab presents the cache size in tokens and no monetary figure [REQ: prices-come-from-one-dated-table-and-a-missing-price-degrades-to-tokens, scenario: a-model-the-table-does-not-know]
- [x] AC-15: WHEN the price table is read THEN the date on which its figures were verified is recorded alongside them [REQ: prices-come-from-one-dated-table-and-a-missing-price-degrades-to-tokens, scenario: the-table-states-its-own-date]
- [x] AC-16: WHEN cache state is computed for a fleet of agents THEN it reaches the surface and is written to no file [REQ: nothing-measured-from-a-session-is-written-down, scenario: the-state-is-displayed-and-discarded]
- [x] AC-17: WHEN two agents became blocked at the same moment and both caches are still live, but one holds several times the tokens of the other THEN the agent holding the larger cache is presented first [REQ: the-queue-is-ordered-by-freshness-of-the-blockage-not-by-arrival, scenario: a-larger-stake-outranks-an-equally-fresh-smaller-one]
- [x] AC-18: WHEN one agent's cache lifetime has elapsed and another's has not THEN the agent whose cache is still live is presented first, whatever their blockage times [REQ: the-queue-is-ordered-by-freshness-of-the-blockage-not-by-arrival, scenario: an-expired-cache-carries-no-urgency]
- [x] AC-19: WHEN one agent became blocked two minutes ago and another forty minutes ago, and neither agent's cache state could be measured THEN the two-minute-old blockage is presented first [REQ: the-queue-is-ordered-by-freshness-of-the-blockage-not-by-arrival, scenario: a-fresh-blockage-outranks-an-old-one]
- [x] AC-20: WHEN more than one project holds queued items the reader has not seen yet THEN every unseen item of the presented item's project is offered before an unseen item of another project [REQ: the-queue-is-ordered-by-freshness-of-the-blockage-not-by-arrival, scenario: a-project-is-exhausted-before-the-next-one-is-entered]


**How each was verified (2026-08-27).** AC-1…AC-4 by the Python reader's fixture
tests (`tests/unit/test_fleet_cache_heat.py`); AC-5…AC-14 by the web unit tests
(`web/tests/unit/fleetCacheHeat.test.ts`) **and** by looking at the running
dashboard — every one of AC-5, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12 and AC-13
was seen on a real strip, not only in a fixture (see 7.3). AC-6's midpoint band
is the one state the live fleet did not hold at the time of the check, and rests
on its unit test. AC-15 by `PRICES_VERIFIED_ON = "2026-08-27"` in
`lib/set_orch/cost.py`, shape-asserted at `tests/unit/test_cost_metrics.py:401`.
AC-16 by inspection (task 3.3). AC-17…AC-20 by
`tests/unit/test_fleet_attention_queue.py`.
