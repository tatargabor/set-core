# CraftBrew E2E — Digest Pipeline Findings

## Run Info
- Date: 2026-03-10
- Spec: scaffold-complex (17 files, ~112KB, CraftBrew webshop)
- Digest result: 178 requirements, 13 domains

## Issues Found

### 1. Digest API timeout (600s nem elég)
- **Tünet**: 610s runtime → timeout kill → sentinel restart
- **Ok**: 118KB prompt (17 spec fájl + instrukciók) + opus model = ~10 perc generálás
- **Fix**: `RUN_CLAUDE_TIMEOUT=600` → `900` a `call_digest_api()`-ban
- **Státusz**: Fixelve, 2. próbálkozásnál sikeres (~10 perc)

### 2. Events fájlnév mismatch (sentinel vs orchestrator) — BLOKKOLÓ BUG
- **Tünet**: sentinel `orchestration-events.jsonl`-t figyel, orchestrator `orchestration-state-events.jsonl`-ba ír
- **Ok**: `events.sh` lazy init deriválja a fájlnevet `STATE_FILENAME`-ból (`orchestration-state.json` → `orchestration-state-events.jsonl`), de sentinel hardcoded `EVENTS_FILE="orchestration-events.jsonl"`
- **Hatás**: sentinel stuck detection effektíve kikapcsolt (nem létező fájl → always alive) AMÍG nincs events fájl. DE ha sentinel ír bele (`sentinel_emit_event`), létrejön a rossz nevű fájl, ami soha nem frissül az orchestrator által → sentinel 180s után "stuck"-nak látja → KILLT küld a healthy orchestratornak
- **Reprodukálva**: PID 131270 — sentinel restart után 183s-nél stuck detect → kill → permanent exit
- **Fix**: `EVENTS_FILE="${STATE_FILE%.json}-events.jsonl"` — derive, ne hardcode
- **Státusz**: Fixelve

### 3. Digest event-ek nem voltak — már fixelve
- `cc4fe813a` commitban fixelve: DIGEST_STARTED/RESPONSE_RECEIVED/COMPLETE/FAILED emit
- Működik: events.jsonl-ben megjelenik

### 4. Directory path resolution — már fixelve
- `93a15bd83` commitban fixelve: `cmd_start()` `-d` check + digest freshness check
- Működik: sentinel → orchestrator → find_input → digest mode

### 5. Planner decomposition timeout (300s nem elég)
- **Tünet**: "Claude decomposition failed" — 850s runtime (planner 300s timeout a digest ~600s-e után)
- **Ok**: digest-mode planner prompt tartalmazza a 178 req + conventions + dependencies + domain summaries-t → nagy input → opus lassan generál
- **Fix**: `RUN_CLAUDE_TIMEOUT=300` → `600` a planner decomposition-ben
- **Megjegyzés**: A sentinel auto-restart 2. próbánál a digest "fresh"-ként megmarad (jó!), de a planner újra timeout-olhat
- **Státusz**: Fixelve, de a jelenlegi run a régi kóddal fut (sentinel nem reload-ol)

## Timing Data
- Scaffold setup: ~5s (17 fájl copy, git init, set-project init)
- Digest scan: <1s
- Digest API call (opus, 118KB prompt): ~10 perc (timeout-olt 600s-nél, sikeres 900s-nél)
- Digest parse + write: <1s
- Digest result: 178 requirements, 13 domains
- Planner decomposition: timeout-olt 300s-nél → TBD with 600s

### 6. "Cannot find input file" — `-f` check rejects directory (dispatcher.sh)
- **Tünet**: Plan sikerül, de dispatch fázisban "Cannot find input file from plan: /tmp/craftbrew-e2e/docs"
- **Ok**: `cmd_start()` két helyen is `-f "$INPUT_PATH"` → false directory-nál
- **Fix**: `-f` → `-e` (exists) a 1052 és 1119 soroknál
- **Státusz**: Fixelve

