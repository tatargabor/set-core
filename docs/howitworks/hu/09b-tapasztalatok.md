# Tapasztalatok és kihívások

## Megoldott problémák

Az alábbiak éles orchestrációs futtatások során derültek ki — jellemzően az első néhány production run (sales-raketa, MiniShop, CraftBrew) tanulságai.

### Token budget kalibráció

**Probléma**: Az eredeti budget tierek (S=500K, M=2M) túl alacsonyak voltak. Az artifact-generálási overhead (proposal → design → specs → tasks) már 500K-800K tokent igényel, mielőtt az implementáció elkezdődne.

**Megoldás**: Kalibrálás éles adatokból: S=2M, M=5M, L=10M. Az éles futtatások visszaigazolták: egy tipikus S change 1.3-1.5M tokent használ (artifact overhead-del együtt).

### Watchdog spam

**Probléma**: A watchdog 15 másodpercenként emittált `WATCHDOG_WARN` eseményeket — egy lassú change-nél 60+ bejegyzés az event log-ban, ami rontotta a sentinel élőség-detekciót és felfújta a napló méretét.

**Megoldás**: Throttle az event emissziónál: csak minden 20. előfordulásnál ír a naplóba.

### Sentinel fájlnév eltérés

**Probléma**: A sentinel a `orchestration-events.jsonl` fájlt figyelte (hardcoded), de az orchestrátor `orchestration-state-events.jsonl`-be írt (dinamikus név). Eredmény: a sentinel 180 másodperc után megölte az egészséges orchestrátort.

**Megoldás**: A sentinel a state fájlnévből származtatja az events fájlnevet, nem hardcode-olja.

### Token tracking félrevezető adatok

**Probléma**: A cache tokenek beleszámítottak a budget-be, de nem jelentek meg a tracking-ben — 18x eltérés a kijelzett és a tényleges fogyasztás között.

**Megoldás**: Cache tokenek bevétele a tracking-be.

### Nagy change-ek megbízhatósága

**Probléma**: 14+ requirement egy change-ben → 40+ perc, 3 verify retry → failed. Az ok: a kontextus ablak nem elég nagy, az ágens elveszíti a fonalat.

**Megoldás**: A planner max 6 REQ/change szabályt alkalmaz. 4-6 requirement-es change-ek megbízhatóan futnak (12-19 perc, 0 retry).

### Jest + Playwright ütközés

**Probléma**: A Jest unit tesztek crash-eltek a Playwright `.spec.ts` fájlokon ("TypeError: Class extends value undefined"), mert a jsdom nem kezeli a browser importokat.

**Megoldás**: `testPathIgnorePatterns` a jest config-ban + worktree-nkénti port izoláció a Playwright tesztekhez.

## Ismert limitációk

### Mock-alapú tesztek elrejtik a runtime hibákat

**Probléma**: A Jest tesztek mock-olják a Next.js API-kat (`cookies()`, `headers()`), így a runtime hibákat nem kapják el. A MiniShop futtatásban 81 Jest teszt zöld volt, miközben az alkalmazás 3 kritikus runtime hibával rendelkezett (auth bypass, cookie crash, dead link).

**Tanulság**: A smoke test (`pnpm build && pnpm test`) és az E2E teszt (`Playwright`) együtt szükséges. A build elkapja a type hibákat, az E2E a funkcionális regressziókat.

### Megosztott erőforrások merge konfliktusa

**Probléma**: Párhuzamos change-ek ugyanazt a fájlt módosítják (pl. `functional-conventions.md`, layout komponensek). Az LLM merge 900+ soros konfliktust nem tud feloldani.

**Jövő**: A planner-nek fel kellene ismernie a cross-cutting fájlokat és sorrendbe állítani a change-eket, nem párhuzamosítani.

### Kontextusvesztés merge után

**Probléma**: Schema változás merge után: a worktree-ben a kód típushelyesen fordult, de a main-en (ahol más change-ek is megváltoztatták a schemát) TypeScript hiba keletkezett.

**Tanulság**: A post-merge build ellenőrzés (`base build health check`) nélkülözhetetlen.

### Memória nem garantálja a minőséget

**Probléma**: A benchmark futtatások kimutatták, hogy a memóriával rendelkező ágensek 50%-kal kevesebbet kutatnak, de alacsonyabb minőségű kódot adnak — a memória "shortcut"-ot biztosít, ami megkerüli a szükséges kód-olvasást.

**Tanulság**: "Recall-then-verify" minta: a memória lekérdezés után mindig ellenőrizni kell a kódbázis aktuális állapotát.

## Ami még hátra van

### Cascade failure logika

Ha egy change elbukik, a függő change-ek jelenleg örökre pending-ben maradnak. Szükséges: automatikus cascade failure propagálás, amely a függő change-eket `skipped` státuszba állítja.

### Trend-alapú token budget

A statikus budget limetek (S=2M, M=5M) nem skálázódnak minden projektre. Szükséges: projekt-szintű tanulás az aktuális token-fogyasztásból, automatikus limit-igazítás.

### Ágens-pontozás dispatch-hoz

Jelenleg a dispatch round-robin módon történik. Szükséges: ágensek pontozása hibaráta, token-hatékonyság és iteráció/haladás arány alapján — a jobb ágensek több feladatot kapnak.

### Circuit breaker API hívásokhoz

Egymás utáni API hibák esetén a rendszer nem áll le, hanem továbbra is próbálkozik. Szükséges: circuit breaker pattern, amely N egymást követő hiba után leáll.

\begin{fontos}
Az orchestráció értéke a második futtatástól kezdve jelentkezik igazán. Az első futtatás mindig felfed problémákat — rossz budget, hiányzó teszt konfiguráció, váratlan merge konfliktus. A lényeg: minden hiba egyszer fordul elő, mert a rendszer tanul belőle (watchdog tuning, budget kalibráció, planner szabályok).
\end{fontos}
