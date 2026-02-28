# Mi történt 2024 végén?

## Az AI, ami kódot ír

Képzeld el, hogy van egy új kolléga a csapatodban. Nem kell neki kávészünet, nem megy szabadságra, és ha éjjel kettőkor eszedbe jut egy ötlet, üzenetet írhatsz neki, és reggelre kész lesz az alapja. Ez a kolléga nem ember — ez egy AI ágens, ami szoftverfejlesztésre lett kiképezve.

2024 végén valami alapvetően megváltozott az AI világában. Az AI modellek elértek egy szintet, ahol nem csak kérdésekre válaszolnak, hanem **önállóan cselekedni** is tudnak: fájlokat olvasnak, kódot írnak, teszteket futtatnak, és ha valami nem működik, megpróbálják kijavítani. Ez a fordulópont az „AI-asszisztenstől" az „AI-ágensig" vezető út mérföldköve.

Ez a könyv arról szól, hogyan változtatja meg ez a fejlődés a szoftverfejlesztést — és mit jelent ez számodra, mint projekt menedzser.

> **Ajánlott olvasmány**: Az Anthropic cég (a Claude fejlesztője) honlapján részletes kutatási anyagokat találsz arról, hogyan jutottak el idáig: [anthropic.com/research](https://www.anthropic.com/research)

## A fejlődés kronológiája

Az AI nem egyik napról a másikra lett ilyen okos. Egy évtizedes kutatás eredménye, ami 2022-ben gyorsult fel drámaian. Íme a főbb mérföldkövek:

| Időpont | Esemény | Jelentősége |
|---------|---------|-------------|
| 2020 jún. | GPT-3 megjelenik | Az első nagy nyelvi modell ami összefüggő szöveget ír |
| 2022 nov. | ChatGPT elindul | AI mindenkinek -- 100 millió felhasználó 2 hónap alatt |
| 2023 márc. | GPT-4 | Programozási feladatokban már jobb, mint sok ember |
| 2023 júl. | Claude 2 | Az Anthropic belép a versenybe |
| 2024 márc. | Claude 3 / Opus | Első modell ami komplex gondolkodásra képes |
| 2024 jún. | Claude 3.5 Sonnet | Áttörés a kód-értésben és generálásban |
| 2024 okt. | SWE-bench rekord | Claude valós GitHub hibák 49%-át önállóan megoldja |
| 2024 nov. | MCP szabvány | Egységes protokoll az AI és külső eszközök között |
| 2025 feb. | Claude Code megjelenés | Teljes fejlesztőkörnyezetben dolgozó AI ágens |
| 2025 máj. | Claude 4.0 / Opus | Komplex, többlépéses feladatokban is megbízható |
| 2025 ősz | Multi-ágens rendszerek | Több AI ágens dolgozik párhuzamosan, koordináltan |
| 2026 feb. | Claude 4.6 / Opus | Még pontosabb, gyorsabb, jobb kontextus-kezelés |

A legfontosabb pillanat ebben az idővonalon **2024 ősze** volt. Ez volt az a pont, amikor az AI túllépett a „kérdezz és válaszolok" szinten, és elkezdte **önállóan megoldani** a problémákat.

> **Háttér**: Ha érdekel a nagy nyelvi modellek működése közérthetően, a 3Blue1Brown YouTube csatorna kiváló vizuális magyarázatot ad: [youtube.com/@3blue1brown](https://www.youtube.com/@3blue1brown) -- keresd a „GPT" és „Transformer" videókat.

## A SWE-bench — amikor az AI levizsgázott

A szoftverfejlesztő közösségnek szüksége volt egy objektív mércére: tényleg tud-e az AI igazi programozói feladatokat megoldani, vagy csak trükközik? Erre hozták létre a **SWE-bench** (Software Engineering Benchmark) nevű tesztet.

A SWE-bench nem tankönyvi feladatokat ad az AI-nak. Ehelyett **valódi hibajelentéseket** vesz elő népszerű nyílt forráskódú projektekből (mint a Django, Flask, vagy a Scikit-learn), és megkéri az AI-t, hogy javítsa ki őket. A feladatok között van egyszerű és rendkívül bonyolult is — pont úgy, ahogy a való életben.

**Hogyan néz ki egy SWE-bench feladat?** Például:

> *„A Django ORM `QuerySet.union()` metódusa hibásan kezeli az `order_by()` hívást unió után. A felhasználók azt jelentik, hogy az eredmények nem a várt sorrendben jönnek vissza. A hiba a `django/db/models/sql/query.py` fájlban van."*

Az AI-nak meg kell találnia a releváns fájlokat egy több ezer fájlos projektben, megértenie a hibát, kijavítania, és biztosítania hogy a meglévő tesztek továbbra is átmenjenek.

**Az eredmény meglepő volt**: az Anthropic SWE-bench Verified tesztjén a Claude 3.5 Sonnet modell **49%-os eredményt** ért el. Ez azt jelenti, hogy a valós, éles hibajelentések közel felét önállóan meg tudta oldani.

> **Forrás**: [Anthropic SWE-bench kutatás](https://www.anthropic.com/research/swe-bench-sonnet) -- a teljes kutatási anyag az Anthropic honlapján olvasható.

> **Ajánlott olvasmány**: A SWE-bench projekt honlapja részletesen bemutatja a módszertant: [swebench.com](https://www.swebench.com/)

Miért fontos ez? Mert a korábbi rekord 45% volt, és a kutatók azt gondolták, hogy még évekbe telik mire az AI eléri az 50%-ot. Ehelyett hónapok alatt történt meg. 2025 végére a legjobb eredmények már 60% felett járnak.

## A „tool use" paradigma — az igazi áttörés

A SWE-bench eredmények mögött nem egyszerűen „okosabb" modellek állnak. Az igazi áttörés az volt, hogy az AI megtanult **eszközöket használni** (tool use). Ez azt jelenti, hogy az AI nem csak szöveget generál — hanem képes:

1. **Fájlokat megnyitni és olvasni** a számítógépen
2. **Parancsokat futtatni** a terminálban (tesztek, build, stb.)
3. **Fájlokat szerkeszteni** és új fájlokat létrehozni
4. **Eredményeket értelmezni** és további lépéseket tervezni

Képzeld el a különbséget:

```
  RÉGI MÓD (ChatGPT, 2023):
  ─────────────────────────
  Te: "Mi a hiba ebben a kódban?" [másolod a kódot]
  AI: "A hiba a 42. sorban van, cseréld ki erre: ..."
  Te: [manuálisan átírod]
  Te: "Most ez a hiba jön" [másolod az új hibát]
  AI: "Próbáld ezt: ..."
  ... és így tovább, oda-vissza

  ÚJ MÓD (Claude Code, 2025):
  ────────────────────────────
  Te: "Javítsd ki a login hibát"
  AI: [megnyitja a fájlokat]
      [megtalálja a hibát]
      [kijavítja]
      [lefuttatja a teszteket]
      [ha kell, tovább javít]
      "Kész, itt a megoldás. Commitoljam?"
```

Ez a különbség alapvető, mert az AI így **komplett feladatokat** tud megoldani, nem csak tanácsot adni.

> **Ajánlott cikk**: Az Anthropic blogja részletesen bemutatja a tool use koncepciót: [anthropic.com/news/tool-use-ga](https://www.anthropic.com/news/tool-use-ga)

## Mit tud ma az AI — és mit nem?

Fontos tisztán látni, mire képes ma egy AI fejlesztő ágens, és hol vannak a határai. Nézzünk konkrét példákat mindkét oldalra.

### Amit már jól csinál

- **Kód olvasás és megértés**: Egy teljes projekt kódbázisát képes áttekinteni és megérteni a struktúráját. Odatalál a releváns fájlokhoz, érti az összefüggéseket. *Példa: „Olvasd be a teljes auth modult és magyarázd el hogyan működik a session kezelés" -- és 30 másodperc alatt átfogó összefoglalót ad.*

- **Hibakeresés és javítás**: Hibaüzenetből kiindulva megkeresi a problémás kódrészt, megérti a hibát, és javítást készít. *Példa: Beillesztesz egy stack trace-t, és az AI nemcsak megtalálja a hiba gyökerét, hanem az összefüggő fájlokat is javítja.*

- **Tesztek írása és futtatása**: Automatikus teszteket ír, lefuttatja őket, és ha valami elbukik, megpróbálja kijavítani a kódot. *Példa: „Írj teszteket az email modul összes publikus függvényéhez" -- és 5 perc alatt 20 teszt eset készül, lefut, és zöld.*

- **Rutin feladatok**: Kód refaktorálás, kódstílus javítás, dokumentáció generálás, dependency frissítés — ezeket gyorsan és megbízhatóan végzi. *Példa: „Alakítsd át az összes JavaScript fájlt TypeScript-re a src/ könyvtárban" -- és egy óra alatt 50 fájlt migrál, típusokkal.*

- **Több fájl együttes kezelése**: Nem csak egy fájlt szerkeszt, hanem érti, hogy egy változtatás más fájlokra is hathat, és azokat is módosítja. *Példa: Ha átnevez egy függvényt, megkeresi és frissíti az összes helyet ahol használva van.*

### Ahol még gyenge

- **Komplex architektúrális döntések**: Az AI nem érti, hogy miért választottál mikroszervizeket monolitikus alkalmazás helyett. Nem ismeri a csapatod képességeit, a budget korlátait, vagy a hosszú távú üzleti stratégiát. *Példa: Nem fogja magától mondani, hogy „ne építsünk saját auth rendszert, használjunk Auth0-t, mert a csapatunk kicsi és nem tudunk biztonsági auditot csinálni."*

- **Üzleti logika megértése**: Ha az alkalmazásod speciális üzleti szabályokat követ, az AI nem fogja ezeket kitalálni magától. *Példa: „A nagykereskedelmi ügyfelek 30 napos fizetési haladékot kapnak, kivéve Q4-ben" -- ezt valakinek el kell mondania, az AI nem fogja kitalálni.*

- **Kontextus korlát**: Minden AI modellnek van egy „kontextus ablaka" — az a mennyiségű szöveg, amit egyszerre kezelni tud. Ha ez megtelik, az AI kezd elfelejteni dolgokat az eleje felől. Erről bővebben a III. fejezetben.

- **Hallucináció**: Néha az AI magabiztosan állít olyasmit, ami nem igaz. Kitalál API-kat amik nem léteznek, vagy hivatkozik funkciókra amik nincsenek a projektben. *Példa: „Használd a `request.user.getPermissions()` metódust" -- ami nem létezik a projektben, de az AI úgy írja, mintha ott lenne.*

- **Csapatdinamika**: Nem érti a cég politikáját, nem tudja, hogy Pista utálja a TypeScript-et, vagy hogy a design csapat már 3 hete dolgozik az új layouton.

### Az arany középút

```
  Amit az AI jól csinál          Ami emberi döntés marad
  ─────────────────────          ─────────────────────────
  Kód írás és javítás       --   Architektúra tervezés
  Tesztek generálása        --   Üzleti követelmények
  Rutin refaktorálás        --   Prioritás meghatározás
  Dokumentáció              --   Csapat koordináció
  Dependency kezelés        --   Költség/haszon elemzés
  Hibakeresés               --   Biztonsági döntések
  Kód review                --   Release stratégia
```

## Miért fontos ez egy PM-nek?

Talán azt gondolod: „Ez mind szép és jó, de én nem fejlesztő vagyok. Miért kellene ezzel foglalkoznom?"

Azért, mert az AI ágensek alapvetően megváltoztatják a projekt menedzsment három alappillérét:

**1. Idő és becslések**

Ha egy fejlesztő eddig 3 napot mondott egy feladatra, az AI ágenssel lehet, hogy 3 óra alatt elkészül az alapja. De ez nem jelenti, hogy 3 óra alatt kész — a review, a finomhangolás, és az integrálás továbbra is időbe telik. A becslési módszereidet újra kell kalibrálnod.

*Gyakorlati példa*: Egy közepes méretű feature (mondjuk egy új keresési funkció) hagyományosan így néz ki:
- Tervezés: 1 nap
- Implementáció: 3 nap
- Tesztelés: 1 nap
- Review + javítás: 1 nap
- **Összesen: ~6 nap**

AI ágenssel:
- Tervezés (spec írás): 2 óra
- AI implementáció: 3-4 óra
- Emberi review: 2 óra
- Javítások: 1 óra
- **Összesen: ~1 nap**

**2. Kapacitás és párhuzamosság**

Eddig ha 3 fejlesztőd volt, 3 feladaton tudtatok dolgozni. AI ágensekkel egyetlen fejlesztő 5-10 feladatot futtathat párhuzamosan. Ez új mennyiségű munkát tesz lehetővé — de új típusú koordinációt is igényel.

*Gyakorlati példa*: Egy fejlesztő reggel indít 5 AI ágenst különböző feature-ökön. Ebéd előtt mindegyik kész az alappal. Délután review-olja az eredményeket, finomhangol, és a nap végére 5 feature megy PR-be. Hagyományosan ez 5 fejlesztő 1 hetes munkája lett volna.

**3. Minőségbiztosítás**

Az AI gyorsan ír kódot, de nem mindig jó kódot. A PM szerepe egyre inkább az lesz, hogy meghatározza a minőségi elvárásokat, és biztosítsa hogy ezek be legyenek tartva — nem az, hogy a fejlesztési folyamatot mikro-menedzselje.

*Gyakorlati példa*: A PM definiálja: „Minden új feature-höz kell legalább 80%-os teszt lefedettség, és a kódnak át kell mennie a lint ellenőrzésen." Az AI ágens automatikusan betartja ezeket — de csak ha valaki előre megmondta.

Erről a három változásról szól ez a könyv: hogyan változik az idő, a kapacitás, és a minőség — és hogyan alkalmazkodhat hozzá egy PM.

> **Ajánlott cikk**: A Harvard Business Review 2025-ös cikke az AI hatásáról a projekt menedzsmentre: [hbr.org](https://hbr.org/) -- keresd az „AI project management" témát.

> **Videó**: Az Anthropic YouTube csatornáján találsz demókat a Claude képességeiről: [youtube.com/@AnthropicAI](https://www.youtube.com/@AnthropicAI)

\begin{kulcsuzenat}
Az AI nem fogja kiváltani a fejlesztőket vagy a projekt menedzsereket. De azok a fejlesztők és PM-ek, akik tudják hogyan kell AI ágensekkel dolgozni, ki fogják váltani azokat, akik nem. A különbség nem a technikai tudásban van, hanem abban, hogy megérted-e az új munkafolyamatot.
\end{kulcsuzenat}
