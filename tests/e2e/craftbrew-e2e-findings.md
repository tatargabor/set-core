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
- Scaffold setup: ~5s (17 fájl copy, git init, wt-project init)
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
- Scaffold setup: ~5s (17 fájl copy, git init, wt-project init)
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
- **Tünet**: Manuális `wt-orchestrate start` → "Orchestrator is already running" → azonnali exit
- **Ok**: Az eredeti sentinel process (wt-sentinel) saját crash recovery-vel rendelkezik — kill -9 után 33s-en belül újraindít. Manuális restart felesleges és ütközik.
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

## Observations
- Sentinel auto-restart működik: digest crash → restart → digest fresh (skip) → planner újra
- Sentinel events fájlnév mismatch BLOKKOLÓ volt — stuck detection killed healthy orchestrator after 183s
- `wt-project init` → `.claude/` deploy teljesen automatikus és gyors
- Digest mode plan: 7 change 1. fázisban, 120/178 req uncovered → auto-replan fog kelleni
- max_parallel: 2 de az első change-nek nincs dependency → azonnal indul
- A digest "fresh" check működik sentinel restart-oknál — nem generálja újra
- Sentinel stale state recovery működik: kill -9 → stale detect → reset → restart (~33s)
- Ha sentinel fut, manuális orchestrator start ütközik ("already running")
