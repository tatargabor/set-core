# Replan és Coverage

## Auto-Replan

Az auto-replan a többfázisú specifikációk kezelésére szolgál. Ha az összes change egy fázisban befejeződött, a rendszer automatikusan megtervezi és elindítja a következő fázist.

### Aktiválás

```yaml
auto_replan: true
```

### Folyamat

1. A monitor loop észleli, hogy minden change `merged` vagy `failed`
2. Ha `auto_replan: true` → `cmd_replan()` hívás
3. A planner megkapja a frissített specifikációt + a kész fázisok listáját
4. Új plan generálódik a következő fázisra
5. A korábbi token számlálók mentésre kerülnek (`prev_total_tokens`)
6. Az állapot resetelődik az új plan-nel
7. A monitor loop folytatja a végrehajtást

### Retry logika

Ha a replan sikertelen (pl. az LLM nem tud jó plan-t generálni):

- Max `MAX_REPLAN_RETRIES` (3) egymás utáni próbálkozás
- Sikertelen replan → figyelmeztetés + várakozás a következő poll-ra
- Ha 3-szor is sikertelen → az orchestrátor megáll

### All-done detekció

Az orchestrátor "kész"-nek tekinti a futást, ha:

1. Nincs `pending` vagy `running` change
2. Nincs merge queue elem
3. `auto_replan` false VAGY a replan "nincs több fázis"-t jelent

```
Fázis 1: [A, B, C] → merged → replan
Fázis 2: [D, E]    → merged → replan
Fázis 3: nincs több → done
```

## Manuális Replan

A felhasználó bármikor kérhet replant:

```bash
set-orchestrate replan
```

Ez hasznos, ha:

- A specifikáció megváltozott futás közben
- A felhasználó új feladatokat adott hozzá
- Néhány change failed és új megközelítés szükséges

A manuális replan:

1. Megőrzi a `merged` change-ek állapotát
2. Figyelembe veszi a `failed` change-eket
3. Csak az új/módosított feladatokra generál change-eket

## Requirement Coverage

A coverage rendszer a digest-ből származó REQ-XXX azonosítókon alapul. Célja: biztosítani, hogy a specifikáció minden követelménye le legyen fedve implementációval.

### Coverage riport

```bash
set-orchestrate coverage
```

Kimenet:

```
━━━ Requirement Coverage ━━━

Coverage: 12/15 (80.0%)

Status breakdown:
  ✓ merged:     8
  ◐ running:    3
  ○ pending:    1
  ✗ failed:     1
  · unassigned: 2

Details:
  REQ-001  ✓  JWT autentikáció          → auth-system (merged)
  REQ-002  ✓  User profil               → user-profile (merged)
  REQ-003  ◐  Avatar feltöltés          → user-profile (running)
  REQ-004  ✓  Token refresh             → auth-system (merged)
  ...
  REQ-014  ·  Admin audit log           → (not assigned)
  REQ-015  ·  Export funkció            → (not assigned)
```

### Coverage tracking lifecycle

```
Plan generálás:
  change.requirements = ["REQ-001", "REQ-004"]
  → populate_coverage() → coverage state init

Change végrehajtás közben:
  status = "running" → REQ-001 status = "running"

Change merge:
  update_coverage_status("auth-system", "merged")
  → REQ-001 status = "merged"
  → REQ-004 status = "merged"

Change failed:
  → REQ-XXX status = "failed"
  → check_coverage_gaps(): figyelmeztetés

Replan:
  A gap-ek (unassigned, failed) bekerülnek a planner prompt-ba
```

### Coverage gap detekció

A `check_coverage_gaps()` figyeli:

- **Unassigned**: Egy REQ-XXX-hez nincs change rendelve
- **Failed**: A change, amelyhez a requirement tartozik, elbukott
- **Orphaned**: A requirement a digest-ben van, de a plan-ből hiányzik

Ezeket a gap-eket a replan figyelembe veszi és új change-eket generál rájuk.

### Cross-cutting követelmények

Egyes követelmények több change-et is érinthetnek. Az `also_affects_reqs` mező ezt jelzi:

```json
{
  "name": "api-endpoints",
  "requirements": ["REQ-005"],
  "also_affects_reqs": ["REQ-012"]
}
```

REQ-012 (pl. "Logging") nem az `api-endpoints` fő feladata, de érintett. A review gate ezt figyelembe veszi az értékelésben.

## Final Coverage Check

A futás végén (done, time-limit) a `final_coverage_check()` egy összesítő riportot generál:

```
Final Coverage: 14/15 (93.3%)
  Uncovered: REQ-015 (Export funkció)
```

Ez az összegzés bekerül:

- A summary email-be
- A HTML riportba
- Az orchestration-summary.md fájlba

\begin{fontos}
A coverage tracking nem garancia a helyes implementációra — csak azt jelzi, hogy egy change "megpróbálta" lefedni a követelményt. A tényleges minőséget a verify és review gate-ek biztosítják. A coverage rendszer fő értéke: a replan nem felejt el semmit a specifikációból.
\end{fontos}

## Összefoglaló riportok

### HTML riport

A `generate_report()` (a `reporter.sh`-ban) egy részletes HTML riportot generál:

- Change-enkénti összefoglaló (státusz, token használat, idő)
- Coverage mátrix
- Gate statisztikák (pass/fail arányok)
- Timeline vizualizáció

### Summary email

Ha email notifikáció konfigurálva van, a futás végén összegző email küldése:

- Futási idő (aktív és fali)
- Change eredmények
- Coverage összefoglaló
- Következő lépések (ha replan aktív)

### orchestration-summary.md

Ember által olvasható markdown összefoglaló, amely a futás végén generálódik.
