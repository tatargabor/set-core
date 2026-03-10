# Monitor és Watchdog

## A Monitor Loop

Az orchestrátor szíve a `monitor_loop()` függvény, amely a `start` parancs kiadása után végtelenül fut. Feladata: 15 másodpercenként ellenőrizni az összes aktív change állapotát, és a megfelelő műveletet végrehajtani.

![A monitor loop ciklusa](diagrams/rendered/05-monitor-loop.png){width=90%}

### A poll ciklus

Minden 15 másodperces ciklusban a következők történnek:

1. **Állapot ellenőrzés**: Az orchestrátor státuszának (running/paused/stopped) vizsgálata
2. **Aktív change-ek pollozása**: `poll_change()` hívás minden `running` és `verifying` change-re
3. **Watchdog ellenőrzés**: `watchdog_check()` hívás stall detekció céljából
4. **Felfüggesztett change-ek**: Ellenőrzés, hogy a `paused` vagy `budget_exceeded` change-ek befejeztek-e
5. **Token budget**: Soft és hard limit ellenőrzés
6. **Verify-failed recovery**: Újrapróbálás, ha a retry limit engedi
7. **Dispatch**: Új change-ek indítása, ha van szabad slot
8. **Merge queue**: Merge sor feldolgozása
9. **Stall recovery**: Elakadt change-ek újraindítása
10. **Cascade failure**: Sikertelen függőségek propagálása
11. **Replan**: Ha minden kész és `auto_replan` aktív, következő fázis

### poll_change()

A `poll_change()` a legfontosabb függvény. Egy change esetén:

- Olvassa a `loop-state.json` fájlt a worktree-ből
- Frissíti a token számlálókat az állapotfájlban
- Ha `status == "done"` → elindítja a verify pipeline-t (teszt → review → verify → smoke → E2E)
- Ha `status == "error"` → retry vagy fail

### Active time tracking

A monitor nem a faliórát méri, hanem az **aktív időt**:

- Csak akkor számol, ha legalább egy Ralph loop fut (`any_loop_active()`)
- Token budget várakozás alatt nem számlál
- Pause alatt nem számlál
- Az aktív idő restart-ok között is kumulálódik

```
Fali idő:    |████████░░████████░░░░████████|  3 óra
Aktív idő:   |████████  ████████    ████████|  2 óra
              ^futás    ^pause      ^futás
```

## A Watchdog rendszer

A watchdog feladata a "ragadt" change-ek detektálása és kezelése. Minden aktív change-nek saját watchdog állapota van.

![A watchdog eszkalációs szintjei](diagrams/rendered/06-watchdog-escalation.png){width=90%}

### Detekciós mechanizmusok

#### 1. Timeout detekció

Státuszonként eltérő timeout:

| Státusz | Alapértelmezett timeout | Leírás |
|---------|------------------------|--------|
| `running` | 600s (10 perc) | Implementáció futás közben |
| `verifying` | 300s (5 perc) | Verify pipeline futás közben |
| `dispatched` | 120s (2 perc) | Dispatch után, Ralph indulás előtt |

Ha az utolsó aktivitás óta több idő telt el, mint a timeout, az eszkaláció elindul.

#### 2. Action hash loop detekció

A watchdog egy "hash ring"-et tart karban minden change-hez:

```json
{
  "action_hash_ring": ["abc123", "abc123", "abc123", "abc123", "abc123"],
  "consecutive_same_hash": 5
}
```

Az action hash a `loop-state.json` kulcs mezőiből (iteráció szám, token szám, státusz) képződik. Ha egymás után N alkalommal (alapértelmezés: 5) ugyanaz a hash → az ágens elakadt.

#### 3. Artifact creation grace period

A dispatch és a Ralph loop indulása között van egy "grace period": az ágens ilyenkor OpenSpec artifact-okat hoz létre (proposal, design, specs, tasks), és még nincs `loop-state.json`. A watchdog ezt felismeri és nem eszkalál.

### Eszkalációs szintek

| Szint | Művelet | Leírás |
|-------|---------|--------|
| **L1** | Figyelmeztetés | Log bejegyzés + notification. Nincs beavatkozás. |
| **L2** | Újraindítás | A Ralph loop leállítása és újraindítása. Context pruning aktiválódik. |
| **L3** | Redispatch | A teljes worktree újraépítése. Max `max_redispatch` (alapértelmezés: 2) alkalommal. |
| **L4** | Feladás | A change `failed` státuszba kerül. Notification küldése. |

Az eszkalációs szintek fokozatos beavatkozást jelentenek. Az L1 csak figyel — hátha az ágens magától megoldja a problémát (pl. hosszú build futás). Az L2 újraindítja a loop-ot friss context-tel — ez a leggyakoribb helyreállítás, kb. 70%-ban sikeres. Az L3 mindent elölről kezd: friss worktree, friss branch, teljes újradispatch — drága, de ha az L2 nem segít, ez az utolsó esély. Az L4 feladja a harcot: jobb egy change-et elveszíteni, mint végtelen tokeneket égetni.

### Recovery detekció

Ha egy eszkalált change újra aktivitást mutat (pl. L2 újraindítás után a hash megváltozik), az eszkaláció **automatikusan resetelődik**:

```
L2 (restart) → aktivitás detektálva → level reset → L0
```

\begin{fontos}
A watchdog az egyetlen biztonsági háló, amely megakadályozza, hogy egy elakadt ágens végtelen ideig fogyassza a tokeneket. Éles futtatásnál a watchdog\_timeout és max\_redispatch értékeket a projekt jellegéhez kell igazítani.
\end{fontos}

## Token biztonsági hálók

A monitor loop két szintű token védelmet biztosít:

### Soft limit (`token_budget`)

Ha az összes change token használata meghaladja a `token_budget` értéket:

- A futó loop-ok befejezhetik az aktuális iterációt
- Új change-ek **nem** indulnak
- Amint a budget alá kerül a használat, a dispatch újraindul

### Hard limit (`token_hard_limit`)

Ha az összes token (beleértve a korábbi replan ciklusokat is) eléri a hard limitet:

- **Checkpoint** aktiválódik: az orchestrátor megáll
- Emberi jóváhagyás szükséges a folytatáshoz
- Jóváhagyás után a limit feljebb tolódik

```bash
wt-orchestrate approve   # jóváhagyás, folytatás
```

## Időlimit

A `time_limit` direktíva (alapértelmezés: 5 óra) az **aktív** futási időt korlátozza:

```bash
wt-orchestrate --time-limit 4h start     # 4 óra limit
wt-orchestrate --time-limit none start   # nincs limit
```

Amikor a limit lejár:

1. Az állapot `time_limit`-re vált
2. Notification küldése
3. Summary email küldése
4. HTML riport generálás
5. A futás megáll, de a worktree-k megmaradnak

A futás folytatható: `wt-orchestrate start` — a timer ott folytatódik, ahol abbahagyta.

## Memória és auditálás

A monitor loop 10 pollásonként (~2.5 percenként) automatikusan:

- `orch_memory_stats()`: memória rendszer állapot
- `orch_gate_stats()`: gate statisztikák
- `orch_memory_audit()`: memória audit (duplikátum detekció)

Ez biztosítja, hogy a hosszú futások során a memória rendszer egészséges marad.
