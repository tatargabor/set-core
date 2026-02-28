# Függelék

## A. Szószedet

| Angol kifejezés | Magyar jelentés | Rövid leírás |
|----------------|-----------------|--------------|
| **A/B Testing** | A/B tesztelés | Két (vagy több) változat párhuzamos tesztelése valós felhasználókkal, hogy mérhető legyen, melyik működik jobban. A PM számára fontos, mert adatalapúvá teszi a döntéshozatalt. |
| **Agent / Ágens** | Ágens, ügynök | AI rendszer ami önállóan cselekszik: fájlokat olvas, kódot ír, parancsokat futtat. Nem csak válaszol, hanem csinálja is amit kell -- ez különbözteti meg egy egyszerű chatbottól. |
| **Agentic Loop** | Ágentikus ciklus | Az AI gondolkodási ciklusa: tervez -> cselekszik -> ellenőriz -> ismétli. Addig fut, amíg a feladat kész nincs. Általában látod a terminálban, ahogy "gondolkodik". |
| **API** | Alkalmazás-programozási felület | Szabványos mód, ahogy szoftverek egymással kommunikálnak. Gondolj rá úgy, mint egy étterem rendelő ablakára: beküldöd a kérést, visszakapod az eredményt. |
| **Artifact** | Műtermék, termék | Az OpenSpec-ben: egy dokumentum (proposal, spec, design, tasks). Minden openspec változásnak megvannak a maga artifact-jai. |
| **Blue-Green Deployment** | Kék-zöld telepítés | Két azonos éles környezet közötti kapcsolás: az egyiken fut az aktuális verzió (kék), a másikra telepíted az újat (zöld), majd átkapcsolod a forgalmat. Ha valami elromlik, egyetlen kattintással vissza tudsz állni. |
| **Branch** | Ág, elágazás | A kód egy párhuzamos verziója amiben valaki dolgozik. Mint egy dokumentum másolata, amiben szabadon változtathatsz anélkül, hogy az eredetit elrontanád. |
| **CI/CD** | Folyamatos integráció és szállítás | Automatikus rendszer ami minden kódváltoztatás után teszteket futtat (CI), és ha minden zöld, automatikusan telepíti az élesbe (CD). A fejlesztés "szállítószalagja". |
| **CLI** | Parancssori felület | Szöveges felület ahol parancsokat írsz (terminál). Nincs grafikus gomb, mindent gépeléssel irányítasz. A Claude Code is így működik. |
| **Code Coverage** | Kódlefedettség | Százalékos mérőeszköz: a tesztek a kód hány százalékát "fedik le", azaz tesztelik. 80% felett általában jó -- de a szám önmagában nem garantálja a minőséget. |
| **Commit** | Mentési pont | Egy változtatáscsomag elmentése a verziókezelőbe. Minden commit kap egy egyedi azonosítót és egy üzenetet, ami leírja, mit változtattunk. |
| **Context Window** | Kontextus ablak | Az AI munkamemóriája -- amennyit egyszerre kezelni tud. Ha túl sok információt adsz neki, a régebbi részeket "elfelejti". Claude-nál ez jelenleg ~200 000 token. |
| **DAG** | Irányított körmentes gráf | Függőségi térkép: mi függ mitől (orchestrációnál). Biztosítja, hogy a feladatok helyes sorrendben fussanak. |
| **Deploy** | Telepítés, élesítés | A kód feltöltése az éles szerverre, ahol a valós felhasználók hozzáférnek. |
| **Design** | Tervezési dokumentum | Technikai döntéseket rögzítő dokumentum. Az OpenSpec-ben a "hogyan?" kérdésre válaszol. |
| **Docker** | Docker konténer-technológia | Egy technológia ami a szoftvert és minden függőségét egy "dobozba" (konténerbe) csomagolja. Így garantáltan ugyanúgy fut mindenhol -- a fejlesztő gépén, a teszt szerveren és az élesben is. |
| **Feature Flag** | Funkció-kapcsoló | Olyan kapcsoló a kódban, amivel egy új funkcióváltozatot be- vagy kikapcsolhatsz anélkül, hogy újra kellene telepíteni. PM-ként fontos: fokozatos bevezetésnél használják (pl. először csak 5% látja az új funkcióváltozatot). |
| **Git** | Git verziókezelő | A legelterjedtebb kód-verziókövető rendszer. A kódot és annak teljes történetét tárolja. Gyakorlatilag minden modern szoftverprojekt használja. |
| **GraphQL** | GraphQL lekérdező nyelv | Modernebb alternatíva a REST API-hoz. A kliens pontosan megmondhatja, milyen adatokat kér -- se többet, se kevesebbet. A Facebook fejlesztette. |
| **Hallucination** | Hallucináció | Amikor az AI magabiztosan állít olyasmit, ami nem igaz. Nem "hazudik" szándékosan -- a statisztikai mintaillesztés néha hibás eredményt ad. Ezért fontos az emberi ellenőrzés. |
| **Hook** | Kampó, automatizmus | Automatikus művelet ami egy eseményre reagál. Például: "minden commit előtt futtasd le a teszteket." |
| **IDE** | Integrált fejlesztőkörnyezet | Szoftver amiben a fejlesztők dolgoznak (pl. VS Code, JetBrains). Szövegszerkesztőnél jóval több: szín-kiemelést, hibakeresést és külső eszközöket is ad. |
| **Kubernetes** | Kubernetes (K8s) konténer-orchestráció | Rendszer ami Docker konténereket kezel nagy léptékben: automatikusan indít, leállít és skáláz. Ha a Docker a "doboz", a Kubernetes a "raktárvezető" aki eldönti, hova, hányat és mikor. |
| **Linter** | Kódstílus-ellenőrző | Automatikus eszköz ami a kód formai és stilusbeli hibáit jelzi (pl. hiányzó pontosvessző, nem konzisztens névkonvenció). Nem a működését vizsgálja, hanem az olvashatóságát és az egységességét. |
| **LLM** | Nagy nyelvi modell | Az AI motor ami a szöveget érti és generálja. A Claude, a GPT és a Gemini mind LLM-ek. Hatalmas mennyiségű szövegen tanultak, ezért értik a kontextust. |
| **MCP** | Modell Kontextus Protokoll | Szabvány az AI és külső eszközök összekapcsolására. Az MCP "USB-csatlakozóként" működik az AI világban: egységes módot ad arra, hogy az AI külső adatforrásokhoz és eszközökhöz kapcsolódjon. |
| **Merge** | Beolvasztás, összefésülés | Két kódverzió egyesítése. Néha konfliktus keletkezik, ha ugyanazt a sort ketten változtatták -- ilyenkor valakinek kézzel kell döntenie. |
| **Microservices** | Mikroszolgáltatások | Architektúrális megközelítés, ahol a szoftvert sok kis, független szolgáltatásra bontják (pl. felhasználókezelés, fizetés, értesítések külön-külön). Előnye: egymásra váró csapatok nélkül lehet fejleszteni. Hátránya: összetettebb üzemeltetés. |
| **Monorepo** | Monorepo | Egyetlen, közös Git repository amiben a projekt összes komponense él (frontend, backend, közös könyvtárak). Előnye: egyszerű függőségkezelés. Hátránya: nagyon nagy tud lenni. |
| **Orchestration** | Orchestráció, karmesterség | Több AI ágens koordinált, párhuzamos futtatása. Mint egy karmester aki vezényel: elosztja a feladatokat, figyeli a haladást, és összefogja a végeredményt. |
| **Pipeline** | Csővezeték, munkafolyamat | Lépések sorozata egy cél elérésére. A CI/CD pipeline például: tesztel -> építés -> telepítés. |
| **Production** | Éles környezet | A szoftver azon verziója amit a felhasználók használnak. Ha "prodba mentünk" -- a felhasználók már látják az új verzióváltozatot. |
| **Prompt** | Utasítás, kérés | Az AI-nak adott szöveges utasítás. A prompt minősége alapvetően meghatározza a válasz minőségét -- ezért mondják: "garbage in, garbage out". |
| **Proposal** | Javaslat | "Mit és miért?" dokumentum az OpenSpec-ben. A PM legfontosabb eszköze: itt lehet emberi nyelven megfogalmazni, mit szeretnénk. |
| **PR / Pull Request** | Beolvasztási kérelem | Kérés hogy a változtatásaid kerüljenek be a fő kódba. A fejlesztő (vagy az AI) "bemutatja" a munkáját, mások átnézik és jóváhagyják. |
| **Refactoring** | Refaktorálás, átrendezés | A kód belső szerkezetének javítása a működés változtatása nélkül. Mint egy lakásban a bútor átrendezése: ugyanazok a bútorok, de használhatóbb az elrendezés. A PM számára azért fontos, mert általában nincs látható eredménye, de hosszú távon felgyorsítja a fejlesztést. |
| **REST API** | REST API | A legelterjedtebb mód ahogy webes rendszerek kommunikálnak egymással. Egyszerűen: URL-ekre küld kéréseket (GET, POST, PUT, DELETE) és JSON formátumban kap adatokat vissza. |
| **Retrospective** | Retrospektív | Sprint végi megbeszélés ahol a csapat átnézi, mi ment jól, mi nem, és min kellene javítani. A PM egyik legfontosabb eszköze a folyamatos javuláshoz. |
| **Review** | Áttekintés, ellenőrzés | Kód vagy dokumentum felülvizsgálata. Az AI korszakban kiemelt fontosságú, mert az AI által írt kódot is ugyanúgy át kell nézni. |
| **Rollback** | Visszaállás, visszagörgetés | Az előző verzió visszaállítása, ha az új hibás. Mint egy "Ctrl+Z" az egész rendszerre. Ezért fontos, hogy minden deploy visszaállítható legyen. |
| **Ralph Loop** | Ralph ciklus | Autonóm munkaciklus ahol az AI ismétlődően dolgozik feladatokon. A wt-tools saját fogalma. |
| **Sandbox** | Homokozó | Elszigetelt környezet ahol az AI biztonságosan futtathat parancsokat. Nem fér hozzá a rendszer többi részéhez. |
| **Session** | Munkamenet | Egy beszélgetés/munkaszakasz az AI-val. Amikor elindítod a `claude` parancsot és bezárod -- ez egy session. |
| **Spec / Specification** | Specifikáció | Pontos, mérhető követelményeket leíró dokumentum. Az OpenSpec-ben a "mit, pontosan?" kérdésre válaszol. |
| **Spec-Driven** | Specifikáció-vezérelt | Fejlesztési megközelítés ahol minden a specifikációból indul. Először leírod mit akarsz, aztán az AI megvalósítja. |
| **Sprint** | Sprint | Általában 1-2 hetes fejlesztési ciklus a Scrum módszertanban. A sprint elején tervezel, a végén demózol és retrospektívet tartasz. |
| **Standup** | Napi gyorsegyeztetés | Rövid (általában 15 perces) napi megbeszélés ahol mindenki három kérdésre válaszol: mit csináltam tegnap? Mit fogok csinálni ma? Van-e akadály? Az AI korszakban érdemes kiegészíteni: "Mit delegáltam AI-nak?" |
| **Subagent** | Alágens | Kisebb, specializált AI ami a fő ágens irányítása alatt dolgozik. Az orchestrációban az egyes feladatokat ezek végzik. |
| **Task** | Feladat | Egy konkrét, elvégzendő munkadarab. Az OpenSpec-ben: egy checkbox a tasks.md-ben. |
| **Technical Debt** | Technikai adósság | Olyan technikai megoldások, amik most működnek, de hosszú távon problémát okoznak. Mint egy lakáshitel: most beköltözhetsz, de a törlesztést fizetned kell. Ha túl sok technikai adósság gyűlik fel, a fejlesztés drasztikusan lelassul. |
| **Token** | Token | Az AI szövegfeldolgozási egysége (~0.75 szó angolul, magyarul több token esik egy szóra). A költség és a kontextusablak mérete tokenben mérhető. |
| **TypeScript** | TypeScript | A JavaScript típusos bővítménye. A legtöbb modern webes projektet TypeScript-ben írják, mert a típusok segítenek a hibák korai felismerésében. |
| **Vibe Coding** | Hangulat-kódolás | AI-val való informális, tervezés nélküli kódolás. Gyors prototípusokra jó, éles projektekre kockázatos. |
| **Worktree** | Munkafa | A git egy funkciója: egy repo több példánya a lemezen. Az orchestráció ezeket használja, hogy több AI ágens párhuzamosan, egymás zavarása nélkül dolgozhasson. |

