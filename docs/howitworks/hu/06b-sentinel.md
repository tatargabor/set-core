# A Sentinel

## Miért kell felügyelő a felügyelőnek?

Az orchestrátor maga is egy process — és a processek néha meghalnak. OOM kill, API timeout, váratlan exception, broken pipe. Ha az orchestrátor éjszaka, felügyelet nélkül fut és leáll, reggel egy félkész állapotot talál a fejlesztő.

A sentinel erre a problémára ad választ: egy Claude ágens, amely figyeli az orchestrátort, és ha az leáll, elemzi a helyzetet és eldönti hogyan tovább. A **web UI**-ból indítható ("Start Sentinel" gomb) vagy a `/set:sentinel` skill-lel.

Nem-interaktív használathoz (CI, scriptek) a `set-orchestrate start` közvetlenül futtatja az orchestrátort, sentinel felügyelet nélkül.

## Hogyan működik

A sentinel egy Claude Code session-ként fut (a `supervisor.py`-n keresztül), amely 30 másodpercenként pollolja az orchestráció állapotát és intelligens döntéseket hoz:

### Tiered beavatkozás

Az ágens sentinel a következő elv alapján működik: **ne avatkozz bele az orchestráció szintű problémákba** — az orchestrátornak van beépített recovery-je.

| Tier | Mikor | Példák |
|------|-------|--------|
| **Tier 1 — Nem avatkozik** | Orchestráció szintű probléma | merge-blocked, test fail, verify retry, replan |
| **Tier 2 — Beavatkozik** | Process szintű probléma | Crash, hang, terminális állapot, checkpoint |

Merge conflict? Az orchestrátor 3-rétegű conflict resolution-nel kezeli. Test failure? Az orchestrátor retry-olja. Egyedi change elbukott? Az orchestrátor folytatja a többivel. Az ágens sentinel csak akkor lép közbe, amikor az orchestrátor processze maga akad el.

### Checkpoint kezelés

- **Periodikus checkpoint** (N merge után): automatikus jóváhagyás
- **Budget checkpoint** (token hard limit): escalate a felhasználóhoz
- **Egyéb checkpoint**: felhasználói döntés kell

### Autonómia szabályok

A sentinel speciális szabálykészlettel dolgozik:

- **Soha ne kérdezz mielőtt javítanál** — ha bug van, javítsd, commitold, indítsd újra
- **Soha ne kérdezz mielőtt újraindítanál** — crash után cleanup és restart, megerősítés nélkül
- **A polling soha ne álljon le magától** — fix után folytasd, restart után folytasd, context compact után folytasd

### Segédeszközök

A sentinel CLI segédprogramokat használ a rendszerrel való interakcióhoz:

| Eszköz | Cél |
|--------|-----|
| `set-sentinel-finding` | Bugok, minták és értékelések logolása a futtatás során |
| `set-sentinel-inbox` | Felhasználói vagy más ágensek üzeneteinek ellenőrzése |
| `set-sentinel-log` | Strukturált eseménynaplózás |
| `set-sentinel-status` | Sentinel státusz regisztráció a web UI-hoz |

\begin{fontos}
A sentinel intelligens felügyeletet biztosít: LLM-mel elemzi az orchestrátor állapotát és döntéseket hoz crashek, hangok és checkpointok esetén. Egyszerű nem-interaktív futtatásokhoz a `set-orchestrate start` elég — az orchestrátornak van beépített crash recovery-je az egyedi change-ekhez.
\end{fontos}

## Sentinel események

A sentinel az events JSONL-be ír:

| Esemény | Jelentés |
|---------|---------|
| `SENTINEL_RESTART` | Orchestrátor leállt, újraindítás (exit code, ok) |
| `SENTINEL_FAILED` | Többszörös rapid crash, a sentinel feladta |
| `STATE_RECONSTRUCTED` | Állapot rekonstruálva events-ből |
