# OpenSpec — Specifikáció-vezérelt fejlesztés

## A probléma újra

Az előző fejezetben láttuk, miért nem elég a vibe coding. De ha nem „chattelünk az AI-val", akkor hogyan mondjuk el neki, mit csináljon?

A válasz: **ugyanúgy, ahogy egy jó PM elmondja egy fejlesztőcsapatnak** — specifikációval, tervvel, és feladatlistával. Csak éppen nem embereknek, hanem AI ágenseknek.

Ez az OpenSpec lényege: egy strukturált munkafolyamat, ahol **minden lépés dokumentált, ellenőrizhető, és visszakövethető**.

## A pipeline — az ötlettől a kódig

Az OpenSpec egy láncot épít fel, ahol minden lépés a következő alapja:

```
  ┌──────────────────────────────────────────────────────────┐
  │                    OpenSpec Pipeline                      │
  │                                                          │
  │   ┌──────────┐                                          │
  │   │ PROPOSAL │  ← "Mit és miért?"                       │
  │   │          │    PM/stakeholder nyelvén                  │
  │   └────┬─────┘                                          │
  │        │                                                 │
  │        ▼                                                 │
  │   ┌──────────┐                                          │
  │   │  SPECS   │  ← "Pontosan mit kell tudnia?"           │
  │   │          │    Mérhető követelmények                   │
  │   └────┬─────┘                                          │
  │        │                                                 │
  │        ▼                                                 │
  │   ┌──────────┐                                          │
  │   │  DESIGN  │  ← "Hogyan építjük meg?"                 │
  │   │          │    Technikai döntések                      │
  │   └────┬─────┘                                          │
  │        │                                                 │
  │        ▼                                                 │
  │   ┌──────────┐                                          │
  │   │  TASKS   │  ← "Mi a teendő lista?"                  │
  │   │          │    Checkboxos feladat lista                │
  │   └────┬─────┘                                          │
  │        │                                                 │
  │        ▼                                                 │
  │   ┌──────────────┐                                      │
  │   │IMPLEMENTATION│  ← Az AI itt kódol                    │
  │   │              │    Feladatról feladatra halad          │
  │   └──────────────┘                                      │
  │                                                          │
  │   Minden lépés: markdown fájl, git-ben tárolva,          │
  │   bárki által olvasható és review-olható                  │
  └──────────────────────────────────────────────────────────┘
```

Nézzük meg egyenként, mit tartalmaz minden lépés.

## 1. Proposal — „Mit és miért?"

A proposal (javaslat) az egyetlen dokumentum, amit ideális esetben **ember ír** — te, a PM, vagy a stakeholder. Ez mondja el, miért van szükség erre a változásra.

**Példa**: Tegyük fel, hogy felhasználói visszajelzések alapján kell egy jelszó-visszaállítási funkció.

```
  ┌──────────── proposal.md ──────────────────┐
  │                                            │
  │  ## Miért                                  │
  │                                            │
  │  A felhasználók 15%-a hetente elfelejti    │
  │  a jelszavát. Jelenleg nincs lehetőség     │
  │  önkiszolgáló visszaállításra — a support  │
  │  csapat manuálisan reseteli. Ez heti 40    │
  │  support ticket.                           │
  │                                            │
  │  ## Mi változik                            │
  │                                            │
  │  - Email alapú jelszó-visszaállítás        │
  │  - Token alapú biztonsági link             │
  │  - Jelszó erősség ellenőrzés               │
  │                                            │
  │  ## Érintett területek                     │
  │                                            │
  │  - Auth modul                              │
  │  - Email küldés                            │
  │  - Felhasználói felület                    │
  │                                            │
  └────────────────────────────────────────────┘
```

**PM szemmel**: A proposal az, amit eddig is írtál — egy rövid leírás a változásról, üzleti indoklással. Semmi technikai zsargon.

## 2. Specs — „Pontosan mit kell tudnia?"

A specifikáció a proposal-ból **mérhető követelményeket** csinál. Ezt általában az AI generálja a proposal alapján, de a PM review-olja.

