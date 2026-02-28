# Vibe Coding — a csábítás és a csapda

## Mi az a „vibe coding"?

2025 februárjában [Andrej Karpathy](https://x.com/karpaborern) — a világ egyik legismertebb AI kutatója, korábban a Tesla AI igazgatója, az OpenAI alapító tagja — közzétett [egy bejegyzést az X-en](https://x.com/karpaborern/status/1886192184808149383), amiben leírta az új fejlesztési stílusát:

> *„Csak látok dolgokat, mondok dolgokat, futtatom a kódot, és bemásolom a dolgokat, és nagyjából működik."*

Ezt nevezte el **vibe coding**-nak — szó szerinti fordításban „hangulat alapú kódolás". A lényeg: nem kell értened a kódot, csak elmondod az AI-nak mit akarsz, és ő megcsinálja. Ha nem jó, mondod újra, más szavakkal. Mintha egy beszélgetésből születne a szoftver.

A kifejezést azóta az egész technológiai iparág átvette. A [ThoughtWorks Technology Radar](https://www.thoughtworks.com/radar) 2025-ös kiadásában már külön pontot kapott, és számos szakmai blogon — például [Simon Willison AI coding blogjában](https://simonwillison.net/) — rendszeresen elemzik az előnyeit és a veszélyeit. A [Fireship YouTube csatorna](https://www.youtube.com/@Fireship) több milliós megtekintésű videókban magyarázza el a koncepciót rövidre fogva.

**És ez működik.** Prototípusokra, egyszerű alkalmazásokra, személyes projektekre tökéletesen alkalmas. Egy hétvége alatt működő weboldalt csinálhatsz anélkül, hogy egyetlen sort írnál.

De van egy probléma. És ez a probléma annál nagyobb, minél komolyabb a projekt.

## A való világban: házépítés terv nélkül

Mielőtt belemerülünk a technikai részletekbe, gondoljunk egy egyszerű analógiára, amit minden PM ismer.

Képzeld el, hogy házat építesz. Két lehetőséged van:

**A) Terv nélkül („vibe building")**

Odamész az építkezésre és azt mondod: „Csináljatok egy szép házat." Az építőmester elkezd téglát rakni. Szép lesz az első szoba. Aztán szólsz: „Legyen még egy emelet." Na, de a fundamentum ehhez gyenge. Szóval: át kell építeni az alapot. Ami azt jelenti, hogy az első szoba fele lerombolódik. Újrakezdés. Aztán jön a villanyszerelő: „Hol menjenek a kábelek?" Senki nem tudja, mert nincs tervrajz. Minden fal felbontása újabb meglepetés.

**B) Tervrajzzal („spec-driven building")**

Először megrajzolja az építész a terveket. Az „elveszett" idő? Két hét. De utána minden szakember pontosan tudja, mit hol kell csinálni. A PM (építésvezető) megnézi a tervet és mondja: „Oké, de a konyha legyen nagyobb." Átrajzolják a papírt — nem kell falat bontani. Az építés után a tervrajz megmarad: ha tíz év múlva felújítasz, pontosan látod, hol mennek a csövek.

**Ez az analógia tökéletesen lefordítható szoftverre:**

```
  Házépítés                          Szoftverfejlesztés
  ─────────                          ───────────────────
  Tervrajz                           Specifikáció
  Fundamentum                        Architektúra
  Falépítés                          Kód írás
  Villanyszerelés                    Integrációk (API, DB)
  Lakás-átadáskor ellenőrzés         Tesztelés és review
  Építésvezető (PM)                  Projektmenedzser
  Tulajdonos                         Stakeholder
```

A vibe coding olyan, mint terv nélkül építeni: az első szoba gyorsan kész, de ahogy nő a ház, egyre több mindent kell újracsinálni.

## A csábítás

A vibe coding azért csábító, mert **azonnali eredményt ad**. Nincs tervezés, nincs specifikáció, nincs design review. Csak te és az AI, beszélgettek, és 10 perc múlva van valami ami működik.

[Addy Osmani](https://addyosmani.com/blog/), a Google senior mérnöke, aki sokat ír a fejlesztői produktivitásról, sokszor rámutatott arra, hogy a „gyors eredmény" érzete megtévesztő lehet. Az azonnali feedback loop — látod hogy valami működik — dopamint ad, és azt az illúziót kelti, hogy a projekt jól halad. De a „működik a képernyőmön" és a „kész a production-re" között hatalmas a különbség.

```
  Vibe Coding munkafolyamat:

  "Csinálj egy webshopot"
           |
           v
  AI generál valamit
           |
           v
  "Ez nem jó, legyen kék"
           |
           v
  AI módosít
           |
           v
  "A kosár nem működik"
           |
           v
  AI javít... vagy ront
           |
           v
  "Már a login sem megy!"
           |
           v
  ???
```

Ismerős? Ez a „javítsd meg A-t, elromlik B" spirál a vibe coding természetes következménye. Nincs terv, nincs struktúra — minden változtatás potenciálisan elront valami mást.

Ez nem is meglepő, ha belegondolunk. [Martin Fowler](https://martinfowler.com/), a szoftverfejlesztés egyik legnagyobb gondolkodója, már évtizedek óta írja, hogy a szoftver entrópiája (rendezetlensége) természetesen nő, hacsak nincs tudatos erőkifejtés a struktúra megtartására. Terv nélkül az entrópia még gyorsabban nő — és az AI ezt csak felgyorsítja, mert hihetetlenül gyorsan generál újabb és újabb kódot, amit senki nem gondolt át.

## Vibe coding kudarcok a valóságban

Mielőtt valaki azt gondolná, hogy ez elméleti probléma, lássunk néhány tipikus forgatókönyvet, amiket PM-ként felismerhetsz:

**1. Az „eltűnő funkciók" esete**

Egy csapat vibe coding-gal épít egy ügyfélportált. Készül a regisztráció, a bejelentkezés, a profil oldal. Minden szépen működik. Aztán jön egy új kérés: „Legyen kereső funkció is." Az AI implementálja a keresést — de közben észrevétlenül felülírja a bejelentkezési logika egy részét. A bejelentkezés még működik az egyszerű esetben, de a „maradj bejelentkezve" funkció csendben eltűnik. Ezt csak három héttel később veszi észre egy ügyfél.

**Miért történik ez?** Mert a vibe coding-ban nincs specifikáció, ami leírná, hogy minek kell működnie. Nincs tesztlista, amit le lehetne futtatni. Nincs mód automatikusan ellenőrizni, hogy a régit nem rontottuk el.

**2. A „már senki nem érti" szindróma**

Egy fejlesztő három hónapon át vibe coding-gal épít egy belső eszközt. Működik, mindenki használja. Aztán a fejlesztő elmegy szabadságra, és valaki másnak kell változtatnia. Az új fejlesztő megnyitja a kódot: semmi dokumentáció, semmi specifikáció, semmi magyarázat arról, hogy miért úgy van megoldva valami, ahogy. A kód „működik", de senki nem tudja biztonságosan módosítani, mert senki nem érti.

**3. A „kicsiben jó, nagyban katasztrófa" projekt**

Egy startup MVP-t épít (Minimum Viable Product — a legkisebb működő termék). Vibe coding-gal két hét alatt készül egy demo. Az investorok lelkesek, jön a finanszírozás. Most jön a valós fejlesztés: több felhasználó, több funkció, biztonság, skálázás. De a vibe coding-gal épített alapok nem bírják: az egész alkalmazást újra kell írni. Az „előnyt" amit a gyorsaság adott, azonnal elveszíti az újraírás.

Mindhárom eset közös tanulsága: a vibe coding rejtett költségeket halmoz fel. Ezeket a szoftverfejlesztésben **technikai adósságnak** hívjuk (erről bővebben később).

## A három alapvető probléma

### 1. A kontextus probléma

Minden AI modellnek van egy **kontextus ablaka** — ez az a mennyiségű szöveg (kód, beszélgetés, fájl tartalom), amit egyszerre kezelni tud. Gondolj rá úgy, mint az AI „munkamemóriájára".

Hogy értsd a méretrendet: a Claude modell kontextus ablaka kb. 200 000 token. Ez elsőre hatalmasnak tűnik, de nézzük meg, mit jelent a gyakorlatban:

- 1 token kb. 4 karakter (angol szövegben; magyar szövegben kicsit kevesebb)
- 200 000 token kb. 150 000 sornyi kód
- Egy átlagos forrásfájl 100-300 sor
- Tehát a kontextus ablak kb. **500-1500 fájlnyi** kódot képes befogadni

De ez félrevezető, mert a kontextus ablakban nem csak a kód van:

- A beszélgetés előzménye (minden kérdés és válasz)
- Az AI „gondolatai" (a válaszgenerálás közbeni lépések)
- A rendszer utasítások (CLAUDE.md, projekt szabályok)
- A fájlok tartalma, amiket az AI megnyitott

A gyakorlatban tehát a használható kontextus **jóval kevesebb** — egy tipikus hosszabb munka session-ben az AI effektíve talán 20-50 fájlt képes átlátni, miközben a beszélgetés-történetet is tartja. Bővebben erről az [Anthropic kontextus kezelési útmutatójában](https://code.claude.com/docs/en/best-practices) olvashatsz.

```
  A kontextus ablak telítődése:

  +─────────────────────────────────────────────────+
  | ##............................................. | 10% -- friss,
  |                                                 |        mindent lát
  | ##############................................. | 30% -- jól dolgozik
  |                                                 |
  | ##############################................. | 60% -- lassul,
  |                                                 |        néha felejt
  | #############################################.. | 90% -- hibázik,
  |                                                 |        korábbi
  | ################################################ | 100%   utasításokat
  |                                                 |        elfelejti
  +─────────────────────────────────────────────────+
```

Vibe coding során ez a kontextus gyorsan megtelik:

- Elküldöd az első kérést --> az AI elolvassa a fájlokat --> 20% foglalt
- Javítást kérsz --> újabb fájlok, előző beszélgetés --> 40%
- Megint javítás --> még több kontextus --> 60%
- A 10. javításnál --> a kontextus szinte tele van --> az AI „elfelejti" az első kéréseidet

**Eredmény**: Az AI javítja a legutóbbi hibát, de közben elrontja amit 5 lépéssel korábban csinált. Mert már nem „emlékszik" rá.

**Spec-driven megközelítésben** ez a probléma kezelhető: az AI nem egy végtelen chat-ből dolgozik, hanem egy rövid, strukturált specifikációból. Minden session elején elolvassa a specifikációt és a feladatlistát — nem kell „emlékezni" a korábbi beszélgetésekre. Ez az, amit az Anthropic hivatalosan is ajánlott gyakorlatként ismertet a [Claude Code best practices](https://code.claude.com/docs/en/best-practices) dokumentációban.

### 2. A minőség probléma

A vibe coding legnagyobb csapdája: **nincs mit ellenőrizni**. Ha nincs specifikáció, honnan tudod, hogy a szoftver azt csinálja, amit kell?

```
  Vibe Coding:                   Spec-Driven:

  "Csinálj login oldalt"         Specifikáció:
        |                        - Email + jelszó mező
        v                        - "Elfelejtett jelszó" link
  AI csinál valamit              - 3 sikertelen próba után zárolás
        |                        - Google OAuth opció
        v                        - Hibás jelszó: "Helytelen adatok"
  "Kész van?"                          |
  "...szerintem igen"                  v
                                 AI implementál a spec alapján
                                       |
                                       v
                                 Ellenőrizhető:
                                 [x] Van email mező?
                                 [x] Van "Elfelejtett jelszó"?
                                 [x] Zárol 3 próba után?
                                 [x] Google OAuth működik?
```

**A spec-driven megközelítésnél** minden követelmény le van írva, és minden követelményhez tartozik egy ellenőrizhető feltétel. A PM pontosan tudja, mi van kész és mi nincs.

**Vibe coding-nál** a „kész" definíciója: „úgy tűnik, működik". Ami production-ben gyakran azt jelenti: „az alap eset működik, de a szélső esetek nem".

[Kent Beck](https://en.wikipedia.org/wiki/Kent_Beck), az agilis szoftverfejlesztés egyik megalkotója, a [Tidy First?](https://www.oreilly.com/library/view/tidy-first/9781098151232/) című könyvében írja, hogy a szoftver minőség nem véletlenül történik — tudatos, inkrementális lépések során épül fel. A vibe coding pont az ellenkezőjét csinálja: véletlenszerű lépéseket tesz, és reménykedik, hogy a végeredmény jó lesz.

PM-ként gondolj erre így: ha egy beszállító azt mondja neked, „szerintem kész van", az nem elfogadható. Ami elfogadható: „itt a követelménylista, minden pontot kipipáltam, és itt a bizonyíték (teszteredmények) hogy működik." A spec-driven megközelítés ezt adja.

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
  Kis script         1-5          ############ Kiváló
  Kis app            5-20         ########.... Jó
  Közepes app        20-50        #####....... Nehézkes
  Nagy app           50-200       ##.......... Alig működik
  Enterprise         200+         ............ Lehetetlen
```

Egy 200 fájlos projektben az AI nem tudja egyszerre a fejében tartani az összeset. A vibe coding egyszerűen nem skálázódik komplex projektekre.

**Miért fontos ez PM-ként?** Mert a legtöbb valóban értéket termelő szoftver — amiért ügyfelek fizetnek, ami a céged működteti — nem 5 fájlból áll. Egy tipikus webes alkalmazás 50-500 fájl. Egy nagyobb vállalati rendszer ezernél is több. Ezeknél a méreteknél a vibe coding nem lassul — összeomlik.

A spec-driven megközelítés azért skálázódik, mert **lebontja a munkát**: a nagy feladat kicsi, független darabokra bomlik, és minden darabnál az AI csak a releváns fájlokkal dolgozik. Több AI ágens párhuzamosan dolgozhat, mindegyik a saját kontextus ablakában, a saját részfeladatán. Erről bővebben a következő fejezetben lesz szó.

## Részletes összehasonlítás: ugyanaz a feature, két megközelítéssel

Lássuk egy konkrét példán, hogyan különbözik a két megközelítés a gyakorlatban. A feladat: **felhasználói értesítési rendszer** egy meglévő alkalmazáshoz. A felhasználók email és push értesítést kapjanak, ha valami fontos történik a fiókjukban.

### A) Vibe coding megközelítés

```
  Idő      Tevékenység                               Állapot
  ─────    ──────────────────────────────────────     ──────────────
  0:00     "Csinálj értesítési rendszert"             Indul
  0:10     AI generál email küldő kódot               Működni tűnik
  0:20     "Push értesítést is kérek"                 AI hozzáad
  0:35     Az email küldés elromlik                    Javítás
  0:50     "A felhasználó nem tudja kikapcsolni"      AI hozzáad UI-t
  1:10     A kikapcsolás elrontja az email kódot       Újra javítás
  1:30     "Legyen logolva, ki mit kapott"            AI nekiáll
  1:50     A logolás lassítja az egészet               Teljesítményhiba
  2:15     Újabb javítás, újabb mellékhatás            Spirál
  2:45     "Kezdjük elölről..."                       Újrakezdés
  3:30     Második nekifutás, ugyanazok a hibák        Frusztráció
  4:00+    Valami "működik", de senki nem biztos       "Kész"(?)
           benne, hogy minden eset le van fedve
```

**Összesen: 4+ óra, bizonytalan eredmény, nulla dokumentáció.**

### B) Spec-driven megközelítés

```
  Idő      Tevékenység                               Állapot
  ─────    ──────────────────────────────────────     ──────────────
  0:00     PM ír proposalt: miért kell, kinek,        Tervezés
           milyen értesítések kellenek
  0:20     AI generál specifikációt:                  Spec kész
           - Email értesítés (5 típus)
           - Push értesítés (3 típus)
           - Felhasználói beállítások
           - Audit log
  0:30     PM review: "A 'rendszer karbantartás'      Review
           értesítést is add hozzá"
  0:35     AI frissíti a spec-et                      Spec végleges
  0:40     AI generál design-t és feladatlistát       Tasks kész (12 task)
  0:45     AI implementál: Task 1-3 (DB séma)         3/12 kész
  1:00     AI implementál: Task 4-6 (email)           6/12 kész
  1:15     AI implementál: Task 7-9 (push)            9/12 kész
  1:30     AI implementál: Task 10-12 (UI, log)       12/12 kész
  1:40     Tesztek futnak: mind zöld                  Ellenőrizve
  1:50     PM review: spec vs. eredmény               KÉSZ
```

**Összesen: ~2 óra, ellenőrzött eredmény, teljes dokumentáció.**

A különbség vizuálisan:

```
  Hatékonyság az idő függvényében:

  Produktivitás
  ^
  |   Vibe ___
  |        /   \
  |       /     \___         ___
  |      /          \       /   \___    (hullámzó, kiszámíthatatlan)
  |     /            \     /
  |    /              \___/
  |   /
  |  /
  |──────────────────────────────────────> Idő
  |
  |                     Spec  ___________
  |                          /
  |                    _____/
  |                   /                     (lassú indulás, egyenletes haladás)
  |             _____/
  |            /
  |   ________/
  |  /
  |──────────────────────────────────────> Idő
```

A vibe coding gyorsan indul, de ahogy növekszik a komplexitás, hullámzik: vannak „jó" időszakok és „újraírás" időszakok. A spec-driven lassan indul (tervezés), de utána egyenletesen, kiszámíthatóan halad.

## A technikai adósság — amit minden PM-nek értenie kell

A szoftverfejlesztésben van egy fontos fogalom, amit PM-ként érdemes ismerni: a **technikai adósság** (angolul: technical debt). Ezt [Martin Fowler részletesen tárgyalja a blogján](https://martinfowler.com/bliki/TechnicalDebt.html), de röviden:

**Technikai adósság az, amikor „gyors megoldást" választunk „jó megoldás" helyett, és később ennek az árát megfizetjük.**

Gondolj rá úgy, mint egy hitelre. Ha hitelt veszel fel (gyors megoldás), most több pénzed van, de később kamatot is fizetsz. Ha eléggé eladósodszol, a kamat többe kerül, mint amennyi pénzt kaptál.

Szoftverre lefordítva:

```
  Technikai adósság hasonlat:

  Gyors megoldás (vibe coding)     =  Hitel felvétel
  Karbantartási költség            =  Kamat
  Újraírási kényszer               =  Csőd (nem tudod fizetni a kamatot)

  Jó megoldás (spec-driven)        =  Önerőből építés
  Alacsony karbantartási költség   =  Nincs kamat
  Könnyű bővítés                   =  Tartalék a jövőre
```

**A vibe coding közvetlenül technikai adósságot termel**, mert:

1. **Nincs dokumentáció**: senki nem tudja, miért úgy van megoldva valami, ahogy
2. **Nincs teszt**: senki nem tudja biztosan, hogy egy változtatás nem ront-e el mást
3. **Nincs struktúra**: a kód „nőtt, nem tervezték" — ezért minden változtatás költséges
4. **Nincs konzisztencia**: különböző stílusok, megközelítések, megoldások keverednek

A spec-driven megközelítés nem eliminálja a technikai adósságot — az minden szoftverben felgyülemlik valamilyen mértékben. De **kontrollálja**: a specifikáció és a design dokumentum biztosítja, hogy a döntések tudatosak legyenek, és a későbbi karbantartás ne legyen rejtvény.

**Miért érdekli ez a PM-et?** Mert a technikai adósság közvetlenül hat a szállítási sebességre. Egy eladósodott kódbázison minden új feature-t lassabban lehet megcsinálni. Az első feature 1 nap. A második 2 nap. A tizedik 2 hét. A PM látja, hogy „egyre lassabbak vagyunk" — de nem érti, miért. Az ok gyakran a felhalmozott technikai adósság.

## A kontextus ablak probléma konkrét számokkal

Hogy jobban értsd a kontextus ablak korlátait, nézzünk egy konkrét példát. Tegyük fel, hogy van egy közepes méretű webes alkalmazás:

```
  Tipikus közepes alkalmazás:

  Fájltípus                     Darabszám    Átlag sorok    Össz. sorok
  ──────────────────────────     ─────────    ───────────    ───────────
  Backend kód (Python/JS)        40            200           8 000
  Frontend komponensek           30            150           4 500
  Tesztek                        25            100           2 500
  Konfigurációs fájlok           10             50             500
  Adatbázis migrációk             8             80             640
  Dokumentáció                    5            200           1 000
  ──────────────────────────     ─────────    ───────────    ───────────
  Összesen                       118                        17 140 sor
```

A Claude kontextus ablaka (200K token) elvileg befogadná mind a ~17 000 sort. De a gyakorlatban:

- A beszélgetés előzménye: ~30% kontextus
- Rendszer utasítások (CLAUDE.md, stb.): ~10% kontextus
- Az AI gondolkodása: ~20% kontextus
- **Kód számára megmaradt hely: ~40%, azaz kb. 6 000 sor**

Ez azt jelenti, hogy az AI egyszerre kb. **30-40 fájlt** lát. Egy 118 fájlos projektnek alig az egyharmada. A többi 80 fájlról egyszerűen „nem tud" abban a pillanatban.

Vibe coding-ban ez katasztrófa: ahogy haladunk előre, az AI egyre kevesebb fájlt lát, és egyre több módosítás történik „vakon" — olyan fájlokra hatva, amiket az AI abban a pillanatban nem látott.

Spec-driven megközelítésben **pont ezért bontjuk szét a munkát kis feladatokra**: minden feladatnál az AI csak a releváns 5-10 fájlt látja, és pontosan tudja mit kell tennie (mert ott a spec). Nem kell „mindent a fejében tartani", elegendő az aktuális feladatot és annak környezetét látnia.

Az [Anthropic kutatási anyagai](https://www.anthropic.com/research) részletesen tárgyalják a nagyméretű kontextus ablakok használatát és korlátait.

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
| **Belső eszközöcske** | Amit csak te használsz, és ha elromlik, nem baj |
| **Adatelemzés** | Egyszeri lekérdezés, vizualizáció, riport |

A kulcs: ha a következő mondatok igazak, a vibe coding rendben van:

1. „Ha holnap törölnöm kell az egészet, nem baj."
2. „Csak én használom."
3. „Nincs benne szenzitív adat."
4. „Nem kell másnak karbantartania."

Ha bármelyikre „nem" a válasz, érdemes spec-driven megközelítésre váltani.

## Mikor ROSSZ a vibe coding?

| Helyzet | Miért rossz itt |
|---------|-----------------|
| **Production kód** | Nincs spec --> nincs mit tesztelni --> hibák |
| **Csapatmunka** | A többiek nem látják mi történt a chat-ben |
| **Komplex rendszer** | A kontextus ablak nem elég |
| **Hosszú projekt** | Nincs memória, minden session újraindul |
| **Szabályozott iparág** | Nincs audit trail, nincs nyomon követhetőség |
| **PM felügyelete alatt** | Nem tudod ellenőrizni, mert nincs mérce |
| **Több fejlesztő** | Nincs közös referencia, mindenki mást ért |
| **Biztonságkritikus** | Nem látod a „szélső esetek" kezelését |

## Az összehasonlítás

| Szempont | Vibe Coding | Spec-Driven |
|----------|-------------|-------------|
| **Indulási sebesség** | Azonnali | 10-30 perc tervezés |
| **Teljes idő (kicsi projekt)** | Gyors | Hasonló |
| **Teljes idő (nagy projekt)** | Lassú (újracsinálás) | Gyorsabb |
| **Kód minőség** | Változó, kiszámíthatatlan | Konzisztens |
| **Nyomon követhetőség** | Nincs (chat history) | Teljes (artifact-ok) |
| **PM rálátás** | „Kész van?" „Igen" | Spec --> Tasks --> Progress |
| **Skálázhatóság** | 1 ember, 1 chat | Több ágens, párhuzamos |
| **Újrafelhasználhatóság** | Semmi | Spec újra felhasználható |
| **Review-olhatóság** | Chat log átolvasása | Strukturált artifact-ok |
| **Technikai adósság** | Gyorsan nő, láthatatlanul | Kontrollált, tudatos |
| **Onboarding** | Új ember: „mi ez a kód?" | Új ember: olvassa a spec-et |
| **Karbantartás 6 hónap múlva** | „Ki írta ezt és miért?" | Spec + design + tasks |

## Miért számít a PM láthatóság?

Egy PM számára a legfontosabb kérdés: **„Hol tartunk?"** És a második: **„Mikorra lesz kész?"**

Vibe coding-ban ezekre a kérdésekre a válasz mindig bizonytalan:

- „Hol tartunk?" --> „Haladunk, most a login-on dolgozunk" (de ez mit jelent pontosan?)
- „Mikorra lesz kész?" --> „Talán péntekre" (de ez becslésen alapul, nem mérésen)

Spec-driven megközelítésben:

- „Hol tartunk?" --> „A tasks.md szerint 18/25 feladat kész, azaz 72%"
- „Mikorra lesz kész?" --> „Napi 5 feladat tempóval ~1.5 nap van hátra"

```
  PM láthatóság összehasonlítás:

  Vibe Coding:                      Spec-Driven:

  PM: "Hogy állsz?"                 PM megnyitja a tasks.md-t:
  Dev: "Jó, haladok."              - [x] 1.1 DB séma
  PM: "De pontosan hol?"            - [x] 1.2 API endpoint
  Dev: "Hát... a login              - [x] 2.1 Email küldés
       nagyjából kész..."           - [x] 2.2 Push értesítés
  PM: "És mi van hátra?"            - [ ] 2.3 Felhasználói UI    <-- itt tart
  Dev: "Még pár dolog."             - [ ] 3.1 Tesztek
  PM: *sóhajt*                      - [ ] 3.2 Dokumentáció

                                    Haladás: 4/7 (57%)
                                    PM: *pontosan látja a helyzetet*
```

Ez nem csak kényelem kérdése. A PM feladata, hogy kommunikáljon a stakeholderek felé: az ügyfélnek, a vezetőségnek, a többi csapatnak. Ha nem látod pontosan, hol tart a projekt, nem tudsz megbízható információt adni. És a megbízható információ a PM legfontosabb eszköze.

## Mikor válik a vibe coding spec-driven-né — a természetes fejlődés

Az érdekesség az, hogy sok csapatnál a vibe coding **természetesen** fejlődik spec-driven megközelítéssé. Ez nem egy bináris váltás („tegnapig vibe, mától spec"), hanem egy fokozatos átmenet:

```
  1. fázis:  Vibe coding        "Wow, ez működik!"
                |
                |  Első kudarcok, újraírások
                v
  2. fázis:  Vibe + review      "Na jó, de nézze meg valaki"
                |
                |  "Miért ne írjuk le először, mit akarunk?"
                v
  3. fázis:  Plan -> vibe       "Előbb gondolkodjunk, aztán kódoljunk"
                |
                |  "Ha már leírjuk, írjuk le rendesen"
                v
  4. fázis:  Spec-driven        "Specifikáció -> design -> implementáció"
                |
                |  "Miért nem dolgozik egyszerre több AI ágens?"
                v
  5. fázis:  Orchestrated       "Több ágens, párhuzamosan, automatizáltan"
```

**Az 1. fázis** az, ahol a legtöbb ember ma tart. Felteszik a ChatGPT-t vagy Claude-ot, beszélgetnek vele, és örülnek az eredménynek.

**A 2. fázis** akkor jön, amikor először történik komoly baj: elveszett munka, rejtett hiba production-ben, vagy egyszerűen a projekt „összeomlik" a komplexitás súlya alatt. Ilyenkor jönnek be az első biztonsági hálók: valaki megnézi a kódot mielőtt production-be kerül.

**A 3. fázis** az, amikor a csapat rájön, hogy a tervezésre fordított 20 perc 2 óra javítást takarít meg. Már nem „csak úgy" kódolnak, hanem először átbeszélik, mit akarnak. De még nincs formális spec.

**A 4. fázis** formalizálja azt, amit a 3. fázisban már informálisan csináltak. Innentől van proposal, spec, design, és feladatlista. Az AI nem „beszélgetésből" dolgozik, hanem strukturált dokumentumokból.

**Az 5. fázis** az, ami ebben a könyvben a következő fejezet témája: több AI ágens dolgozik párhuzamosan, mindegyik a saját részfeladatán, központi koordinációval.

A legtöbb csapat számára a 3-as fázis már hatalmas előrelépés a vibe coding-hoz képest. Nem kell rögtön az 5-ös fázisba ugrani — a lényeg, hogy **a fejlődés iránya egyértelmű**: a struktúra felé.

## Hogyan segít mindez a cégednek?

Ha PM vagy és azt gondolod, „oké, de engem a kódolás technikai részletei nem érdekelnek" — teljesen jogos. De íme, miért érdekel téged is ez a különbség:

1. **Kiszámítható szállítás**: Spec-driven megközelítéssel pontosabb becslést tudsz adni a stakeholdereknek, mert látható a haladás.

2. **Alacsonyabb kockázat**: A specifikáció és a tesztek csökkentik annak az esélyét, hogy production-ben derül ki egy hiba.

3. **Jobb kommunikáció**: A spec, a design, és a tasks.md olyan dokumentumok, amiket nem-technikai emberek is olvashatnak. Nem kell „lefordítani" a fejlesztő szavait.

4. **Onboarding**: Ha új fejlesztő jön a csapatba, olvassa a specifikációt — nem kell három hetet a régi kódban böngészni.

5. **Audit és compliance**: Szabályozott iparágakban (pénzügy, egészségügy) a specifikáció és a design dokumentum audit trail-ként is szolgál.

6. **Hosszú távú költség**: A spec-driven megközelítéssel épített szoftvert olcsóbb karbantartani, mert strukturált és dokumentált.

## Következő lépések

A következő fejezetben a 4. és 5. fázist nézzük meg részletesen: hogyan működik a spec-driven fejlesztés a gyakorlatban (OpenSpec), és hogyan skálázható több ágens párhuzamos munkájával (orkesztráció).

\begin{kulcsuzenat}
A vibe coding a szoftverfejlesztés fast food-ja: gyors, olcsó, és alkalmi használatra remek. De ha egy céget akarsz belőle felépíteni — szükséged van igazi konyhára, igazi receptekre, és igazi minőségellenőrzésre. A spec-driven fejlesztés adja ezt a struktúrát. Ahogy az építkezésnél sem a téglarakással kezdjük, hanem a tervrajzzal — a szoftverfejlesztésben sem a kóddal kell kezdeni, hanem a specifikációval. A PM feladata nem az, hogy kódot írjon vagy értsen — hanem az, hogy láthatóságot, struktúrát, és kiszámíthatóságot biztosítson. A spec-driven megközelítés pontosan ezt teszi lehetővé.
\end{kulcsuzenat}
