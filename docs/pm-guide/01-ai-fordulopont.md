# Mi történt 2024 végén?

## Az AI, ami kódot ír

Képzeld el, hogy van egy új kolléga a csapatodban. Nem kell neki kávészünet, nem megy szabadságra, és ha éjjel kettőkor eszedbe jut egy ötlet, üzenetet írhatsz neki, és reggelre kész lesz az alapja. Ez a kolléga nem ember — ez egy AI ágens, ami szoftverfejlesztésre lett kiképezve.

2024 végén valami alapvetően megváltozott az AI világában. Az AI modellek elértek egy szintet, ahol nem csak kérdésekre válaszolnak, hanem **önállóan cselekedni** is tudnak: fájlokat olvasnak, kódot írnak, teszteket futtatnak, és ha valami nem működik, megpróbálják kijavítani. Ez a fordulópont az „AI-asszisztenstől" az „AI-ágensig" vezető út mérföldköve.

Ez a könyv arról szól, hogyan változtatja meg ez a fejlődés a szoftverfejlesztést — és mit jelent ez számodra, mint projekt menedzser.

## A fejlődés kronológiája

Az AI nem egyik napról a másikra lett ilyen okos. Íme a főbb mérföldkövek:

| Időpont | Esemény | Jelentősége |
|---------|---------|-------------|
| 2020 jún. | GPT-3 megjelenik | Az első nagy nyelvi modell ami összefüggő szöveget ír |
| 2022 nov. | ChatGPT elindítása | AI mindenkinek — 100 millió felhasználó 2 hónap alatt |
| 2023 márc. | GPT-4 | Programozási feladatokban már jobb, mint sok ember |
| 2024 jún. | Claude 3.5 Sonnet | Áttörés a kód-értésben és generálásban |
| 2024 okt. | SWE-bench rekord | Claude valós GitHub hibák 49%-át önállóan megoldja |
| 2025 feb. | Claude Code megjelenés | Teljes fejlesztőkörnyezetben dolgozó AI ágens |
| 2025 máj. | Claude 4.0 / Opus | Komplex, többlépéses feladatokban is megbízható |
| 2025 ősz | Multi-ágens rendszerek | Több AI ágens dolgozik párhuzamosan, koordináltan |
| 2026 feb. | Claude 4.6 / Opus | Még pontosabb, gyorsabb, jobb kontextus-kezelés |

A legfontosabb pillanat ebben az idővonalon **2024 ősze** volt. Ez volt az a pont, amikor az AI túllépett a „kérdezz és válaszolok" szinten, és elkezdte **önállóan megoldani** a problémákat.

## A SWE-bench — amikor az AI levizsgázott

A szoftverfejlesztő közösségnek szüksége volt egy objektív mércére: tényleg tud-e az AI igazi programozói feladatokat megoldani, vagy csak trükközik? Erre hozták létre a **SWE-bench** (Software Engineering Benchmark) nevű tesztet.

A SWE-bench nem tankönyvi feladatokat ad az AI-nak. Ehelyett **valódi hibajelentéseket** vesz elő népszerű nyílt forráskódú projektekből (mint a Django, Flask, vagy a Scikit-learn), és megkéri az AI-t, hogy javítsa ki őket. A feladatok között van egyszerű és rendkívül bonyolult is — pont úgy, ahogy a való életben.

**Az eredmény meglepő volt**: az Anthropic (a Claude fejlesztő cége) SWE-bench Verified tesztjén a Claude 3.5 Sonnet modell **49%-os eredményt** ért el. Ez azt jelenti, hogy a valós, éles hibajelentések közel felét önállóan meg tudta oldani.

