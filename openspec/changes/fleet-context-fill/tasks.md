## 1. Server — resolve the window and publish the fill

- [x] 1.1 Add a model→window table with normalised matching (anthropic 200 000 and its 1M variants, glm 900 000, gpt-6-astra 272 000), returning "unresolved" — never a default — for an unmatched name [REQ: the-window-is-resolved-from-the-measured-model-never-the-recorded-provider]
- [x] 1.2 Resolve each live agent's window from the MEASURED `cache.model`, ignoring `provider.recorded` entirely [REQ: the-window-is-resolved-from-the-measured-model-never-the-recorded-provider]
- [x] 1.3 Publish a `context` block per agent in the fleet payload (window, tokens, fill fraction, resolved model), as a sibling of `cache` rather than fields added to it [REQ: the-fill-and-its-window-are-computed-once-server-side]
- [x] 1.4 Emit an explicit unmeasured state when the window is unresolved or no token figure exists — never a zero window and never a zero fill [REQ: an-unknown-window-is-unmeasured-and-never-a-bar]
- [x] 1.5 Band the fill at 70 % / 90 % reusing the values `usage/glm.py` already documents, so one screen teaches one reading [REQ: a-fill-mark-per-live-agent-on-the-headers-own-line]

## 2. Web — the pure decisions, separately assertable

- [x] 2.1 New `web/src/lib/fleetContextFill.ts` holding the mark decisions as pure functions, mirroring how `fleetUsageBars.ts` and `fleetCacheHeat.ts` are structured [REQ: a-fill-mark-per-live-agent-on-the-headers-own-line]
- [x] 2.2 Map the payload's unmeasured state onto the strip's existing `?` form, with no bar drawn [REQ: an-unknown-window-is-unmeasured-and-never-a-bar]
- [x] 2.3 Sort by descending fill and apply the cap, returning both the drawn marks and the count of the remainder [REQ: the-cap-may-not-hide-a-fuller-agent]
- [x] 2.4 Build each mark's description from the token count, the window and the resolved model, stating the count is a proxy for context size [REQ: the-token-figure-is-stated-as-a-proxy]
- [x] 2.5 Consume the payload's fill fraction directly — assert no window table or fraction arithmetic exists in the web layer [REQ: the-fill-and-its-window-are-computed-once-server-side]

## 3. Web — render it on the header

- [x] 3.1 Draw the marks on the fleet header's own line beside the account quota bars, visually distinct from them [REQ: a-fill-mark-per-live-agent-on-the-headers-own-line]
- [x] 3.2 Render the overflow count and the unmeasured count as icon+count marks in the existing header style [REQ: the-cap-may-not-hide-a-fuller-agent]
- [x] 3.3 Draw nothing at all when no agent is live — no empty or zero-width bar [REQ: a-fill-mark-per-live-agent-on-the-headers-own-line]

## 4. Tests

- [x] 4.1 Python: window resolution — each known family resolves, an unknown name resolves to unmeasured, and an agent with `recorded: false` still resolves from its measured model [REQ: the-window-is-resolved-from-the-measured-model-never-the-recorded-provider]
- [x] 4.2 Python: payload carries window+fill when resolvable and the unmeasured state otherwise, asserting no zero window or zero fill is ever emitted [REQ: the-fill-and-its-window-are-computed-once-server-side]
- [x] 4.3 Web: unmeasured renders as `?` and never as a bar, in both the no-window and no-tokens cases [REQ: an-unknown-window-is-unmeasured-and-never-a-bar]
- [x] 4.4 Web: with more agents than the cap, assert every hidden agent's fill is ≤ every drawn agent's fill — the property, not one example [REQ: the-cap-may-not-hide-a-fuller-agent]
- [x] 4.5 Web: the description names tokens, window and model and carries the proxy wording [REQ: the-token-figure-is-stated-as-a-proxy]
- [x] 4.6 Prove each new test fails without its fix: stash the implementation and re-run, confirming the mutation reaches the interpreter (clear `.pyc`) and that the restore actually restored [REQ: the-fill-and-its-window-are-computed-once-server-side]

## 5. Look at it — required, not optional

