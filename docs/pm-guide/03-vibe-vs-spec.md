# Vibe Coding — a csábítás és a csapda

## Mi az a „vibe coding"?

2025 februárjában Andrej Karpathy — a világ egyik legismertebb AI kutatója, korábban a Tesla AI igazgatója — közzétett egy bejegyzést, amiben leírta az új fejlesztési stílusát:

> *„Csak látok dolgokat, mondok dolgokat, futtatom a kódot, és bemásolom a dolgokat, és nagyjából működik."*

Ezt nevezte el **vibe coding**-nak — szó szerinti fordításban „hangulat alapú kódolás". A lényeg: nem kell értened a kódot, csak elmondod az AI-nak mit akarsz, és ő megcsinálja. Ha nem jó, mondod újra, más szavakkal. Mintha egy beszélgetésből születne a szoftver.

**És ez működik.** Prototípusokra, egyszerű alkalmazásokra, személyes projektekre tökéletesen alkalmas. Egy hétvége alatt működő weboldalt csinálhatsz anélkül, hogy egyetlen sort írnál.

De van egy probléma.

## A csábítás

A vibe coding azért csábító, mert **azonnali eredményt ad**. Nincs tervezés, nincs specifikáció, nincs design review. Csak te és az AI, beszélgettek, és 10 perc múlva van valami ami működik.

```
  Vibe Coding munkafolyamat:

  "Csinálj egy webshopot"
           │
           ▼
  AI generál valamit
           │
           ▼
  "Ez nem jó, legyen kék"
           │
           ▼
  AI módosít
           │
           ▼
  "A kosár nem működik"
           │
           ▼
  AI javít... vagy ront
           │
           ▼
  "Már a login sem megy!"
           │
           ▼
  ???
```

Ismerős? Ez a „javítsd meg A-t, elromlik B" spirál a vibe coding természetes következménye. Nincs terv, nincs struktúra — minden változtatás potenciálisan elront valami mást.

## A három alapvető probléma

### 1. A kontextus probléma

Minden AI modellnek van egy **kontextus ablaka** — ez az a mennyiségű szöveg (kód, beszélgetés, fájl tartalom), amit egyszerre kezelni tud. Gondolj rá úgy, mint az AI „munkamemóriájára".

```
  A kontextus ablak telítődése:

  ┌─────────────────────────────────────────────────┐
  │ ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ 10% — friss,
  │                                                  │        mindent lát
  │ ██████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ 30% — jól dolgozik
  │                                                  │
  │ ██████████████████████████████░░░░░░░░░░░░░░░░░ │ 60% — lassul,
  │                                                  │        néha felejt
  │ █████████████████████████████████████████████░░░ │ 90% — hibázik,
  │                                                  │        korábbi
  │ ████████████████████████████████████████████████ │ 100%   utasításokat
  │                                                  │        elfelejti
  └─────────────────────────────────────────────────┘
```

Vibe coding során ez a kontextus gyorsan megtelik:

- Elküldöd az első kérést → az AI elolvassa a fájlokat → 20% foglalt
- Javítást kérsz → újabb fájlok, előző beszélgetés → 40%
- Megint javítás → még több kontextus → 60%
- A 10. javításnál → a kontextus szinte tele van → az AI „elfelejti" az első kéréseidet

**Eredmény**: Az AI javítja a legutóbbi hibát, de közben elrontja amit 5 lépéssel korábban csinált. Mert már nem „emlékszik" rá.

