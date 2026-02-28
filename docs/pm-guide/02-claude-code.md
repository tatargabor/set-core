# Claude Code — Az új fejlesztői eszköz

## Mi az a Claude Code?

A Claude Code az Anthropic cég által fejlesztett **AI kódolási eszköz**, ami közvetlenül a fejlesztő munkakörnyezetében dolgozik. Nem egy webes chatablak, ahová be kell másolni a kódot és ki kell másolni a választ — ehelyett egy teljes jogú résztvevő a fejlesztési folyamatban.

Gondolj rá úgy, mint egy rendkívül gyors gyakornokra, akinek:

- Hozzáférése van a projekt összes fájljához
- Képes parancsokat futtatni a számítógépen
- Érti a projekt szerkezetét és összefüggéseit
- Teszteket tud futtatni és az eredmények alapján javítani
- Git-ben tud commitolni és pull requestet nyitni

> *Hivatalos dokumentáció: [code.claude.com/docs](https://code.claude.com/docs/en/overview)*

## Hol fut?

A Claude Code több környezetben is elérhető — a fejlesztő választja ki, melyik illik a munkafolyamatához:

```
  ┌─────────────────────────────────────────────────────┐
  │                  Claude Code                         │
  │                                                      │
  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
  │  │ Terminál │ │  VS Code  │ │ Desktop  │ │  Web   │ │
  │  │  (CLI)   │ │  (IDE)   │ │  (app)   │ │(böng.) │ │
  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
  │                                                      │
  │  Mind ugyanaz a motor — csak a felület más           │
  └─────────────────────────────────────────────────────┘
```

- **Terminál (CLI)**: A legteljesebb élmény. A fejlesztő a parancssort nyitja meg, beírja hogy `claude`, és beszélgethet az AI-val miközben az fájlokat szerkeszt és parancsokat futtat.
- **VS Code / JetBrains**: IDE kiegészítőként — a kódszerkesztőbe beágyazva, a kód kontextusában.
- **Desktop app**: Önálló alkalmazás több session párhuzamos kezelésére.
- **Web**: Böngészőben, telepítés nélkül — hosszú feladatokhoz, amikhez nem kell helyben futtatni.

> *Részletek: [Claude Code overview](https://code.claude.com/docs/en/overview)*

## Az agentic loop — hogyan gondolkodik

A hagyományos AI chatbotnál te kérdezel, az AI válaszol, aztán te cselekszel. A Claude Code másképp működik. Ő is **cselekszik**: fájlokat olvas, kódot szerkeszt, parancsokat futtat, és az eredmények alapján tovább dolgozik.

Ezt hívjuk **agentic loop**-nak (ágentikus ciklusnak):

```
         ┌──────────────────────────────────────────┐
         │                                          │
         │    ┌──────────┐                          │
         │    │  GONDOL   │  "Milyen fájlokat kell  │
         │    │ (tervez)  │   módosítani?"           │
         │    └─────┬─────┘                          │
         │          │                                │
         │          ▼                                │
         │    ┌──────────┐                          │
         │    │ CSELEKSZIK│  Fájlt olvas, kódot ír, │
         │    │(végrehajt)│  parancsot futtat        │
         │    └─────┬─────┘                          │
         │          │                                │
         │          ▼                                │
         │    ┌──────────┐                          │
         │    │ ELLENŐRIZ │  Teszt fut? Hiba van?   │
         │    │(verifikál)│  Build rendben?          │
         │    └─────┬─────┘                          │
         │          │                                │
         │          │ ha kész ──────────▶ EREDMÉNY   │
         │          │                                │
         │          │ ha nem kész                    │
         │          └──────────────────┐             │
         │                             │             │
         └─────────────────────────────┘             │
                     ismétli amíg                    │
                     kész nem lesz                   │
```

**Konkrét példa**: Mondjuk azt mondod neki: *„Javítsd ki a bejelentkezési hibát."*

1. **Gondol**: Megkeresi a bejelentkezéssel kapcsolatos fájlokat a projektben.
2. **Cselekszik**: Megnyitja az `auth.py` fájlt, megtalálja a hibát (elírt változónév), kijavítja.
3. **Ellenőriz**: Lefuttatja a teszteket. Két teszt elbukik.
4. **Gondol**: Elemzi a teszthibát — kiderül, egy másik fájlban is van összefüggő hiba.
5. **Cselekszik**: Megnyitja és kijavítja azt a fájlt is.
6. **Ellenőriz**: Újra lefuttatja a teszteket. Mind zöld.
7. **Eredmény**: „Két fájlt módosítottam, a bejelentkezési hiba javítva, minden teszt átmegy."

Ez a ciklus teljesen automatikus — a fejlesztő csak a végeredményt ellenőrzi.

## Az eszközök — mivel dolgozik

A Claude Code nem varázsol. Konkrét, meghatározott eszközöket használ, pont úgy, mint egy emberi fejlesztő:

| Eszköz | Mit csinál | Emberi párhuzam |
|--------|-----------|-----------------|
| **Read** | Fájlokat olvas | Megnyitja a fájlt a szerkesztőben |
| **Edit** | Fájl egy részét módosítja | Átír egy kódrészt |
| **Write** | Új fájlt hoz létre | Új fájlt ment |
| **Bash** | Parancssori parancsokat futtat | Terminálba gépel |
| **Grep** | Szöveget keres a fájlokban | „Hol van ez a függvény?" |
| **Glob** | Fájlokat keres minta alapján | „Hol vannak a teszt fájlok?" |

Ezek az eszközök teszik lehetővé, hogy a Claude Code ne csak „mondja" mit kellene csinálni, hanem **meg is csinálja**.

> *Teljes eszközlista: [Claude Code settings — tools](https://code.claude.com/docs/en/settings)*

## CLAUDE.md — a projekt memóriája

Minden projektben lehet egy `CLAUDE.md` nevű fájl. Ez egy egyszerű szöveges fájl, amit a Claude Code **minden beszélgetés elején elolvas**. Ide kerülnek a projekt sajátos tudnivalói:

```
  ┌──────────── CLAUDE.md ────────────────┐
  │                                        │
  │  # Kód stílus                          │
  │  - TypeScript-et használunk            │
  │  - Tesztek: pytest-tel futtatjuk       │
  │                                        │
  │  # Fontos                              │
  │  - A main branch-re tilos pusholni     │
  │  - Minden PR-hez kell legalább 1 teszt │
  │                                        │
  │  # Parancsok                           │
  │  - Build: npm run build                │
  │  - Teszt: npm test                     │
  │                                        │
  └────────────────────────────────────────┘
```

**PM szemmel**: A CLAUDE.md hasonlít egy belső wiki oldalhoz, amit a fejlesztőknek írsz. Csak éppen nem embereknek szól, hanem az AI-nak. Ha eddig fusztráltad, hogy az új fejlesztő nem olvassa el a projekt konvenciókat — az AI garantáltan elolvassa, minden egyes alkalommal.

> *Bővebben: [CLAUDE.md dokumentáció](https://code.claude.com/docs/en/claude-md)*

## Hookrendszer — automatikus minőségbiztosítás

A hookrendszer (kampórendszer) lehetővé teszi, hogy bizonyos eseményekre automatikus műveleteket kössünk. Gondolj rá úgy, mint szabályokra, amik **mindig lefutnak**, emberi feledékenységtől függetlenül.

Például:

- **Fájl szerkesztés után** → automatikusan lefut a kódformázó (linter)
- **Commit előtt** → automatikusan lefutnak a tesztek
- **Bash parancs futtatásakor** → ellenőrzi, hogy nem töröl-e fontos fájlokat
- **Session elején** → betölti a korábbi tapasztalatokat (memória)
- **Session végén** → elmenti a tanulságokat a következő session-höz

```
  Esemény                    Hook (automatikus akció)
  ────────                   ────────────────────────
  AI fájlt szerkeszt    ──▶  Kódformázó lefut
  AI commitolni akar    ──▶  Tesztek lefutnak
  AI bash-t használ     ──▶  Biztonsági ellenőrzés
  Session indul         ──▶  Korábbi emlékek betöltése
  Session véget ér      ──▶  Tanulságok mentése
```

**PM szemmel**: A hookrendszer az, ami biztosítja, hogy az AI betartsa a csapat szabályait. Nem kell bízni abban, hogy „emlékezni fog" — a hookrendszer kikényszeríti.

> *Részletek: [Hooks guide](https://code.claude.com/docs/en/hooks-guide)*

## MCP — az „USB-C" az AI alkalmazásoknak

Az MCP (Model Context Protocol — Modell Kontextus Protokoll) egy nyílt szabvány, ami lehetővé teszi, hogy az AI eszközök **külső rendszerekhez** csatlakozzanak.

Gondolj rá úgy, mint az USB-C-re: ahogy az USB-C szabványos csatlakozást biztosít különböző elektronikai eszközök között, az MCP szabványos csatlakozást biztosít az AI és a külvilág között.

```
  ┌──────────┐     MCP      ┌──────────────────┐
  │          │──────────────▶│ Google Drive      │
  │          │               └──────────────────┘
  │          │     MCP      ┌──────────────────┐
  │  Claude  │──────────────▶│ Jira / Notion    │
  │  Code    │               └──────────────────┘
  │          │     MCP      ┌──────────────────┐
  │          │──────────────▶│ Adatbázis        │
  │          │               └──────────────────┘
  │          │     MCP      ┌──────────────────┐
  │          │──────────────▶│ Figma / Design   │
  └──────────┘               └──────────────────┘
```

Az MCP nélkül az AI csak a helyi fájlrendszert és a parancssort látja. MCP-vel viszont:

- Elolvashatja a Google Drive-on lévő követelményeket
- Megnézheti a Jira ticketeket
- Lekérdezheti az adatbázist
- Behúzhatja a Figma design-okat

**PM szemmel**: Az MCP teszi lehetővé, hogy az AI ne csak kódot írjon, hanem a teljes fejlesztési ökoszisztémában mozogjon. Ha a követelmények Google Docsban vannak, az AI onnan is el tudja olvasni.

> *MCP bevezető: [modelcontextprotocol.io](https://modelcontextprotocol.io/introduction)*

## Subágensek — párhuzamos munkavégzés

A Claude Code képes **több kisebb ágenst** (subágenst) indítani, amik párhuzamosan dolgoznak. Ez olyan, mintha a gyakornokod szólna 3 másik gyakornoknak, hogy „te nézd meg az adatbázist, te a frontend-et, te pedig futtasd a teszteket" — és utána összefoglalja az eredményt.

```
  ┌─────────────────────────────────────────────┐
  │            Fő Claude Code session            │
  │                                              │
  │    "Vizsgáld meg az auth, a db, és az API   │
  │     modult párhuzamosan"                     │
  │                                              │
  │    ┌───────────┐ ┌──────────┐ ┌──────────┐  │
  │    │ Subágens A│ │Subágens B│ │Subágens C│  │
  │    │  Auth     │ │  DB      │ │  API     │  │
  │    │ vizsgálat │ │ vizsgálat│ │ vizsgálat│  │
  │    └─────┬─────┘ └────┬─────┘ └────┬─────┘  │
  │          │             │            │         │
  │          └─────────────┼────────────┘         │
  │                        │                      │
  │                   Összefoglalás               │
  │                                              │
  └─────────────────────────────────────────────┘
```

Miért fontos ez?

- **Sebesség**: 3 párhuzamos vizsgálat gyorsabb, mint 3 egymás utáni
- **Kontextus védelem**: Minden subágens a saját ablakában dolgozik, nem terheli a fő beszélgetést
- **Specializáció**: Minden subágens más feladatra optimalizálható

> *Bővebben: [Sub-agents dokumentáció](https://code.claude.com/docs/en/sub-agents)*

## Egy konkrét példa: bugfix a gyakorlatban

Lássunk egy valós forgatókönyvet. A fejlesztő reggel megnyitja a terminált:

```
  Fejlesztő:  "A felhasználók azt jelentik, hogy a jelszó-
               visszaállítás nem működik timeout hibával.
               Javítsd ki és írj rá tesztet."

  Claude Code: [Gondol] Megkeresem a jelszó-visszaállítás kódot...
               [Cselekszik] Olvasom: src/auth/password-reset.ts
               [Gondol] A probléma: az email küldés 5 másodperces
                        timeoutot használ, ami túl kevés a SMTP
                        szervernek.
               [Cselekszik] Módosítom: timeout 5000 → 30000
               [Cselekszik] Írok egy tesztet:
                        tests/auth/password-reset.test.ts
               [Ellenőriz] Tesztek futtatása... 12/12 átment.
               [Gondol] Van egy másik hely is ahol hasonló
                        timeout van: src/auth/email-verify.ts
               [Cselekszik] Azt is javítom.
               [Ellenőriz] Tesztek futtatása... 14/14 átment.

               "Kész. Két fájlt módosítottam:
               - password-reset.ts: timeout 5s → 30s
               - email-verify.ts: timeout 5s → 30s
               Írtam 2 új tesztet. Minden átmegy.
               Commitoljam?"
```

A fejlesztő átnézi a változtatásokat, jóváhagyja, és a Claude Code commitol. Az egész **3-5 perc** volt, amihez egy ember 30-60 percet ülne.

## Összefoglalva

| Fogalom | Mit jelent PM-nek |
|---------|-------------------|
| Claude Code | AI fejlesztő eszköz, ami fájlokat szerkeszt, tesztel, commitol |
| Agentic loop | Automatikus ciklus: gondol → cselekszik → ellenőriz |
| CLAUDE.md | Projekt szabályok amit az AI mindig betart |
| Hookrendszer | Automatikus minőségellenőrzés minden lépésnél |
| MCP | Az AI csatlakozhat Jira-hoz, Google Docs-hoz, stb. |
| Subágensek | Több AI dolgozik párhuzamosan, majd összegez |

\begin{kulcsuzenat}
A Claude Code nem ChatGPT, ahová kódot másolsz. Ez egy teljes fejlesztőkörnyezetben dolgozó ágens, ami fájlokat szerkeszt, teszteket futtat, és commitol — a fejlesztő felügyeletével. Mint PM, nem a kódot kell értened, hanem a munkafolyamatot: az AI önállóan dolgozik, és te az eredményt ellenőrzöd.
\end{kulcsuzenat}
