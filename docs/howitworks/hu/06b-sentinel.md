# A Sentinel

## Miért kell felügyelő a felügyelőnek?

Az orchestrátor maga is egy process — és a processek néha meghalnak. OOM kill, API timeout, váratlan exception, broken pipe. Ha az orchestrátor éjszaka, felügyelet nélkül fut és leáll, reggel egy félkész állapotot talál a fejlesztő.

A `set-sentinel` erre a problémára ad választ: egy supervisor, amely figyeli az orchestrátort, és ha az leáll, megpróbálja újraindítani. Két üzemmódban működik: **bash mód** (költségmentes, determinisztikus) és **ágens mód** (LLM-alapú, intelligens döntéshozatal).

## Bash Sentinel

A bash sentinel egy önálló script, amely a `set-orchestrate start` parancsot csomagolja:

```bash
set-sentinel --spec docs/v3.md --time-limit 5h
# ↑ minden opció az orchestrátornak adódik tovább
```

### Crash Recovery exponenciális backoff-fal

Ha az orchestrátor leáll, a sentinel nem azonnal indítja újra — exponenciális backoff-fal vár:

```
Crash 1: vár 30s  (+ 0-25% jitter)
Crash 2: vár 60s
Crash 3: vár 120s
Crash 4: vár 240s (maximum)
Crash 5: feladja → SENTINEL_FAILED event
```

Ha az orchestrátor legalább 5 percig futott (sustained run), a számláló és a backoff alaphelyzetbe áll. Ez megkülönbözteti az indítási hibákat (konfigurációs probléma, ami mindig azonnal megöli) a futásidejű crashektől (API timeout, ami egyszer fordul elő és utána rendben megy).

### Élőség-detekció

A sentinel nem a logot elemzi — az events fájl módosítási idejét (mtime) figyeli:

```
Orchestrátor → WATCHDOG_HEARTBEAT (15s-enként) → events.jsonl mtime frissül
Sentinel → pollolja az mtime-ot (10s-enként)
  → Ha >180s óta nem változott → az orchestrátor beragadt
  → SIGTERM → 30s várakozás → ha kell, SIGKILL → újraindítás
```

A `WATCHDOG_HEARTBEAT` eseményt a monitor loop minden ciklusban kibocsátja. Ha ez elmarad 3 percnél tovább, a sentinel beavatkozik.

### Állapot-helyreállítás

Minden újraindítás előtt a sentinel megpróbálja javítani az állapotot:

1. **Event-alapú rekonstrukció**: Ha az `orchestration-state.json` régebbi, mint az events log, a sentinel az események visszajátszásából rekonstruálja az állapotot — melyik change hol tartott, mennyi tokent használt
2. **Halott PID detekció**: A `running` státuszú change-ek PID-jét ellenőrzi. Ha a process már nem él, a change `stalled` státuszba kerül (a watchdog fog foglalkozni vele)
3. **Állapot normalizálás**: Ha az orchestrátor státusza `running` de nincs process, `stopped`-ra állítja

### Kilépési osztályozás

A sentinel különbséget tesz **végleges** és **átmeneti** kilépés között:

| Állapot | Kategória | Sentinel művelete |
|---------|-----------|-------------------|
| `done` | Végleges | Leáll, nem indít újra |
| `stopped` | Végleges | Leáll |
| `time_limit` | Végleges | Leáll |
| `plan_review` | Végleges | Leáll (emberi döntés kell) |
| Bármilyen crash | Átmeneti | Újraindít backoff-fal |

## Ágens Sentinel

A `/set:sentinel` skill egy Claude Code session-ként fut, és intelligens döntéseket hoz:

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

\begin{fontos}
A sentinel kettős védelmet biztosít: a bash sentinel költségmentesen figyeli a process-t és automatikusan újraindít, míg az ágens sentinel LLM-mel analizálja a helyzetet és intelligens döntéseket hoz. Éles futtatásoknál a bash sentinel az alap; az ágens sentinel opcionális, E2E teszteléshez és fejlesztéshez hasznos.
\end{fontos}

## Sentinel események

A sentinel közvetlenül ír az events JSONL-be (nem függ az `events.sh` modultól):

| Esemény | Jelentés |
|---------|---------|
| `SENTINEL_RESTART` | Orchestrátor leállt, újraindítás (exit code, backoff, crash count) |
| `SENTINEL_FAILED` | 5 rapid crash, a sentinel feladta |
| `STATE_RECONSTRUCTED` | Állapot rekonstruálva events-ből |