> *Forrás: [Anthropic SWE-bench kutatás](https://www.anthropic.com/research/swe-bench-sonnet)*

Miért fontos ez? Mert a korábbi rekord 45% volt, és a kutatók azt gondolták, hogy még évekbe telik mire az AI eléri az 50%-ot. Ehelyett hónapok alatt történt meg.

## Mit tud ma az AI — és mit nem?

Fontos tisztán látni, mire képes ma egy AI fejlesztő ágens, és hol vannak a határai.

### Amit már jól csinál

- **Kód olvasás és megértés**: Egy teljes projekt kódbázisát képes áttekinteni és megérteni a struktúráját. Odatalál a releváns fájlokhoz, érti az összefüggéseket.
- **Hibakeresés és javítás**: Hibaüzenetből kiindulva megkeresi a problémás kódrészt, megérti a hibát, és javítást készít.
- **Tesztek írása és futtatása**: Automatikus teszteket ír, lefuttatja őket, és ha valami elbukik, megpróbálja kijavítani a kódot.
- **Rutin feladatok**: Kód refaktorálás, kódstílus javítás, dokumentáció generálás, dependency frissítés — ezeket gyorsan és megbízhatóan végzi.
- **Több fájl együttes kezelése**: Nem csak egy fájlt szerkeszt, hanem érti, hogy egy változtatás más fájlokra is hathat, és azokat is módosítja.

### Ahol még gyenge

- **Komplex architektúrális döntések**: Az AI nem érti, hogy miért választottál mikroszervizeket monolitikus alkalmazás helyett. Nem ismeri a csapatod képességeit, a budget korlátait, vagy a hosszú távú üzleti stratégiát.
- **Üzleti logika megértése**: Ha az alkalmazásod speciális üzleti szabályokat követ (pl. „a nagykereskedelmi ügyfelek 30 napos fizetési haladékot kapnak, kivéve Q4-ben"), az AI nem fogja ezeket kitalálni magától.
- **Kontextus korlát**: Minden AI modellnek van egy „kontextus ablaka" — az a mennyiségű szöveg, amit egyszerre kezelni tud. Ha ez megtelik, az AI kezd elfelejteni dolgokat az eleje felől. (Erről bővebben a III. fejezetben.)
- **Hallucináció**: Néha az AI magabiztosan állít olyasmit, ami nem igaz. Kitalál API-kat amik nem léteznek, vagy hivatkozik funkciókra amik nincsenek a projektben.
- **Csapatdinamika**: Nem érti a cég politikáját, nem tudja, hogy Pista utálja a TypeScript-et, vagy hogy a design csapat már 3 hete dolgozik az új layouton.

### Az arany középút

```
  Amit az AI jól csinál          Ami emberi döntés marad
  ─────────────────────          ─────────────────────────
  Kód írás és javítás      --   Architektúra tervezés
  Tesztek generálása       --   Üzleti követelmények
  Rutin refaktorálás       --   Prioritás meghatározás
  Dokumentáció             --   Csapat koordináció
  Dependency kezelés       --   Költség/haszon elemzés
```

## Miért fontos ez egy PM-nek?

Talán azt gondolod: „Ez mind szép és jó, de én nem fejlesztő vagyok. Miért kellene ezzel foglalkoznom?"

Azért, mert az AI ágensek alapvetően megváltoztatják a projekt menedzsment három alappillérét:

**1. Idő és becslések**
Ha egy fejlesztő eddig 3 napot mondott egy feladatra, az AI ágenssel lehet, hogy 3 óra alatt elkészül az alapja. De ez nem jelenti, hogy 3 óra alatt kész — a review, a finomhangolás, és az integrálás továbbra is időbe telik. A becslési módszereidet újra kell kalibrálnod.

**2. Kapacitás és párhuzamosság**
Eddig ha 3 fejlesztőd volt, 3 feladaton tudtatok dolgozni. AI ágensekkel egyetlen fejlesztő 5-10 feladatot futtathat párhuzamosan. Ez új mennyiségű munkát tesz lehetővé — de új típusú koordinációt is igényel.

**3. Minőségbiztosítás**
Az AI gyorsan ír kódot, de nem mindig jó kódot. A PM szerepe egyre inkább az lesz, hogy meghatározza a minőségi elvárásokat, és biztosítsa hogy ezek be legyenek tartva — nem az, hogy a fejlesztési folyamatot mikro-menedzselje.

Erről a három változásról szól ez a könyv: hogyan változik az idő, a kapacitás, és a minőség — és hogyan alkalmazkodhat hozzá egy PM.

\begin{kulcsuzenat}
Az AI nem fogja kiváltani a fejlesztőket vagy a projekt menedzsereket. De azok a fejlesztők és PM-ek, akik tudják hogyan kell AI ágensekkel dolgozni, ki fogják váltani azokat, akik nem. A különbség nem a technikai tudásban van, hanem abban, hogy megérted-e az új munkafolyamatot.
\end{kulcsuzenat}