### 7. `parse_directives` "read error: Is a directory" (utils.sh)
- **Tünet**: `read: read error: 0: Is a directory` a logban
- **Ok**: `resolve_directives()` → `parse_directives("$input_file")` → `while read < "$brief_file"` — directory-ra read nem megy
- **Fix**: `resolve_directives()`-ben directory check: ha `-d`, parse_directives /dev/null (defaults only)
- **Státusz**: Fixelve

## Timing Data (updated)
- Scaffold setup: ~5s (17 fájl copy, git init, set-project init)
- Digest scan: <1s
- Digest API call (opus, 118KB prompt): ~10 perc
- Digest parse + write: <1s
- Digest result: 178 requirements, 13 domains
- Planner decomposition (opus): ~8 perc
- Planner result: 7 changes (1. fázis), 58 req covered, 120 uncovered (auto-replan)
- Dispatch first change: <5s
- Total time to first agent working: ~20 perc (digest + planner + dispatch)

### 8. Stall recovery működik
- `test-infrastructure-setup` stalled (Ralph PID dead, worktree dir deleted by sentinel restart)
- 300s cooldown → auto-resume → running újra
- Ez normális sentinel viselkedés: fresh start törli a worktree-ket, de a monitor újradispatch-olja

### 9. Sentinel vs manuális restart konfliktus
- **Tünet**: Manuális `set-orchestrate start` → "Orchestrator is already running" → azonnali exit
- **Ok**: Az eredeti sentinel process (set-sentinel) saját crash recovery-vel rendelkezik — kill -9 után 33s-en belül újraindít. Manuális restart felesleges és ütközik.
- **Tanulság**: Ha sentinel fut, NE indítsunk manuálisan orchestrator-t. A sentinel a sole process manager.
- **Hatás**: 3 "rapid crash" a sentinel megfigyelésben, de valójában nem crash volt — hanem "already running" error
- **Státusz**: Nem bug, hanem operational lesson

### 10. Sentinel stale state reset működik
- **Tünet**: kill -9 után state.json "running" maradt process nélkül
- **Ok**: Sentinel `check_stale_state()` detektálja: status=running + nincs process → reset to stopped → újraindítás
- **Log**: `[sentinel] Stale state detected (status=running but no process) — resetting to stopped`
- **Státusz**: Működik correctly

### 11. user-auth-and-accounts FAILED — túl nagy change (14 REQ)
- **Tünet**: 3x verify-failed → failed, 708K token elégetve
- **Timeline**: dispatch 14:03 → 66 watchdog warn → verify-fail 14:34, 14:39, 14:43 → failed
- **Ok**: 14 requirement egy change-ben (auth + regisztráció + login + password reset + profil + címkezelés + rendelés-történet + API route-ok + tesztek). Túl nagy scope, agent nem tudta a verify gate-et teljesíteni 3 próbálkozásra sem.
- **Összehasonlítás**: 5-7 REQ-es change-ek (első 4) mind 12-19 perc alatt merged, 0 retry. 14 REQ-es change 41 perc + failed.
- **Fix**: Planner granularity rules commitolva (max 6 REQ/change, M complexity cap, sub-domain chaining). Következő run-tól hatályos.
- **Státusz**: Root cause fixelve (planner prompt), ez a run a régi szabályokkal futott

### 12. product-catalog 1M+ token és még fut (22 REQ)
- **Tünet**: 22 requirement, 1M+ token, még running ~45 perc után
- **Ok**: Ugyanaz mint #11 — túl nagy change. List + detail + filters + search + equipment + merch + bundles mind egy change-ben.
- **Prognózis**: Ha átmegy verify-en, nagyon drága. Ha nem, újabb failed.
- **Státusz**: Következő run-ban max 4 change-re bomlik az új szabályokkal