## B. Linkgyűjtemény

### Anthropic és Claude Code

| Link | Leírás |
|------|--------|
| [code.claude.com/docs](https://code.claude.com/docs/en/overview) | Claude Code hivatalos dokumentáció |
| [Claude Code Best Practices](https://code.claude.com/docs/en/best-practices) | Bevált gyakorlatok Claude Code használatához |
| [Claude Code Hooks](https://code.claude.com/docs/en/hooks-guide) | Hook rendszer útmutató |
| [Claude Code Sub-agents](https://code.claude.com/docs/en/sub-agents) | Subágensek használata |
| [CLAUDE.md dokumentáció](https://code.claude.com/docs/en/claude-md) | Projekt memória fájl |
| [claude.ai](https://claude.ai) | Claude AI webes felület -- telepítés nélkül kipróbálható |
| [anthropic.com](https://www.anthropic.com) | Anthropic cég honlapja |
| [Anthropic árazás](https://www.anthropic.com/pricing) | Előfizetési csomagok és árak |

### MCP (Model Context Protocol)

| Link | Leírás |
|------|--------|
| [modelcontextprotocol.io](https://modelcontextprotocol.io/introduction) | MCP bevezető -- mi ez és miért fontos |
| [MCP dokumentáció](https://modelcontextprotocol.io/docs/learn/architecture) | Architektúra és működés |
| [MCP specifikáció](https://modelcontextprotocol.io/) | A teljes MCP szabvány -- referenciadokumentáció |

### Kutatás és benchmarkok

| Link | Leírás |
|------|--------|
| [SWE-bench kutatás](https://www.anthropic.com/research/swe-bench-sonnet) | Claude teljesítménye valós hibák javításában |
| [SWE-bench weboldal](https://www.swebench.com/) | A szoftverfejlesztési benchmark hivatalos oldala |

### Iparági eszközök

| Link | Leírás |
|------|--------|
| [GitHub Copilot](https://github.com/features/copilot) | Microsoft/GitHub AI kódolási eszköz |
| [Cursor](https://cursor.com) | AI-natív kódszerkesztő |
| [Devin](https://devin.ai) | Cognition Labs autonóm AI fejlesztő |

### Blogok és cikkek

| Link | Leírás |
|------|--------|
| [Simon Willison blogja](https://simonwillison.net/) | Az egyik legjobb forrás AI-támogatott fejlesztésről. Willison a Django framework egyik megalkotója, és rendszeresen ír arról, hogyan használja az LLM-eket a mindennapi munkában. |
| [Martin Fowler](https://martinfowler.com/) | A szoftverarchitektúra és a clean code guruja. A "Refactoring" könyv szerzője. Az oldalán található cikkek segítenek megérteni, mit jelent a "jó kód" -- ami azért fontos, mert az AI-nak is jó kódot kell írnia. |
| [Kent Beck: Tidy First?](https://tidyfirst.substack.com/) | Kent Beck (az Extreme Programming megalkotója) Substack-je arról, hogyan érdemes a kódot kis lépésekben rendbe tenni. PM-ként azért érdekes, mert segít megérteni, miért kérnek a fejlesztők "refaktorálási időt". |
| [Addy Osmani blogja](https://addyosmani.com/blog/) | A Google mérnökségi vezetője a Chrome csapatnál. Fejlesztői produktivitásról és AI eszközök hatékonyságáról ír -- PM szemmel is emészthető stílusban. |

### YouTube csatornák

| Link | Leírás |
|------|--------|
| [Anthropic](https://www.youtube.com/@AnthropicAI) | Az Anthropic hivatalos csatornája: termékbemutatók, kutatási eredmények és interjúk. Elsőkézből kapott információ a Claude fejlődéséről. |
| [Fireship](https://www.youtube.com/@Fireship) | Rövid (2-5 perces), lényegretörő tech videók. Ha gyorsan meg akarsz érteni egy technológiát (Docker, Kubernetes, TypeScript), itt 5 perc alatt megkapod a lényeget. |
| [Two Minute Papers](https://www.youtube.com/@TwoMinutePapers) | Akadémiai AI kutatásokat magyaráz el közérthetően, vizuálisan. "What a time to be alive!" -- a jelmondata. Kitűnő ahhoz, hogy a PM értse, mi történik az AI kutatás élén. |
| [3Blue1Brown](https://www.youtube.com/@3blue1brown) | Vizuális matematikai és AI magyarázatok. Ha meg akarod érteni, hogyan működik belülről egy neurális háló -- itt a legjobb helyen jársz. Nem kell hozzá matematikusnak lenni. |
| [TechWorld with Nana](https://www.youtube.com/@TechWorldwithNana) | DevOps fogalmak érthetően: Docker, Kubernetes, CI/CD, cloud. Ha a fejlesztőcsapat ezekről beszél és te nem érted -- ez a csatorna segít. |

### Podcastok

| Link | Leírás |
|------|--------|
| [Lex Fridman Podcast](https://lexfridman.com/podcast/) | Hosszú, mélységű interjúk AI kutatóktól, CEO-któl és gondolkodóktól. Hallható benne Sam Altman, Dario Amodei (Anthropic CEO), Elon Musk és mások. Utazásra, futásra ideális. |
| [Hard Fork (New York Times)](https://www.nytimes.com/column/hard-fork) | Kevin Roose és Casey Newton heti tech podcastja. Közérthető, szórakoztató, és mindig a legaktuálisabb tech híreket tárgyalja -- PM-ként ezzel "képben" maradsz a tech világról. |
| [Latent Space](https://www.latent.space/) | AI engineering podcast. Kicsit technikusabb, de ha egy PM komolyabban szeretné érteni az AI infrastruktúrát és eszközöket, ez a legjobb forrás. |

### Közösségek és tanulás

| Link | Leírás |
|------|--------|
| [Anthropic Discord](https://discord.gg/anthropic) | Hivatalos Anthropic Discord szerver -- itt kérdezni tudsz, és megtudod mások tapasztalatait Claude Code-dal. |
| [r/ClaudeAI (Reddit)](https://www.reddit.com/r/ClaudeAI/) | Reddit közösség Claude felhasználóknak. Tippek, tapasztalatok, hibajelentések és workaround-ok. |
| [Hacker News](https://news.ycombinator.com/) | A tech világ "hírportálja" -- itt jelenik meg először a legtöbb fontos tech hír és diskurzus. Magas színvonalú hozzászólások. |

### Szabványok és szabályozás

| Link | Leírás |
|------|--------|
| [EU AI Act](https://artificialintelligenceact.eu/) | Az Európai Unió mesterséges intelligencia szabályozása. PM-ként fontos ismerni, mert befolyásolja, hogyan és milyen AI eszközöket használhatsz üzleti környezetben. |
| [MCP specifikáció](https://modelcontextprotocol.io/) | A Model Context Protocol teljes specifikációja. |

### Iparági jelentések és kutatások

| Link | Leírás |
|------|--------|
| [McKinsey Digital](https://www.mckinsey.com/capabilities/mckinsey-digital/our-insights) | A McKinsey digitalizációs és AI elemzései. Üzleti döntéshozó szemmel írt jelentések arról, hogyan változtatja az AI az ipart -- prezentációkhoz és üzleti esetek alátámasztásához ideális. |
| [Gartner AI kutatások](https://www.gartner.com/en/topics/artificial-intelligence) | Gartner AI elemzései és előrejelzései. A "Hype Cycle" diagram különösen hasznos: megmutatja, hol tart egy-egy technológia az érési görbén. |
| [Stack Overflow Developer Survey](https://survey.stackoverflow.co/) | Éves fejlesztői felmérés: milyen eszközöket használnak, mennyit keresnek, és hogyan látják az AI-t. Adatokkal alátámasztja az érdemi vitákat -- ahelyett, hogy "szerintem" legyen az érv. |

## C. "Kipróbálom" -- Quick Start

### Ha nem akarsz semmit telepíteni

A legegyszerűbb mód a Claude kipróbálására a webes felület:

1. Menj a [claude.ai](https://claude.ai) oldalra
2. Regisztrálj egy ingyenes fiókot
3. Kezdj el beszélgetni

Ez nem ugyanaz, mint a Claude Code (nem fér hozzá a fájljaidhoz, nem futtat parancsokat), de kipróbálhatod rajta az AI gondolkodásmódját, prompt-írást, és dokumentumok elemzését. PM munkára (emailek fogalmazása, összefoglalók, brainstorming) már ez is hasznos.

### Ha szeretnéd kipróbálni a Claude Code-ot

A Claude Code a parancssori eszköz, ami hozzáfér a fájljaidhoz és önállóan dolgozik. Ez a "valós" ágentikus élmény.

#### 1. lépés: Telepítés (2 perc)

Nyiss egy terminált (Mac: Terminal.app, Windows: PowerShell, Linux: bármilyen terminál) és futtasd:

**Mac / Linux:**
```
curl -fsSL https://claude.ai/install.sh | bash
```

**Windows PowerShell:**
```
irm https://claude.ai/install.ps1 | iex
```

**Mire számíts:** A telepítő letölt egy binárist és hozzáadja a rendszer PATH-jához. Nem kell hozzá admin jog. Ha a terminál nem ismeri fel a `claude` parancsot a telepítés után, zárd be és nyisd újra a terminált.

#### 2. lépés: Bejelentkezés

```
claude
```

Az első indításnál a böngészőben bejelentkezel a Claude fiókodba. Szükséged lesz fizetős előfizetésre (lásd lentebb az árazást).

**Mire számíts:** Megnyílik egy böngészőfül ahol bejelentkezhetsz. Utána a terminál visszajelzi, hogy sikeres volt a bejelentkezés.

#### 3. lépés: Próbáld ki egy projekten

Navigálj egy meglévő projektbe és indítsd el:

```
cd a-te-projekted
claude
```

**Mire számíts:** Az AI először "körülnéz" -- megnézi a fájlstruktúrát, a README-t, és megpróbálja megérteni a projektet. Ez az első alkalommal néhány másodpercbe telhet.

#### 4. lépés: Első parancsok

Próbáld ki ezeket:

```
"Magyarázd el, mit csinál ez a projekt"

"Keress hibákat a kódban"

"Írj teszteket a fő funkcióhoz"

"Javítsd ki a legfontosabb hibát amit találtál"
```

**Mire számíts:** Az AI olvasni fogja a fájlokat, gondolkodik (látni fogod a "thinking" állapotot), majd válaszol vagy csinál valamit. Az első kérdés után általában 10-30 másodperc múlva jön a válasz, a bonyolultabb feladatoknál akár percekig is dolgozhat.

#### 5. lépés: Fedezd fel

- Nyomd meg a `Tab` billentyűt a kontextusváltáshoz (Plan Mode / Normal Mode)
- Írd be `/help` a parancsok listájáért
- Írd be `/init` egy CLAUDE.md fájl generálásához

### Hibaelhárítás

| Probléma | Megoldás |
|----------|---------|
| "command not found: claude" | Zárd be és nyisd újra a terminált. Ha még mindig nem működik, futtasd újra a telepítő parancsot. |
| "Authentication failed" | Ellenőrizd, hogy aktív-e az előfizetésed a [claude.ai](https://claude.ai) oldalon. |
| Az AI túl lassan válaszol | Nagy projekteknél az első válasz lassabb lehet. Próbáld kisebb kérdéssel kezdeni. |
| Az AI nem látja a fájljaimat | Ellenőrizd, hogy abban a könyvtárban vagy-e, ahol a fájlok vannak (`pwd` parancs). |
| "Rate limit exceeded" | Túl sok kérést küldtél rövid időn belül. Várj néhány percet és próbáld újra. |

### Mi legyen a következő lépés?

Ha már működik a Claude Code és kipróbáltad az alapokat:

1. **CLAUDE.md létrehozása**: Futtasd a `/init` parancsot a projektedben. Ez létrehoz egy CLAUDE.md fájlt ami az AI "memóriáját" tárolja a projektről. Legközelebb már tudni fogja, mi hogyan működik.

2. **Bevált promptok**: Próbáld ki ezeket a haladóbb kérdéseket:
   - "Nézd át a biztonsági szempontból kritikus részeket és jelöld a kockázatokat"
   - "Írj egy összefoglalót a projekt architektúrájáról -- PM szemmel, nem fejlesztői"
   - "Milyen technikai adósságot látsz a kódban?"

3. **Tervezési mód**: Nyomj `Tab`-ot a Plan Mode-ba váltáshoz. Így az AI először tervez, és csak a jóváhagyásod után cselekszik. Éles projekteknél ezt használd.

4. **OpenSpec megismerése**: Olvasd el ennek az útmutatónak a 4. fejezetét (OpenSpec), és próbálj meg egy `wt-new` paranccsal új változást indítani.

### Árazás (2025. február)

| Csomag | Ár | Kinek való | Claude Code használat |
|--------|----|-----------|-----------------------|
| **Free** | \$0/hó | Kipróbálás, alkalmi használat | Nem támogatott |
| **Pro** | \$20/hó | Egyéni felhasználók, kisebb projektek | Támogatott, napi limittel |
| **Team** | \$25/fő/hó | Kis-közepes csapatok (max ~50 fő) | Támogatott, magasabb limittel |
| **Enterprise** | Egyedi | Nagyvállalatok | Támogatott, egyedi limitekkel, SSO, admin konzol |

**Fontos:** A Claude Code használata a Pro csomagnál napi tokenkorlátos. Ha intenzíven dolgozol (pl. orchestrációt futtatsz több ágenssel), a napi limit hamar elfogyhat. Team vagy Enterprise csomag esetén a limitek magasabbak.

Az aktuális árakat mindig az [Anthropic árazás](https://www.anthropic.com/pricing) oldalon ellenőrizd.

## D. Ajánlott olvasmányok

Ha mélyebben szeretnéd megérteni az AI-vezérelt szoftverfejlesztés világát, az alábbi könyveket ajánlom. Egyik sem vár el programozási ismeretet -- mind PM, vezető vagy üzleti döntéshozó szemszögéből ír.

**1. Ethan Mollick: Co-Intelligence -- Living and Working with AI (2024)**
Az AI korszak egyik legjobb bevezető könyve. Mollick a Wharton Business School professzora, és nem a technológiát, hanem az emberi oldalt állítja középpontba: hogyan gondolkozz az AI-ról, hogyan használd a mindennapi munkában, és milyen hibákat kerülj el. Gyakorlatias, közérthető, és rengeteg valós példa van benne.

**2. Gene Kim, Jez Humble, Nicole Forsgren: Accelerate (2018)**
Adatokkal alátámasztott elemzés arról, hogy mi különbözteti meg a magas teljesítményű szoftverfejlesztői csapatokat. A CI/CD, a deploy gyakoriság és a "lead time" fogalmak innen származnak. Ha PM-ként meg akarod érteni, miért fontos az automatizáció és miért számít a fejlesztési sebesség -- ez a könyv az alap.

**3. Martin Fowler: Refactoring -- Improving the Design of Existing Code (2018, 2. kiadás)**
A refaktorálás bibliája. Nem kell programozónak lenned ahhoz, hogy értsd a lényeget: a szoftvert folyamatosan karban kell tartani, mint egy házat. Ez a könyv segít a PM-nek megérteni, miért kérnek a fejlesztők "takarítási időt" és miért nem szabad azt mondani, hogy "ne refaktorálj, írj inkább új feature-öket".

**4. Cal Newport: Deep Work (2016)**
Nem AI-könyv, de találkozik az AI korszak legfontosabb kérdésével: hogyan végezz mély munkát egy világban teli megszakításokkal. PM-ként az AI eszközök segítenek abban, hogy a "sekélyes munkát" (emailek, összefoglalók, státuszjelentések) automatizáld, és a felszabaduló időt mély gondolkodásra használd. Newport keretrendszere segít ezt tudatosan megcsinálni.

**5. Marty Cagan: Inspired -- How to Create Tech Products Customers Love (2018, 2. kiadás)**
A termékfejlesztés bibliája. Cagan a Silicon Valley legtapasztaltabb product management tanácsadója, és ez a könyv leírja, hogyan működnek a legjobb termékcsapatok. Az AI korszakban különösen releváns: ha az AI átveszi a kódolás nagy részét, a PM szerepe a termékfelfedezés (discovery) felé tolódik -- és erről szól ez a könyv.
