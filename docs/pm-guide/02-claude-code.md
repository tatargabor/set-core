# Claude Code -- Az új fejlesztői eszköz

## Mi az a Claude Code?

A Claude Code az Anthropic cég által fejlesztett **AI kódolási eszköz**, ami közvetlenül a fejlesztő munkakörnyezetében dolgozik. Nem egy webes chatablak, ahová be kell másolni a kódot és ki kell másolni a választ -- ehelyett egy teljes jogú résztvevő a fejlesztési folyamatban.

Gondolj rá úgy, mint egy rendkívül gyors gyakornokra, akinek:

- Hozzáférése van a projekt összes fájljához
- Képes parancsokat futtatni a számítógépen
- Érti a projekt szerkezetét és összefüggéseit
- Teszteket tud futtatni és az eredmények alapján javítani
- Git-ben tud commitolni és pull requestet nyitni

De fontos megérteni, miben különbözik ez a ChatGPT-től, amit valószínűleg már használsz. A ChatGPT (és hasonló chatbotok) egy **beszélgetési felület**: te kérdezel, az AI válaszol szöveggel. Ha kódot kérsz, kapsz egy választ amit másolgatnod kell. A Claude Code ezzel szemben nem beszélget a kódról -- **dolgozik** a kóddal. Közvetlenül hozzáfér a fájlokhoz, futtatja a parancsokat, ellenőrzi az eredményt. Ez a különbség olyan, mint a különbség aközött, hogy valaki **leírja** hogyan kell megjavítani a csapot, és aközött, hogy **megjavítja** a csapot.