### 13. Watchdog event spam — 66+ WARN egy change-hez
- **Tünet**: user-auth-and-accounts 66 db WATCHDOG_WARN event (hash_loop_pid_alive), product-catalog-nál még több
- **Ok**: emit_event hívás nem volt throttle-ölve, csak a log üzenet
- **Fix**: emit_event bekerült a throttle condition-be (minden 20. occurrence). Commitolva.
- **Státusz**: Fixelve

### 14. Sentinel restart törli worktree-ket → resume fail
- **Tünet**: Sentinel restart után `cd: /tmp/craftbrew-e2e-wt-content-stories: No such file or directory`
- **Ok**: Sentinel fresh start prune-olja a stale worktree-ket. Ha a state.json is elveszett (vagy nincs), az orchestrator megpróbálja resume-olni a change-eket de a worktree dir nem létezik.
- **Hatás**: content-stories és product-catalog nem tudott resume-olni → orchestrator crash → crash loop
- **Megjegyzés**: A worktree prune helyes viselkedés, de az orchestrator resume-nak kezelnie kell a hiányzó worktree-t (re-dispatch helyett crash)
- **Státusz**: Ismert limitáció, nem fixelve ebben a runban

## Final Run Report

### Status: INTERRUPTED (state lost, 4/7 merged)

| Change | REQs | Status | Time | Notes |
|--------|------|--------|------|-------|
| test-infrastructure-setup | ~5 | merged | ~12 min | stall recovery tested, OK |
| prisma-schema-and-seed | ~7 | merged | ~15 min | 0 retries |
| app-layout-and-design-tokens | ~6 | merged | ~15 min | 0 retries |
| i18n-routing | ~5 | merged | ~19 min | 1 E2E retry, then OK |
| user-auth-and-accounts | 14 | **FAILED** | 41 min | 3x verify-fail, 708K tokens |
| product-catalog | 22 | **INTERRUPTED** | >45 min | 1M+ tokens, worktree lost |
| content-stories | ? | **INTERRUPTED** | ? | Only artifacts created, no impl |

### Timeline
- 12:00 — Sentinel starts, digest already fresh (skipped)
- 12:00 — Planner decomposition (~8 min)
- 12:08 — First dispatch (test-infrastructure-setup)
- 12:08–13:30 — First 4 changes dispatched and merged (max_parallel: 2)
- 13:30–14:03 — Large changes dispatched (user-auth 14 REQ, product-catalog 22 REQ)
- 14:43 — user-auth-and-accounts FAILED after 3 verify retries
- ~14:50 — Sentinel/orchestrator killed externally
- 14:55 — Sentinel restarted, state.json lost, worktrees pruned → crash loop
- 14:57 — Sentinel killed manually (rapid crash 2/5)

