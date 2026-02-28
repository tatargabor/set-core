# OpenSpec -- Specifikacio-vezerelt fejlesztes

## A problema ujra

Az elozo fejezetben lattuk, miert nem eleg a vibe coding. De ha nem "chattelunk az AI-val", akkor hogyan mondjuk el neki, mit csinaljon?

A valasz: **ugyanugy, ahogy egy jo PM elmondja egy fejlesztocsapatnak** -- specifikacioval, tervvel, es feladatlistaval. Csak eppen nem embereknek, hanem AI agenseknek.

Ez az OpenSpec lenyege: egy strukturalt munkafolyamat, ahol **minden lepes dokumentalt, ellenorizheto, es visszakovetheto**.

Ez nem uj gondolat. Az [Agile Manifesto](https://agilemanifesto.org/) 2001-ben fogalmazta meg, hogy a "mukodo szoftver" fontosabb, mint a "reszletes dokumentacio". Ez igaz -- de az AI agensek vilagaban a mukodo szoftver eppen a jo dokumentaciobol szuletik. Az OpenSpec ezt az egyensulyt keresi: **annyi dokumentacio, amennyi kell -- se tobb, se kevesebb**.

## Az OpenSpec es az ismert PM eszkozok -- forditorozsetta

Mielott belemegyunk a reszletekbe, erdemes megerteni, hogyan viszonyulnak az OpenSpec fogalmak ahhoz, amit mar ismersz. Ha dolgoztol Jira-val, Confluence-szel, vagy barmilyen PM eszkozzel ([Linear](https://linear.app/), [Notion](https://www.notion.so/), Asana), a kovetkezo tablazat segit osszekotni a ket vilagot:

| OpenSpec artifact | Ismert PM megfeleloje | Peldak |
|---|---|---|
| **Proposal** | PRD (Product Requirements Document), Product Brief | Amit a PM vagy stakeholder ir: miert kell ez, kinek, mi valtozik |
| **Spec** | User Story-k + Acceptance Criteria, BDD scenariok | "Felhasznalokent szeretnem visszaallitani a jelszavam, hogy..." |
| **Design** | Technical Design Document, ADR (Architecture Decision Record) | Technikai dontesek es indoklasaik |
| **Tasks** | Sprint Backlog, Jira Sub-tasks | Checkboxos lista, amit az AI "pipalgat" |
| **Implementation** | A sprint maga -- a fejlesztes | Az AI ir kodot, commitol, tesztel |

A kulonbseg: a hagyomanyos eszkozoknel ezek **kulonallo rendszerekben** elnek (Jira-ban a ticket, Confluence-ben a spec, Slack-en a dontesek, a fejleszto fejeben a terv). Az OpenSpec-ben **minden egy helyen van, egymast epiti, es a kod mellett el a git-ben**.

Ha eddig [Atlassian eszkozokkel](https://www.atlassian.com/agile/project-management) dolgoztol, gondolj ugy az OpenSpec-re, mint egy "all-in-one" megkozelitesre, ahol a Jira ticket, a Confluence oldal, es a fejlesztes egybeforrva letezik.

## A pipeline -- az otlettol a kodig

Az OpenSpec egy lancot epit fel, ahol minden lepes a kovetkezo alapja:

```
  +------------------------------------------------------------+
  |                    OpenSpec Pipeline                        |
  |                                                            |
  |   +----------+                                             |
  |   | PROPOSAL |  <-- "Mit es miert?"                        |
  |   |          |    PM/stakeholder nyelven                    |
  |   +----+-----+                                             |
  |        |                                                   |
  |        | .......... PM review gate ..........               |
  |        v                                                   |
  |   +----------+                                             |
  |   |  SPECS   |  <-- "Pontosan mit kell tudnia?"            |
  |   |          |    Merheto kovetelmenyek                     |
  |   +----+-----+                                             |
  |        |                                                   |
  |        | .......... PM review gate ..........               |
  |        v                                                   |
  |   +----------+                                             |
  |   |  DESIGN  |  <-- "Hogyan epitjuk meg?"                  |
  |   |          |    Technikai dontesek                        |
  |   +----+-----+                                             |
  |        |                                                   |
  |        | .......... Dev review gate .........               |
  |        v                                                   |
  |   +----------+                                             |
  |   |  TASKS   |  <-- "Mi a teendo lista?"                   |
  |   |          |    Checkboxos feladat lista                  |
  |   +----+-----+                                             |
  |        |                                                   |
  |        v                                                   |
  |   +--------------+                                         |
  |   |IMPLEMENTATION|  <-- Az AI itt kodol                    |
  |   |              |    Feladatrol feladatra halad            |
  |   +--------------+                                         |
  |                                                            |
  |   Minden lepes: markdown fajl, git-ben tarolva,            |
  |   barki altal olvashato es review-olhato                    |
  +------------------------------------------------------------+
```

Figyeld meg a "review gate"-eket a diagramon. Ezek az a pontok, ahol **ember -- te, a PM -- ellenorzi es jovahagyja** a kovetkezo lepes elindulasat. Errol bovebben lentebb.

Nezzuk meg egyenkent, mit tartalmaz minden lepes.

## 1. Proposal -- "Mit es miert?"

A proposal (javaslat) az egyetlen dokumentum, amit idealis esetben **ember ir** -- te, a PM, vagy a stakeholder. Ez mondja el, miert van szukseg erre a valtozasra.

A proposal a klasszikus [PRD (Product Requirements Document)](https://www.atlassian.com/agile/project-management/requirements) egyszeru, tomor megfeleloje. Nem kell 20 oldalas dokumentumot irnod -- 1-2 oldal eleg. A lenyeg: **kontextust adsz az AI-nak**, hogy megertse a problema hatteret.

### Miert fontos a "miert?"

Martin Fowler, a szoftverfejlesztes egyik legismertebb gondolkodoja [irja](https://martinfowler.com/): a legjobb specifikaciok nem azzal kezdodnek, *mit* kell epiteni, hanem azzal, *miert*. Ha az AI (vagy egy fejleszto) erti a miert-et, jobb donteseket hoz a reszletekben.

**Pelda**: Tegyuk fel, hogy felhasznaloi visszajelzesek alapjan kell egy jelszo-visszaallitasi funkcio. Ime egy reszletes proposal:

```
  +-------------- proposal.md ----------------------+
  |                                                  |
  |  # Jelszo-visszaallitas funkcio                  |
  |                                                  |
  |  ## Hatter es motivacio                          |
  |                                                  |
  |  A felhasznalok 15%-a hetente elfelejti          |
  |  a jelszavat. Jelenleg nincs lehetoseg           |
  |  onkiszolgalo visszaallitasra -- a support       |
  |  csapat manualisan reseteli. Ez heti 40          |
  |  support ticket, ami evi ~2000 ticket,           |
  |  atlagosan 15 perc/ticket = 500 ora/ev           |
  |  support koltseg.                                |
  |                                                  |
  |  ## Celcsoport                                   |
  |                                                  |
  |  Minden regisztralt felhasznalo (jelenleg        |
  |  ~12.000 aktiv felhasznalo).                     |
  |                                                  |
  |  ## Sikerkritérium                               |
  |                                                  |
  |  - Support ticketek szama 80%-kal csokken        |
  |    (heti 40 -> heti 8)                           |
  |  - A felhasznalok 90%-a sikeres onkiszolgalo     |
  |    visszaallitast vegez                          |
  |  - A rendszer 99.9% rendelkezesre allassal       |
  |    mukodik                                       |
  |                                                  |
  |  ## Mi valtozik                                  |
  |                                                  |
  |  - Email alapu jelszo-visszaallitas              |
  |  - Token alapu biztonsagi link                   |
  |  - Jelszo erosség ellenorzes                     |
  |  - Audit log minden visszaallitasrol             |
  |                                                  |
  |  ## Erintett teruletek                           |
  |                                                  |
  |  - Auth modul                                    |
  |  - Email kuldes                                  |
  |  - Felhasznaloi felulet                          |
  |  - Admin dashboard (uj riport)                   |
  |                                                  |
  |  ## Amit NEM tartalmaz (scope hatarok)           |
  |                                                  |
  |  - Kétfaktoros hitelesites (kulon projekt)       |
  |  - SMS alapu visszaallitas (kovetkezo fazis)     |
  |  - Social login (kulon proposal)                 |
  |                                                  |
  +--------------------------------------------------+
```

**PM szemmel**: A proposal az, amit eddig is irtal -- egy rovid leiras a valtozasrol, uzleti indoklassal. Semmi technikai zsargon. De figyeld meg a ket uj szekciót: a **Sikerkritérium** (honnan tudjuk, hogy sikeres volt?) es az **Amit NEM tartalmaz** (mi az, amihez nem nyulunk). Ez a ket szekció rengeteg felreertest eloz meg -- mind az AI, mind a csapat fele.

**Tipp**: A [Shape Up metodologia](https://basecamp.com/shapeup) -- amit a Basecamp fejlesztett ki -- ugyanezt javasolja: minden projekt elinditasa elott határozd meg, mi az "appetite" (mennyi idot akarsz raszanni) es mi a "no-go" (amihez biztosan nem nyulsz). A proposalban a scope hatarok pontosan ezt a ceelt szolgaljak.

## 2. Specs -- "Pontosan mit kell tudnia?"

A specifikacio a proposal-bol **merheto kovetelményeket** csinal. Ezt altalaban az AI generalja a proposal alapjan, de a PM review-olja.

A specifikacio formatuma a BDD (Behaviour-Driven Development) szcenariokra hasonlit: "HA ez tortenik, AKKOR ez legyen az eredmeny". Ez a formatum azert hasznos, mert **minden forgatokonyv kozvetlenul tesztelhetove valik** -- az AI teszt kodot tud generalni belole.

```
  +-------------- spec.md ---------------------------------+
  |                                                         |
  |  # Jelszo-visszaallitas -- Specifikacio                 |
  |                                                         |
  |  ## 1. Kovetelmeny: Visszaallitas keres                 |
  |                                                         |
  |  A felhasznalo a bejelentkezo oldalon kepes             |
  |  jelszó-visszaallitast kezdemenyezni az email           |
  |  cime megadasaval.                                      |
  |                                                         |
  |  ### 1.1 Forgatokonyv: Sikeres keres                    |
  |  - HA a felhasznalo megadja az email cimet              |
  |  - ES az email cim letezik a rendszerben                |
  |  - AKKOR a rendszer kuld egy linket                     |
  |    ami 24 oraig ervenyes                                |
  |  - ES a felhasznalo sikeres visszajelzest kap           |
  |    ("Ellenorizd az emailjeidet")                        |
  |                                                         |
  |  ### 1.2 Forgatokonyv: Nem letezo email                 |
  |  - HA az email cim nincs a rendszerben                  |
  |  - AKKOR a rendszer UGYANAZT a visszajelzest            |
  |    mutatja (biztonsagi okokbol)                         |
  |  - ES NEM kuld emailt                                   |
  |  - ES NEM jelzi, hogy a cim nem letezik                 |
  |                                                         |
  |  ### 1.3 Forgatokonyv: Tul sok keres                    |
  |  - HA a felhasznalo 5-nel tobb kerest kuld              |
  |    1 oran belul                                         |
  |  - AKKOR a rendszer 1 orara blokkolja                   |
  |    a további keréseket                                  |
  |  - ES naplozza a gyanús tevékenysget                    |
  |                                                         |
  |  ## 2. Kovetelmeny: Token hasznalat                      |
  |                                                         |
  |  ### 2.1 Forgatokonyv: Ervenyes token                   |
  |  - HA a felhasznalo a kapott linkre kattint             |
  |  - ES a token 24 oran belul van                         |
  |  - AKKOR uj jelszo megadasa oldal jelenik meg           |
  |                                                         |
  |  ### 2.2 Forgatokonyv: Lejart token                     |
  |  - HA a felhasznalo 24 ora utan kattint                 |
  |  - AKKOR hibauzenet es uj keres lehetoseg              |
  |                                                         |
  |  ### 2.3 Forgatokonyv: Mar hasznalt token               |
  |  - HA a token mar egyszer felhasznalasra kerult         |
  |  - AKKOR hibauzenet: "Ez a link mar felhasznalt"        |
  |                                                         |
  |  ## 3. Kovetelmeny: Uj jelszo beallitas                  |
  |                                                         |
  |  ### 3.1 Forgatokonyv: Ervenyes uj jelszo               |
  |  - HA az uj jelszo megfelel a szabalyoknak              |
  |    (min. 8 karakter, szam, nagybetu)                    |
  |  - AKKOR a jelszo megvaltozik                           |
  |  - ES minden aktiv session kijelentkezik                |
  |  - ES a felhasznalo ertesito emailt kap                 |
  |                                                         |
  |  ### 3.2 Forgatokonyv: Gyenge jelszo                    |
  |  - HA az uj jelszo nem felel meg a szabalyoknak         |
  |  - AKKOR real-time visszajelzes mutatja                 |
  |    melyik szabaly nem teljesul                          |
  |                                                         |
  +----------------------------------------------------------+
```

**PM szemmel**: A spec az, amit eddig a fejlesztovel egyeztettel szoban -- de most le van irva, visszakeresheto, es az AI is erti. Minden "forgatokonyv" egy potencialis teszt eset. Amikor review-olod, a kovetkezo kerdeseket tedd fel magadnak:

1. **Teljes-e?** -- Van-e olyan felhasznaloi szituacio, ami kimaradt?
2. **Ertelmes-e?** -- Ertened-e mint felhasznalo, mit csinal a rendszer?
3. **Tesztelheto-e?** -- Minden forgatokonyvnek van egyertelmu "AKKOR" resze?
4. **Konzisztens-e?** -- Nincsenek-e ellentmondasok a forgatokonyvek kozott?

A specifikacio-review a PM legfontosabb minoseg-ellenorzo eszkoze. Ha a spec jo, a kod jo lesz. Ha a spec hibas, a kod is hibas lesz -- de legalabb tudjuk, *miert*.

## 3. Design -- "Hogyan epitjuk meg?"

A design dokumentum a technikai donteseket rogziti. Ezt az AI kesziti, de a senior fejleszto review-olja.

A design az ugynevezett [ADR (Architecture Decision Record)](https://www.thoughtworks.com/radar) formátumot koveti -- ez a [ThoughtWorks Tech Radar](https://www.thoughtworks.com/radar) altal is javasolt bevalt gyakorlat. Minden technikai dontes egy onallo bejegyzés, ami tartalmazza a dontest, az alternativakat, es az indoklast.

```
  +-------------- design.md -----------------------------------+
  |                                                             |
  |  # Jelszo-visszaallitas -- Design                           |
  |                                                             |
  |  ## Architekturalis dontesek                                |
  |                                                             |
  |  ### ADR-001: Token generalas                               |
  |  Statusz: Elfogadva                                         |
  |  Dontes: Veletlenszeru 256-bites token                      |
  |  Kontextus: Biztonsagos, egyedi tokent kell                 |
  |    generalni minden visszaallitasi kereshez.                |
  |  Alternativa 1: JWT token -- elvetettuk, mert               |
  |    nem vonhato vissza (stateless).                          |
  |  Alternativa 2: Szamlalo alapu ID -- elvetettuk,            |
  |    mert kitalalhato (brute force tamadas).                  |
  |  Kovetkezmeny: Token tablat kell letrehozni                 |
  |    az adatbazisban, lejarat mezovel.                        |
  |                                                             |
  |  ### ADR-002: Email szolgaltatas                             |
  |  Statusz: Elfogadva                                         |
  |  Dontes: A meglevo SendGrid integraciot                     |
  |    hasznaljuk.                                              |
  |  Kontextus: Mar van SendGrid fiokunk, nincs                 |
  |    szukseg uj szolgaltatasra.                               |
  |  Alternativa: Sajat SMTP -- tul komplex                     |
  |    ehhez a feladathoz.                                      |
  |  Kovetkezmeny: A meglevo email modulra epitunk.             |
  |                                                             |
  |  ### ADR-003: Session kezelés                                |
  |  Statusz: Elfogadva                                         |
  |  Dontes: Jelszo valtoztatas utan minden                     |
  |    aktiv session lezarasra kerul.                            |
  |  Kontextus: Ha valaki jogosulatlanul hasznalta              |
  |    a fiokot, a jelszo valtoztatas utan sem                  |
  |    maradhat bejelentkezve.                                  |
  |  Alternativa: Csak az aktualis session marad --             |
  |    biztonsagi kockazat.                                     |
  |                                                             |
  |  ## Kockazatok                                              |
  |                                                             |
  |  - [Kockazat] Email deliverability                          |
  |    -> Spam filterek blokkolhatjak                           |
  |    -> Megoldas: SPF/DKIM beallitas                          |
  |    -> Felelős: DevOps csapat                                |
  |                                                             |
  |  - [Kockazat] Token brute force                             |
  |    -> Rosszindulatu felhasznalo probalgathatja              |
  |       a tokeneket                                           |
  |    -> Megoldas: Rate limiting + 256-bites                   |
  |       token (gyakorlatilag kitalalhatatlan)                 |
  |                                                             |
  |  - [Kockazat] Email keses                                   |
  |    -> A felhasznalo nem kapja meg ideben                    |
  |    -> Megoldas: "Nem kaptad meg?" ujrakuldo                 |
  |       gomb + 2 perc varakozasi ido utana                    |
  |                                                             |
  +-------------------------------------------------------------+
```

**PM szemmel**: Nem kell ertened a technikai reszleteket. De ket dolgot erdemes figyelni:
- **Dontesek**: Vannak alternativak feltuntetve? (Ha igen, atgondolt dontes volt. Ha nem, kerd meg az AI-t, hogy mutassa meg az alternativakat.)
- **Kockazatok**: Vannak megoldasi javaslatok mellettuk? (Ha igen, felkeszultek. Ha nincs megoldasi javaslat, az piros flag -- kerdezz ra.)

Az ADR formatum egyik nagy elonye, hogy **a dontesek visszakovethetek**. Ha 3 honap mulva felmerul a kerdes "miert nem JWT-t hasznalunk?", nem kell senki fejeben turkalni -- ott van a design.md-ben, indoklassal egyutt.

A [GitLab fejlesztoi kezikonyve](https://handbook.gitlab.com/handbook/engineering/) hasonlo megkozelitest kovet: minden architekturalis dontest dokumentalnak, es a dokumentum a kod mellett el. Ez nem burokracia -- ez **intezmenyi memoria**.

## 4. Tasks -- "Mi a teendo lista?"

A tasks.md a feladatok checkboxos listaja. Ez az AI munkalapja -- feladatrol feladatra halad, es bejeloli ami kesz.

```
  +-------------- tasks.md --------------------------------+
  |                                                         |
  |  ## 1. Adatbazis                                        |
  |                                                         |
  |  - [x] 1.1 Token tabla letrehozasa                      |
  |  - [x] 1.2 Token lejarat mezo hozzaadasa                |
  |                                                         |
  |  ## 2. Backend                                          |
  |                                                         |
  |  - [x] 2.1 Reset endpoint implementalas                 |
  |  - [x] 2.2 Token generalas logika                       |
  |  - [ ] 2.3 Email kuldes integracio             <-- itt  |
  |  - [ ] 2.4 Rate limiting (5 keres/ora)                  |
  |                                                         |
  |  ## 3. Frontend                                         |
  |                                                         |
  |  - [ ] 3.1 Reset keres form                             |
  |  - [ ] 3.2 Uj jelszo form                               |
  |  - [ ] 3.3 Jelszo-erosség indikator                     |
  |                                                         |
  |  ## 4. Biztonsag                                        |
  |                                                         |
  |  - [ ] 4.1 Session invalidalas jelszo valtoztatáskor     |
  |  - [ ] 4.2 Audit log implementalas                      |
  |                                                         |
  |  ## 5. Teszteles                                        |
  |                                                         |
  |  - [ ] 5.1 Unit tesztek                                 |
  |  - [ ] 5.2 E2E tesztek                                  |
  |  - [ ] 5.3 Biztonsagi tesztek (brute force)             |
  |                                                         |
  |  Haladas: 4/13 kesz (31%)                               |
  |                                                         |
  +----------------------------------------------------------+
```

**PM szemmel**: Ez a tasks.md a projektmenedzsment aranybanyaja. Egyetlen fajl, ami megmondja:
- **Mi van kesz** es **mi nincs** -- pontosan, valos idoben
- **Mennyi maradt** -- szazalekos haladas
- **Mi a kovetkezo** -- az elso bepipálatlan feladat
- **Milyen kategoriak vannak** -- adatbazis, backend, frontend, biztonsag, teszteles

Nem kell a fejlesztot kerdezned: "Hogy allsz?" Megnyitod a tasks.md fajlt, es latod.

Ha megszoktad a [Linear](https://linear.app/) vagy Jira sprint board-ot, gondolj a tasks.md-re ugy, mint annak a szoveges valtozatara -- csak ezt nem kell manuálisan frissíteni, mert az AI automatikusan bepipalja a kesz feladatokat.

## A review gate -- a PM mint minosegkapu

Az OpenSpec pipeline legfontosabb eleme nem maga a dokumentum, hanem a **review gate-ek** -- azok a pontok, ahol ember ellenorzi es jovahagyja a kovetkezo lepes elindulasat.

```
  +------------------------------------------------------------+
  |                  Review Gate-ek                             |
  |                                                            |
  |  PROPOSAL (ember irja)                                     |
  |       |                                                    |
  |       v                                                    |
  |  [=== GATE 1: PM review ===]                               |
  |  Kerdesek:                                                 |
  |  - Teljes-e a hatter es motivacio?                         |
  |  - Van sikerkritérium?                                     |
  |  - Vilagosak a scope hatarok?                              |
  |       |                                                    |
  |       v                                                    |
  |  SPEC (AI generalja)                                       |
  |       |                                                    |
  |       v                                                    |
  |  [=== GATE 2: PM review ===]                               |
  |  Kerdesek:                                                 |
  |  - Minden felhasznaloi szituacio le van fedve?             |
  |  - A forgatokonyvek tesztelhetoek?                         |
  |  - Nincs ellentmondas?                                     |
  |       |                                                    |
  |       v                                                    |
  |  DESIGN (AI generalja)                                     |
  |       |                                                    |
  |       v                                                    |
  |  [=== GATE 3: Dev review ===]                              |
  |  Kerdesek:                                                 |
  |  - Van alternativa minden dontesnel?                       |
  |  - A kockazatok kezelve vannak?                            |
  |  - A PM: van-e uzleti kockazat?                            |
  |       |                                                    |
  |       v                                                    |
  |  TASKS -> IMPLEMENTATION                                   |
  |       |                                                    |
  |       v                                                    |
  |  [=== GATE 4: Vegso review ===]                            |
  |  Kerdesek:                                                 |
  |  - Minden task bepipálva?                                  |
  |  - Tesztek futnak?                                         |
  |  - A spec-nek megfelel az eredmeny?                        |
  |                                                            |
  +------------------------------------------------------------+
```

Minden gate-nel **a PM donti el, hogy tovabbmegy-e a folyamat**. Ez nem lassitja le a munkat -- egy spec review 10-20 perc. De megelozi, hogy az AI rossz iranyba induljon el, es orak munkaját kelljen kidobni.

Ez a megkozelftes hasonlit a [Shape Up metodologia](https://basecamp.com/shapeup) "betting table" koncepciojahoz: a csapat nem indit el mindent, ami felmerul, hanem **tudatosan dont, mi az, ami erdemes a befektett idore**. A review gate ugyanez mikro-szinten: minden fazis elott tudatos dontes szuletik.

## A PM szerepe az OpenSpec munkafolyamatban

A legfontosabb kerdes: hol vagy te ebben a folyamatban?

```
  +-------------------------------------------------------+
  |                                                       |
  |  PM ir --------> PROPOSAL ------> AI generalja ----> |
  |                  PM review                            |
  |                                                       |
  |  AI generalja --> SPECS --> PM review --------------> |
  |                   "Igen, ezt akarom"                  |
  |                    vagy                               |
  |                   "Nem, ez hiányzik: ..."             |
  |                                                       |
  |  AI generalja --> DESIGN --> Dev review -------------> |
  |                   PM: dontesek es kockazatok OK?      |
  |                                                       |
  |  AI generalja --> TASKS ---> AI implemental ---------> |
  |                   PM: haladas nyomon kovetese         |
  |                                                       |
  |  AI implemental --> KOD ---> Dev + PM review -------> |
  |                    Tesztek futnak?                     |
  |                    Spec-nek megfelel?                  |
  |                                                       |
  +-------------------------------------------------------+
```

**Osszefoglalva a PM teendoit**:

| Fazis | PM feladata | Idoigeny |
|-------|------------|----------|
| Proposal | Megirja | 15-30 perc |
| Specs | Review-olja: teljes-e, pontos-e? | 10-20 perc |
| Design | Atfutja: vannak-e kockazatok? | 5-10 perc |
| Tasks | Nyomon koveti a haladast | Folyamatos, passziv |
| Implementation | Vegeredmenyt ellenorzi | Review-nkent 10-20 perc |

**A teljes PM idoráforditas egy feature-re: 1-2 ora**, szemben a korabbi napokkal amit egyeztetesre, status meetingekre, es kerdesek megvalaszolasara forditott.

## Egy PM napja az OpenSpec-kel -- gyakorlati peldak

Hogyan nez ki egy tipikus munkanap, ha OpenSpec-et hasznalsz? Ime egy valos szcenario:

```
  +------------------------------------------------------------+
  |  PM napirend -- OpenSpec munkafolyamat                     |
  |                                                            |
  |  09:00  Reggeli attekintes                                 |
  |         - Megnyitod a futo change-ek tasks.md fajljait     |
  |         - Megnezed: mi keszult el tegnapota                |
  |         - Halvanyodik: 60% -> 78% (jo utemben halad)       |
  |                                                            |
  |  09:30  Uj proposal iras                                   |
  |         - A stakeholder tegnap kerte az export funkciót    |
  |         - 20 percben megírod a proposal.md-t               |
  |         - Elinditod: az AI generalja a specifikaciot       |
  |                                                            |
  |  10:00  Spec review                                        |
  |         - Az AI elkeszitette a spec.md-t az export         |
  |           funkciohoz                                       |
  |         - Vegigolvasod: 8 forgatokonyv, 3 kovetelmeny      |
  |         - Eszrevetel: "hiányzik a CSV export, csak         |
  |           XLSX van" -> visszakuldod javitasra               |
  |         - 15 perc munka                                    |
  |                                                            |
  |  11:00  Stakeholder meeting                                |
  |         - A jelszó-visszaallitas feature 78%-ban kesz      |
  |         - Megmutatod a tasks.md-t: "13-bol 10 task kesz,   |
  |           a teszteles van hatra"                           |
  |         - Nem "erzesre" mondod az allapotat -- szamok      |
  |           vannak                                           |
  |                                                            |
  |  14:00  Design review                                      |
  |         - Az export funkcio design.md-je elkeszult          |
  |         - Atfutod a donteseket: az AI streaming CSV-t      |
  |           javasol nagy fajlokhoz -- jol hangzik             |
  |         - Kockazat: memoriahaszanlat nagy exportnal         |
  |           -> van megoldas mellette -> OK                    |
  |         - 10 perc munka                                    |
  |                                                            |
  |  15:00  Vegso review                                       |
  |         - A jelszó-visszaallitas 100%: minden task kesz    |
  |         - Vegnezed az eredmenyt: a spec forgatokonyvei     |
  |           alapjan ellenorzod                               |
  |         - "Lejart token -> hibauzenet" -- OK               |
  |         - "Rate limiting -> blokkol 5 keres utan" -- OK    |
  |         - Jovahagyod a merge-et                            |
  |                                                            |
  |  16:00  Riportolas                                         |
  |         - A nap vegen osszegzed: 1 feature lezarva,        |
  |           1 uj feature specifikacios fazisban               |
  |         - A kovetkezo napi terv: spec review az            |
  |           export funkciohoz                                |
  |                                                            |
  +------------------------------------------------------------+
```

Figyeld meg: a PM napjanak nagy resze **olvasas es dontes**, nem koordinacio es statuszkerdezgetes. Ez az OpenSpec legnagyobb elonye a PM szamara.

## Hogyan nez ki ez a gyakorlatban?

Lassunk egy valos peldat a wt-tools projektbol. Egy uj funkciot akartunk hozzaadni: "az AI agensek kuldjenek uzeneteket egymasnak".

**1. lepes**: Proposal megirasa (5 perc)
> *"A parhuzamosan dolgozo AI agensek nem tudnak kommunikalni egymassal. Ha az egyik agens felfedez valamit, ami a masik munkajat erinti, nincs modja szolni. Megoldas: egyszeru uzenetküldo rendszer."*

**2. lepes**: Az AI geneval specifikaciot (automatikus)
> *Kovetelmenyek: uzenet kuldes agens -> agens, inbox lekerdezes, broadcast uzenet mindenkinek, uzenetek szinkronizálasa gepek kozott.*

**3. lepes**: PM review -- "A broadcast jo otlet, viszont legyen timestamp is" -> specifikacio frissul

**4. lepes**: Design generalas (automatikus)
> *Dontes: fajl alapu rendszer, nincs szerver szukseges. Uzenetek JSON sornonkent egy fajlban, a meglevo git sync viszi gepek kozott.*

**5. lepes**: Tasks generalas -> 8 feladat, checkboxos lista

**6. lepes**: Implementacio -> az AI dolgozik, PM nezi a haladast a tasks.md-ben

**Eredmeny**: 3 ora alatt kesz egy funkcio, ami hagyomanyos modon 2-3 nap lett volna. Es minden lepes dokumentalva van, visszakeresheto.

## Visszakovethetos -- a proposal-tol a kodig

Az OpenSpec egyik legfontosabb tulajdonsaga a **teljes visszakovethetoseg** (traceability). Minden sor kod visszavezetheto egy feladatra, minden feladat egy specifikaciohoz, minden specifikacio egy proposal-hoz.

```
  +------------------------------------------------------------+
  |  Visszakovethetosegi lanc                                  |
  |                                                            |
  |  Proposal: "A felhasznalok 15%-a elfelejti a jelszavat"   |
  |       |                                                    |
  |       +---> Spec 2.3: "Mar hasznalt token -> hibauzenet"  |
  |                 |                                          |
  |                 +---> Task 4.2: "Audit log implementalas"  |
  |                           |                                |
  |                           +---> Commit: "feat: add         |
  |                                 password reset audit log"  |
  |                                    |                       |
  |                                    +---> Fajl:             |
  |                                    src/auth/audit.ts       |
  |                                                            |
  |  Ha barki megkerdezi: "Miert van ez a kod itt?"            |
  |  A valasz: vegigkoveted a lancot a proposal-ig.            |
  +------------------------------------------------------------+
```

Ez kulonosen fontos szabalyozott iparagakban (penzugy, egeszsegugy, kormányzat), ahol auditalhatosag szukseges. De akar egy startup-nal is hasznos: 6 honap mulva nem kell talalgatnod, miert van egy adott funkcio a rendszerben.

A hagyomanyos fejlesztesben ez a lanc altalaban **fejekben el** -- es amikor valaki tavozik a csapatbol, a tudas elveszik. Az OpenSpec-ben a lanc **fajlokban el**, a kod mellett, a git-ben.

## Mi van, ha a spec hibas? -- Iteraciok es frissitesek

A valosag az, hogy **a legjobb specifikacio sem tokeletes**. Fejlesztes kozben derulhetnek ki uj szempontok, a stakeholder meggondolhatja magat, vagy a technikai korlatokkal szembesulve modositani kell.

Az OpenSpec erre is felkeszult:

```
  +------------------------------------------------------------+
  |  Spec iteracio munkafolyamat                               |
  |                                                            |
  |  Eredeti spec                                              |
  |       |                                                    |
  |       v                                                    |
  |  Implementacio soran felfedezunk valamit:                  |
  |  "A SendGrid API nem tamogatja a sablon                    |
  |   nyelvet, amit terveztunk"                                |
  |       |                                                    |
  |       v                                                    |
  |  Lehetosegek:                                              |
  |                                                            |
  |  A) Spec frissites -- a kovetelmeny modosul                |
  |     -> spec.md-ben uj verzio, git commit-ban lathato       |
  |     -> tasks.md frissul (uj/modositott feladatok)          |
  |     -> PM review: "OK, ez elfogadhato kompromisszum"       |
  |                                                            |
  |  B) Design frissites -- a megvalositas modosul             |
  |     -> design.md-ben uj ADR bejegyzes                      |
  |     -> a spec valtozatlan marad                            |
  |     -> Dev review: "OK, ez jobb megoldas"                  |
  |                                                            |
  |  C) Proposal frissites -- az scope modosul                 |
  |     -> proposal.md-ben uj "Amit NEM tartalmaz" bejegyzes   |
  |     -> PM + stakeholder review                             |
  |     -> Dontes: "Ezt kiemeljuk kulon feature-be"            |
  |                                                            |
  +------------------------------------------------------------+
```

A lenyeg: **minden valtozas dokumentalt**. A git tortenete megmutatja, mi volt az eredeti spec, es hogyan modosult. Nem veszik el semmi -- a korabbi verziok mindig visszanezhetoek.

Ez kulonbozik a hagyomanyos megkozelitestol, ahol a specifikacio-valtozasok gyakran szobeli megallapodasok ("egyeztettunk Marcieval, hogy ez nem kell"). Az OpenSpec-ben minden modositas egy commit, ami lathato, review-olhato, es visszavonhato.

## Osszehasonlitas: Waterfall vs Agile vs OpenSpec

Ha ismered a klasszikus projekt-modszertanokat, erdemes latni, hogyan viszonyul hozzajuk az OpenSpec:

```
  +------------------------------------------------------------+
  |  Harom megkozelites osszehasonlitasa                       |
  |                                                            |
  |  WATERFALL (hagyományos)                                   |
  |  +------+------+------+------+------+                      |
  |  | Kove-| Terv | Impl.| Teszt| Atad.|                      |
  |  | telm.|      |      |      |      |                      |
  |  +------+------+------+------+------+                      |
  |  |----- 6-12 honap ------------------>                     |
  |  Jellemzo: Minden elore megtervezett.                      |
  |  Hatrany: Keson derul ki, ha rossz iranyba ment.           |
  |                                                            |
  |  AGILE / SCRUM                                             |
  |  +----+ +----+ +----+ +----+ +----+                        |
  |  | S1 | | S2 | | S3 | | S4 | | S5 |                       |
  |  +----+ +----+ +----+ +----+ +----+                        |
  |  |-2hét-|-2hét-|-2hét-|-2hét-|-2hét->                      |
  |  Jellemzo: Kis iteraciok, folyamatos visszajelzes.         |
  |  Hatrany: Gyakran hiányzik a dokumentacio,                 |
  |  a tudas a fejleszto fejeben marad.                        |
  |                                                            |
  |  OPENSPEC                                                  |
  |  +--------+    +--------+    +--------+                    |
  |  |Proposal|    |Proposal|    |Proposal|                    |
  |  |Spec    |    |Spec    |    |Spec    |                    |
  |  |Design  |    |Design  |    |Design  |                    |
  |  |Tasks   |    |Tasks   |    |Tasks   |                    |
  |  |Impl.   |    |Impl.   |    |Impl.   |                    |
  |  +--------+    +--------+    +--------+                    |
  |  |--orak--| -> |--orak--| -> |--orak--|-->                 |
  |  Jellemzo: Teljesen dokumentalt, AI vegrehajtja,           |
  |  orak alatt kesz ami regen hetekbe telt.                   |
  |  Hatrany: A proposal minosege meghatarozo.                 |
  |                                                            |
  +------------------------------------------------------------+
```

| Szempont | Waterfall | Agile/Scrum | OpenSpec |
|----------|-----------|-------------|---------|
| Tervezes | Mindent elore | Sprint elejen | Feature elejen |
| Dokumentacio | Tulzott | Minimalis | Pont eleg |
| Visszajelzes | Keso (honapok) | Gyors (2 het) | Azonnali (orak) |
| Ki implemental | Fejleszto | Fejleszto | AI agens |
| PM lathatos | Merfoldko riport | Standup + board | tasks.md (valos ideju) |
| Valtozas kezelese | Nehezkes (CR) | Sprint hataron | Spec update + ujrafutas |
| Szallitas | Egy nagy release | Sprint vegeken | Folyamatosan |

Az [Agile Manifesto](https://agilemanifesto.org/) negy alapelve kozul harom kozvetlenul vonatkozik az OpenSpec-re:

1. **"Mukodo szoftver a reszletes dokumentacio helyett"** -- Az OpenSpec pontosan annyi dokumentaciot keszit, amennyit a mukodo szoftver eloallitasa igenyel, se tobbet, se kevesebbet.
2. **"Egyuttmukodes az ugyfellel a szerzodeses targyalas helyett"** -- A PM folyamatosan review-olja es igazitja az iranyt, nem egyszer ad meg mindent elore.
3. **"Valtozasra valaszolas a terv kovetese helyett"** -- A spec barmiktor frissitheto, es az AI az uj spec alapjan dolgozik tovabb.

## Az OpenSpec es a Shape Up metodologia

A [Shape Up](https://basecamp.com/shapeup) -- a Basecamp altal kifejlesztett termekfejlesztesi modszertan -- sok szempontbol az OpenSpec szellemi elode. Erdemes latni a parhuzamokat:

| Shape Up fogalom | OpenSpec megfeleloje |
|---|---|
| **Shaping** (a problema "formaba ontese") | Proposal iras |
| **Appetite** (mennyi idot szanunk ra) | A proposal scope hatarai |
| **Pitch** (rovid javaslat, amit elfogadnak/elutasitanak) | A proposal maga |
| **Betting table** (dontes, mi az, amire "fogadunk") | PM review gate |
| **Hill chart** (haladas vizualizalasa) | tasks.md szazalekos haladas |
| **Cool down** (pihenoszunet ciklusok kozott) | Review es iteracios idoszak |

A Shape Up legfontosabb tanítása: **a projekt sikeret a shaping (formázás) fazis minosege hatarozza meg**. Ha jol "formázod" a problemat, a megvalositás egyszeru. Ha rosszul, semmilyen mennyisegu fejlesztoi munka nem menti meg.

Az OpenSpec-ben ugyanez igaz: **a proposal minosege meghatarozo**. Egy jo proposal-bol jo spec szuletik, abbol jo design, abbol jo kod. Egy rossz proposal-bol kaotikus specifikacio lesz, es az AI rossz iranyba halad.

## Az OpenSpec es a hagyomanyos PM eszkozok

Talan felmerul: "Miben mas ez, mint a Jira?"

| Szempont | Jira / hagyomanyos | OpenSpec |
|----------|-------------------|----------|
| Ki irja a ticketet? | PM | PM (proposal) |
| Ki bontja feladatokra? | Dev + PM meeting | AI automatikusan |
| Hol van a spec? | Confluence (talaan) | A kod mellett, git-ben |
| Hol van a haladas? | Jira board | tasks.md (valos ideju) |
| Ki frissiti? | Dev (ha emlekszik) | AI automatikusan |
| Review-olhato? | Board szintjen | Artifact szintjen |
| Visszakovetheto? | Ticket linkek (ha vannak) | Teljes lanc (proposal -> kod) |
| Valtozas tortenete? | Ticket kommentek | Git history (minden verzio) |

**Az OpenSpec nem helyettesiti a Jirat.** De kiegesziti: a Jira ticket-bol lesz egy proposal, abbol specifikacio, abbol feladatlista, abbol kod. Minden osszefugg, minden visszakovetheto.

A gyakorlatban sok csapat megtartja a Jira-t (vagy a [Linear](https://linear.app/)-t, [Notion](https://www.notion.so/)-t) a magasabb szintu portfolio menedzsmenthez es stakeholder riportolashoz, mig az OpenSpec a **fejlesztesi vegrehajtast** strukturalja. A ketto egyutt mukodik: a Jira ticket hivatkozik az OpenSpec proposal-ra, a tasks.md haladas visszatukrozodik a Jira status-ban.

## Tovabbolvasas

Ha tobbnet szeretnel tudni az itt emlitett koncepciekrol, ime a legfontosabb forrasok:

- **[Agile Manifesto](https://agilemanifesto.org/)** -- Az agilis fejlesztes alapelvei, amelyekre az OpenSpec is epit.
- **[Shape Up (Basecamp)](https://basecamp.com/shapeup)** -- A Basecamp termekfejlesztesi modszertana, az OpenSpec szellemi elode. Ingyenesen olvashato online.
- **[Atlassian Agile Guides](https://www.atlassian.com/agile/project-management)** -- Gyakorlati utmutatok specifikaciok es kovetelmenykezeles temakon.
- **[Martin Fowler blogja](https://martinfowler.com/)** -- A szoftverfejlesztes egyik legelismertebb gondolkodoja, akinek irásai a specifikaciok es tervezes temaiban kulonosen relevansak.
- **[GitLab Engineering Handbook](https://handbook.gitlab.com/handbook/engineering/)** -- Peldaerteku nyilt fejlesztesi folyamat, architekturalis dontesek dokumentalasaval.
- **[Claude Code dokumentacio](https://code.claude.com/docs/en/overview)** -- Az Anthropic hivatalos dokumentacioja az AI-vezérelt fejleszteshez.
- **[ThoughtWorks Tech Radar](https://www.thoughtworks.com/radar)** -- Technologiai trendek es bevalt gyakorlatok, beleertve az ADR formátumot.

\begin{kulcsuzenat}
Az OpenSpec munkafolyamatban a PM vegre nem a fejlesztot kerdezgeti, hanem olvashato dokumentumokat review-ol. Az AI a tervbol dolgozik, nem a levegobe beszeltek. A haladas valos ideju, a minoseg merheto, es ha valami nem stimmel, visszamehetsz a specifikaciohoz es ramutathatsz ra: "ezt kertem, ezt kaptam -- mi a kulonbseg?" A review gate-ek biztositjak, hogy a PM megmarad donthozonak -- nem az AI donti el, mit epit, hanem te. Az AI vegrehajtja, amit a specifikaciod eloir.
\end{kulcsuzenat}
