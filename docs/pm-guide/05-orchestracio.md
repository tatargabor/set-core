# Párhuzamos AI ágensek -- Orchestráció

## Az ötlet

Az előző fejezetben láttuk, hogyan dolgozik egyetlen AI ágens egy feladaton: specifikáció --> design --> tasks --> implementáció. De mi van, ha nem egy feladatod van, hanem tíz? Vagy húsz?

Gondolj egy valós projektre: egy webshop modernizálása. Kell bele:

- Felhasználói regisztráció átdolgozás
- Fizetési rendszer frissítés
- Email értesítések
- Admin felület
- API átírás
- Keresés javítás

Hagyományos módszerrel ez 6 fejlesztő, 6 hétnyi munka. **De mi lenne, ha 6 AI ágens dolgozna rajta egyszerre?**

Ez az orchestráció lényege.

A gondolat nem új: a szoftverfejlesztés történetében mindig keresték a módszert, hogyan lehet több ember munkáját párhuzamosítani. Fred Brooks 1975-ös klasszikusa, a *The Mythical Man-Month*, már rámutatott, hogy több ember nem jelent lineáris gyorsulást -- mert nő a koordinációs költség. Az AI ágensekkel ez megváltozik: az ágenseknek nem kell meetingelniük, nem kell email-ezniük, és nem sértődnek meg. A koordinációt egy szoftver végzi, automatikusan.

## Git worktree-k -- a párhuzamos munkaterületek

Mielőtt az orchestrációba merülnénk, meg kell érteni egy egyszerű fogalmat: **hogyan dolgozik több ágens egyszerre ugyanazon a projekten anélkül, hogy egymást zavarnák?**