> *Bővebben a kontextus kezelésről: [Claude Code best practices — manage context](https://code.claude.com/docs/en/best-practices)*

### 2. A minőség probléma

A vibe coding legnagyobb csapdája: **nincs mit ellenőrizni**. Ha nincs specifikáció, honnan tudod, hogy a szoftver azt csinálja, amit kell?

```
  Vibe Coding:                   Spec-Driven:

  "Csinálj login oldalt"         Specifikáció:
        │                        - Email + jelszó mező
        ▼                        - "Elfelejtett jelszó" link
  AI csinál valamit              - 3 sikertelen próba után zárolás
        │                        - Google OAuth opció
        ▼                        - Hibás jelszó: "Helytelen adatok"
  "Kész van?"                          │
  "...szerintem igen"                  ▼
                                 AI implementál a spec alapján
                                       │
                                       ▼
                                 Ellenőrizhető:
                                 ✓ Van email mező?
                                 ✓ Van "Elfelejtett jelszó"?
                                 ✓ Zárol 3 próba után?
                                 ✓ Google OAuth működik?
```

**A spec-driven megközelítésnél** minden követelmény le van írva, és minden követelményhez tartozik egy ellenőrizhető feltétel. A PM pontosan tudja, mi van kész és mi nincs.

**Vibe coding-nál** a „kész" definíciója: „úgy tűnik, működik". Ami production-ben gyakran azt jelenti: „az alap eset működik, de a szélső esetek nem".

### 3. A skálázás probléma

A vibe coding egyetlen chat session-ben zajlik. Ez a session:

- **Egy ember** beszélget **egy AI-val**
- **Egy szál** gondolkodás — nem párhuzamosítható
- **Egy kontextus ablak** — korlátozott kapacitás
- **Nincs memória** — a következő session-ben minden előlről

```
  Vibe Coding skálázása:

  Projekt mérete:    Fájlok:      Vibe Coding hatékonysága:
  ──────────────     ──────       ──────────────────────────
  Kis script         1-5          ████████████ Kiváló
  Kis app            5-20         ████████░░░░ Jó
  Közepes app        20-50        █████░░░░░░░ Nehézkes
  Nagy app           50-200       ██░░░░░░░░░░ Alig működik
  Enterprise         200+         ░░░░░░░░░░░░ Lehetetlen
```

Egy 200 fájlos projektben az AI nem tudja egyszerre a fejében tartani az összeset. A vibe coding egyszerűen nem skálázódik komplex projektekre.

## Mikor JÓ a vibe coding?

Fontos hangsúlyozni: a vibe coding nem rossz eszköz — rossz helyen használva az. Vannak helyzetek, ahol tökéletesen megfelel:

| Helyzet | Miért jó itt a vibe coding |
|---------|---------------------------|
| **Prototípus** | Gyors validáció, nem kell tartós minőség |
| **Hackathon** | Sebesség számít, nem karbantarthatóság |
| **Személyes projekt** | Nincs csapat, nincs PM, nincs production |
| **Tanulás** | Az AI magyaráz miközben generálja a kódot |
| **Egyszerű script** | 1-2 fájl, jól körülhatárolt feladat |
| **Ötlet validáció** | „Működne ez egyáltalán?" kérdésre válasz |

## Mikor ROSSZ a vibe coding?

| Helyzet | Miért rossz itt |
|---------|-----------------|
| **Production kód** | Nincs spec → nincs mit tesztelni → hibák |
| **Csapatmunka** | A többiek nem látják mi történt a chat-ben |
| **Komplex rendszer** | A kontextus ablak nem elég |
| **Hosszú projekt** | Nincs memória, minden session újraindul |
| **Szabályozott iparág** | Nincs audit trail, nincs nyomon követhetőség |
| **PM felügyelete alatt** | Nem tudod ellenőrizni, mert nincs mérce |

## Az összehasonlítás

| Szempont | Vibe Coding | Spec-Driven |
|----------|-------------|-------------|
| **Indulási sebesség** | Azonnali | 10-30 perc tervezés |
| **Teljes idő (kicsi projekt)** | Gyors | Hasonló |
| **Teljes idő (nagy projekt)** | Lassú (újracsinálás) | Gyorsabb |
| **Kód minőség** | Változó, kiszámíthatatlan | Konzisztens |
| **Nyomon követhetőség** | Nincs (chat history) | Teljes (artifact-ok) |
| **PM rálátás** | „Kész van?" „Igen" | Spec → Tasks → Progress |
| **Skálázhatóság** | 1 ember, 1 chat | Több ágens, párhuzamos |
| **Újrafelhasználhatóság** | Semmi | Spec újra felhasználható |
| **Review-olhatóság** | Chat log átolvasása | Strukturált artifact-ok |

## A váltás: vibe-ból spec-be

A jó hír az, hogy a két megközelítés nem kizáró. Sőt, a legtöbb csapatnál a fejlődés így néz ki:

```
  1. fázis:  Vibe coding        "Wow, ez működik!"
                │
                ▼
  2. fázis:  Vibe + review      "Na jó, de nézze meg valaki"
                │
                ▼
  3. fázis:  Plan → vibe        "Előbb gondolkodjunk, aztán kódoljunk"
                │
                ▼
  4. fázis:  Spec-driven        "Specifikáció → design → implementáció"
                │
                ▼
  5. fázis:  Orchestrated       "Több ágens, párhuzamosan, automatizáltan"
```

A következő fejezetben a 4. és 5. fázist nézzük meg részletesen.

\begin{kulcsuzenat}
A vibe coding a szoftverfejlesztés fast food-ja: gyors, olcsó, és alkalmi használatra remek. De ha egy céget akarsz belőle felépíteni — szükséged van igazi konyhára, igazi receptekre, és igazi minőségellenőrzésre. A spec-driven fejlesztés adja ezt a struktúrát.
\end{kulcsuzenat}
