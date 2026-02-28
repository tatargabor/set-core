# A szoftverfejlesztés jövője

## Hol tartunk most?

2026 elején a szoftverfejlesztés egy történelmi átmenet közepén van. Ahhoz, hogy megértsd mi történik, érdemes megnézni a számokat: a [Stack Overflow Developer Survey 2025](https://survey.stackoverflow.co/) szerint a fejlesztők többsége már használt valamilyen AI eszközt a munkájához, és a többség szerint ez érdemben megváltoztatta a napi munkájukat. A [McKinsey felmérései](https://www.mckinsey.com/capabilities/mckinsey-digital/our-insights) hasonló képet mutatnak: az AI-alapú fejlesztői eszközök 20-50%-os produktivitásnövekedést hoznak a feladattól függően.

Az AI ágensek már képesek:

- Önállóan megoldani valós hibákat (SWE-bench: ~50%, és egyre javul)
- Specifikáció alapján implementálni feature-öket
- Párhuzamosan, koordináltan dolgozni (lásd V. fejezet: Orchestráció)
- Tanulni korábbi tapasztalatokból (lásd VI. fejezet: Memória)
- Teszteket írni, futtatni, és az eredmények alapján javítani a kódot
- Többszáz fájlból álló projektekben navigálni

De még nem képesek:

- Komplex architektúrákat tervezni az üzleti kontextus teljes megértésével
- Emberi csapatdinamikát kezelni
- Kreatív, újszerű megoldásokat kitalálni ahol nincs precedens
- 100%-ban megbízható, production-ready kódot írni review nélkül
- A "miért" kérdést megválaszolni -- miért pont ezt a feature-t építjük
- Üzleti prioritásokat felállítani

Hol tartunk tehát? Valahol a "hasznos eszköz" és az "önálló fejlesztő" között. A [Gartner legfrissebb előrejelzései](https://www.gartner.com/en/topics/artificial-intelligence) szerint 2027-re a szoftverfejlesztő csapatok 80%-a használjon majd valamilyen AI ágenst -- de teljes autonómiát még nem várunk.

> **Ajánlott videó**: A [Two Minute Papers](https://www.youtube.com/@TwoMinutePapers) YouTube csatorna rendszeresen összefoglalja az AI legújabb eredményeit könnyen emészthető formában -- érdemes követni a fejlődést.

## Három időhorizont

### Rövid táv: 2025--2026 -- AI mint páros programozó

```
  +--------------------------------------------+
  |  MA: AI Pair Programming                    |
  |                                            |
  |  Fejleszto <-----------> AI Agens          |
  |     |                      |               |
  |     |  "Javitsd ki ezt"    |               |
  |     |--------------------> |               |
  |     |                      |  javit        |
  |     |  <-------------------|  tesztel      |
  |     |  "Kesz, nezd meg"    |               |
  |     |                      |               |
  |  Ember iranyit, AI vegrehajt               |
  |  Ember review-ol minden valtoztatast       |
  +--------------------------------------------+
```

**Ez van most.** A fejlesztő megmondja mit kell csinálni, az AI megcsinálja, a fejlesztő ellenőrzi. A PM a fejlesztővel egyeztet, aki az AI-t irányítja.

**Hogyan néz ki egy PM napja ebben a fázisban?**

Reggel: Átnézed a Jira board-ot. Észreveszed, hogy a fejlesztők az eddigi tempónál 2-3-szor gyorsabban zárnak le feladatokat. A sprintbe felvett feladatok felét már az első napra elvégezték. Utántöltés kell -- reggeli standup-on átnézed a backlogot, és kiválasztod a következő prioritásokat.

Délelőtt: Egyeztetsz a senior fejlesztővel, aki megmutatja, hogyan használja a Claude Code-ot egy bonyolultabb feladatnál. Látod, hogy ő irányítja az AI-t, de azért a komplex részeknél még sokat gondolkodik. Megérted: az AI nem varázslat, hanem egy nagyon jó asszisztens.

Délután: Reviewolod a PR-eket (Pull Request -- kódjavaslat). Most több PR jön, mint korábban. Néhány nagyon jó, néhány felületesen készült. Észreveszed: a minőség egyenetlen. Meg kell határoznod, mi a minimális minőségi mérce.

Este: Átgondolod a sprint vég becslését. Korrigálnod kell -- a csapat gyorsabb, de a review és integráció még mindig ugyanannyi idő.

**PM feladata**: Ugyanaz mint eddig, de a fejlesztő gyorsabb. A becsléseket le kell kalibrálnod -- ami eddig 3 nap volt, most 1 nap lehet. Fontos: az AI által generált kód review-ja **több időt** is igényelhet, mert a PM-nek meg kell győződnie a minőségről.

### Közép táv: 2026--2028 -- AI csapatok emberi felügyelettel

```
  +--------------------------------------------+
  |  HOLNAP: AI Csapatok                       |
  |                                            |
  |           Ember (Architect / PM)            |
  |                   |                         |
  |          Spec + Review                      |
  |                   |                         |
  |     +-------------+-------------+          |
  |     |             |             |          |
  |     v             v             v          |
  |  +------+    +------+    +------+         |
  |  |AI Ag.|    |AI Ag.|    |AI Ag.|         |
  |  |  #1  |    |  #2  |    |  #3  |         |
  |  |front |    |back  |    |test  |         |
  |  +------+    +------+    +------+         |
  |                                            |
  |  Ember ad specifikaciot, AI csapat          |
  |  dolgozik, ember review-olja a vegen       |
  +--------------------------------------------+
```

**Ez felé tartunk.** Az orchestrációs réteg (V. fejezet) ennek az előfutára. Egy ember ír egy specifikációt, az AI csapat implementálja, az ember a végeredményt ellenőrzi.

**Hogyan néz ki egy PM napja ebben a fázisban?**

Reggel: Megnyitod az orchestrátor dashboardot (lásd V. fejezet). Látod, hogy az éjszaka indított 3 change-ből 2 kész van, 1 elakadt. Az elakadtat megnézed: az AI ágensnek nem volt elég kontextus a fizetési modul üzleti szabályairól. Írsz egy kiegészítést a specbe, újraindítod.

Délelőtt: Nem standup van, hanem "spec review". A product owner-rel és az architect-tel átnézitek a következő sprint specifikációit. A specek minősége kritikus -- ha pontatlanok, az AI rossz eredményt ad. A beszélgetés nem arról szól, "ki csinálja meg", hanem arról, "hogyan írjuk le pontosan, mit akarunk".

Délután: 5 percet töltesz azzal, hogy átnézed az automatikus review eredményeket. Az AI review rendszer már a legtöbb problémát kiszűri. Csak a komplex architektúrális kérdések kerülnek eléd. Egynél látod, hogy az AI ágens egy új dependency-t húzott be -- erről beszélned kell a security csapattal.

Este: Dashboardon látod a sprint metrikákat. A csapat produktivitása 4-5x-e a korábbinak, de a spec írás ideje megnőtt. Ez rendben van -- a spec írás a legértékesebb tevékenység.

**PM feladata**: A specifikáció minősége kritikussá válik. Eddig ha a spec pontatlan volt, a fejlesztő megkérdezte. Az AI nem mindig kérdez -- megpróbálja értelmezni. Jobb spec = jobb eredmény. A PM fókusza: **specifikációk írása, review koordinálása, és minőségi kapu definiálása**.

> **Ajánlott cikk**: A [Harvard Business Review](https://hbr.org/) rendszeresen közöl cikkeket az AI hatásáról a menedzsmentre -- érdemes követni az "AI and Management" témakörben.

### Hosszú táv: 2028+ -- AI-vezérelt fejlesztés emberi irányítással

```
  +--------------------------------------------+
  |  HOLNAPUTAN: AI-vezerelt fejlesztes        |
  |                                            |
  |  Ember: Vizio + Minoseg + Uzleti dontes   |
  |                   |                         |
  |          "Mit akarunk?"                     |
  |          "Ez eleg jo?"                      |
  |                   |                         |
  |                   v                         |
  |         +-----------------+                |
  |         |  AI Orchestrator |                |
  |         |  (spec, design,  |                |
  |         |   tasks, impl.,  |                |
  |         |   test, deploy)  |                |
  |         +-----------------+                |
  |                   |                         |
  |          Ember: szuroproba review           |
  |          Ember: release dontes              |
  |                                            |
  +--------------------------------------------+
```

**Ez a legvalószínűbb hosszú távú kép.** Az AI nemcsak implementál, hanem tervez is -- az ember az üzleti víziót adja, és a minőségi kaput kontrollálja.

**Hogyan néz ki egy PM napja ebben a fázisban?**

Reggel: Kávés közben átnézed a heti "vision document"-et. Leírtad benne, hogy a következő hónapban milyen üzleti célokat akarsz elérni (pl. "20%-kal csökkenteni a checkout abandonment rate-et"). Az AI orchestrátor már lebontotta ezt feature-ökre, szúrópróba-szerű átválogatást végzel: "Ez jó irány? Ez összhangban van a stratégiával?"

Délelőtt: Két órát töltesz az üzleti stakeholder-ekkel. Az ő igényeiket fordítod le arra a nyelvre, amit az AI rendszer ért: világos célok, mérőszámok, sikerkritériumok. Ez a te legfontosabb képességed -- senki más nem ért az üzleti és technikai világ között.

Délután: Az AI rendszer automatikusan deployolt egy új feature-t staging környezetbe. Kipróbálod, néhány dolog nem tetszik. Visszajelzést írsz -- nem "javítsd ki a 42. sort", hanem "a checkout flow túl bonyolult, a felhasználó 3 lépés helyett 5-öt lát, egyszerűsítsd". Az AI orchestrátor újratervezi.

Este: Reviewolod a heti metrikákat. A csapatod (ami főleg AI ágensekből áll, néhány senior engineer felügyeletével) 50 feature-t szállított ki ezen a héten. A te dolgod: ebből melyik mozdította előrébb az üzleti célokat?

**PM feladata**: A PM szerepe a "mit" és "miért" kérdésekre fókuszálódik. Kevesebb "ki csinálja meg?" és "hol tartunk?" -- több "mit csinálunk és miért?" és "elég jó ez a felhasználóknak?"

## A PM szerep evolúciója

```
  2024:     PM --> Jira ticket --> Dev --> Review --> Deploy
                   (reszletes)    (kodol)  (kezi)

  2026:     PM --> Proposal --> AI Agent --> Auto-review --> PM OK --> Deploy
                   (mit+miert)  (spec->kod)  (tesztek)       (check)

  2028+:    PM --> Vizio doc --> AI Orchestr. --> AI Review --> PM spot-check
                   (nagy kep)    (minden auto.)   (auto.)       (szuroproba)
```

**Ami változik:**

| Terület | Régi PM | Új PM |
|---------|---------|-------|
| **Becslések** | Napokban/hetekben gondolkodik | Órákban gondolkodik, kapacitást ágensekben méri |
| **Státusz meeting** | Napi standup, hetente retro | Dashboard nézegetés, ritkább sync |
| **Spec írás** | "Nice to have" | Kritikus -- a spec minősége = a kód minősége |
| **Review** | Kódot nem néz, ticketet mozgat | Artifact-okat reviewol (proposal, spec) |
| **Koordináció** | Ember -- ember | Ember --> spec --> AI csapat |
| **Minőség** | "A devek megoldják" | Minőségi kapu-t definiál és betartatja |
| **Kockázatkezelés** | Manuális figyelemmel kísérés | AI által jelzett kockázatok értékelése |
| **Stakeholder mgmt** | Fejlesztői státusz közvetítése | Üzleti célú eredmények kommunikálása |

## Iparági szereplők -- részletes összehasonlítás

Nem csak az Anthropic dolgozik ezen. Az AI-alapú fejlesztői eszközök piaca robbanásszerűen nő -- a [Sequoia Capital](https://www.sequoiacap.com/) és az [a16z](https://a16z.com/ai/) kockázati tőkealapok milliárdos befektetésekkel támogatják ezt a területet. Íme a főbb szereplők részletesebb összehasonlítása:

### Az eszközök részletesen

**Claude Code** (Anthropic) -- [anthropic.com/research](https://www.anthropic.com/research)

A könyvben részletesen tárgyalt eszköz. Erősségei: agentic (önállóan cselekvő) működési mód, hook rendszer, MCP szabvány, sub-ágensek, memória rendszer, orchestráció. Parancssori (CLI) és IDE integrációval is használható. A specifikáció-vezérelt megközelítés (OpenSpec) különösen erős. Gyengeségei: parancssori interface-e nem minden felhasználónak intuitív, és az Anthropic ökoszisztémára építkezik (bár az MCP szabvány nyitott).

**GitHub Copilot** -- [github.com/features/copilot](https://github.com/features/copilot)

A Microsoft/GitHub terméke, a legelterjedtebb AI fejlesztői eszköz. Erősségei: mélyen integrált a GitHub ökoszisztémába (pull request-ek, issues, actions), széles IDE támogatás (VS Code, JetBrains, Neovim), Copilot Workspace ami projekt szinten dolgozik. Gyengeségei: az agent mód még kevésbé érett mint a Claude Code, és kisebb a kontextus-ablak.

**Cursor** -- [cursor.com](https://cursor.com)

AI-natív IDE (fejlesztői környezet), ami a VS Code-ra épül. Erősségei: az egész IDE körüli élményt AI-ra tervezték, gyors és intuitív, több AI modellt támogat (Claude, GPT-4, stb.), a "Composer" feature komplex, többfájlos feladatokra képes. Gyengeségei: önmagában IDE, nincs orchestrációs réteg, és a fejlett agentikus képességek még fejlődés alatt állnak.

**Devin** -- [devin.ai](https://devin.ai)

A Cognition Labs terméke, az első "teljes AI szoftverfejlesztő". Erősségei: teljesen autonóm -- saját böngészővel, terminállal, és szerkesztővel rendelkezik, bonyolultabb feladatokat is képes önállóan megoldani. Gyengeségei: lassú (percek-órák egy feladatra), drága, és a minőség egyenetlen -- néha brilliáns, néha katasztrofális. A felhasználó kevésbé tudja irányítani, mint a többi eszközt.

**Amazon Q Developer** -- [aws.amazon.com/q/developer/](https://aws.amazon.com/q/developer/)

Az Amazon AWS-be integrált AI fejlesztői eszköze. Erősségei: mélyen integrált az AWS ökoszisztémába (Lambda, DynamoDB, S3, stb.), biztonsági szkennelést is végez, és a nagyvállalati megfelelőség (compliance) területén erős. Gyengeségei: alapvetően AWS-fókuszú, más felhő-szolgáltatókkal való használata korlátolt.

**Google Jules**

A Google AI kódoló ágense. Korai fázisban van, a fejlesztés gyors. A Google Gemini modellek erejéből merít. Erősségei: a Google Cloud integráció és a Gemini modellek kontextus-ablaka (rekord méretű). Gyengeségei: még nem érett, a Google hajlamos termékeket megszüntetni (lásd: Google Graveyard).

### Összehasonlító táblázat

| Eszköz | Autonómia | IDE integr. | Orchestráció | Ár (2026) | Legjobb ha... |
|--------|-----------|-------------|--------------|-----------|---------------|
| **Claude Code** | Magas | CLI + IDE | Van (wt-tools) | \$\$\$ | Specifikáció-vezérelt AI csapatokat akarsz |
| **Copilot** | Közepes | Kitűnő | Korlátolt | \$\$ | Már GitHub-ot használsz és gyors kiegészítés kell |
| **Cursor** | Közepes | Natív IDE | Nincs | \$\$ | Intuitív, vizuális fejlesztői élményt keresel |
| **Devin** | Nagyon magas | Saját env. | Van | \$\$\$\$ | Teljes autonómiát akarsz és bírod a kockázatot |
| **Amazon Q** | Közepes | AWS konzol | Korlátolt | \$\$ | AWS ökoszisztémában dolgozol |
| **Jules** | Közepes | GCP | Korlátolt | \$\$ | Google Cloud-ban dolgozol |

```
  Autonomia szint:

  Alacsony                                          Magas
  +-------------+----------------+-----------------+
  |             |                |                  |
  Copilot    Cursor        Claude Code          Devin
  (kiegeszit)  (szerkeszt)   (agens)          (autonom)
```

**A trend egyértelmű**: minden szereplő az autonómia felé mozog. A kérdés nem az, hogy az AI ágensek át fogják-e venni a rutin kódolási feladatokat, hanem **mikor** és **milyen szinten**. A [Gartner](https://www.gartner.com/en/topics/artificial-intelligence) elemzései szerint 2028-ra az AI ágensek a kódolási feladatok 70%-át elvégzik majd.

## AI-natív vállalatok: az új paradigma

Egy teljesen új kategória jelent meg az utolsó évben: az **AI-natív vállalatok**. Ezek olyan startup-ok és cégek, amelyeket az első naptól kezdve AI ágensekkel való együttműködés köré építettek.

### Mi az AI-natív vállalat?

Hagyományos startup: felépít egy 5-10 fős fejlesztői csapatot, behúzzák a laptopokat, Jira-t, Slack-et, és elkezdenek kódolni.

AI-natív startup: 1-2 technical founder + AI ágensek csapata. A "fejlesztői csapat" nagyrészt AI ágensekből áll, az emberek specifikációt írnak, reviewolnak, és üzleti döntéseket hoznak.

A [Y Combinator](https://www.ycombinator.com/) -- a világ legismertebb startup inkubátora -- már 2025-ben jelezte, hogy egyre több AI-natív startup pályázik hozzájuk. Ezek a cégek:

- **1-3 ember** képviseli a teljes "fejlesztői csapatot"
- Specifikációkat írnak, nem kódot
- AI ágensek implementálnak, tesztelnek, deployolnak
- A fejlesztési költség a töredéke a hagyományosnak
- Hihetetlen gyorsan iterálnak -- naponta több release

**Példa**: Képzeld el, hogy egy 2 fős startup 3 hónap alatt létrehoz egy teljes SaaS terméket (webes szoftver szolgáltatásként), ami korábban 10 fős csapatnak 1 évet vett volna igénybe. Az egyik alapító a termék vízióját és az üzleti stratégiát adja, a másik a technikai specifikációkat írja és az AI ágenseket irányítja.

### Mit jelent ez a PM-nek?

Ha AI-natív cégnél dolgozol (vagy ilyenné válik a céged):

- A PM és a "tech lead" szerep összeolvadhat
- Specifikáció-írás a legfontosabb technikai képesség
- A csapat mérete nem a fejlesztők számáról szól, hanem az ágensek számáról és a spec minőségéről
- A "velocity" (fejlesztési sebesség) a sokszorosára nőhet
- Az ügyfél-visszajelzés integráció sokkal gyorsabb -- reggelre megkapod a feedbacket, délutánra már kijavítod

> **Ajánlott olvasmány**: Az [a16z (Andreessen Horowitz)](https://a16z.com/ai/) rendszeresen közöl elemzéseket az AI-natív cégek trendjeiről, és arról hogyan változtatja meg az AI a szoftveripart.

## Gazdasági hatás: számok és becslések

Az AI ágensek nem csak technológiai, hanem gazdasági forradalmat is hoznak. Érdemes megnézni a számokat, mert ezek segítenek a PM-nek meggyőzni a vezetőséget az AI eszközökbe való befektetésről.

### Produktivitás-növekedés

A különböző kutatások 20-80%-os produktivitás-növekedést mérnek, a feladat típusától függően:

| Feladat típusa | Produktivitás növekedés | Forrás |
|---------------|-------------------------|--------|
| Rutin kódolás (boilerplate) | 50-80% | [McKinsey Digital](https://www.mckinsey.com/capabilities/mckinsey-digital/our-insights) |
| Hibakeresés és javítás | 30-50% | [Stack Overflow Survey](https://survey.stackoverflow.co/) |
| Teszt írás | 40-60% | Belső mérések |
| Dokumentáció | 60-80% | Iparági átlag |
| Komplex architektúra tervezés | 5-15% | McKinsey |
| Új technológia tanulása | 20-40% | Fejlesztői visszajelzések |

**Fontos**: a produktivitás-növekedés NEM egyenletes. A rutin feladatoknál drámai, a kreatív és architektúrális feladatoknál minimális. Ez azt jelenti, hogy az AI főleg az "unalmas" munkát veszi át, és az emberi munkaerő a magasabb értékű feladatokra fókuszálhat.

### Költségmegtakarítás

Egy példával szemléltetve:

```
  HAGYOMANYOS FEJLESZTES (5 fos csapat, 6 honapos projekt):
  -----------------------------------------------------------
  5 fejleszto x 6 honap x ~1.5M Ft/ho (brutt. ber+koltseg) = 45M Ft
  + Infrastruktura, eszkozok:                                  5M Ft
  + PM, tesztelo, designer:                                   15M Ft
  Osszesen:                                                   ~65M Ft

  AI-TAMOGATOTT FEJLESZTES (2 fejleszto + AI agensek, 3 honap):
  ----------------------------------------------------------------
  2 fejleszto x 3 honap x ~1.8M Ft/ho (magasabb ber):         10.8M Ft
  + AI eszkozok (Claude, infra):                                2M Ft
  + PM, designer:                                               5M Ft
  Osszesen:                                                   ~18M Ft

  Megtakaritas: ~72% (47M Ft)
  Gyorsabb szallitas: 3 honap a 6 helyett
```

*Megjegyzés*: ezek becsült értékek, a konkrét számok projektenként változnak. A legfontosabb üzenet nem a pontos összeg, hanem a nagyságrend.

### ROI (Return on Investment) számítás PM-eknek

Ha a vezetőséged kérdezi, "megéri-e AI eszközökbe fektetni?", itt egy egyszerű keret:

1. **Befektetés**: AI eszközök havidíja (tipikusan \$50-500/fejlesztő/hó) + betanítás ideje (1-2 hét)
2. **Megtakarítás**: Fejlesztési idő csökkenés (tipikusan 30-60%) * fejlesztői bérköltség
3. **ROI**: Általában az első hónapban megtérül

A [McKinsey](https://www.mckinsey.com/capabilities/mckinsey-digital/our-insights) felmérései szerint az AI eszközökbe való befektetés ROI-ja az iparági átlagban 3-5x a befektetett összegnek az első évben.

## Kockázatok és kihívások

Minden technológiai forradalomnál vannak kockázatok. Ezeket fontos ismerni:

### 1. AI hallucináció

Az AI néha magabiztosan állít olyasmit, ami nem igaz. Kitalál API-kat, hivatkozik nem létező függvényekre, vagy logikusnak tűnő de hibás megoldásokat ad.

*Példa*: Az AI azt írja: "Használd a `request.user.getActiveSubscription()` metódust" -- ami nem létezik a projektben. A kód lefordul, de futáskor hibát dob. Ha nincs teszt lefedettség, ez production-be kerülhet.

**Mitigáció**: Automatikus tesztek, kód review, és a spec-driven megközelítés (ami mérhető követelményeket ad). Minél több automatizált ellenőrzés van, annál kisebb a kockázat.

### 2. Biztonsági kérdések

Az AI ágens hozzáfér a fájlrendszerhez, futtat parancsokat, és potenciálisan érzékeny adatokkal dolgozik. Ha rosszindulatú input-ot kap (prompt injection), nem kívánt műveleteket végezhet.

*Példa*: Ha az AI ágens hozzáfér egy .env fájlhoz ami API kulcsokat tartalmaz, és a kód amit generál véletlenül kilogolja ezeket, biztonsági incidens történhet.

**Mitigáció**: Sandboxing (elszigetelt futtatás), jogosultsági rendszerek, és a hookrendszer ami blokkolhatja a veszélyes műveleteket (lásd II. fejezet). A legtöbb modern AI eszköz beépített biztonsági rétegeket tartalmaz.

### 3. Vendor lock-in

Ha egy csapat teljesen egy AI provider-re (pl. Anthropic, OpenAI) épít, annak kiesése megbéníthatja a munkát.

*Példa*: 2025 elején több AI szolgáltató is tapasztalt órákig tartó kieséseket. Azok a csapatok, amelyek kizárólag egy szolgáltatóra építettek, órákig nem tudtak dolgozni.

**Mitigáció**: A specifikáció-vezérelt megközelítés provider-független -- a specek, design-ok, és taskok szöveges fájlok, amik bármely AI-val használhatók. Az MCP szabvány szintén provider-független. Érdemes "Plan B"-t tartani -- pl. ha a Claude Code nem elérhető, a Cursor-t is ismerd.

### 4. Szabályozási kérdések -- az EU AI Act

Az [EU AI Act](https://artificialintelligenceact.eu/) 2024-ben lép életbe fokozatosan, és 2026-ra már számos rendelkezés hatályos. Ez a világ első átfogó AI szabályozása, és közvetlen hatása van arra, hogyan használhatók AI ágensek a szoftverfejlesztésben.

**Mi az EU AI Act lényege PM szemszögből?**

Az EU AI Act kockázati szintek szerint kategorizálja az AI rendszereket:

| Kockázati szint | Példa | Követelmény |
|----------------|-------|-------------|
| **Elfogadhatatlan** | Social scoring, manipulatív AI | Tiltott |
| **Magas kockázatú** | Egészségügyi, pénzügyi, kritikus infra | Szigorú audit, dokumentáció, emberi felügyelet |
| **Korlátozott kockázat** | Chatbotok, AI generált tartalom | Átláthatósági követelmény (jelezni kell, hogy AI) |
| **Minimális kockázat** | AI kód-segédeszköz, spam filter | Nincs külön követelmény |

**Mit jelent ez a gyakorlatban egy fejlesztői csapatnak?**

- Ha a projektedben **magas kockázatú** AI alkalmazást fejlesztesz (pl. pénzügyi döntés-támogató, egészségügyi szoftver), az AI ágens által generált kódot külön dokumentálni és auditálni kell
- Az AI ágensek használata a fejlesztésben (mint eszköz) általában **minimális kockázat** -- nincs külön követelmény
- DE: ha az AI ágens által generált kód egy magas kockázatú rendszer része, a teljes fejlesztési folyamatot dokumentálni kell

**A spec-driven megközelítés előnye**: A specifikáció-vezérelt fejlesztés (lásd III. és IV. fejezet) teljes audit trail-t biztosít -- minden döntés, változás, és AI-művelet dokumentálva van git-ben. Ez pont az, amit az EU AI Act megkövetel.

> **Hivatalos forrás**: Az EU AI Act teljes szövege és magyarázata: [artificialintelligenceact.eu](https://artificialintelligenceact.eu/)

### 5. Munkaerőpiaci hatás

Az AI ágensek csökkentik a rutin kódolási feladatokat. Ez egyes fejlesztői pozíciókat átalakíthat.

A [World Economic Forum Future of Jobs Report 2025](https://www.weforum.org/publications/the-future-of-jobs-report-2025/) szerint az AI nem annyira megszüntet munkahelyeket, mint inkább átalakítja őket. A szoftverfejlesztés területén:

- A **junior fejlesztői** pozíciók száma csökkenhet, de a szerepük átalakul (több review, kevesebb boilerplate kód írás)
- A **senior fejlesztői** és **architekti** szerepek értéke nő (ők irányítják az AI ágenseket)
- Új pozíciók jelennek meg: "AI Engineer", "Prompt Engineer", "AI Operations"
- A **PM szerep** értéke nő, mert a specifikáció-írás és az üzleti-technikai fordítás egyre fontosabb

**Mitigáció**: A fejlesztői szerep átalakulása -- kevesebb kódírás, több architektúra, review, és AI-felügyelet. Hasonló ahhoz, ahogy a számítógépek nem szüntették meg a könyvelést, hanem átalakították. A táblázatkezelők megjelenése után nem kellett kevesebb könyvelő, hanem másképp dolgozó könyvelő.

### 6. Minőségi és megbízhatósági kockázat

Az AI gyorsan generálja a kódot, de a minőség egyenetlen. Ha a csapat elbizakodik és csökkenti a review-t, a technikai adósság gyorsan felhalmozódhat.

**Mitigáció**: Automatizált minőségi kapuk (tesztek, lint, security scan), és a "trust but verify" (bízz benne, de ellenőrizd) megközelítés. A PM feladata: definiálni a minőségi minimumot, és ragaszkodni hozzá.

## Gyakori tévhitek az AI-ról a szoftverfejlesztésben

Sok félreértés kering az AI ágensekről. Itt a leggyakoribbak, és a valóság mellettük:

### Tévhit #1: "Az AI helyettesíti a fejlesztőket"

**Valóság**: Az AI átalakítja a fejlesztői szerepet, de nem szünteti meg. Pont úgy, ahogy az Excel nem szüntette meg a könyvelőket, és az AutoCAD nem szüntette meg az építészeket. A fejlesztők magasabb szintű munkára fókuszálnak: architektúra, review, és az AI irányítása. A [Stack Overflow Developer Survey 2025](https://survey.stackoverflow.co/) szerint a fejlesztők többsége pozitívan értékeli az AI eszközöket, és nem fél a munkahely elvesztésétől.

### Tévhit #2: "Az AI által generált kód rossz minőségű"

**Valóság**: Az AI által generált kód minősége erősen függ a specifikáció minőségétől és a review folyamattól. Egy jó specifikációt kapó AI ágens gyakran jobb kódot ír, mint egy siető junior fejlesztő -- mert következetesen betartja a stílus-konvenciókat, minden esetben ír teszteket, és nem felejt el hibakezelést. A kulcs: a spec minősége határozza meg az output minőségét.

### Tévhit #3: "Csak programozóknak hasznos"

**Valóság**: Az AI ágensek PM-eknek is közvetlenül hasznosak:

- Specifikációk validálása (az AI "eljátssza" az implementációt és jelezheti a lyukakat)
- Projekt progress automatikus nyomon követése
- Technikai dokumentáció érthetővé fordítása
- "Mi lenne ha" forgatókönyvek gyors kipróbálása

### Tévhit #4: "Drága és jó AI eszközök kellenek, olcsóbb nem használni"

**Valóság**: A legtöbb AI fejlesztői eszköz \$20-100/hó/fejlesztő árban mozog. Ha egy fejlesztő óra-bére \$50-150, és az AI eszköz napi 1 órát megtakarít, az eszköz az első nap megtérül. Az ROI (megtérülés) szinte mindig pozitív az első héten belül.

### Tévhit #5: "Nem kell hozzá technikai tudás"

**Valóság**: Nem kell kódolni tudni, de értened kell az alapfogalmakat (API, adatbázis, tesztek, deployment). Hasonló, mint az autóvezetéshez: nem kell autószerelőnek lenned, de értened kell a közlekedési szabályokat. Ez a könyv pont ezt adja: a szükséges minimum technikai kontextust.

### Tévhit #6: "Az AI kód biztonságilag veszélyes"

**Valóság**: Az AI által generált kód nem veszélyesebb, mint az ember által írt kód -- feltéve, hogy megfelelő review és tesztelés folyamat van. Sőt, az AI következetesebben követ biztonsági best practice-eket, mert nem felejt, nem siet, és nem "majd később megcsinálom". A kockázat nem maga az AI, hanem a review nélküli elfogadás.

## Ami NEM fog eltűnni

Az AI forradalom közepén fontos tisztán látni, mi marad változatlanul értékes:

```
  +----------------------------------------------+
  |  EMBERI ERTEKEK AMIK MEGMARADNAK             |
  |                                              |
  |  * Uzleti gondolkodas                        |
  |    "Mit akar a felhasznalo?"                 |
  |    "Melyik feature hoz bevetelt?"            |
  |    "Melyik piacra lepjunk be?"               |
  |                                              |
  |  * Architekturalis dontesek                  |
  |    "Monolitikus vagy mikroszervizes?"         |
  |    "Cloud vagy on-premise?"                   |
  |    "Build vs. buy?"                           |
  |                                              |
  |  * Csapat es kultura                         |
  |    "Hogyan dolgozunk egyutt?"                |
  |    "Mi a csapat erossege?"                   |
  |    "Hogyan motivaljuk az embereket?"         |
  |                                              |
  |  * Minosegi merce                            |
  |    "Eleg jo ez a felhasznaloknak?"           |
  |    "Megbizhatunk ebben?"                      |
  |    "Skalazodik ez 10x felhasznalora?"        |
  |                                              |
  |  * Etikai es uzleti itelokeepesseg           |
  |    "Szabad ezt csinalnunk?"                  |
  |    "Mi a kockazat?"                          |
  |    "Osszhangban van ez az ertekeinkkel?"     |
  |                                              |
  |  * Kreativitas es innovacio                  |
  |    "Mi lenne ha teljesen maskepp csinalnak?" |
  |    "Milyen problemat nem lat meg senki?"     |
  |    "Hogyan lephetjuk meg a felhasznalokat?"  |
  |                                              |
  |  * Empatia es felhasznaloi szemlelet        |
  |    "Milyen erzest kelt ez a termek?"         |
  |    "Erti-e a nagymamam is?"                  |
  |    "Mi frusztralja a felhasznalot?"          |
  |                                              |
  +----------------------------------------------+
```

**A szoftverfejlesztés nem a kódolásról szól** -- a problémamegoldásról szól. Az AI átveszi a kódolás jelentős részét, de a probléma meghatározása, a prioritások felállítása, és a végeredmény értékelése emberi feladat marad.

Gondolj erre: az AI brilliánsan tud kódot írni, de nem tudja megmondani, hogy érdemes-e egyáltalán megírni. Nem tudja, hogy a felhasználóid többsége mobilról használja a terméked, ezért a desktop verzió kevésbé fontos. Nem tudja, hogy a fő versenytársad épp hasonló feature-ön dolgozik, ezért gyorsabbnak kell lenned. Ezek **emberi** döntések, és a PM az, aki ezeket meghozza.

> **Ajánlott cikk**: Az [Anthropic kutatási oldala](https://www.anthropic.com/research) rendszeresen közöl anyagokat arról, hogyan gondolkodnak a felelős AI fejlesztésről -- érdemes olvasni, hogy megértsd az AI képességeit és korlátait a fejlesztők szemével.

## Képességek, amiket egy PM-nek most érdemes fejleszteni

A következő években a legértékesebb PM-ek azok lesznek, akik az alábbi képességeket elsajátítják:

### 1. Specifikáció-írás (Spec Writing)

Ez a legfontosabb új PM képesség. A specifikáció az a dokumentum, ami leírja, MIT kell megcsinálni, MIÉRT, és HOGYAN mérjük a sikert. Ha AI ágensek implementálnak, a spec minősége egyenesen arányos az eredmény minőségével.

**Gyakorlati tanács**:

- Írj SMART célokat (Specific, Measurable, Achievable, Relevant, Time-bound)
- Használd az OpenSpec formátumot (lásd IV. fejezet) -- proposal, design, tasks
- Minden specben legyen: elvárás, sikerkritérium, és "anti-goal" (mit NEM akarunk)
- Kérj AI-tól visszajelzést a specre: "Van valami ami nem világos ebben a specben?"

### 2. AI műveltség (AI Literacy)

Nem kell AI kutatónak lenned, de értened kell az alap fogalmakat: mi az LLM, mi az a kontextus-ablak, mit jelent a hallucináció, mi az agent loop. Ez a könyv ennek az alapját adja.

**Gyakorlati tanács**:

- Olvasd el ezt a könyvet :)
- Kövesd a [Two Minute Papers](https://www.youtube.com/@TwoMinutePapers) YouTube csatornát a legújabb fejleményekért
- Próbáld ki személyesen a ChatGPT-t, Claude-ot, és a Cursor-t -- a saját élményed pótolhatatlan
- Olvass rendszeresen: [HBR AI cikkek](https://hbr.org/), [McKinsey AI insights](https://www.mckinsey.com/capabilities/mckinsey-digital/our-insights)

### 3. Prompt engineering alapok

A "prompt" az az utasítás, amit az AI-nak adsz. A jó prompt = jó eredmény. PM-ként nem kell expert szinten értened, de az alapok fontosak:

**Gyakorlati tanács**:

- Légy specifikus: "Írj egy kereső funkciót" rossz. "Írj egy kereső funkciót ami a felhasználó név és email cím alapján keres a users táblában, és az eredményeket pagináltan adja vissza, oldalanként 20 találat" jó.
- Adj kontextust: mondd el mi a projekt, ki a felhasználó, mi a cél
- Kérj strukturált outputot: "A válaszodat 3 részre oszd: probléma, megoldás, kockázatok"
- Iterálj: ha az első eredmény nem jó, pontosítsd az utasítást, ne add fel

### 4. Minőségi kapu (Quality Gate) definiálás

A PM feladata meghatározni: "mikor tekintünk késznek egy feladatot?" Ez AI ágensek esetén különösen fontos, mert az AI gyorsan szállít, de a "kész" definíciója megváltozott.

**Gyakorlati tanács**:

- Definiáld a "Definition of Done"-t (pl. tesztek átmennek, lint rendben, dokumentáció kész, review megvolt)
- Automatizáld ami automatizálható (CI/CD pipeline-ban)
- A PM-nek nem kell kódot olvasnia, de látnia kell: átment-e a teszteken, van-e review, megfelel-e a specnek

### 5. Változás-menedzsment (Change Management)

Az AI eszközök bevezetése a csapatba változás-menedzsmentet igényel. Nem elég telepíteni az eszközt -- az embereket is fel kell készíteni.

**Gyakorlati tanács**:

- Kezdd kicsiben: 1 fejlesztő, 1 projekt, 1 sprint
- Mérd az eredményt: gyorsabb lett? jobb lett? a fejlesztő elégedett?
- Kommunikáld a sikereket és a tanulságokat
- Ne kényszerítsd: aki nem akarja használni, adj időt. A sikertörténetek magukért beszélnek.

## Akcióterv: hogyan kezdj hozzá?

Ha eddig eljutottál a könyvben, valószínűleg felmerült a kérdés: "És most mit csináljak?" Itt egy gyakorlati akcióterv, lépésről lépésre:

### 1. hét: Ismerkedés (0 kockázat)

| Nap | Tevékenység | Cél |
|-----|-------------|-----|
| Hétfő | Próbáld ki a ChatGPT-t vagy a Claude-ot egy egyszerű feladattal | Érzetet kapni arról, mit tud az AI |
| Kedd | Kérdezz az AI-tól a saját projektedről (általánosságban) | Látni, hogyan gondolkodik |
| Szerda | Nézd meg a [GitHub Copilot](https://github.com/features/copilot) demót | Érteni, mit lát a fejlesztő |
| Csütörtök | Nézd meg a [Cursor](https://cursor.com) demót | Másik megközelítés megismerése |
| Péntek | Beszélj egy fejlesztővel a csapatodból: használsz már AI-t? | Valós tapasztalat, nem marketing |

### 2. hét: Első kísérlet (alacsony kockázat)

- Válassz egy kis, nem kritikus feladatot a backlogból
- Kérd meg egy fejlesztőt, hogy használja AI-t (ha még nem teszi)
- Mérd: mennyi ideig tartott? Milyen minőségű az eredmény?
- Hasonlítsd össze a korábbi becslésekkel

### 3. hét: Spec-driven próbálkozás (közepes kockázat)

- Írj egy részletes specifikációt egy közepes méretű feladathoz
- Használd az OpenSpec formátumot (lásd IV. fejezet)
- A fejlesztő az AI-t használja az implementációhoz
- Reviewold együtt az eredményt: a spec alapján mérhető az eredmény?

### 4. hét: Értékelés és következő lépések

- Gyűjtsd össze a tanulságokat: mi működött, mi nem?
- Számold ki a hatékonyság-növekedést
- Készíts egy rövid beszámolót a vezetőségnek
- Tervezd meg a következő sprintet az új tudás alapján

### Folyamatos tevékenységek (1. hónaptól)

- Hetente 30 percet szánj AI hírek olvasására ([McKinsey](https://www.mckinsey.com/capabilities/mckinsey-digital/our-insights), [HBR](https://hbr.org/), [a16z](https://a16z.com/ai/))
- Havonta próbálj ki egy új AI eszközt
- Negyedévente értékeld újra a becslési modelleket
- Évente komplett AI-stratégia felülvizsgálat

## Az átmenet kezelése: csapat menedzsment az AI-korszakban

Az AI eszközök bevezetése nem csak technikai, hanem emberi kihívás is. Íme a leggyakoribb helyzetek és a megoldásuk:

### "A fejlesztők félnek, hogy az AI elveszi a munkájukat"

Ez a leggyakoribb és legérthetőbb reakció. A valóság az, hogy az AI nem a fejlesztőket váltja ki, hanem a fejlesztés módját változtatja meg.

**Mit tegyél PM-ként:**

- Kommunikáld nyíltan: "Az AI eszköz, nem helyettesítő. Azért vezetjük be, mert hatékonyabbak leszünk, nem mert kevesebb emberre van szükségünk."
- Mutasd meg a pozitív oldalát: "Kevesebb boilerplate kódot kell írnod, több idő jut az érdekes feladatokra."
- Adj példát más iparágakból: "Az Excel nem szüntette meg a könyvelőket. Az AutoCAD nem szüntette meg az építészeket."

### "Egyes fejlesztők lelkesek, mások szkeptikusak"

Ez természetes. Minden új technológiánál vannak korai alkalmazók és szkeptikusok.

**Mit tegyél PM-ként:**

- Ne kényszerítsd: hadd az önkéntesek kezdjék
- A korai alkalmazók sikereiről szólj a csapatnak
- A szkeptikusok konkrét aggodalmaikra adj konkrét választ
- Adj időt: általában 2-3 hónap kell, mire a többség átáll

### "A review folyamat még nem alkalmazkodott"

Ha az AI 5x annyi kódot generál, az eddigi review folyamat nem skálázódik.

**Mit tegyél PM-ként:**

- Automatizáld ami automatizálható: lint, tesztek, security scan
- A manuális review fókuszáljon az architektúrára és az üzleti logikára, ne a stílusra
- Fontold meg: az AI-t is bevonhatod a review-ba (AI review + emberi spot-check)
- Definiáld, mit KELL embernek reviewolnia, és mit ELÉG automatizáltan

### "Nem tudjuk hogyan becsüljünk"

A régi becslési modellek nem működnek. Ha a fejlesztő most 3x gyorsabb, de a review ugyanannyi idő, az összkép komplex.

**Mit tegyél PM-ként:**

- Az első 2-3 sprintben ne becsülj, hanem mérj: mennyi ideig tart valóban?
- Építs új referenciapontokat az AI-támogatott fejlesztésre
- Különböztesd meg: "AI implementáció ideje" + "review ideje" + "integráció ideje"
- A becslések pontossága 2-3 sprint után javul

### "A vezetőség túl nagy elvárásokat támaszt"

Ha a vezetőség hall arról, hogy "az AI 10x gyorsabb", irreális elvárásokat támaszthat.

**Mit tegyél PM-ként:**

- Mutass valós számokat a saját csapatodból, ne marketing anyagokból
- Kommunikáld: "Az AI a kódolást gyorsítja, de a tervezés, review, és integráció ideje nem változik drasztikusan"
- Adj reális becsléseket: "30-50% össz-gyorsulás, nem 10x"
- A megtakarított időt használd jobb minőségre, nem több feature-re

## Összefoglalás: mit tegyen most egy PM?

| Lépés | Mit | Miért | Mikor |
|-------|-----|-------|-------|
| **1. Ismerd meg** | Próbáld ki a Claude Code-ot (lásd Függelék) | Személyes tapasztalat nélkül nem értheted meg | Ez a hét |
| **2. Gondolkodj spec-ben** | Kezdj részletesebb specifikációkat írni | A spec minősége = az AI output minősége | Most azonnal |
| **3. Kalibráld újra** | A becslési modelleket igazítsd | Ami 5 nap volt, lehet 1 nap + review | Következő sprint |
| **4. Fókuszálj minőségre** | Definiáld a "kész" definícióját | Az AI gyorsan ír kódot -- de jót? | Következő sprint |
| **5. Kísérletezz** | Egy kisebb feladaton próbáld ki a flow-t | Alacsony kockázat, nagy tanulság | 2 héten belül |
| **6. Tanulj** | Olvass, nézz videókat, beszélgess | Ez a terület gyorsan változik | Folyamatosan |
| **7. Kommunikálj** | Oszd meg a tanulságokat a csapattal és a vezetőséggel | A változás-menedzsment a PM feladata | Folyamatosan |
| **8. Iterálj** | Értékeld újra negyedévente: mi működik, mi nem? | Az AI eszközök és a legjobb gyakorlatok gyorsan változnak | Negyedévente |

\begin{kulcsuzenat}
A PM szerep nem tűnik el -- átalakul. Kevesebb "ki csinálja meg?" és "mikor lesz kész?" -- több "mit csinálunk és miért?" és "elég jó ez?". A legjobb PM-ek azok lesznek, akik értik az AI ágensek képességeit és korlátait, és tudják hogyan kell jó specifikációkat írni. A specifikáció-írás, az AI műveltség, és a minőségi kapuk definiálása -- ezek lesznek a PM legfontosabb képességei az előttünk álló évtizedben. A \href{https://www.weforum.org/publications/the-future-of-jobs-report-2025/}{World Economic Forum} ezt a képet erősíti: az AI nem munkahelyeket szüntet meg, hanem szerepeket alakít át. Ez a könyv az első lépés ezen az úton -- de a tanulás soha nem áll meg.
\end{kulcsuzenat}
