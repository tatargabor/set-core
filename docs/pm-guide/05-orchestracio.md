# Párhuzamos AI ágensek — Orchestráció

## Az ötlet

Az előző fejezetben láttuk, hogyan dolgozik egyetlen AI ágens egy feladaton: specifikáció → design → tasks → implementáció. De mi van, ha nem egy feladatod van, hanem tíz? Vagy húsz?

Gondolj egy valós projektre: egy webshop modernizálása. Kell bele:

- Felhasználói regisztráció átdolgozás
- Fizetési rendszer frissítés
- Email értesítések
- Admin felület
- API átírás
- Keresés javítás

Hagyományos módszerrel ez 6 fejlesztő, 6 hétnyi munka. **De mi lenne, ha 6 AI ágens dolgozna rajta egyszerre?**

Ez az orchestráció lényege.

## Git worktree-k — a párhuzamos munkaterületek

Mielőtt az orchestrációba merülnénk, meg kell érteni egy egyszerű fogalmat: **hogyan dolgozik több ágens egyszerre ugyanazon a projekten anélkül, hogy egymást zavarnák?**

A válasz: **git worktree-k** (munkafák). Gondolj rá úgy, mint párhuzamos munkaterületekre:

```
  Képzeld el, hogy van egy irodád (a projekt).
  De az irodának 5 különálló szobája van,
  mindben egy-egy fejlesztő dolgozik.

  ┌─────────────────────────────────────────────┐
  │                  Projekt                     │
  │                                              │
  │  ┌──────────┐  "szoba" = worktree           │
  │  │ Master   │  A fő verzió, ahova az        │
  │  │ (előtér) │  elkészült munka kerül        │
  │  └──────────┘                                │
  │                                              │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
  │  │ Szoba 1  │  │ Szoba 2  │  │ Szoba 3  │  │
  │  │ Ágens A  │  │ Ágens B  │  │ Ágens C  │  │
  │  │ regisztr.│  │ fizetés  │  │ email    │  │
  │  └──────────┘  └──────────┘  └──────────┘  │
  │                                              │
  │  ┌──────────┐  ┌──────────┐                 │
  │  │ Szoba 4  │  │ Szoba 5  │                 │
  │  │ Ágens D  │  │ Ágens E  │                 │
  │  │ admin    │  │ keresés  │                 │
  │  └──────────┘  └──────────┘                 │
  │                                              │
  │  Minden szobában a projekt egy másolata,     │
  │  de mindenki a saját változtatásain dolgozik.│
  │  Amikor kész, a változtatások beolvadnak     │
  │  a fő verzióba.                              │
  └─────────────────────────────────────────────┘
```

**PM szemmel**: Mintha 5 fejlesztő 5 külön gépen dolgozna, és a munkájukat a végén összefésülik. Annyi a különbség, hogy itt AI ágensek dolgoznak, automatikusan, és az „összefésülés" is automatikus.

## A Ralph Loop — az autonóm munkaciklus

Minden worktree-ben egy **Ralph Loop** nevű ciklus fut. Ez adja az ágens önállóságát: nem kell egy emberi felügyelőnek minden lépésnél bólintania.

```
  ┌──────────────── Ralph Loop ──────────────────┐
  │                                               │
  │   ┌─────────────┐                            │
  │   │ Feladat      │  Olvas: tasks.md          │
  │   │ kiválasztása │  Találja: első [ ] elem   │
  │   └──────┬──────┘                            │
  │          │                                    │
  │          ▼                                    │
  │   ┌─────────────┐                            │
  │   │ Claude Code  │  Implementálja a feladatot│
  │   │ fut          │  (fájlok, tesztek, commit)│
  │   └──────┬──────┘                            │
  │          │                                    │
  │          ▼                                    │
  │   ┌─────────────┐                            │
  │   │ Ellenőrzés   │  Minden teszt átment?     │
  │   │              │  Van még feladat?          │
  │   └──────┬──────┘                            │
  │          │                                    │
  │          ├── Van még feladat ──▶ Következő   │
  │          │                                    │
  │          ├── Minden kész ──▶ Beolvasztás      │
  │          │                                    │
  │          └── Elakadt ──▶ Leáll, jelent       │
  │                                               │
  │   Biztonsági korlátok:                        │
  │   - Max. iteráció szám (alapért. 10)          │
  │   - Max. futási idő (alapért. 45 perc/iter.)  │
  │   - Elakadás detekció (2 iteráció haladás     │
  │     nélkül → leáll)                           │
  └───────────────────────────────────────────────┘
```

