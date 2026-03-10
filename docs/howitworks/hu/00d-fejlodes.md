# Fejlődéstörténet

## Négy hét alatt a specifikációtól az autonóm orchestrációig

A `wt-tools` fejlesztése 2026. február 10-én indult. Négy hét alatt a projekt egy egyszerű worktree-kezelőből egy teljes autonóm orchestrációs keretrendszerré nőtte ki magát. Ez a fejezet bemutatja a főbb mérföldköveket és a fejlődés ívét.

## 1. hét — Alapok (feb. 10-16.)

**Worktree menedzsment és ágens-felügyelet.**

Az első hét a "hogyan futtassunk több Claude Code ágenst párhuzamosan" kérdéssel foglalkozott. A válasz: git worktree-k — minden ágens saját branch-en, saját könyvtárban dolgozik, és a merge a végén történik.

Elkészült:

- `wt-new` — worktree létrehozás és inicializálás
- `wt-list`, `wt-status` — ágensek állapotának nyomon követése
- `wt-merge` — worktree merge main-be
- `wt-close` — worktree cleanup
- `wt-loop` ("Ralph") — iteratív ágens ciklus, automatikus újraindítás

A "Ralph loop" nevet a belső fejlesztés során kapta: egy ágens, aki újra és újra nekifut a feladatnak, amíg kész nem lesz — mint egy kitartó kolléga.

## 2. hét — Orchestráció és OpenSpec (feb. 17-23.)

**A kézi koordináció automatizálása.**

A második héten lett nyilvánvaló, hogy a worktree-k kézi kezelése nem skálázódik. Ha 10 feature-t kell párhuzamosan fejleszteni, kell valami, ami:

- Megtervezi a sorrendet (mi függ mitől)
- Elindítja az ágenseket (dispatch)
- Figyeli őket (monitor)
- Összefésüli az eredményt (merge)

Elkészült:

- `wt-orchestrate` — a teljes orchestrációs pipeline első verziója
- Plan generálás brief-ből → DAG → dispatch → monitor loop
- Topológiai rendezés és párhuzamos dispatch
- Checkpoint-alapú merge policy
- OpenSpec integráció — strukturált proposal/design/tasks workflow

## 3. hét — Minőség és megbízhatóság (feb. 24. – márc. 2.)

**A "működik, de néha elromlik" fázisból a "megbízható" fázisba.**

A harmadik hét az éles futtatások tanulságaiból dolgozott. Az első production run-ok (sales-raketa projekt) feltárták:

- Az ágensek néha elakadnak → **Watchdog rendszer** (4-szintű eszkaláció)
- A merge néha konfliktusba fut → **LLM conflict resolution** (3-rétegű)
- A tesztek néha nem futnak → **Verify pipeline** (test → review → smoke)
- A token fogyasztás néha elszáll → **Budget kontroll** (soft + hard limit)

Elkészült:

- Watchdog: stall detekció, hash loop felismerés, eszkaláció L1→L4
- Verify pipeline: test gate, code review gate, smoke test
- Token tracking: per-change + összesített számlálók
- Email notifikáció (Resend integráció)
- `wt-sentinel` — az orchestrátor felügyelője (crash recovery)

## 4. hét — Digest, coverage, és öngyógyulás (márc. 3-10.)

**A spec megértésétől a követelmény-nyomkövetésig.**

A negyedik hét hozta el a "professzionális" szintet: a rendszer már nem csak végrehajtja a feladatokat, hanem *érti* a specifikációt.

Elkészült:

- **Spec digest pipeline** — multi-file specifikációk strukturált feldolgozása, REQ-XXX azonosítók
- **Ambiguity triage** — kétértelmű pontok automatikus felismerése, emberi döntéshozatal
- **Requirement coverage** — nyomon követés, hogy minden követelmény le van-e fedve
- **Cascade failure** — ha egy függőség elbukik, az arra épülő feladatok is leállnak
- **Watchdog redispatch** — elakadt change teljes újraépítése friss worktree-ben
- **Phase-end E2E** — Playwright tesztek a fázis végén, screenshot galériával
- **HTML riport generálás** — részletes futási összefoglaló, coverage mátrix

## Az érés

A fejlődés nem lineáris volt, hanem exponenciális: minden hét az előző tanulságaira épült. Az első héten 5 percig futott a rendszer felügyelet nélkül. A negyedik héten már 5 órát is kibírt — éjszaka, alvás közben, production kódbázisokon.

```
Hét 1: wt-new + wt-merge      → "kézi multi-ágens"
Hét 2: orchestrate + plan      → "automatikus koordináció"
Hét 3: watchdog + verify       → "megbízható automatizálás"
Hét 4: digest + coverage       → "intelligens orchestráció"
```

\begin{fontos}
A legfontosabb tanulság: egy orchestrációs rendszer értéke nem a "happy path" kezelésében van — azt bárki megcsinálja. Az érték a hibakezelésben, a recovery-ben, és az eszkalációban van. A rendszer 80\%-a azzal foglalkozik, ami elromolhat.
\end{fontos}
