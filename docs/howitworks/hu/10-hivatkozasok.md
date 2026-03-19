# Hivatkozások

## CLI Referencia

### set-orchestrate

A fő orchestrációs parancs.

```
set-orchestrate [globális opciók] <parancs> [parancs opciók]
```

#### Globális opciók

| Opció | Leírás |
|-------|--------|
| `--spec <path>` | Specifikáció fájl vagy könyvtár |
| `--brief <path>` | Brief fájl (legacy) |
| `--phase <hint>` | Fázis szűrő (--spec-hez) |
| `--max-parallel <N>` | Max párhuzamos override |
| `--time-limit <dur>` | Időlimit (pl. "4h", "2h30m", "none") |

#### Parancsok

| Parancs | Leírás |
|---------|--------|
| `plan [--show]` | Plan generálás vagy meglévő megjelenítés |
| `start` | Plan végrehajtás indítása |
| `status` | Aktuális állapot megjelenítés |
| `pause <name\|--all>` | Change vagy összes felfüggesztése |
| `resume <name\|--all>` | Change vagy összes folytatása |
| `replan` | Újratervezés frissített spec-ből |
| `approve [--merge]` | Checkpoint jóváhagyás |
| `digest --spec <path>` | Strukturált digest generálás |
| `coverage` | Requirement lefedettség riport |
| `specs [list\|show\|archive]` | Spec dokumentumok kezelése |
| `events [opts]` | Eseménynapló lekérdezés |
| `tui` | Terminál dashboard indítás |
| `self-test` | Belső tesztek futtatása |

### set-new / set-merge / set-loop

| Parancs | Leírás |
|---------|--------|
| `set-new <name>` | Új worktree és branch létrehozás |
| `set-merge <name> [--llm-resolve]` | Worktree merge main-be |
| `set-loop start [opts]` | Ralph loop indítás |
| `set-loop status` | Loop állapot lekérdezés |

## Change állapotgép

A change-ek a következő állapotok között mozognak az életciklusuk során:

![A change teljes állapotgépe](diagrams/rendered/09-change-lifecycle.png){width=95%}

### Állapotok

| Állapot | Leírás |
|---------|--------|
| `pending` | Várakozik dispatch-re (függőségek nem teljesültek) |
| `dispatched` | Worktree létrehozva, Ralph loop indítás alatt |
| `running` | Ralph loop aktív, fejlesztés folyamatban |
| `verifying` | Verify pipeline fut (test → review → verify → smoke) |
| `verify-failed` | Verify gate sikertelen, retry várakozik |
| `stalled` | Watchdog észlelte, hogy az ágens elakadt |
| `paused` | Manuálisan felfüggesztve |
| `waiting:budget` | Token budget limit miatt várakozik |
| `budget_exceeded` | Token budget meghaladva |
| `merge_queue` | Verify sikeres, merge-re vár |
| `merging` | Merge folyamatban |
| `merge_blocked` | Merge konfliktus, nem tudta feloldani |
| `merged` | Sikeresen merge-elve a fő ágba |
| `smoking` | Post-merge smoke test fut |
| `smoke_failed` | Smoke test sikertelen |
| `smoke_blocked` | Smoke fix retry limit elérve |
| `completed` | Minden gate sikeresen teljesítve |
| `failed` | Véglegesen sikertelen (retry limit elérve) |
| `skipped` | Kihagyva (függőség failed) |

### Főbb állapotátmenetek

```
pending → dispatched → running → verifying
  ↑                      ↕          ↓
  │                   stalled    merge_queue → merging → merged → completed
  │                      ↓          ↑
  │                   failed    verify-failed (→ running retry)
  │                                 ↓
  └── skipped (dependency failed)  failed (retry exhausted)
```

## Direktíva táblázat

A direktívák a rendszer viselkedését szabályozzák. Az alábbi táblázatok kategóriánként mutatják az összes elérhető beállítást. A legtöbb projekt az alapértelmezett értékekkel indul, és csak a tesztelési parancsokat (`test_command`, `smoke_command`) és a párhuzamossági szintet (`max_parallel`) állítja be. A többi direktíva finomhangolásra szolgál, amire jellemzően csak az első néhány futtatás tapasztalatai után van szükség.