A válasz: **[git worktree-k](https://git-scm.com/docs/git-worktree)** (munkafák).

### Az iroda hasonlat

Képzeld el, hogy a projekted egy nagy iroda. A fő iroda az, ahol az éles, működő szoftver van -- ez a "master" ág. Amikor új munkára van szükség, nem a fő irodában dolgozol (mert az zárolhat lenne), hanem nyitsz egy **különálló szobát**. Ebben a szobában a projekt egy teljes másolata van -- az összes fájl, az egész történelem -- de amit itt változtatsz, az nem befolyásolja a fő irodát, amíg te úgy nem döntesz.

```
  Képzeld el, hogy van egy irodád (a projekt).
  De az irodának 5 különálló szobája van,
  mindben egy-egy fejlesztő dolgozik.

  +---------------------------------------------+
  |                  Projekt                     |
  |                                              |
  |  +----------+  "szoba" = worktree           |
  |  | Master   |  A fő verzió, ahova az        |
  |  | (előtér) |  elkészült munka kerül        |
  |  +----------+                                |
  |                                              |
  |  +----------+  +----------+  +----------+  |
  |  | Szoba 1  |  | Szoba 2  |  | Szoba 3  |  |
  |  | Ágens A  |  | Ágens B  |  | Ágens C  |  |
  |  | regisztr.|  | fizetés  |  | email    |  |
  |  +----------+  +----------+  +----------+  |
  |                                              |
  |  +----------+  +----------+                 |
  |  | Szoba 4  |  | Szoba 5  |                 |
  |  | Ágens D  |  | Ágens E  |                 |
  |  | admin    |  | keresés  |                 |
  |  +----------+  +----------+                 |
  |                                              |
  |  Minden szobában a projekt egy másolata,     |
  |  de mindenki a saját változtatásain dolgozik.|
  |  Amikor kész, a változtatások beolvadnak     |
  |  a fő verzióba.                              |
  +---------------------------------------------+
```

Ez nem egyszerűen metafora -- pontosan így működik technikai szinten is. A git worktree funkció (bővebben lásd: [Git Worktree dokumentáció](https://git-scm.com/docs/git-worktree)) lehetővé teszi, hogy egyetlen repository-ból több munkakönyvtárat hozz létre. Minden munkakönyvtár egy különálló "branch"-en (ágon) dolgozik, de mindegyik ugyanahhoz a központi tárhelyhez tartozik.

### Miért jobb ez, mint a "színpadi" párhuzamosság?

Ha valaha dolgoztál úgy, hogy 5 fejlesztő ugyanazon a Git repo-n dolgozott, tudod: állandóan ütköznek. Az egyik megváltoztat egy fájlt, a másik is, és jön a "merge conflict" -- az összeolvasztási ütközés. A worktree-kkel ez ritkább, mert:

1. **Teljes izoláció**: Minden ágens a saját könyvtárában dolgozik, nem látja a másik munkáját
2. **Nem kell várni**: Az ágens nem várja meg, amíg a másik "push-ol" (felküldi a munkáját)
3. **Atomi beolvasztás**: Amikor kész, az egész munka egyben olvad be -- nem darabonként

**PM szemmel**: Mintha 5 fejlesztő 5 külön gépen dolgozna, és a munkájukat a végén összefésülik. Annyi a különbség, hogy itt AI ágensek dolgoznak, automatikusan, és az "összefésülés" is automatikus. A worktree-k a háttértechnológia -- neked PM-ként nem kell ezzel foglalkoznod, de jó tudni, hogy ez garantálja a biztonságos párhuzamosságot. Többet a branching stratégiákról az [Atlassian Git Workflows](https://www.atlassian.com/git/tutorials/comparing-workflows) oldalán olvashatsz.

## A Ralph Loop -- az autonóm munkaciklus

Minden worktree-ben egy **Ralph Loop** nevű ciklus fut. Ez adja az ágens önállóságát: nem kell egy emberi felügyelőnek minden lépésnél bólintania.

### Miért "loop"?

Mert az ágens nem egyszer próbálja meg a feladatot, hanem ismételten: kiválasztja a következő feladatot, megpróbálja megoldani, futtatja a teszteket, és ha nem sikerült, újra próbálja. Ez az iteratív megközelítés sokkal robusztusabb, mint egy egyszeri próbálkozás -- ahogy egy emberi fejlesztő is "debugol" (hibát keres), az AI ágens is iterálhat.

```
  +---------------- Ralph Loop ----------------+
  |                                             |
  |   +-------------+                          |
  |   | Feladat      |  Olvas: tasks.md        |
  |   | kiválasztása |  Találja: első [ ] elem |
  |   +------+------+                          |
  |          |                                  |
  |          v                                  |
  |   +-------------+                          |
  |   | Claude Code  |  Implementálja a feladat|
  |   | fut          |  (fájlok, tesztek, comm.)|
  |   +------+------+                          |
  |          |                                  |
  |          v                                  |
  |   +-------------+                          |
  |   | Ellenőrzés   |  Minden teszt átment?   |
  |   |              |  Van még feladat?        |
  |   +------+------+                          |
  |          |                                  |
  |          +-- Van még feladat -->  Következő |
  |          |                                  |
  |          +-- Minden kész --> Beolvasztás    |
  |          |                                  |
  |          +-- Elakadt --> Leáll, jelent      |
  |                                             |
  |   Biztonsági korlátok:                      |
  |   - Max. iteráció szám (alapért. 10)        |
  |   - Max. futási idő (alapért. 45 perc/iter.)|
  |   - Elakadás detekció (2 iteráció haladás   |
  |     nélkül --> leáll)                       |
  +---------------------------------------------+
```

**PM szemmel**: A Ralph Loop az, ami garantálja, hogy az ágens nem áll le az első hiba után, de nem is fut a végtelenségig. Ha elakad, jelzi és vár. Ha kész, jelzi és megáll.

### Ralph Loop részletesen -- iterációról iterációra

Lássunk egy konkrét példát: az ágens a "felhasználói regisztráció" change-en dolgozik. A tasks.md-ben 6 feladat van.

**1. iteráció:**
- Az ágens megnyitja a tasks.md-t, látja az első bepipálatlan feladatot: "1.1 Regisztrációs form komponens létrehozása"
- Elindítja a [Claude Code](https://code.claude.com/docs/en/overview)-ot a feladattal
- Claude Code létrehozza a fájlt, megírja a kódot, futtatja a teszteket
- A tesztek átmennek -- bejelöli: [x] 1.1 Regisztrációs form
- Commitol (menti a munkáját)
- Ellenőrzi: van még feladat? Igen --> következő iteráció

**2. iteráció:**
- Következő feladat: "1.2 Email validáció hozzáadása"
- Claude Code implementálja
- Egy teszt eltörik ("invalid email" esetet nem kezeli)
- Claude Code automatikusan javítja, újrafuttatja a tesztet
- Most átment -- bejelöli, commitol
- Van még feladat? Igen --> következő iteráció

**3. iteráció:**
- Következő feladat: "2.1 Backend endpoint a regisztrációhoz"
- Claude Code megírja az endpoint-ot, adatbázis migrációs fájlt
- Tesztek átmennek
- Bejelölés, commit

**4. iteráció:**
- Következő feladat: "2.2 Jelszó hash-elés és biztonság"
- Ez bonyolultabb -- Claude Code első nekifutásra nem találja el a tesztelvényt
- Második próbálkozás: javítja a salt generation logikáját
- Harmadik próbálkozás: most átmennek a tesztek
- Bejelölés, commit
- (Megjegyzés: ez az iteráción belüli újrapróbálkozás -- a Ralph Loop iterációja "felülről" nézi a feladatokat, de egy iteráción belül Claude Code többször is próbálkozhat)

**5. iteráció:**
- Hátramaradt 2 feladat: frontend összekötés és teszt kiírás
- Mindkettőt megcsinálja (ha elég egyszerű, egy iterációban több feladat is lehet)

**6. iteráció:**
- Az utolsó feladat: integrációs tesztek
- Minden átment
- Nincs több [ ] elem a tasks.md-ben
- **A Ralph Loop leáll és jelenti: "change kész, kész a beolvasztásra"**

Az egész folyamat -- 6 iteráció -- jellemzően 20-40 perc alatt zajlik le. Emberi beavatkozás nulla.

### Biztonsági mechanizmusok -- mi van, ha valami rosszul sül?

Az AI ágensek nem tökéletesek. Néha elakadhatnak, végtelen ciklusba kerülhetnek, vagy rossz irányba indulhatnak. A rendszer többrétegű védelmet épít be:

**1. Iterációs limit**: Alapértelmezetten egy Ralph Loop maximum 10 iterációt futhat. Ha 10 iteráció után sincs kész, leáll és jelzi: "nem sikerült befejezni". Ez megakadályozza, hogy egy elakadt ágens órákig fusson feleslegesen (és fogyassza az API kreditet).

**2. Időkorlát**: Minden egyes iteráció maximum 45 percig futhat. Ha ennyi idő alatt sem fejezi be az aktuális feladatot, az iteráció leáll.

**3. Elakadás-detektálás (stall detection)**: Ha az ágens 2 egymás utáni iterációban nem jelöl be új feladatot -- azaz nem halad -- a rendszer leállítja. Ez a leggyakoribb biztonsági esemény: az ágens próbálkozik, de nem képes megoldani a feladatot.

**4. Azonnali leállítás**: PM-ként vagy fejlesztőként bármikor leállíthatod az ágenst. A `wt-ralph stop <change-id>` parancs azonnal megállít egy adott ágenst. Nincs várni -- a következő lehetőségnél leáll.

**5. Visszagörgethetőség (rollback)**: Mivel minden ágens git-ben dolgozik, és minden lépés commit, bármikor visszamehetsz egy korábbi állapotra. Ha az ágens hibás kódot írt, a git történelem megmondja, melyik commit volt az utolsó jó, és egyszerűen visszaállítható. Ez nem tudományos-fantasztikus: ez a git alapfunkciója, amit évtizedek óta használnak fejlesztők.

**6. Izoláció**: Az ágens worktree-je teljesen különáll a fő ágtól. Ha egy ágens "megőrül" és rommá ír tele mindent, az a fő ágat nem érinti -- egyszerűen töröljük a worktree-t és kész. Mintha egy részeg dolgozót kikísérsz az irodából: a fő iroda érintetlen marad.

**PM szemmel**: Nem kell félned, hogy az AI "eltöri" a projektet. A legrosszabb ami történhet: egy ágens nem végzi el a feladatát, és újra kell indítani. A fő projekt mindig védett.

## Az orchestrátor -- a karmester

Az orchestrátor a legmagasabb szintű automatizálás. Input: egy specifikáció dokumentum. Output: kész, beolvasztott, tesztelt kód.

Az orchestrátor szerepe hasonlít egy karmesterhez: nem ő játszik az egyes hangszereken, hanem koordinálja, hogy ki mikor játszik, és az egész együtt szépen szóljon. Ha tetszik, gondolhatsz rá úgy is, mint egy "szuper PM-re" -- aki elolvassa a specifikációt, felbontja feladatokra, kiosztja őket a "fejlesztőknek" (AI ágenseknek), figyeli a haladást, és az eredményt összefésüli.

A Netflix mutatott rá először, hogy az ilyen fajta automatizált orchestráció -- ahol sok kis szolgáltatás párhuzamosan dolgozik -- nagyszabású rendszereknél is működik (lásd: [Netflix Tech Blog](https://netflixtechblog.com/)). Az AI ágensek orchestrációja ennek a gondolatnak a közvetlen leszármazottja.

### Hogyan működik?

```
  +-------------------------------------------------------+
  |                   ORCHESTRÁTOR                         |
  |                                                        |
  |  1. INPUT: Spec dokumentum (bármilyen markdown)        |
  |     "Webshop modernizálás: regisztráció, fizetés,     |
  |      email, admin, API, keresés"                       |
  |            |                                           |
  |            v                                           |
  |  2. AI ELEMZÉS: Claude felbontja change-ekre           |
  |     +----------------------------------+              |
  |     |  Change 1: user-registration  [S] |              |
  |     |  Change 2: payment-update     [M] |              |
  |     |  Change 3: email-service      [S] |              |
  |     |  Change 4: admin-panel        [L] |              |
  |     |  Change 5: api-rewrite        [M] |              |
  |     |  Change 6: search-upgrade     [S] |              |
  |     +----------------------------------+              |
  |            |                                           |
  |            v                                           |
  |  3. FÜGGŐSÉGI GRÁF: Mi függ mitől?                     |
  |                                                        |
  |     user-registration --+                              |
  |                         +-->  api-rewrite              |
  |     payment-update -----+        |                     |
  |                                  v                     |
  |     email-service -------->  admin-panel               |
  |                                                        |
  |     search-upgrade (független)                         |
  |            |                                           |
  |            v                                           |
  |  4. PÁRHUZAMOS VÉGREHAJTÁS:                            |
  |                                                        |
  |     Kör 1:  [user-reg] [payment] [email] [search]     |
  |              ---------- párhuzamosan ----------        |
  |                    |         |                          |
  |                    v         v                          |
  |     Kör 2:     [api-rewrite]                           |
  |                    |                                    |
  |                    v                                    |
  |     Kör 3:     [admin-panel]                           |
  |            |                                           |
  |            v                                           |
  |  5. EREDMÉNY: Összefoglaló riport                      |
  |     6/6 change kész, 0 hiba, 47 teszt átment          |
  |                                                        |
  +-------------------------------------------------------+
```

### A folyamat lépésről lépésre

**1. lépés: Specifikáció beolvasása**
Adsz egy markdown dokumentumot (lehet akár egy product brief), és az orchestrátor Claude-al elemezteti. A Claude értelmezi, mit kell csinálni, és felbontja kisebb, kezelhető darabokra (change-ekre). Ez a lépés jellemzően 2-3 percet vesz igénybe -- az AI elolvassa a specifikációt, azonosítja a független munkaegységeket, és javaslatot tesz a felosztásra.

**2. lépés: Méretezés**
Minden change kap egy méretet:
- **S (kicsi)**: 1-3 fájl módosítás, egyszerű feladat. Példa: "Kereső mező placeholder szövegének átírása"
- **M (közepes)**: 5-10 fájl, komplex logika. Példa: "Fizetési rendszer új szolgáltatóval bővítése"
- **L (nagy)**: Sok fájl, architektúrális hatás. Példa: "Admin felület teljes újratervezése"

A méret fontos a PM-nek, mert befolyásolja az idő- és költségbecslést. Egy S change jellemzően 10-20 perc, egy M 30-60 perc, egy L 1-2 óra.

**3. lépés: Függőségi gráf (DAG)**
A Claude meghatározza, mely change-ek függenek egymástól. Például: az API átírás nem kezdődhet el, amíg a felhasználói regisztráció nincs kész (mert az API-nak ismernie kell az új felhasználói modellt).

Ezt a függőségi gráfot technikai nyelven **DAG**-nak hívják (Directed Acyclic Graph -- irányított körmentes gráf). De ne ijedj meg a névtől. A következő hasonlat megmagyarázza.

**4. lépés: Párhuzamos végrehajtás**
Ami független, az egyszerre indul. Minden change kap egy worktree-t, egy Ralph Loop-ot, és a teljes OpenSpec pipeline-t (proposal --> specs --> design --> tasks --> implementáció). Az orchestrátor figyeli mindegyiket.

**5. lépés: Beolvasztás és tesztelés**
Amikor egy change kész, az orchestrátor beolvasztja a fő ágba, és lefuttatja a teszteket. Ha a teszt sikeres, feloldja a függő change-eket -- azok elindulhatnak.

### A függőségi gráf (DAG) -- a főzési hasonlat

A DAG bonyolultan hangzik, de a mindennapi életben is használod. Képzeld el, hogy vacsorát főzöl: az étel hús, saláta, és desszert.

```
  A vacsora "függőségi gráfja":

  +------------+    +----------+    +----------+
  | Hús sütése |    | Saláta   |    | Desszert |
  | (30 perc)  |    | (10 perc)|    | (20 perc)|
  +-----+------+    +-----+----+    +----+-----+
        |                  |              |
        |                  |              |
        v                  v              v
  +------------+    +----------+    +----------+
  | Szósz      |    | (kész)   |    | (kész)   |
  | készítés   |    |          |    |          |
  | (5 perc)   |    +----------+    +----------+
  +-----+------+
        |
        v
  +------------+
  | Tálalás    |  <-- erre vár mindhárom
  | (1 perc)   |
  +------------+
```

- A **saláta** és a **desszert** függetlenek -- ezeket párhuzamosan készítheted (vagy két különböző ember készítheti egyszerre)
- A **szósz** függ a **hústól** -- nem tudod elkészíteni a szószt, amíg a hús nem sül meg (kell a szaftja!), tehát a szósz várakozik
- A **tálalás** minden komponenstől függ -- amíg mindhárom nem kész, nem ehetsz

Pontosan így működik az orchestrátor is:

```
  Szoftver projekt "DAG":

  +------------------+   +-----------------+   +----------------+
  | user-registration|   | email-service   |   | search-upgrade |
  | (független)      |   | (független)     |   | (független)    |
  +--------+---------+   +--------+--------+   +-------+--------+
           |                       |                     |
           v                       v                     v
  +------------------+   +--------+--------+   +--------+--------+
  | api-rewrite      |   | admin-panel     |   | (kész)          |
  | (várja: user-reg)|   | (várja: email)  |   |                 |
  +--------+---------+   +--------+--------+   +-----------------+
           |                       |
           v                       v
        [KÉSZ]                  [KÉSZ]
```

A függetleneket párhuzamosan indítja -- ez a sebesség titka. A függőeket sorban, a helyes sorrendben. Az orchestrátor automatikusan kiszámítja az optimális sorrendet és ütemezést, ahogy egy jó séf is tudja, melyik fogást kell előbb elkezdeni, hogy minden egyszerre legyen kész.

Martin Fowler írásai a [Continuous Integration](https://martinfowler.com/articles/continuousIntegration.html)-ról részletesen tárgyalják, miért fontos, hogy a párhuzamos munkaágak rendszeresen visszaolvadjanak a fő ágba -- az orchestrátor pontosan ezt valósítja meg, automatikusan.

### Valós példa: egy projekt az orchestrátorral, elejétől a végéig

Lássunk egy részletes példát. Tegyük fel, hogy egy e-learning platformot modernizálsz. A specifikációd így néz ki:

> *"Modernizáljuk az e-learning platformot: új kurzus-kereső, videó lejátszó upgrade, certifikát-generálás, és admin statisztikák."*

**09:00 -- Spec betöltése és elemzés**
Az orchestrátor elolvassa a specifikációt. Az AI 4 change-et azonosít:
- `course-search` [S] -- új kereső funkció
- `video-player` [M] -- videó lejátszó frissítés
- `certificate-gen` [S] -- certifikát generálás
- `admin-stats` [M] -- admin statisztikás dashboard

Függőség: az `admin-stats` függ a `course-search`-től (mert a keresési statisztikákat mutatja). A többi független.

**09:03 -- Párhuzamos indítás**
Az orchestrátor létrehoz 3 worktree-t és elindítja a Ralph Loop-ot a 3 független change-re:
- Worktree 1: `course-search` -- Ralph Loop indul
- Worktree 2: `video-player` -- Ralph Loop indul
- Worktree 3: `certificate-gen` -- Ralph Loop indul

Az `admin-stats` várakozik.

**09:15 -- Első eredmény**
A `course-search` (kis méretű) már kész! 3 iterációt használt, 12 percbe telt. Az orchestrátor beolvasztja a fő ágba, futtatja a teszteket -- minden átment.

Mivel a `course-search` kész, az `admin-stats` függősége feloldódik. Az orchestrátor azonnal elindítja a 4. worktree-t: `admin-stats` Ralph Loop indul.

**09:30 -- Második eredmény**
A `certificate-gen` is kész: 2 iteráció, 14 perc. Beolvasztás, teszt, minden jó.

**09:45 -- Dashboard közbeni állapot**
A dashboard ilyesmit mutat:

```
  Change           Státusz    Iteráció    Token
  ---------------  -------    --------    -----
  course-search    [KÉSZ]     3/10        18k
  certificate-gen  [KÉSZ]     2/10        12k
  video-player     [FUT]      5/10        64k
  admin-stats      [FUT]      2/10        22k
```

**10:10 -- video-player kész**
A közepes méretű change 7 iterációt használt -- volt egy bonyolultabb rész, ahol a codec-támogatás tesztjeivel szenvedett az ágens. De végül minden átment.

**10:35 -- admin-stats kész**
Az utolsó change is befejeződött. Összesítés:

```
  ORCHESTRÁTOR RIPORT
  -------------------
  Összesen:  4/4 change kész
  Idő:       1 óra 35 perc
  Token:     ~142k token
  Költség:   ~\$8.50
  Tesztek:   63 teszt, mind átment
  Merge:     4/4 sikeresen beolvasztva
```

**Egyetlen ember érintette a folyamatot**: te, a PM, aki megírta a 10 soros specifikációt. A fejlesztő majd a code review-nál jön képbe.

## Merge policy-k -- mennyire legyen automatikus?

Az orchestrátor három szintű automatizálást kínál:

```
  +-------------------------------------------------+
  |  eager     |  Azonnal beolvasztja amikor kész    |
  |            |  --> Leggyorsabb, de kockázatos     |
  +------------+------------------------------------+
  | checkpoint |  N darab után megáll és vár         |
  |            |  --> Egyensúly sebesség és kontroll |
  +------------+------------------------------------+
  |  manual    |  Sorba áll, ember hagy jóvá         |
  |            |  --> Leglassabb, de legbiztonságosab|
  +------------+------------------------------------+
```

**PM szemmel**: A merge policy a bizalom szintje. Új projekten érdemes `checkpoint`-tal indulni -- az orchestrátor minden 2-3 kész change után megáll és vár, hogy átnézd. Amikor már bízol benne, átállhatsz `eager`-re.

### A bizalmi gradiens -- manual-tól eager-ig

Az orchestrátor használata során a legtöbb csapat egy természetes fejlődési utat jár be:

**1. fázis: Manual (az első hét)**
Minden egyes change-et kézi review után olvasztasz be. Lassú, de sokat tanulsz arról, milyen minőségű kódot ír az AI. Megtanulod, mire figyel a rendszer, és mire nem. Ez az ismerkedési fázis.

Jellemző kihívások ebben a fázisban:
- Nem bízol az AI döntéseiben -- minden sort átnézel
- Sokat tanulsz arról, hogyan gondolkodik az AI
- A review idő magas: feladatonként 15-20 perc

**2. fázis: Checkpoint (2-4. hét)**
Elkezded látni a mintákat: a kis (S) change-ek szinte mindig rendben vannak, a közepesek (M) is nagyrészt jók. Átállsz checkpoint üzemmódra: minden 2-3 change után nézed át a batch-et. Ha találsz hibát, javítod és tovább megy.

Jellemző tapasztalatok:
- Az S change-ek 90%+ arányban review nélkül is jók
- Az M change-eknél alkalmanként kell kézi javítás
- A review idő csökkent: batch-enként 10-15 perc
- A sebesség 2-3x gyorsabb, mint manual módban

**3. fázis: Eager (5. hét~)**
A nagy change-eket még mindig kézi review-olod, de a kis és közepes méretű change-eket automatikusan engeded beolvadni. Ez már szinte teljes automatizálás -- az orchestrátor ontja a kész kódot, te csak a napi összefoglalót nézed át, és a nagy, architektúrális change-eket review-olod.

Jellemző jellemzők:
- A napi output megtöbbszöröződik
- A PM szerepe inkább "minőségbiztosítás" és "iránymutatás"
- A fejlesztő review változatlanul fontos -- ez nem marad el!

**Fontos**: A bizalmi gradiens nem a code review kihagyásáról szól. A fejlesztő review mindig megmarad. A kérdés az, hogy a **beolvasztás** automatikus-e, vagy várakozik-e emberi jóváhagyásra. Az eager módban a beolvasztás automatikus, de a fejlesztő utána nézi át a kódot -- és ha valami nem jó, javítja. Ez hasonló a [Continuous Integration](https://martinfowler.com/articles/continuousIntegration.html) elvéhez: előszőr olvasszd be, aztán javítsd ha kell -- a lényeg, hogy a kódágak ne távolodjanak el egymástól.

## A GUI -- valós idejű áttekintés

Az orchestrátor egy vizuális dashboard-ot biztosít, ahol minden ágens állapota valós időben látszik:

```
  +--------------------------------------------------+
  |  wt-tools Control Center                         |
  |                                                  |
  |  Change               Státusz   Iteráció  Token  |
  |  -----------------    -------   --------  -----  |
  |  user-registration    * kész    3/10      45k    |
  |  payment-update       > fut     5/10      82k    |
  |  email-service        * kész    2/10      28k    |
  |  search-upgrade       * kész    1/10      15k    |
  |  api-rewrite          ~ vár    -         -      |
  |  admin-panel          ~ vár    -         -      |
  |                                                  |
  |  Összesen: 3/6 kész | 1 aktív | 2 várakozik     |
  |  Eltelt idő: 2h 34m | API költség: \$12.50        |
  |                                                  |
  +--------------------------------------------------+
```

**PM szemmel**: Mint egy Jira board, de valós időben frissül, és nem emberektől függ hogy frissüljön. Nem kell standup meetinget tartanod -- megnyitod a dashboardot és látod.

### Milyen metrikákat figyel egy PM a dashboardon?

Nem minden szám egyformán fontos. Íme, amire érdemes figyelni:

**1. Haladási arány (X/Y kész)**
A legfontosabb szám. Ha 6 change-ből 4 már kész, a projekt 67%-ánál jársz. Ez a "nagy kép" -- ezt mondod a stakeholdernek.

**2. Aktív ágensek száma**
Ha 3 ágens fut párhuzamosan, az a maximum kihasználtság. Ha 1 fut és 4 várakozik, az függőségi szűk keresztmetszet -- érdemes megvizsgálni, miért.

**3. Iterációszám / change**
Ha egy change már 8/10 iterációnál tart, az figyelmeztető jel: talán túl bonyolult, vagy a specifikáció nem elég pontos. Ilyenkor érdemes megnézni az ágens logját, és ha kell, segíteni (pontosítani a specifikációt, vagy a feladatot kisebbekre bontani).

**4. Token-felhasználás**
Közvetlenül arányos a költséggel. Ha egy change szokatlanul sok tokent használ (például 200k egy S méretű change-hez), az valószínűleg azt jelenti, hogy az ágens körökben jár -- elakadt, és újra meg újra próbálkozik ugyanazzal.

**5. Eltelt idő**
A teljes projekt futási ideje. Általában 1-5 óra közepes projektre, a change-ek számától és bonyolultságától függően. Ha ez eltér a megszokottól (például 8 óra egy 4-change-es projektre), érdemes utánanézni.

A [Google SRE Book](https://sre.google/sre-book/table-of-contents/) részletesen tárgyalja, hogyan érdemes rendszer-metrikákat figyelni és reagálni anomáliákra -- az elvek itt is alkalmazhatók.

## Hibakezelés: mi történik, ha valami rosszul megy?

Bármilyen jó is az automatizálás, hibák előfordulnak. PM-ként fontos tudni, milyen típusú hibák vannak, és mi a teendő.

### 1. Merge conflict -- összeolvasztási ütközés

Ez a leggyakoribb probléma. Kétfelé ágens dolgozik két különböző change-en, de történetesen mindkettő módosítja ugyanazt a fájlt. Amikor az orchestrátor megpróbálja beolvasztani a másodikat, **ütközés** keletkezik.

**Mi történik automatikusan?**
- Az orchestrátor észleli az ütközést
- Újraindítja az érintett ágenst a frissített fő ág alapján
- Az ágens újra megcsinálja a munkáját, most már látva a másik ágens változásait
- Ha ez sikerült, beolvasztja

**Mi történik, ha az automatikus megoldás nem sikerül?**
- Az orchestrátor megjelöli a change-et "conflict" státusszal
- Várakozik emberi beavatkozásra
- A PM/fejlesztő kézi review-val oldja meg az ütközést

**PM teendő**: Ha a dashboardon "conflict" státuszt látsz, szólj a fejlesztőnek. Ez nem katasztrófa -- a hagyományos fejlesztésben is naponta előfordul. Az orchestrátor az esetek 80-90%-ában maga megoldja; csak a maradék 10-20%-hoz kell ember.

### 2. Ágens elakadás (stall)

Az ágens nem képes megoldani egy feladatot. Például: a spec nem elég részletes, az ágens nem érti, mit kell csinálni, és körökben jár.

**Jelei a dashboardon:**
- Magas iterációszám, alacsony bejelölési arány
- Sok token-felhasználás, kevés commit

**PM teendő:**
1. Nézd meg az ágens logját -- mit próbál csinálni?
2. Ha a spec nem elég pontos, pontosítsd és indítsd újra
3. Ha a feladat túl nagy, bontsd kisebbre (oszd az L-es change-et két M-esre)

### 3. Teszthiba a beolvasztás után

Néha egy change egyedül működik, de beolvasztás után eltöri a másik change valamelyik tesztjét. Ez az "integrációs hiba".

**Mi történik automatikusan?**
- Az orchestrátor futtatja a teljes teszt-készletet beolvasztás után
- Ha hiba van, visszagörgeti a beolvasztást (az előző jó állapotba)
- Újraindítja az érintett ágenst a javításra

**PM teendő**: Általában semmi -- az orchestrátor kezeli. Ha többször is előfordul, az a függőségi gráf hiányosságára utalhat: talán két change függne egymástól, de az AI nem ismerte fel a függőséget. Ilyenkor érdemes kézi függőséget beállítani.

### 4. API rate limit vagy költség-túllépés

Ha az AI API szolgáltató (például Anthropic) rate limitet alkalmaz, az ágensek lelassulnak vagy ideiglenesen leállnak.

**PM teendő**: A dashboardon látod, ha egy ágens "vár API válaszra". Érdemes a párhuzamos ágensek számát csökkenteni (például 5 helyett 3-ra), vagy az API terv szintjét növelni.

## Valós számok

Egy közepméretű projekt modernizálása az orchestrátorral:

| Mutató | Érték |
|--------|-------|
| Input | 1 specifikáció dokumentum (2 oldal) |
| Change-ek száma | 8 |
| Párhuzamos ágensek | 3 (egyszerre max.) |
| Teljes futási idő | ~4-5 óra |
| Emberi beavatkozás | 2x review (merge checkpoint) |
| API költség | ~\$15-25 |
| Hagyományos becslés | 3-5 fejlesztőnap |

**Bővebb kontextus a számokhoz:**

- A **\$15-25** API költség a Claude API használatra vonatkozik (tokenenként számolva). Egy S méretű change általában \$1-3, egy M méretű \$3-8, egy L méretű \$8-15. Ezek 2026 eleji árak -- az AI szolgáltatás árak évről évre csökkennek.
- A **4-5 óra futási idő** nem jelent 4-5 óra emberi munkát. A PM 15-30 percet tölt a specifikációval, aztán 2x10 percet a checkpoint review-val. A többi automatikus.
- A **3 párhuzamos ágens** az általános beállítás. Több ágens gyorsabb, de drágább és több merge conflictet okoz. Kevesebb ágens lassabb, de olcsóbb és biztonságosabb. A helyes szám projektről projektre változik.

### Költségbecslés: hogyan tervezz büdzsét AI ágens használatra?

A leggyakoribb PM kérdés: "Mennyibe kerül ez?" Az AI ágensi munka költsége három fő tételből áll:

**1. API tokenek (a fő költség)**
Az AI minden kérdésre és válaszra tokent használ. Egy token kb. egy angol szó-rész (magyar szöveggel kicsit több, mert a magyar szavak hosszabbak). Az Anthropic Claude árazása (2026 eleje):
- Input: ~\$3 / millió token
- Output: ~\$15 / millió token

Egy átlagos change 30-100k tokent használ. Egy 8-change-es projekt tehát 240-800k token, azaz **\$5-25**.

**2. Számítási erőforrások (elhanyagolható)**
A worktree-k és Ralph Loop-ok helyi gépen futnak. A számítási költség minimális -- egy átlagos fejlesztői laptop elbír 3-5 párhuzamos ágenst.

**3. Fejlesztői idő (a review)**
A fejlesztő review-ra fordított idő nem változik sokat -- az AI által írt kódot ugyanúgy át kell nézni, mint az emberi kódot. De a **fejlesztési idő** jelentősen csökken.

**Összevetés hagyományos költségekkel:**

```
  Hagyományos:
    5 fejlesztőnap x 8 óra x \$80/óra = \$3,200
    + PM idő: 2 nap x 8 óra x \$60/óra = \$960
    Összesen: ~\$4,160

  Orchestrátorral:
    API költség: \$20
    PM idő: 1 óra x \$60/óra = \$60
    Fejlesztő review: 3 óra x \$80/óra = \$240
    Összesen: ~\$320

  Megtakarítás: ~92%
```

Természetesen ez egy idealizált példa -- a valós megtakarítás a feladat bonyolultságától és a szükséges emberi beavatkozás mértékétől függ. De a nagyságrend jellemzően 5-10x megtakarítás a hagyományos módszerhez képest.

**Fontos megjegyzés**: Az orchestrátor nem teszi feleslegessé az emberi review-t. Az AI által írt kódot egy senior fejlesztőnek végig kell néznie. Az orchestrátor az elkészülést gyorsítja, nem a review-t eliminálja.

## Mikor érdemes orchestrálni?

| Helyzet | Orchestrátor? |
|---------|---------------|
| 1 kis feature | Nem -- egyetlen Claude Code session elég |
| 2-3 összefüggő feature | Talán -- ha vannak függetlenek |
| 5+ feature, projekt szintű | Igen -- ez az orchestrátor erőssége |
| Kritikus, biztonsági kód | Nem -- emberi kézi munka kell |
| Gyors prototípus | Nem -- vibe coding gyorsabb |
| Terv alapú modernizáció | Igen -- pont erre készült |
| Legacy kód átírás | Igen -- sok független modult lehet párhuzamosítani |
| Egyszerű szövegcsere 50 fájlban | Nem -- egy script gyorsabb |

### Döntési fa PM-eknek

Ha bizonytalan vagy, használd ezt az egyszerű döntési fát:

```
  Van legalább 3 független feladat?
    |
    +-- Nem --> Használj egyetlen Claude Code session-t
    |
    +-- Igen
          |
          Van specifikáció vagy product brief?
            |
            +-- Nem --> Először írd meg a specifikációt
            |
            +-- Igen
                  |
                  A feladatok biztonságkritikusak?
                    |
                    +-- Igen --> Emberi fejlesztés + AI asszisztens
                    |
                    +-- Nem --> ORCHESTRÁTOR (manual/checkpoint módban)
```

## Összefoglalás: az orchestráció mint PM szupererő

Az orchestráció a PM számára azt jelenti, hogy a feladat-lebontás, kiosztás, nyomonkövetés és beolvasztás -- amit eddig napokig tartott koordinálni -- **automatikusan történik**. A PM szerepe megváltozik:

- **Régi modell**: PM lebontja a feladatokat --> kiosztja a fejlesztőknek --> naponta standup --> kérdezgeti "hogy állsz?" --> összefésüli az eredményt
- **Új modell**: PM megírja a specifikációt --> az orchestrátor mindent kioszt, futtat, és beolvaszt --> PM a dashboardot nézi és review-ol

Ez nem a PM feleslegessé tételét jelenti -- éppen ellenkezőleg. A PM szerepe felértékelődik, mert a **specifikáció minősége** soha nem volt ennyire fontos. Ha a specifikáció pontos, az orchestrátor remek munkát végez. Ha a specifikáció homályos, az ágensek is homályos kódot írnak. A PM feladata tehát: pontos, mérhető specifikációkat írni, és a végeredményt ellenőrizni.

További olvasnivalók az AI ágensek és multi-agent rendszerek témájából: [Anthropic Research](https://www.anthropic.com/research), valamint DevOps és automatizálás témában a [TechWorld with Nana YouTube csatorna](https://www.youtube.com/@TechWorldwithNana) kiváló bevezető videókat kínál.

\begin{kulcsuzenat}
Az orchestráció lényege: egyetlen specifikációból több AI ágens dolgozik párhuzamosan, mindegyik a saját izolált munkaterületén, automatikus koordinálással. Mint PM, nem az ágenseket irányítod -- a specifikációt írod, és a végeredményt review-olod. Közben a dashboard mutatja mi történik. Indulj manual módban, építsd fel a bizalmat checkpoint-on át, és végül engedd el eager módban -- a költség töredéke a hagyományos fejlesztésnek, a sebesség többszöröse.
\end{kulcsuzenat}