**PM szemmel**: A Ralph Loop az, ami garantálja, hogy az ágens nem áll le az első hiba után, de nem is fut a végtelenségig. Ha elakad, jelzi és vár. Ha kész, jelzi és megáll.

## Az orchestrátor — a karmester

Az orchestrátor a legmagasabb szintű automatizálás. Input: egy specifikáció dokumentum. Output: kész, beolvasztott, tesztelt kód.

### Hogyan működik?

```
  ┌───────────────────────────────────────────────────────┐
  │                   ORCHESTRÁTOR                         │
  │                                                        │
  │  1. INPUT: Spec dokumentum (bármilyen markdown)        │
  │     "Webshop modernizálás: regisztráció, fizetés,     │
  │      email, admin, API, keresés"                       │
  │            │                                           │
  │            ▼                                           │
  │  2. AI ELEMZÉS: Claude felbontja change-ekre           │
  │     ┌──────────────────────────────────┐              │
  │     │  Change 1: user-registration  [S] │              │
  │     │  Change 2: payment-update     [M] │              │
  │     │  Change 3: email-service      [S] │              │
  │     │  Change 4: admin-panel        [L] │              │
  │     │  Change 5: api-rewrite        [M] │              │
  │     │  Change 6: search-upgrade     [S] │              │
  │     └──────────────────────────────────┘              │
  │            │                                           │
  │            ▼                                           │
  │  3. FÜGGŐSÉGI GRÁF: Mi függ mitől?                     │
  │                                                        │
  │     user-registration ──┐                              │
  │                         ├──▶ api-rewrite               │
  │     payment-update ─────┘        │                     │
  │                                  ▼                     │
  │     email-service ──────▶ admin-panel                  │
  │                                                        │
  │     search-upgrade (független)                         │
  │            │                                           │
  │            ▼                                           │
  │  4. PÁRHUZAMOS VÉGREHAJTÁS:                            │
  │                                                        │
  │     Kör 1:  [user-reg] [payment] [email] [search]     │
  │              ────────── párhuzamosan ──────────        │
  │                    │         │                          │
  │                    ▼         ▼                          │
  │     Kör 2:     [api-rewrite]                           │
  │                    │                                    │
  │                    ▼                                    │
  │     Kör 3:     [admin-panel]                           │
  │            │                                           │
  │            ▼                                           │
  │  5. EREDMÉNY: Összefoglaló riport                      │
  │     6/6 change kész, 0 hiba, 47 teszt átment          │
  │                                                        │
  └───────────────────────────────────────────────────────┘
```

### A folyamat lépésről lépésre

**1. lépés: Specifikáció beolvasása**
Adsz egy markdown dokumentumot (lehet akár egy product brief), és az orchestrátor Claude-al elemezteti. A Claude értelmezi, mit kell csinálni, és felbontja kisebb, kezelhető darabokra (change-ekre).

**2. lépés: Méretezés**
Minden change kap egy méretet:
- **S (kicsi)**: 1-3 fájl módosítás, egyszerű feladat
- **M (közepes)**: 5-10 fájl, komplex logika
- **L (nagy)**: Sok fájl, architektúrális hatás

**3. lépés: Függőségi gráf**
A Claude meghatározza, mely change-ek függenek egymástól. Például: az API átírás nem kezdődhet el, amíg a felhasználói regisztráció nincs kész (mert az API-nak ismernie kell az új felhasználói modellt).

**4. lépés: Párhuzamos végrehajtás**
Ami független, az egyszerre indul. Minden change kap egy worktree-t, egy Ralph Loop-ot, és a teljes OpenSpec pipeline-t (proposal → specs → design → tasks → implementáció). Az orchestrátor figyeli mindegyiket.