```
  ┌──────────── spec.md ─────────────────────────┐
  │                                               │
  │  ### Követelmény: Email küldés                │
  │                                               │
  │  A rendszer email-t küld a felhasználónak     │
  │  egy egyedi, időkorlátos token linkkel.        │
  │                                               │
  │  #### Forgatókönyv: Sikeres kérés             │
  │  - HA a felhasználó megadja az email címét    │
  │  - AKKOR a rendszer küld egy linket           │
  │    ami 24 óráig érvényes                      │
  │                                               │
  │  #### Forgatókönyv: Nem létező email          │
  │  - HA az email cím nincs a rendszerben         │
  │  - AKKOR a rendszer UGYANAZT a visszajelzést  │
  │    mutatja (biztonsági okokból)                │
  │                                               │
  │  #### Forgatókönyv: Lejárt token              │
  │  - HA a felhasználó 24 óra után kattint       │
  │  - AKKOR hibaüzenet és új kérés lehetőség     │
  │                                               │
  └───────────────────────────────────────────────┘
```

**PM szemmel**: A spec az, amit eddig a fejlesztővel egyeztettél szóban — de most le van írva, visszakereshető, és az AI is érti. Minden „forgatókönyv" egy potenciális teszt eset.

## 3. Design — „Hogyan építjük meg?"

A design dokumentum a technikai döntéseket rögzíti. Ezt az AI készíti, de a senior fejlesztő review-olja.

```
  ┌──────────── design.md ───────────────────────┐
  │                                               │
  │  ## Döntések                                  │
  │                                               │
  │  ### D1: Token generálás                      │
  │  Döntés: Véletlenszerű 256-bites token        │
  │  Alternatíva: JWT token — elvetettük, mert    │
  │  nem vonható vissza.                          │
  │                                               │
  │  ### D2: Email szolgáltatás                   │
  │  Döntés: A meglévő SendGrid integrációt       │
  │  használjuk.                                  │
  │  Alternatíva: Saját SMTP — túl komplex        │
  │  ehhez a feladathoz.                          │
  │                                               │
  │  ## Kockázatok                                │
  │                                               │
  │  - [Kockázat] Email deliverability             │
  │    → Spam filterek blokkolhatják               │
  │    → Megoldás: SPF/DKIM beállítás              │
  │                                               │
  └───────────────────────────────────────────────┘
```

**PM szemmel**: Nem kell értened a technikai részleteket. De két dolgot érdemes figyelni:
- **Döntések**: Vannak alternatívák feltüntetve? (Ha igen, átgondolt döntés volt.)
- **Kockázatok**: Vannak megoldási javaslatok mellettük? (Ha igen, felkészültek.)

## 4. Tasks — „Mi a teendő lista?"

A tasks.md a feladatok checkboxos listája. Ez az AI munkalapja — feladatról feladatra halad, és bejelöli ami kész.

```
  ┌──────────── tasks.md ────────────────────────┐
  │                                               │
  │  ## 1. Adatbázis                              │
  │                                               │
  │  - [x] 1.1 Token tábla létrehozása            │
  │  - [x] 1.2 Token lejárat mező hozzáadása      │
  │                                               │
  │  ## 2. Backend                                │
  │                                               │
  │  - [x] 2.1 Reset endpoint implementálás        │
  │  - [x] 2.2 Token generálás logika              │
  │  - [ ] 2.3 Email küldés integráció     ◀── itt│
  │                                               │
  │  ## 3. Frontend                               │
  │                                               │
  │  - [ ] 3.1 Reset kérés form                   │
  │  - [ ] 3.2 Új jelszó form                     │
  │                                               │
  │  ## 4. Tesztelés                              │
  │                                               │
  │  - [ ] 4.1 Unit tesztek                        │
  │  - [ ] 4.2 E2E tesztek                        │
  │                                               │
  │  Haladás: 4/9 kész (44%)                       │
  │                                               │
  └───────────────────────────────────────────────┘
```

**PM szemmel**: Ez a tasks.md a projektmenedzsment aranybányája. Egyetlen fájl, ami megmondja:
- **Mi van kész** és **mi nincs** — pontosan, valós időben
- **Mennyi maradt** — százalékos haladás
- **Mi a következő** — az első bepipálatlan feladat

Nem kell a fejlesztőt kérdezned: „Hogy állsz?" Megnyitod a tasks.md fájlt, és látod.

## A PM szerepe az OpenSpec munkafolyamatban

A legfontosabb kérdés: hol vagy te ebben a folyamatban?