### Végrehajtás

Ezek a direktívák a futtatás alapvető paramétereit határozzák meg: hány ágens dolgozzon egyszerre, hogyan történjen a merge, és meddig futhat a rendszer.

| Direktíva | Típus | Alapért. | Leírás |
|-----------|-------|----------|--------|
| `max_parallel` | szám | 3 | Max párhuzamos worktree |
| `merge_policy` | enum | checkpoint | eager / checkpoint / manual |
| `checkpoint_every` | szám | 3 | Checkpoint merge szám |
| `time_limit` | string | 5h | Aktív idő limit |
| `pause_on_exit` | bool | false | Pause ha orchestrátor leáll |
| `context_pruning` | bool | true | Context window optimalizálás |
| `model_routing` | string | off | Model routing stratégia |

### Modellek

Három modell-szint van: opus a nehéz munkához (implementáció), sonnet a gyorsabb feladatokhoz (review, egyszerű change-ek), haiku az összegzéshez. A model routing automatikusan választhat a change komplexitása alapján.

| Direktíva | Típus | Alapért. | Leírás |
|-----------|-------|----------|--------|
| `default_model` | string | opus | Implementáció model |
| `review_model` | string | sonnet | Review model |
| `summarize_model` | string | haiku | Összegzés model |

### Tesztelés

A tesztelési direktívák a minőségi gate-eket konfigurálják. A `test_command` a legfontosabb: ha üres, a teszt gate teljesen kimarad. A smoke és E2E tesztek opcionálisak, de éles futtatásnál erősen ajánlottak — a smoke elkapja a build hibákat, az E2E a funkcionális regressziókat.

| Direktíva | Típus | Alapért. | Leírás |
|-----------|-------|----------|--------|
| `test_command` | string | "" | Teszt parancs |
| `test_timeout` | szám | 300 | Teszt timeout (mp) |
| `smoke_command` | string | "" | Smoke test parancs |
| `smoke_timeout` | szám | 120 | Smoke timeout (mp) |
| `smoke_blocking` | bool | true | Smoke fail blokkol-e |
| `smoke_fix_token_budget` | szám | 500K | Smoke fix token limit |
| `smoke_fix_max_turns` | szám | 15 | Smoke fix max iteráció |
| `smoke_fix_max_retries` | szám | 3 | Smoke fix max retry |
| `smoke_health_check_url` | string | "" | Health check URL |
| `smoke_health_check_timeout` | szám | 30 | Health check timeout |
| `e2e_command` | string | "" | E2E test parancs |
| `e2e_timeout` | szám | 120 | E2E timeout (mp) |
| `e2e_mode` | enum | per_change | per_change / phase_end |

### Review és Verify

| Direktíva | Típus | Alapért. | Leírás |
|-----------|-------|----------|--------|
| `review_before_merge` | bool | false | LLM review gate |
| `max_verify_retries` | szám | 2 | Verify retry limit |

### Token kontroll

A token kontroll a költségek kezelésére szolgál. A soft limit (`token_budget`) figyelmeztet és lelassítja a dispatch-et, de a futó ágensek befejezhetik a munkájukat. A hard limit (`token_hard_limit`) megállítja a rendszert és emberi jóváhagyást kér — ez a végső biztonsági háló a váratlan token-fogyasztás ellen.

| Direktíva | Típus | Alapért. | Leírás |
|-----------|-------|----------|--------|
| `token_budget` | szám | 0 | Soft limit (0=ki) |
| `token_hard_limit` | szám | 20M | Hard limit |
| `checkpoint_auto_approve` | bool | false | Auto checkpoint approve |

### Tervezés

| Direktíva | Típus | Alapért. | Leírás |
|-----------|-------|----------|--------|
| `auto_replan` | bool | false | Auto-replan fázis végén |
| `plan_method` | enum | api | api / agent |
| `plan_token_budget` | szám | 500K | Agent plan budget |

### Watchdog