> *Hivatalos dokumentáció: [Claude Code overview](https://code.claude.com/docs/en/overview) -- az Anthropic részletes leírása az eszközről, annak képességeiről és használatáról.*

## Hol fut?

A Claude Code több környezetben is elérhető -- a fejlesztő választja ki, melyik illik a munkafolyamatához:

```
  +-----------------------------------------------------+
  |                  Claude Code                         |
  |                                                      |
  |  +----------+ +----------+ +----------+ +--------+  |
  |  | Terminál  | |  VS Code | | Desktop  | |  Web   |  |
  |  |  (CLI)    | |  (IDE)   | |  (app)   | |(böng.) |  |
  |  +----------+ +----------+ +----------+ +--------+  |
  |                                                      |
  |  Mind ugyanaz a motor -- csak a felület más          |
  +-----------------------------------------------------+
```

- **Terminál (CLI)**: A legteljesebb élmény. A fejlesztő a parancssort nyitja meg, beírja hogy `claude`, és beszélgethet az AI-val miközben az fájlokat szerkeszt és parancsokat futtat. Ez a legtöbbet használt mód professzionális fejlesztőknél.
- **VS Code / JetBrains**: IDE kiegészítőként -- a kódszerkesztőbe beágyazva, a kód kontextusában. A fejlesztő az editorban marad, és az AI ott szerkeszt mellette. Részletek: [IDE integration](https://code.claude.com/docs/en/ide-integration).
- **Desktop app**: Önálló alkalmazás több session párhuzamos kezelésére. Hasznos, ha a fejlesztő több projekten dolgozik egyszerre.
- **Web**: Böngészőben, telepítés nélkül -- hosszú feladatokhoz, amikhez nem kell helyben futtatni. Hasznos, ha a fejlesztő nincs a gépe előtt, de el akar indítani egy feladatot.

A PM szempontjából mindegy, melyiket használják a fejlesztők -- a lényeg, hogy **ugyanaz az AI motor** fut mindegyik mögött. Ha valaki a terminálból dolgozik, ugyanazt az eredményt kapja, mint aki a VS Code-ból.

> *IDE-specifikus részletek és telepítési útmutató: [Claude Code IDE integration](https://code.claude.com/docs/en/ide-integration)*

## Az agentic loop -- hogyan gondolkodik

A hagyományos AI chatbotnál te kérdezel, az AI válaszol, aztán te cselekszel. A Claude Code másképp működik. Ő is **cselekszik**: fájlokat olvas, kódot szerkeszt, parancsokat futtat, és az eredmények alapján tovább dolgozik.

Ezt hívjuk **agentic loop**-nak (ágentikus ciklusnak):

```
         +----------------------------------------------+
         |                                              |
         |    +----------+                              |
         |    |  GONDOL   |  "Milyen fájlokat kell      |
         |    | (tervez)  |   módosítani?"               |
         |    +-----+-----+                              |
         |          |                                    |
         |          v                                    |
         |    +----------+                              |
         |    | CSELEKSZIK|  Fájlt olvas, kódot ír,      |
         |    |(végrehajt)|  parancsot futtat             |
         |    +-----+-----+                              |
         |          |                                    |
         |          v                                    |
         |    +----------+                              |
         |    | ELLENŐRIZ |  Teszt fut? Hiba van?        |
         |    |(verifikál)|  Build rendben?               |
         |    +-----+-----+                              |
         |          |                                    |
         |          | ha kész ------------> EREDMÉNY     |
         |          |                                    |
         |          | ha nem kész                        |
         |          +------------------+                 |
         |                             |                 |
         +-----------------------------+                 |
                     ismétli amíg                        |
                     kész nem lesz                       |
```

Ez a ciklus az, ami az AI-t **ágenssé** teszi, nem csak chatbottá. A Claude Code nem áll meg az első válasznál -- addig dolgozik, amíg a feladat ténylegesen készen nincs. Ha az első javítás nem jó, megpróbálja másképp. Ha a teszt elbukik, megnézi miért, és újra javít.

Az Anthropic ezt a működést részletesen leírja a [Claude Code best practices](https://code.claude.com/docs/en/best-practices) oldalon, ahol gyakorlati tanácsokat is adnak, hogyan érdemes a leghatékonyabban használni.

**Részletes példa**: Lássuk lépésről lépésre, hogyan dolgozik az AI, amikor egy valós feladatot kap. Mondjuk a fejlesztő azt mondja: *"A felhasználók azt jelentik, hogy a profil oldal lassan tölt be. Derítsd ki miért, és javítsd ki."*

1. **Gondol**: "Teljesítmény probléma a profil oldalon. Keresem a releváns fájlokat. A profil oldal valószínűleg a `pages/profile` vagy `routes/profile` könyvtárban lesz."
2. **Cselekszik**: A Grep eszközzel megkeresi a "profile" szót a routing fájlokban. Találat: `src/pages/ProfilePage.tsx`.
3. **Cselekszik**: Beolvassa a `ProfilePage.tsx` fájlt. Látja, hogy az oldal betöltéskor 3 külön API hívást indít: felhasználói adatok, bejegyzések, és követők listája.
4. **Gondol**: "3 szekvenciális API hívás -- ez lassítja a betöltést. De előbb nézzük meg, mennyi idő telik el. Futtatom a teszteket, hogy lássam van-e már teljesítmény teszt."
5. **Cselekszik**: Bash eszközzel lefuttatja: `npm test -- --grep "profile"`. Találat: van egy teszt, de nem mér teljesítményt.
6. **Gondol**: "A 3 API hívást párhuzamosítani kell (`Promise.all`). Így a három hívás egyidejűleg indul, és a leglassabb határozza meg a teljes időt, nem összeadódnak."
7. **Cselekszik**: Módosítja a `ProfilePage.tsx` fájlt -- a 3 szekvenciális `await` hívást egyetlen `Promise.all` blokkba fogja.
8. **Cselekszik**: Ír egy teljesítmény tesztet: `tests/pages/profile-performance.test.ts` -- ami ellenőrzi, hogy az oldal betöltése 2 másodpercen belül megtörténik.
9. **Ellenőriz**: Lefuttatja az összes tesztet. 1 teszt elbukik -- de nem a saját új tesztje, hanem egy másik, ami a profil oldal renderelését teszteli, és elvárta a régi szekvenciális viselkedést.
10. **Gondol**: "A meglévő teszt a régi API hívás sorrendet várta el. Frissítenem kell, hogy az új párhuzamos hívást tükrözze."
11. **Cselekszik**: Módosítja a másik tesztfájlt is.
12. **Ellenőriz**: Újra futtatja a teszteket. 24/24 átment.
13. **Eredmény**: "Kész. Két fájlt módosítottam, egy új tesztet írtam. A profil oldal betöltési ideje kb. harmadára csökken, mert a három API hívás most párhuzamosan fut. Commitoljam?"

Ez a példa jól mutatja a ciklus lényegét: az AI nem akar mindent egyetlen lépésben megoldani. Lépésről lépésre halad, minden lépésnél ellenőrzi az eredményt, és ha valami nem stimmel, visszalép és javít. Pontosan úgy, ahogy egy jó fejlesztő dolgozik -- csak sokkal gyorsabban.

## Az eszközök -- mivel dolgozik

A Claude Code nem varázsol. Konkrét, meghatározott eszközöket használ, pont úgy, mint egy emberi fejlesztő. Minden egyes lépésnél az AI kiválasztja a megfelelő eszközt, használja, és az eredmény alapján dönt a következő lépésről.

| Eszköz | Mit csinál | Emberi párhuzam |
|--------|-----------|-----------------|
| **Read** | Fájlokat olvas | Megnyitja a fájlt a szerkesztőben |
| **Edit** | Fájl egy részét módosítja | Átír egy kódrészt |
| **Write** | Új fájlt hoz létre | Új fájlt ment |
| **Bash** | Parancssori parancsokat futtat | Terminálba gépel |
| **Grep** | Szöveget keres a fájlokban | "Hol van ez a függvény?" |
| **Glob** | Fájlokat keres minta alapján | "Hol vannak a teszt fájlok?" |
| **WebFetch** | Weboldalt olvas el | Böngészőt nyit |
| **WebSearch** | Interneten keres | Google-t használ |

Lássunk pár gyakorlati példát, hogy ezek az eszközök hogyan működnek együtt:

**1. példa -- Hibakeresés (Read + Grep + Edit + Bash)**

A fejlesztő azt mondja: *"A regisztrációs form nem menti el a telefonszámot."*

- Az AI **Grep**-pel megkeresi a "telefonszám" vagy "phone" szót a kódban
- **Read**-del beolvassa a találatokat: megtalálja a regisztrációs formot és az API endpoint-ot
- Észreveszi, hogy a form elküldi a `phone` mezőt, de az API endpoint nem menti el (hiányzó mező az adatbázis műveletnél)
- **Edit**-tel hozzáadja a hiányzó mezőt az API-hoz
- **Bash**-sel futtatja a teszteket: `npm test`
- Ha a teszt átment, jelenti az eredményt

**2. példa -- Kutatás (WebSearch + WebFetch + Read)**

A fejlesztő azt mondja: *"A Stripe API v3-ra kell migrálni. Derítsd ki mit kell változtatni."*

- Az AI **WebSearch**-csel megkeresi a Stripe v3 migration guide-ot
- **WebFetch**-csel beolvassa a hivatalos migrációs dokumentációt
- **Grep**-pel megkeresi a projektben az összes Stripe API hívást
- **Read**-del beolvassa az érintett fájlokat
- Összefoglalót ad: "12 fájlban van Stripe hívás, ebből 4 igényel változtatást a v3-hoz"

Ezek az eszközök teszik lehetővé, hogy a Claude Code ne csak "mondja" mit kellene csinálni, hanem **meg is csinálja**. Az Anthropic részletesen dokumentálja az összes elérhető eszközt: [Claude Code settings -- tools](https://code.claude.com/docs/en/settings).

> *Az Anthropic blogján olvashatod, hogyan működik az "eszközhasználat" (tool use) koncepciója: [Tool use GA](https://www.anthropic.com/news/tool-use-ga)*

## Az engedélyezési rendszer -- ki mit engedhet

Egy fontos kérdés, ami PM-ként biztosan felmerül: **mennyire biztonságos?** Ki kontrollálja, mit csinálhat az AI?

A Claude Code-nak van egy részletes engedélyezési rendszere (permission model), ami a fejlesztő kezében tartja az irányítást. Két fő szintje van:

**1. Olvasási eszközök (mindig engedélyezettek)**

Az AI bármikor olvashat fájlokat, kereshet a kódban, és megnézhet dolgokat. Ez nem változtat semmin, tehát nem kockázatos.

**2. Írási eszközök (engedélyt kell kérni)**

Amikor az AI fájlt akar szerkeszteni, parancsot akar futtatni, vagy bármit akar változtatni, **engedélyt kér a fejlesztőtől**. A fejlesztő háromféleképpen reagálhat:

```
  AI: Szeretném módosítani a src/auth/login.ts fájlt.
      [Megmutatja a tervezett változtatást]

  Fejlesztő választhat:
  +--------------------------------------------+
  |  [y] Igen, engedélyezem                    |
  |  [n] Nem, ne csináld                       |
  |  [a] Igen, és innentől mindig engedélyezd  |
  |      az ilyen típusú műveletet             |
  +--------------------------------------------+
```

A fejlesztő tehát létrehozhat **szabályokat**: "A fájl szerkesztés mindig engedélyezett a `src/` könyvtárban, de a `config/` könyvtárban mindig kérdezzen." Vagy: "A `npm test` parancsot mindig futtathatja, de a `rm` (törlés) parancsot soha."

Ezek a szabályok a [Claude Code settings](https://code.claude.com/docs/en/settings) fájlban tárolódnak, és a csapat szintjén is beállíthatóak -- tehát a PM vagy a tech lead meghatározhatja, hogy az egész csapatnak mit szabad és mit nem.

**PM szemmel**: Az engedélyezési rendszer az, ami biztosítja, hogy az AI nem csinál semmi váratlan dolgot. A fejlesztő dönti el, mennyire "engedi szabadjára" az AI-t -- és bármikor vissza tudja vonni az engedélyeket. Ez olyan, mint amikor a gyakornoknak szólsz: "A kis feladatokat csináld meg egyedül, de a fontos dolgoknál kérj engedélyt."

## CLAUDE.md -- a projekt memóriája

Minden projektben lehet egy `CLAUDE.md` nevű fájl. Ez egy egyszerű szöveges fájl, amit a Claude Code **minden beszélgetés elején elolvas**. Ide kerülnek a projekt sajátos tudnivalói.

Gondolj rá úgy: amikor egy új kolléga érkezik a csapatba, az első héten átolvassa a belső dokumentációt, megismeri a konvenciókat, és megtanulja, hogyan működnek a dolgok. A `CLAUDE.md` pontosan ezt a "belső dokumentációt" biztosítja az AI számára -- de az AI **garantáltan el is olvassa**, minden egyes alkalommal.

A CLAUDE.md fájl több szinten is létezhet (a részletes szabályokat az Anthropic dokumentációja írja le: [CLAUDE.md](https://code.claude.com/docs/en/claude-md)):

```
  Projekt gyökér/
  |
  +-- CLAUDE.md              <-- A fő projekt szintű utasítások
  |
  +-- src/
  |   +-- CLAUDE.md          <-- Az src könyvtár sajátos szabályai
  |   +-- auth/
  |   |   +-- CLAUDE.md      <-- Az auth modul specifikus szabályai
  |   +-- api/
  |       +-- CLAUDE.md      <-- Az API modul specifikus szabályai
  |
  +-- tests/
      +-- CLAUDE.md          <-- Teszt írási konvenciók
```

Ez a hierarchikus rendszer lehetővé teszi, hogy különböző könyvtárakban különböző szabályok legyenek -- anélkül, hogy egyetlen hatalmas fájl lenne.

Lássunk egy realisztikus példát, hogyan néz ki egy valós projekt `CLAUDE.md` fájlja:

```
  +-------------- CLAUDE.md --------------------------------+
  |                                                         |
  |  # Projekt: WebShop Backend                             |
  |                                                         |
  |  ## Kód stílus                                         |
  |  - TypeScript strict mode-ban írunk                     |
  |  - Változókhoz camelCase-t használunk                   |
  |  - Függvényekhez egyértelmű, angol neveket adunk        |
  |  - Minden publikus függvényhez JSDoc kommentet írunk    |
  |                                                         |
  |  ## Architektúra                                       |
  |  - Backend: Express.js + TypeORM                        |
  |  - Adatbázis: PostgreSQL                                |
  |  - Cache: Redis                                         |
  |  - A src/services/ réteg tartalmazza az üzleti logikát  |
  |  - A src/controllers/ csak a HTTP kezelést végzi        |
  |                                                         |
  |  ## Tesztek                                             |
  |  - Teszt framework: Jest                                |
  |  - Futtatás: npm test                                   |
  |  - Minimum lefedettség: 80%                             |
  |  - Minden új feature-höz kell unit és integration teszt |
  |  - Mock-ot használunk külső API hívásokhoz              |
  |                                                         |
  |  ## Git konvenciók                                      |
  |  - Branch név: feature/JIRA-123-rövid-leírás            |
  |  - Commit üzenet: "feat: leírás" vagy "fix: leírás"    |
  |  - A main branch-re TILOS közvetlenül pusholni          |
  |  - Minden PR-hez kell legalább 1 approver               |
  |                                                         |
  |  ## Fontos szabályok                                    |
  |  - A .env fájlokat SOHA ne commitold                    |
  |  - Az adatbázis migrációkat kézzel kell futtatni        |
  |  - A /admin/* endpointokhoz mindig kell admin role      |
  |    ellenőrzés                                           |
  |  - Érzékeny adatokat (jelszó, token) SOHA ne logold     |
  |                                                         |
  |  ## Gyakori parancsok                                   |
  |  - Build: npm run build                                 |
  |  - Teszt: npm test                                      |
  |  - Lint: npm run lint                                   |
  |  - Dev szerver: npm run dev                             |
  |  - Migráció: npm run db:migrate                         |
  |                                                         |
  +---------------------------------------------------------+
```

**PM szemmel**: A CLAUDE.md hasonlít egy belső wiki oldalhoz, amit a fejlesztőknek írsz. Csak éppen nem embereknek szól, hanem az AI-nak. Ha eddig frusztráltad, hogy az új fejlesztő nem olvassa el a projekt konvenciókat -- az AI garantáltan elolvassa, minden egyes alkalommal.

Még egy fontos szempont: a CLAUDE.md **verziócontrollba** kerül (Git-ben tárolódik). Tehát a PM látja, ki mikor változtatta meg a szabályokat, és visszakövethető, hogyan fejlődött a projekt konfigurációja.

> *Bővebben: [CLAUDE.md dokumentáció](https://code.claude.com/docs/en/claude-md) -- példa fájlok, hierarchia, és advanced tippek.*

## Hookrendszer -- automatikus minőségbiztosítás

A hookrendszer (kampórendszer) lehetővé teszi, hogy bizonyos eseményekre automatikus műveleteket kössünk. Gondolj rá úgy, mint szabályokra, amik **mindig lefutnak**, emberi feledékenységtől függetlenül.

Például:

- **Fájl szerkesztés után** --> automatikusan lefut a kódformázó (linter)
- **Commit előtt** --> automatikusan lefutnak a tesztek
- **Bash parancs futtatásakor** --> ellenőrzi, hogy nem töröl-e fontos fájlokat
- **Session elején** --> betölti a korábbi tapasztalatokat (memória)
- **Session végén** --> elmenti a tanulságokat a következő session-höz

```
  Esemény                    Hook (automatikus akció)
  --------                   ------------------------
  AI fájlt szerkeszt    -->  Kódformázó lefut
  AI commitolni akar    -->  Tesztek lefutnak
  AI bash-t használ     -->  Biztonsági ellenőrzés
  Session indul         -->  Korábbi emlékek betöltése
  Session véget ér      -->  Tanulságok mentése
```

Lássunk két konkrét példát, hogy érthetőbb legyen, hogyan is működik ez a gyakorlatban:

**1. példa -- A kódformázó hook**

A csapatban megállapodás, hogy a kód mindig egységes formátumú legyen (pl. behúzások, sortörések, zárójelek). Amikor az AI módosít egy fájlt, automatikusan lefut a kódformázó:

```
  AI módosítja: src/auth/login.ts
       |
       v
  Hook aktiválódik: "prettier --write src/auth/login.ts"
       |
       v
  A fájl automatikusan formázva lesz
       |
       v
  AI látja az eredményt és tovább dolgozik
```

Ez biztosítja, hogy az AI által írt kód **mindig megfelel** a csapat formázási szabályainak -- anélkül, hogy bárki szólna neki.

**2. példa -- A biztonsági hook (amikor megakadályoz valamit)**

Tegyük fel, hogy a hookrendszerben van egy szabály: "A `rm -rf` parancsot soha ne futtasd a projekt gyökerében." Mi történik, ha az AI mégis megpróbálja?

```
  AI futtatni akarja: "rm -rf ./node_modules && npm install"
       |
       v
  Hook ellenőrzi a parancsot
       |
       v
  BLOKKOL! "A 'rm -rf' parancs nem engedélyezett
            a projekt gyökerében. Használd a
            'npm ci' parancsot ehelyett."
       |
       v
  AI megkapja az üzenetet, és másképp oldja meg:
  "npm ci"  (ami ugyanazt éri el, biztonságosan)
```

A hook tehát nem csak figyelmeztet -- **meg is akadályozza** a veszélyes műveletet, és általában alternatívát is javasol. Az AI megkapja a hook üzenetet, alkalmazkodik, és másképp oldja meg a feladatot.

**PM szemmel**: A hookrendszer az, ami biztosítja, hogy az AI betartsa a csapat szabályait. Nem kell bízni abban, hogy "emlékezni fog" -- a hookrendszer kikényszeríti. Ez olyan, mint egy automatikus minőség-ellenőrző sor egy gyárban: minden termék (változtatás) átmegy rajta, és ami nem felel meg, az nem megy tovább.

> *Részletek és konfigurációs példák: [Hooks guide](https://code.claude.com/docs/en/hooks-guide)*

## MCP -- az "USB-C" az AI alkalmazásoknak

Az MCP (Model Context Protocol -- Modell Kontextus Protokoll) egy nyílt szabvány, ami lehetővé teszi, hogy az AI eszközök **külső rendszerekhez** csatlakozzanak.

Gondolj rá úgy, mint az USB-C-re: ahogy az USB-C szabványos csatlakozást biztosít különböző elektronikai eszközök között, az MCP szabványos csatlakozást biztosít az AI és a külvilág között. Az MCP-t maga az Anthropic fejlesztette ki, és nyílt szabványként adta ki -- tehát bárki fejleszthet MCP szervereket, és bármely AI eszköz csatlakozhat hozzájuk. A teljes architektúra leírása elérhető: [MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture).

```
  +----------+     MCP      +------------------+
  |          |------------->| Google Drive      |
  |          |              +------------------+
  |          |     MCP      +------------------+
  |  Claude  |------------->| Jira / Notion    |
  |  Code    |              +------------------+
  |          |     MCP      +------------------+
  |          |------------->| Adatbázis        |
  |          |              +------------------+
  |          |     MCP      +------------------+
  |          |------------->| Figma / Design   |
  |          |              +------------------+
  |          |     MCP      +------------------+
  |          |------------->| Slack / Teams    |
  +----------+              +------------------+
```

Az MCP nélkül az AI csak a helyi fájlrendszert és a parancssort látja. MCP-vel viszont:

- Elolvashatja a Google Drive-on lévő követelményeket
- Megnézheti a Jira ticketeket
- Lekérdezheti az adatbázist
- Behúzhatja a Figma design-okat
- Üzenetet küldhet Slack-en

Lássunk két konkrét példát, hogyan néz ki ez a gyakorlatban:

**1. példa -- Jira integráció**

A fejlesztő azt mondja: *"Nézd meg a PROJ-456 Jira ticket-et és implementáld amit kér."*

MCP nélkül az AI nem tudná mit csinálni -- nincs hozzáférése a Jira-hoz. MCP-vel viszont:

```
  Fejlesztő: "Nézd meg a PROJ-456 ticketet és csináld meg"
       |
       v
  AI használja az MCP Jira eszközt:
  jira.get_issue("PROJ-456")
       |
       v
  Visszakapja:
  - Cím: "Kereső mező hozzáadása a termék listához"
  - Leírás: "Szöveges kereső mező kell a termék lista
    tetejére, ami név és kategória szerint szűr.
    Elfogadási kritérium: a keresés debounce-olt legyen
    (300ms), és üres állapotban minden terméket mutasson."
       |
       v
  AI implementálja a keresőt a specifikáció alapján
       |
       v
  AI frissíti a Jira ticketet: állapot -> "In Review"
```

**2. példa -- Adatbázis lekérdezés**

A fejlesztő hibát keres: *"A /users endpoint üres listát ad vissza. Nézd meg az adatbázisban, van-e egyáltalán felhasználó."*

```
  AI használja az MCP adatbázis eszközt:
  db.query("SELECT COUNT(*) FROM users")
       |
       v
  Eredmény: 15,234 felhasználó van az adatbázisban
       |
       v
  AI: "Az adatbázisban vannak felhasználók. A probléma
       nem az adatban van, hanem a lekérdezésben.
       Megvizsgálom az API kódot..."
```

**PM szemmel**: Az MCP teszi lehetővé, hogy az AI ne csak kódot írjon, hanem a teljes fejlesztési ökoszisztémában mozogjon. Ha a követelmények Google Docsban vannak, az AI onnan is el tudja olvasni. Ha a feladatok Jira-ban vannak, az AI közvetlenül onnan dolgozik. Ez csökkenti a "kontextus váltást" -- az AI nem kéri, hogy másold be a Jira ticketet, hanem maga olvassa el.

> *MCP bevezető és koncepció: [Model Context Protocol -- Introduction](https://modelcontextprotocol.io/introduction)*

## Subágensek -- párhuzamos munkavégzés

A Claude Code képes **több kisebb ágenst** (subágenst) indítani, amik párhuzamosan dolgoznak. Ez olyan, mintha a gyakornokod szólna 3 másik gyakornoknak, hogy "te nézd meg az adatbázist, te a frontend-et, te pedig futtasd a teszteket" -- és utána összefoglalná az eredményt.

```
  +---------------------------------------------+
  |            Fő Claude Code session            |
  |                                              |
  |    "Vizsgáld meg az auth, a db, és az API   |
  |     modult párhuzamosan"                     |
  |                                              |
  |    +-----------+ +----------+ +----------+  |
  |    | Subágens A| |Subágens B| |Subágens C|  |
  |    |  Auth     | |  DB      | |  API     |  |
  |    | vizsgálat | | vizsgálat| | vizsgálat|  |
  |    +-----+-----+ +----+-----+ +----+-----+  |
  |          |             |            |         |
  |          +-------------+------------+         |
  |                        |                      |
  |                   Összefoglalás               |
  |                                              |
  +---------------------------------------------+
```

Lássunk egy részletes példát arra, hogyan működik ez a gyakorlatban.

**Példa: Biztonsági audit**

A fejlesztő azt mondja: *"Vizsgáld át a projekt biztonságát: az authentikációt, az SQL lekérdezéseket, és a környezeti változók kezelését."*

A fő ágens három subágenst indít:

```
  Fő ágens: "Biztonsági audit -- 3 területet kell átvizsgálni"
       |
       +---> Subágens A: Autentikáció vizsgálat
       |     - Beolvassa az auth/ könyvtár összes fájlját
       |     - Ellenőrzi a jelszó hash-elést (bcrypt? salt?)
       |     - Megvizsgálja a session kezelést
       |     - Keresi a hard-coded tokeneket
       |     - Eredmény: "A jelszó hash-elés rendben (bcrypt),
       |       de a session token nem jár le soha -- javítandó."
       |
       +---> Subágens B: SQL injection vizsgálat
       |     - Megkeresi az összes adatbázis lekérdezést
       |     - Ellenőrzi, hogy mindenhol paraméterezett
       |       lekérdezéseket használnak-e (nem string concat.)
       |     - Eredmény: "2 helyen raw SQL van paraméterezés
       |       nélkül: src/reports/export.ts és
       |       src/admin/search.ts -- kritikus."
       |
       +---> Subágens C: Környezeti változók vizsgálat
             - Ellenőrzi a .env.example fájlt
             - Keresi a hard-coded jelszavakat és API kulcsokat
             - Megvizsgálja, hogy a .env a .gitignore-ban van-e
             - Eredmény: "A .env a .gitignore-ban van (rendben),
               de a src/config/stripe.ts-ben hard-coded test
               API kulcs van -- javítandó."

  Fő ágens összefoglal:
  "Biztonsági audit eredménye:
   - KRITIKUS: 2 SQL injection sebezhetőség
   - FONTOS: Session token nem jár le
   - FONTOS: Hard-coded Stripe API kulcs
   - RENDBEN: Jelszó hash-elés, .env kezelés
   Javítsam a kritikus problémákat?"
```

Miért fontos a subágensek használata?

- **Sebesség**: 3 párhuzamos vizsgálat gyorsabb, mint 3 egymás utáni. A fenti audit 3 perc alatt lefut, nem 9 perc alatt.
- **Kontextus védelem**: Minden subágens a saját ablakában dolgozik, nem terheli a fő beszélgetést. A fő ágens kontextusa tiszta marad az összefoglaláshoz.
- **Specializáció**: Minden subágens más feladatra optimalizálható -- más utasításokat kap, más fájlokat lát.
- **Megbízhatóság**: Ha egy subágens elakad, a többi tovább dolgozik.

> *Bővebben: [Sub-agents dokumentáció](https://code.claude.com/docs/en/sub-agents) -- architektúra, konfiguráció, és advanced használati minták.*

## GitHub Actions -- AI a CI/CD folyamatban

Az eddigi példákban a Claude Code mindig a fejlesztő gépén futott, a fejlesztő felügyelete mellett. De mi van, ha az AI-t be akarjuk építeni az **automatizált fejlesztési folyamatba** -- hogy emberi beavatkozás nélkül is dolgozzon?

Erre való a [Claude Code GitHub Actions](https://code.claude.com/docs/en/github-actions) integráció. Ez lehetővé teszi, hogy a Claude Code **automatikusan reagáljon** GitHub eseményekre:

```
  GitHub esemény              Claude Code reakció
  ----------------            ---------------------
  Új issue nyílik        -->  AI elemzi és címkézi a hibajegyet
  PR nyílik              -->  AI code review-t végez
  PR-re komment érkezik  -->  AI válaszol / javít
  Label hozzáadva        -->  AI implementálja a feature-t
```

**Példa: Automatikus code review**

Képzelj el egy munkafolyamatot, ahol minden pull request automatikusan kap egy AI review-t:

```
  1. Fejlesztő megnyitja a PR-t: "Add search functionality"
       |
       v
  2. GitHub Actions elindítja a Claude Code-ot
       |
       v
  3. AI áttekinti a PR-ben lévő összes változtatást
       |
       v
  4. AI kommentet ír a PR-re:

     "Code Review Összefoglalás:

     Általános: A keresési funkcionalitás jól strukturált.

     Észrevételeim:
     - src/search.ts:42 -- A keresési lekérdezésben nincs
       index a 'name' mezőn. Nagy adatbázisnál ez lassú
       lesz. Javaslom egy index létrehozását.
     - src/search.ts:67 -- A felhasználói input nincs
       sanitizálva -- XSS kockázat.
     - tests/search.test.ts -- Hiányoznak az üres input
       és a speciális karakterek tesztesetei."
```

**Példa: Issue-ből automatikus implementáció**

Még érdekesebb: a Claude Code képes **GitHub issue-ból automatikusan PR-t csinálni**:

```
  1. PM létrehoz egy issue-t: "A láblécből hiányzik a
     copyright évszám"
       |
       v
  2. Valaki hozzáadja a "claude" labelt
       |
       v
  3. GitHub Actions elindítja a Claude Code-ot
       |
       v
  4. AI elolvassa az issue-t, megkeresi a releváns fájlokat,
     elvégzi a változtatást, és megnyit egy PR-t:
     "fix: add copyright year to footer"
       |
       v
  5. A PR-t egy ember review-olja és mergeli
```

**PM szemmel**: A GitHub Actions integráció az, ami lehetővé teszi, hogy az AI ne csak "kérésre" dolgozzon, hanem **automatikusan reagáljon** a fejlesztési folyamat eseményeire. Ez különösen hasznos rutinfeladatoknál: code review, egyszerűbb bugfixek, dokumentáció frissítés. Az ember pedig a fontos döntésekre összpontosíthat.

## Egy konkrét példa: bugfix a gyakorlatban

Lássunk egy valós forgatókönyvet, lépésről lépésre, részletesen. A fejlesztő reggel megnyitja a terminált:

```
  Fejlesztő:  "A felhasználók azt jelentik, hogy a jelszó-
               visszaállítás nem működik timeout hibával.
               Javítsd ki és írj rá tesztet."
```

Most követjük, mit csinál az AI, minden egyes lépést:

```
  [1. lépés -- Keresés]
  AI gondolkodik: "Jelszó visszaállítás... Keresem a releváns
                   fájlokat."
  AI használja: Grep("password-reset" VAGY "passwordReset")

  Találatok:
    src/auth/password-reset.ts
    src/auth/password-reset.service.ts
    src/email/templates/password-reset.html
    tests/auth/password-reset.test.ts

  [2. lépés -- Olvasás]
  AI használja: Read(src/auth/password-reset.ts)

  Látja a kódot:
    async function resetPassword(email: string) {
      const user = await findUser(email);
      const token = generateToken();
      await sendEmail(email, token, { timeout: 5000 });
      //                              ^^^^^^^^^^^^^^^
      //   AI észreveszi: 5000ms = 5 másodperc timeout
      await saveToken(user.id, token);
    }

  [3. lépés -- Elemzés]
  AI gondolkodik: "5 másodperces timeout az email küldésre.
                   Az SMTP szerverek általában 10-30 másodperc
                   alatt válaszolnak. Ez túl rövid. De nézzük
                   meg a service fájlt is, hátha ott is van
                   hasonló."

  AI használja: Read(src/auth/password-reset.service.ts)

  Találat: itt is van egy 5000-es timeout az email
  verifikálásnál.

  [4. lépés -- Javítás]
  AI használja: Edit(src/auth/password-reset.ts)
    timeout: 5000  -->  timeout: 30000

  AI használja: Edit(src/auth/password-reset.service.ts)
    timeout: 5000  -->  timeout: 30000

  [5. lépés -- Teszt írás]
  AI használja: Write(tests/auth/password-reset-timeout.test.ts)

    describe('Password Reset Timeout', () => {
      it('should handle slow SMTP server', async () => {
        // Szimulál egy lassú SMTP szervert (15 másodperc)
        mockSmtp.setDelay(15000);
        const result = await resetPassword('user@test.com');
        expect(result.success).toBe(true);
      });

      it('should timeout after 30 seconds', async () => {
        // Szimulál egy nagyon lassú szervert (35 másodperc)
        mockSmtp.setDelay(35000);
        await expect(resetPassword('user@test.com'))
          .rejects.toThrow('timeout');
      });
    });

  [6. lépés -- Teszt futtatás]
  AI használja: Bash("npm test -- --grep password-reset")

  Eredmény:
    PASS tests/auth/password-reset.test.ts (8 teszt)
    PASS tests/auth/password-reset-timeout.test.ts (2 teszt)
    FAIL tests/email/email-service.test.ts
      > "Expected timeout to be 5000 but got 30000"

  [7. lépés -- Újabb javítás]
  AI gondolkodik: "Van egy teszt ami az 5 másodperces
                   timeout-ot várta. Frissítenem kell."

  AI használja: Read(tests/email/email-service.test.ts)
  AI használja: Edit(tests/email/email-service.test.ts)
    expect(config.timeout).toBe(5000)
    -->
    expect(config.timeout).toBe(30000)

  [8. lépés -- Végső ellenőrzés]
  AI használja: Bash("npm test")

  Eredmény:
    47 passing (12s)
    0 failing

  [9. lépés -- Jelentés]
  AI: "Kész. A javítás összefoglalása:

       Probléma: Az email küldés 5 másodperces timeout-ot
       használt, ami túl rövid volt az SMTP szervernek.

       Javítás:
       - src/auth/password-reset.ts: timeout 5s --> 30s
       - src/auth/password-reset.service.ts: timeout 5s --> 30s
       - tests/email/email-service.test.ts: timeout assert
         frissítése

       Új tesztek:
       - tests/auth/password-reset-timeout.test.ts:
         2 új teszt eset (lassú szerver + timeout)

       Összes teszt: 47/47 átment.
       Commitoljam?"
```

A fejlesztő átnézi a változtatásokat, jóváhagyja, és a Claude Code commitol. Az egész **3-5 perc** volt, amihez egy ember 30-60 percet ülne.

Fontos: a fejlesztő végig látta, mit csinál az AI. Nem kellett vakon bíznia benne -- minden lépés látható, és bármikor közbe tudott volna lépni. Ez a "human-in-the-loop" elv: az AI dolgozik, de az ember felügyel.

## Tippek a hatékony használathoz

Az Anthropic összegyűjtötte a [Claude Code best practices](https://code.claude.com/docs/en/best-practices) oldalon a legfontosabb tippeket. Íme a PM számára relevánsak:

**1. Pontos utasítások adása**

Minél pontosabb az utasítás, annál jobb az eredmény:

```
  Rossz:  "Javítsd meg a login-t"
  Jó:     "A login oldalon a 'Password' mező nem fogad el
           speciális karaktereket (pl. @, #). Javítsd ki,
           és írj tesztet ami ellenőrzi a speciális
           karakterek működését."
```

**2. A CLAUDE.md karbantartása**

Ha a csapat új konvenciót vezet be, az kerüljön be a CLAUDE.md-be is. Különben az AI a régi szabályok szerint fog dolgozni.

**3. Kis, jól definiált feladatok**

Az AI jobban teljesít, ha egy feladatot kap, nem tízet egyszerre:

```
  Rossz:  "Csináld meg az egész user management modult"
  Jó:     "Csinálj egy GET /users endpoint-ot, ami
           paginált listát ad vissza, maximum 50 elem/oldal"
```

**4. Az eredmény ellenőrzése**

Bármennyire is jó az AI, az emberi review elengedhetetlen. A PM feladata biztosítani, hogy **minden AI által írt kód** átmenjen code review-n -- pont úgy, mint egy emberi fejlesztő kódja.

> *További tippek: [Claude Code best practices](https://code.claude.com/docs/en/best-practices) -- kontextus kezelés, prompt stratégiák, és advanced technikák.*
>
> *Az Anthropic YouTube csatornáján demókat és tutorialokat találsz: [youtube.com/@AnthropicAI](https://www.youtube.com/@AnthropicAI)*

## Összefoglalva

| Fogalom | Mit jelent PM-nek |
|---------|-------------------|
| Claude Code | AI fejlesztő eszköz, ami fájlokat szerkeszt, tesztel, commitol |
| Agentic loop | Automatikus ciklus: gondol --> cselekszik --> ellenőriz |
| Eszközök (tools) | Konkrét képességek: olvasás, írás, keresés, futtatás |
| Engedélyezési rendszer | A fejlesztő kontrollálja mit csinálhat az AI |
| CLAUDE.md | Projekt szabályok amit az AI mindig betart |
| Hookrendszer | Automatikus minőség-ellenőrzés minden lépésnél |
| MCP | Az AI csatlakozhat Jira-hoz, Google Docs-hoz, stb. |
| Subágensek | Több AI dolgozik párhuzamosan, majd összegez |
| GitHub Actions | Az AI automatikusan reagál GitHub eseményekre |

\begin{kulcsuzenat}
A Claude Code nem ChatGPT, ahová kódot másolsz. Ez egy teljes fejlesztőkörnyezetben dolgozó ágens, ami fájlokat szerkeszt, teszteket futtat, és commitol -- a fejlesztő felügyeletével. Mint PM, nem a kódot kell értened, hanem a munkafolyamatot: az AI önállóan dolgozik, de az ember felügyel és dönt. Az engedélyezési rendszer, a hookrendszer, és a CLAUDE.md együtt biztosítják, hogy az AI a csapat szabályai szerint dolgozzon. A GitHub Actions integráció pedig lehetővé teszi, hogy az AI a CI/CD folyamatban is részt vegyen -- automatikus code review-tól az egyszerű bugfixekig.
\end{kulcsuzenat}