```
  ┌─────────────────────────────────────────────────────┐
  │                                                     │
  │  PM ír ─────▶ PROPOSAL ───▶ AI generálja ──────▶   │
  │               PM review                             │
  │                                                     │
  │  AI generálja ─▶ SPECS ─▶ PM review ──────────▶    │
  │                   "Igen, ezt akarom"                │
  │                    vagy                             │
  │                   "Nem, ez hiányzik: ..."           │
  │                                                     │
  │  AI generálja ─▶ DESIGN ─▶ Dev review ─────────▶   │
  │                   PM: döntések és kockázatok OK?    │
  │                                                     │
  │  AI generálja ─▶ TASKS ──▶ AI implementál ─────▶   │
  │                   PM: haladás nyomon követése       │
  │                                                     │
  │  AI implementál ─▶ KÓD ──▶ Dev + PM review ───▶   │
  │                    Tesztek futnak?                   │
  │                    Spec-nek megfelel?                │
  │                                                     │
  └─────────────────────────────────────────────────────┘
```

**Összefoglalva a PM teendőit**:

| Fázis | PM feladata | Időigény |
|-------|------------|----------|
| Proposal | Megírja | 15-30 perc |
| Specs | Review-olja: teljes-e, pontos-e? | 10-20 perc |
| Design | Átfutja: vannak-e kockázatok? | 5-10 perc |
| Tasks | Nyomon követi a haladást | Folyamatos, passzív |
| Implementation | Végeredményt ellenőrzi | Review-nként 10-20 perc |

**A teljes PM időráfordítás egy feature-re: 1-2 óra**, szemben a korábbi napokkal amit egyeztetésre, státusz meetingekre, és kérdések megválaszolására fordított.

## Hogyan néz ki ez a gyakorlatban?

Lássunk egy valós példát a wt-tools projektből. Egy új funkciót akartunk hozzáadni: „az AI ágensek küldjenek üzeneteket egymásnak".

**1. lépés**: Proposal megírása (5 perc)
> *„A párhuzamosan dolgozó AI ágensek nem tudnak kommunikálni egymással. Ha az egyik ágens felfedez valamit, ami a másik munkáját érinti, nincs módja szólni. Megoldás: egyszerű üzenetküldő rendszer."*

**2. lépés**: Az AI generál specifikációt (automatikus)
> *Követelmények: üzenet küldés ágens → ágens, inbox lekérdezés, broadcast üzenet mindenkinek, üzenetek szinkronizálása gépek között.*

**3. lépés**: PM review — „A broadcast jó ötlet, viszont legyen timestamp is" → specifikáció frissül

**4. lépés**: Design generálás (automatikus)
> *Döntés: fájl alapú rendszer, nincs szerver szükséges. Üzenetek JSON soronként egy fájlban, a meglévő git sync viszi gépek között.*

**5. lépés**: Tasks generálás → 8 feladat, checkboxos lista

**6. lépés**: Implementáció → az AI dolgozik, PM nézi a haladást a tasks.md-ben

**Eredmény**: 3 óra alatt kész egy funkció, ami hagyományos módon 2-3 nap lett volna. És minden lépés dokumentálva van, visszakereshető.

## Az OpenSpec és a hagyományos PM eszközök

Talán felmerül: „Miben más ez, mint a Jira?"

| Szempont | Jira / hagyományos | OpenSpec |
|----------|-------------------|----------|
| Ki írja a ticketet? | PM | PM (proposal) |
| Ki bontja feladatokra? | Dev + PM meeting | AI automatikusan |
| Hol van a spec? | Confluence (talán) | A kód mellett, git-ben |
| Hol van a haladás? | Jira board | tasks.md (valós idejű) |
| Ki frissíti? | Dev (ha emlékszik) | AI automatikusan |
| Review-olható? | Board szintjén | Artifact szintjén |

**Az OpenSpec nem helyettesíti a Jirát.** De kiegészíti: a Jira ticket-ből lesz egy proposal, abból specifikáció, abból feladatlista, abból kód. Minden összefügg, minden visszakövethető.

\begin{kulcsuzenat}
Az OpenSpec munkafolyamatban a PM végre nem a fejlesztőt kérdezgeti, hanem olvasható dokumentumokat review-ol. Az AI a tervből dolgozik, nem a levegőbe beszéltek. A haladás valós idejű, a minőség mérhető, és ha valami nem stimmel, visszamehetsz a specifikációhoz és rámutathatszra: „ezt kértem, ezt kaptam — mi a különbség?"
\end{kulcsuzenat}