A watchdog az "éjszakai őr": akkor lép közbe, amikor az ágens elakad és magától nem tud továbblépni. A timeout értéket érdemes a projekt build idejéhez igazítani — ha a build 5 percet vesz igénybe, a 600s-os timeout helyes; ha 30 másodpercet, érdemes levinni 180s-ra.

| Direktíva | Típus | Alapért. | Leírás |
|-----------|-------|----------|--------|
| `watchdog_timeout` | szám | 600 | Stall timeout (mp) |
| `watchdog_loop_threshold` | szám | 5 | Loop detekció küszöb |
| `max_redispatch` | szám | 2 | Max redispatch próba |

### Hookak

A hookak lehetővé teszik, hogy a projekt-specifikus logika beépüljön a pipeline-ba. A `pre_merge` hook blokkoló: ha hibát dob, a merge nem történik meg. A többi hook nem blokkoló — ha hibáznak, a pipeline folytatódik. A `post_merge_command` a leggyakrabban használt hook: tipikusan adatbázis migrációs generálásra (Prisma, Drizzle) vagy build artifact frissítésre szolgál.

| Direktíva | Típus | Alapért. | Leírás |
|-----------|-------|----------|--------|
| `hook_pre_dispatch` | string | "" | Dispatch előtt |
| `hook_post_verify` | string | "" | Verify után |
| `hook_pre_merge` | string | "" | Merge előtt (blokkoló) |
| `hook_post_merge` | string | "" | Merge után |
| `hook_on_fail` | string | "" | Fail-kor |
| `post_merge_command` | string | "" | Post-merge parancs |

### Eseménynapló

| Direktíva | Típus | Alapért. | Leírás |
|-----------|-------|----------|--------|
| `events_log` | bool | true | Eseménynapló aktív-e |
| `events_max_size` | szám | 1MB | Max napló méret |

## Fájl struktúra referencia

### Projekt szintű fájlok

```
.claude/
├── orchestration.yaml          ← konfiguráció
└── orchestration.log           ← futási napló

wt/orchestration/
├── digest/
│   ├── requirements.json       ← REQ-XXX azonosítók
│   ├── phases.json             ← fázis struktúra
│   ├── digest-meta.json        ← hash, dátum
│   └── ambiguities.json        ← kétértelmű pontok
└── specs/
    ├── v12.md                  ← aktív spec-ek
    └── archive/
        └── v11.md              ← archivált spec-ek

orchestration-plan.json         ← aktuális plan (gitignore)
orchestration-state.json        ← futási állapot (gitignore)
orchestration-summary.md        ← összefoglaló (gitignore)
```

### Worktree szintű fájlok

```
.claude/worktrees/<change-name>/
├── .claude/
│   └── loop-state.json         ← Ralph loop állapot
├── openspec/changes/<name>/
│   ├── proposal.md             ← OpenSpec proposal
│   ├── design.md               ← tervezési dokumentum
│   └── tasks.md                ← feladatlista
└── ... (projekt fájlok)
```

### Eseménytípusok

| Esemény | Leírás |
|---------|--------|
| `STATE_CHANGE` | Change státusz változás |
| `DISPATCH` | Change dispatch |
| `MERGE_ATTEMPT` | Merge kísérlet |
| `MERGE_SUCCESS` | Sikeres merge |
| `MERGE_FAIL` | Sikertelen merge |
| `VERIFY_PASS` | Verify gate pass |
| `VERIFY_FAIL` | Verify gate fail |
| `TEST_PASS` / `TEST_FAIL` | Teszt eredmény |
| `SMOKE_PASS` / `SMOKE_FAIL` | Smoke teszt eredmény |
| `WATCHDOG_ESCALATE` | Watchdog eszkaláció |
| `CHECKPOINT` | Checkpoint aktiválás |
| `REPLAN` | Replan indítás |
| `DIGEST_STARTED` / `DIGEST_FAILED` | Digest események |

Az események a `.claude/orchestration.log` JSONL fájlba kerülnek, és a `set-orchestrate events` paranccsal lekérdezhetők:

```bash
set-orchestrate events --type MERGE_SUCCESS --last 10 --json
```