### Key Metrics
- **Wall clock**: ~3 hours (12:00–14:57)
- **Changes merged**: 4/7 (57%)
- **Changes failed**: 1/7 (user-auth, too large)
- **Changes interrupted**: 2/7 (worktree lost)
- **Sentinel restarts**: 5+ (events bug, external kills, crash loop)
- **Bugs found & fixed**: 7 (#1–7) during this run
- **Bugs found for next run**: 3 (#11–13, planner granularity + watchdog spam)

### Conclusions

1. **Digest pipeline works end-to-end**: 17 spec files → 178 REQs → 7 changes → 4 merged. First successful digest-mode orchestration.
2. **Small changes succeed reliably**: 5-7 REQ changes merged in 12-19 min with 0-1 retries. This is the sweet spot.
3. **Large changes fail or are very expensive**: 14+ REQ changes either fail verify (708K tokens wasted) or exceed 1M tokens. Max 6 REQ/change rule already committed.
4. **Sentinel crash recovery works well**: Stale state detection, auto-restart, event-based monitoring all function correctly after the events filename fix.
5. **Missing: graceful worktree-gone handling**: When worktrees are pruned but state references them, orchestrator should re-dispatch (not crash). This is a follow-up fix.
6. **Total time to first agent**: ~20 min (digest + planner + dispatch). Acceptable for 17-file specs.

---

## Run #2 — Granularity Rules Applied

### Run Info
- Date: 2026-03-10 (same day, restart after Run #1 cleanup)
- Plan: 8 changes (all ≤6 REQ), sub-domain dependency chaining
- Digest: reused from Run #1 (fresh check worked)
- Granularity rules: max 6 REQ/change, M complexity cap, sub-domain chaining

### 15. user-auth E2E fail — Next.js logout server crash (FAILED)
- **Tünet**: 8/9 Playwright teszt pass, 1 fail: `logout clears session and reverts header`
- **Hiba**: `page.waitForURL("**/hu"): net::ERR_CONNECTION_REFUSED` — a Next.js dev server elcrashelt a logout action feldolgozása közben
- **Ok**: Server Action-ben a cookie/session törlés crasheli a dev server-t. Ugyanaz a pattern mint MiniShop Run #1-ben ("Cookies can only be modified in Server Action")
- **Hatás**: user-auth failed (1.02M token, 2 verify retry kimerítve). A Ralph kétszer próbálta fixelni, nem sikerült.
- **Tanulság**: Ez nem granularity probléma (6 REQ, normális méret). Runtime bug amit Jest mock-ok nem kapnak el, csak Playwright.
- **Lehetséges javítás**: verify retry prompt-ba Next.js-specifikus hint: "If E2E shows ERR_CONNECTION_REFUSED after server action, check cookies() usage in Server Actions"
- **Státusz**: Finding, nem fixelve

### 16. Failed dependency deadlock — BLOKKOLÓ BUG
- **Tünet**: user-auth failed → user-profile, user-addresses-orders, product-catalog-search-crosssell örökre pending maradnak
- **Ok**: `deps_satisfied()` (state.sh:170) csak `merged` statust fogad el. Ha a dependency `failed`, a függő change-ek nem indulnak el, de `active_count`-ba továbbra is `pending`-ként számítanak.
- **Hatás**: `active_count > 0` → monitor loop soha nem jut el a replan/done ágba → **orchestrator örökre várakozik**
- **Dependency graph**:
  ```
  user-auth (FAILED)
    └→ user-profile (stuck pending)
        └→ user-addresses-orders (stuck pending)
    └→ product-catalog-search-crosssell (stuck pending, also depends on detail)
  ```
- **Fix**: Ha egy dependency `failed`, a függő change-eket is `failed`-nek jelölni (cascade), VAGY `pending`-et nem active-nek számolni ha minden dependency-je terminal (failed/merge-blocked)
- **Státusz**: Nem fixelve, de blokkolja a Run #2 befejezését

### 17. active_seconds megragad — timer bug
- **Tünet**: `active_seconds` 1260-on ragadt 18+ heartbeat-en át
- **Ok**: A monitor loop timer nem incrementálja az active_seconds-et verify retry fázisban
- **Hatás**: TUI és reporting hibás időt mutat
- **Státusz**: Finding, nem fixelve

### Run #2 Status (in progress)

| Change | REQs | Status | Tokens | Notes |
|--------|------|--------|--------|-------|
| content-stories | 4 | **merged** | 1.30M | 2 verify retry, E2E pass 3. próba |
| user-auth | 6 | **FAILED** | 1.02M | logout E2E crash, 2 retry kimerítve |
| product-catalog-list | 6 | running | 22K | artifact creation fázis |
| product-catalog-detail | 6 | pending | — | blocked by list |
| product-catalog-filter | 6 | pending | — | blocked by list |
| product-catalog-search-crosssell | 3 | pending | — | **deadlocked** (depends on detail + user-auth) |
| user-profile | 4 | pending | — | **deadlocked** (depends on user-auth) |
| user-addresses-orders | 4 | pending | — | **deadlocked** (depends on user-profile) |

### 18. Checkpoint crash loop — BLOKKOLÓ BUG
- **Tünet**: Orchestrator ~20s-nél meghalt minden restart-nál. Log: "Checkpoint triggered: periodic" → "Orchestrator interrupted by signal"
- **Ok**: `checkpoint_every=3` (default), `changes_since_checkpoint=3` (3 merged change a run során). Restart-nál a monitor loop azonnal triggerelte a checkpoint-ot (3 >= 3). A `trigger_checkpoint()` → `generate_summary()` crashelt `set -e` alatt, ami a signal trap-et hívta → exit.
- **Másodlagos ok**: A `checkpoint_every` null check hiányzott — ha a directive nincs beállítva, jq `"null"` stringet ad, bash `[[ "3" -ge "null" ]]` → "null" = 0 numerikusan → mindig triggerel
- **Fix**: (1) Null/empty guard a `checkpoint_every` check-ben (monitor.sh), (2) Counter reset 0-ra restart-nál
- **Megjegyzés**: MiniShop-nál nem jött elő mert mind a 6-7 change egy fázisban volt, a counter soha nem érte el a 3-as threshold-ot merge között
- **Státusz**: Fixelve

### 19. Phase-end E2E mode implementálva
- **Motiváció**: Per-change E2E retry drága (~20-30 perc + token waste phase 2-ben: 4/7 change E2E fail → retry)
- **Megoldás**: Új `e2e_mode` directive: `per_change` (default, mai viselkedés) | `phase_end` (E2E futtatás phase végén, main-en)
- **Működés**: `phase_end` módban per-change verify = test+build only (~15-20s). Phase végén `run_phase_end_e2e()` az integrált kódon. Ha fail → context megy a replan-be (`_REPLAN_E2E_FAILURES`)
- **Érintett fájlok**: monitor.sh (directive parse + phase-end trigger), verifier.sh (run_phase_end_e2e func), planner.sh (E2E fail context injection), reporter.sh (phase-end E2E results section + e2e_mode display)
- **Státusz**: Implementálva, nem tesztelve élesben

### 20. Replan decomposition timeout (600s nem elég cycle 3-tól)
- **Tünet**: Cycle 3 replan 3x timeout-ol 600s-nél (attempt 1: 20:47→20:57, attempt 2: 20:58→21:08, attempt 3: 21:09→TBD)
- **Ok**: Cycle 3 replan prompt tartalmazza az összes eddigi completed change-t (12 merged) + coverage context + remaining 100+ REQ → nagyobb prompt mint cycle 2
- **Fix**: `RUN_CLAUDE_TIMEOUT=600` → `900` a planner decomposition-ben (planner.sh:1203)
- **Megjegyzés**: Cycle 2 pont beleférte a 600s-be (~6 perc), de cycle 3 már nem. A timeout növelés nem hot-reload-ból jön, orchestrator restart kell.
- **Státusz**: Fixelve (900s), de a futó orchestrator még a régi 600s-sel dolgozik

### 21. Digest JSON parse failure during replan — blocks phase 5
- **Tünet**: Replan cycle 5 digest re-generation 3x failed: `ERROR: Could not parse digest JSON`
- **Ok**: Auto-re-digest triggerelődik (stale hash), de a Claude digest response nem valid JSON → parse fail → replan fail → retry → same fail
- **Hatás**: Phase 5 nem indul el. Phase 4 viszont 7/8 merged, tehát a futás sikeres.
- **Megjegyzés**: A digest hash ugyanaz (`b386afee...`) mint a sikeres run-ban, de a re-generálás mégis fail. Valószínűleg a digest prompt a replan contextben más (több completed change info), és a Claude response formátuma eltér.
- **Lehetséges fix**: (1) Digest JSON parse robusztusabbá tétele (toleráns parser), (2) Ha a hash nem változott, ne re-digest-áljon, (3) Fallback: használja a régi digest-et ha re-generation fail
- **Státusz**: Finding, nem fixelve

### Phase 4 Final Report (Run #2 continuation)

| Change | REQs | Status | Retries | Notes |
|--------|------|--------|---------|-------|
| email-infrastructure | S | **merged** | E2E 1x | Build-first verify OK |
| user-profile-password | S | **merged** | E2E 1x (Ralph) | Ralph self-healed |
| promotions-coupon-logic | S | **merged** | Build 1x → stall → **watchdog redispatch** | First successful redispatch! |
| promotions-giftcard-promoday | S | **merged** | E2E 1x (Ralph) | Ralph self-healed |
| welcome-password-reset-emails | S | **merged** | Build 1x (Ralph) | Ralph self-healed |
| cart-coupon-giftcard-ui | S | **merged** | Build 1x (Ralph) | Ralph self-healed |
| cart-shipping-display | S | **merged** | 0 | Clean pass, no retry |
| promo-day-banner-and-seed | S | **FAILED** | Build+E2E 2x | E2E fail permanent |

**Phase 4 metrics:**
- Wall clock: ~1h40m (22:00→23:40)
- Changes merged: 7/8 (87.5%)
- Changes failed: 1/8 (promo-day E2E)
- Merge-blocked: 0
- Sentinel interventions: 0
- Verify gate: 480s across 6 changes (7% of active time)
- Total retries: 10 (+141k tokens)
- Watchdog redispatch: 1 (successful — promotions-coupon-logic)

**New features validated:**
- Build-first verify gate order (build→test→E2E) — catches errors early
- Watchdog redispatch — recovered stalled change successfully
- max_parallel=4 via orchestration.yaml config — works with directive hierarchy
- 1800s planner timeout — cycle 4 decomposition succeeded (~3 min)
- Post-merge sync — running worktrees auto-synced after each merge

### Observations (Run #2)
- Granularity rules működnek: 8 change, mind ≤6 REQ
- Sub-domain dependency chaining működik: product-catalog chain (list→detail→filter→search), user chain (auth→profile→addresses)
- Watchdog throttle működik: 7 WARN event (vs Run #1: 66+)
- content-stories merged 2 retry után — small change (4 REQ) végül átment
- user-auth fail nem granularity probléma — runtime bug (Next.js logout crash)
- **Dependency deadlock** a legfontosabb bug: failed dependency→stuck pending→no replan. Fixelni kell.
- **Build-first verify** bevált: minden phase 4 change build-del kezd, ha fail → sync with main → retry, ha main OK de branch fail → agent code issue → Ralph retry
- **Watchdog redispatch** élesben először működött: coupon-logic stall → 10 perc cooldown → fresh worktree → success
- **Digest re-generation fragilis**: replan-nél 3/3 attempt fail digest JSON parse error-rel

## Observations
- Sentinel auto-restart működik: digest crash → restart → digest fresh (skip) → planner újra
- Sentinel events fájlnév mismatch BLOKKOLÓ volt — stuck detection killed healthy orchestrator after 183s
- `set-project init` → `.claude/` deploy teljesen automatikus és gyors
- Digest mode plan: 7 change 1. fázisban, 120/178 req uncovered → auto-replan fog kelleni
- max_parallel: 2 de az első change-nek nincs dependency → azonnal indul
- A digest "fresh" check működik sentinel restart-oknál — nem generálja újra
- Sentinel stale state recovery működik: kill -9 → stale detect → reset → restart (~33s)
- Ha sentinel fut, manuális orchestrator start ütközik ("already running")
- 5-7 REQ/change a sweet spot: gyors, megbízható, 0 retry
- 14+ REQ/change nem működik: verify gate nem teljesíthető 3 próbálkozásra
- Orchestrator resume nem kezeli a hiányzó worktree-t gracefully (crash helyett re-dispatch kéne)