**5. lépés: Beolvasztás és tesztelés**
Amikor egy change kész, az orchestrátor beolvasztja a fő ágba, és lefuttatja a teszteket. Ha a teszt sikeres, feloldja a függő change-eket — azok elindulhatnak.

## Merge policy-k — mennyire legyen automatikus?

Az orchestrátor három szintű automatizálást kínál:

```
  ┌─────────────────────────────────────────────────┐
  │  eager     │  Azonnal beolvasztja amikor kész    │
  │            │  → Leggyorsabb, de kockázatos       │
  ├────────────┼────────────────────────────────────┤
  │ checkpoint │  N darab után megáll és vár         │
  │            │  → Egyensúly sebesség és kontroll   │
  ├────────────┼────────────────────────────────────┤
  │  manual    │  Sorba áll, ember hagy jóvá         │
  │            │  → Leglassabb, de legbiztonságosabb │
  └────────────┴────────────────────────────────────┘
```

**PM szemmel**: A merge policy a bizalom szintje. Új projekten érdemes `checkpoint`-tal indulni — az orchestrátor minden 2-3 kész change után megáll és vár, hogy átnézd. Amikor már bízol benne, átállhatsz `eager`-re.

## A GUI — valós idejű áttekintés

Az orchestrátor egy vizuális dashboard-ot biztosít, ahol minden ágens állapota valós időben látszik:

```
  ┌──────────────────────────────────────────────────┐
  │  wt-tools Control Center                         │
  │                                                  │
  │  Change               Státusz   Iteráció  Token  │
  │  ─────────────────    ───────   ────────  ─────  │
  │  user-registration    ✓ kész    3/10      45k    │
  │  payment-update       ▶ fut     5/10      82k    │
  │  email-service        ✓ kész    2/10      28k    │
  │  search-upgrade       ✓ kész    1/10      15k    │
  │  api-rewrite          ~ vár    -         -      │
  │  admin-panel          ~ vár    -         -      │
  │                                                  │
  │  Összesen: 3/6 kész │ 1 aktív │ 2 várakozik     │
  │  Eltelt idő: 2h 34m │ API költség: $12.50        │
  │                                                  │
  └──────────────────────────────────────────────────┘
```

**PM szemmel**: Mint egy Jira board, de valós időben frissül, és nem emberektől függ hogy frissüljön. Nem kell standup meetinget tartanod — megnyitod a dashboardot és látod.

## Valós számok

Egy középméretű projekt modernizálása az orchestrátorral:

| Mutató | Érték |
|--------|-------|
| Input | 1 specifikáció dokumentum (2 oldal) |
| Change-ek száma | 8 |
| Párhuzamos ágensek | 3 (egyszerre max.) |
| Teljes futási idő | ~4-5 óra |
| Emberi beavatkozás | 2x review (merge checkpoint) |
| API költség | ~$15-25 |
| Hagyományos becslés | 3-5 fejlesztőnap |

**Fontos megjegyzés**: Az orchestrátor nem teszi feleslegessé az emberi review-t. Az AI által írt kódot egy senior fejlesztőnek végig kell néznie. Az orchestrátor az elkészülést gyorsítja, nem a review-t eliminálja.

## Mikor érdemes orchestrálni?

| Helyzet | Orchestrátor? |
|---------|---------------|
| 1 kis feature | Nem — egyetlen Claude Code session elég |
| 2-3 összefüggő feature | Talán — ha vannak függetlenek |
| 5+ feature, projekt szintű | Igen — ez az orchestrátor erőssége |
| Kritikus, biztonsági kód | Nem — emberi kézi munka kell |
| Gyors prototípus | Nem — vibe coding gyorsabb |
| Terv alapú modernizáció | Igen — pont erre készült |

\begin{kulcsuzenat}
Az orchestráció lényege: egyetlen specifikációból több AI ágens dolgozik párhuzamosan, mindegyik a saját izolált munkaterületén, automatikus koordinálással. Mint PM, nem az ágenseket irányítod — a specifikációt írod, és a végeredményt review-olod. Közben a dashboard mutatja mi történik.
\end{kulcsuzenat}