- [ ] 5.1 Open the running dashboard in the browser and look at the header with real live agents; confirm the bars are legible at their real width and do not read as one bar [REQ: a-fill-mark-per-live-agent-on-the-headers-own-line]
- [ ] 5.2 Confirm on screen that a differing-window agent (Astra 272k beside a GLM 900k) reads correctly and that the two marks are not confusable with the quota bars [REQ: a-fill-mark-per-live-agent-on-the-headers-own-line]
- [ ] 5.3 Choose the final cap by looking at the real header at a realistic fleet size, and record the number chosen and why [REQ: the-cap-may-not-hide-a-fuller-agent]
- [ ] 5.4 If the browser cannot be reached, leave 5.1–5.3 OPEN and say so in the commit and to the user — never substitute a structural count [REQ: a-fill-mark-per-live-agent-on-the-headers-own-line]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN the fleet holds live agents whose measured models resolve to different windows THEN the header carries one fill mark per live agent, each against its own model's window [REQ: a-fill-mark-per-live-agent-on-the-headers-own-line, scenario: several-live-agents-on-different-providers]
- [ ] AC-2: WHEN no agent is live THEN the header carries no context-fill mark and no empty or zero-width bar [REQ: a-fill-mark-per-live-agent-on-the-headers-own-line, scenario: no-live-agents]
- [ ] AC-3: WHEN an agent's provider is unrecorded and its measured model is known THEN a fill mark is drawn, resolved from the measured model [REQ: the-window-is-resolved-from-the-measured-model-never-the-recorded-provider, scenario: provider-unrecorded-model-measured]
- [ ] AC-4: WHEN an agent's recorded model and measured model resolve to different windows THEN the measured model's window is used and the description states which model resolved it [REQ: the-window-is-resolved-from-the-measured-model-never-the-recorded-provider, scenario: the-record-and-the-measurement-disagree]
- [x] AC-5: WHEN an agent's measured model is not in the window table THEN the mark is the unmeasured form and names the unresolved model [REQ: an-unknown-window-is-unmeasured-and-never-a-bar, scenario: the-measured-model-has-no-known-window]
- [x] AC-6: WHEN an agent has no cache record so no token figure exists THEN the mark is the unmeasured form, not a bar [REQ: an-unknown-window-is-unmeasured-and-never-a-bar, scenario: the-agent-carries-no-token-figure]
- [x] AC-13: WHEN an agent's token figure is larger than its resolved window THEN the mark is unmeasured, its description says the window is wrong, and no fill or band is reported [REQ: an-unknown-window-is-unmeasured-and-never-a-bar, scenario: the-token-figure-exceeds-the-resolved-window]
- [x] AC-14: WHEN an agent's token figure equals its resolved window THEN the agent is measured, at a full fill [REQ: an-unknown-window-is-unmeasured-and-never-a-bar, scenario: the-token-figure-exactly-fills-the-window]
- [ ] AC-7: WHEN a reader inspects a drawn fill mark THEN the description carries the token count, the window and the resolved model, and states the count is a proxy [REQ: the-token-figure-is-stated-as-a-proxy, scenario: reading-one-marks-description]
- [ ] AC-8: WHEN more live agents carry a resolvable fill than the cap allows THEN the fullest agents up to the cap are drawn with a count of the remainder [REQ: the-cap-may-not-hide-a-fuller-agent, scenario: more-live-agents-than-the-cap]
- [ ] AC-9: WHEN the cap has hidden one or more agents THEN no hidden agent's fill is greater than any drawn agent's fill [REQ: the-cap-may-not-hide-a-fuller-agent, scenario: the-hidden-agents-are-never-the-fullest]
- [ ] AC-10: WHEN one or more agents are in the unmeasured state THEN they are reported by their own count or mark and not silently omitted [REQ: the-cap-may-not-hide-a-fuller-agent, scenario: unmeasured-agents-are-counted-not-dropped]
- [x] AC-11: WHEN the fleet payload describes a live agent with a resolvable window THEN it carries that agent's context window and fill fraction [REQ: the-fill-and-its-window-are-computed-once-server-side, scenario: the-payload-states-the-window-and-the-fill]
- [x] AC-12: WHEN an agent's window cannot be resolved or it carries no token figure THEN the payload marks it unmeasured rather than carrying a zero window or zero fill [REQ: the-fill-and-its-window-are-computed-once-server-side, scenario: the-payload-states-the-unmeasured-case]
