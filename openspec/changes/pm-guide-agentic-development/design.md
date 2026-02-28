## Context

PM barátnak készülő ~60-75 oldalas magyar nyelvű könyv-jellegű dokumentáció az agentic szoftverfejlesztésről. A célközönség ChatGPT szinten van, nem fejlesztő. A wt-tools projekt kontextusán belül készül, de a tartalom univerzálisabb — a wt-tools mint esettanulmány jelenik meg benne.

Jelenleg nincs hasonló magyar nyelvű összefoglaló ami a spec-driven agentic fejlesztést PM szemszögből mutatná be.

## Goals / Non-Goals

**Goals:**
- 7 fejezetes, összefüggő könyv-jellegű dokumentum ami fokozatosan vezet be az agentic fejlesztés világába
- PM-barát nyelvezet: technikai fogalmak mindig magyarázattal
- PDF formátum amit offline is lehet olvasni, nyomtatni
- ASCII diagramok a szövegben (nem külső képfájlok)
- Működő külső hivatkozások (Anthropic docs, MCP, SWE-bench, stb.)
- Reprodukálható build: `build.sh` futtatásával bármikor újragenerálható

**Non-Goals:**
- Nem fejlesztői dokumentáció (nem kell kódrészleteket magyarázni)
- Nem tutorial (nem lépésről-lépésre útmutató az eszközök telepítéséhez)
- Nem marketing anyag (objektív, tényalapú)
- Nem angol nyelvű változat készítése (csak magyar)
- Nem interaktív (nincs web verzió, nincs linkelt videó beágyazás)

## Decisions

### D1: Fájlstruktúra — fejeztenként külön Markdown
**Döntés:** Minden fejezet külön `.md` fájl a `docs/pm-guide/` könyvtárban, számozással prefixelve.
**Alternatíva:** Egyetlen nagy Markdown fájl — elvetettük mert nehezen karbantartható és a párhuzamos szerkesztés nehéz.
**Indoklás:** Fejeztenként külön fájl lehetővé teszi hogy az apply során fejezetenként haladjunk, és a pandoc képes több input fájlt sorrendben összefűzni.

### D2: PDF generálás — pandoc + xelatex
**Döntés:** `pandoc` a Markdown → LaTeX konverzióhoz, `xelatex` a LaTeX → PDF-hez. XeLaTeX a magyar ékezetes karakterek natív Unicode támogatása miatt.
**Alternatíva:** pdflatex — elvetettük mert az ékezetes karakterek (ő, ű) extra csomagokat igényelnek. wkhtmltopdf — elvetettük mert a tipográfiai minőség gyengébb.
**Indoklás:** pandoc + xelatex a legjobb minőség/egyszerűség arány Markdown input esetén.

### D3: Diagramok — ASCII art a Markdown-ban
**Döntés:** Minden diagram ASCII art formátumban közvetlenül a Markdown szövegben, monospace fonttal renderelve a PDF-ben.
**Alternatíva:** Mermaid diagramok — elvetettük mert extra dependency (mermaid-cli/puppeteer) és a PM nem tudja szerkeszteni. Külső képfájlok — elvetettük mert nehezítik a karbantartást.
**Indoklás:** Az ASCII art azonnal olvasható, nem igényel külső eszközt, és a monospace font a PDF-ben tisztán rendereli.

### D4: Pandoc template — custom Hungarian header
**Döntés:** Egyszerű pandoc YAML frontmatter a `00-meta.md`-ben (title, author, date, lang: hu, toc: true), plusz egy minimális LaTeX header-include ami beállítja a magyar nyelvet és a monospace fontot.
**Alternatíva:** Teljes custom LaTeX template — elvetettük mert túl komplex ehhez a feladathoz.
**Indoklás:** Pandoc beépített template + minimális override elegendő.

### D5: Hangnem és stílus
**Döntés:** Edukációs, közvetlen megszólítás ("képzeld el...", "gondolj arra..."), technikai zsargon mindig azonnali magyarázattal zárójelben vagy lábjegyzetben. Minden fejezet végén "Kulcs üzenet PM-nek" box.
**Alternatíva:** Formális/akadémiai stílus — elvetettük mert a célközönség nem akadémikus, hanem PM aki gyorsan akar megérteni dolgokat.

### D6: Hivatkozások kezelése
**Döntés:** Inline markdown linkek a szövegben + összegyűjtött linkgyűjtemény a függelékben. Minden fejezet tartalmaz 2-4 hivatkozást releváns Anthropic/MCP dokumentációra.
**Alternatíva:** Lábjegyzetes hivatkozások — elvetettük mert PDF-ben a lábjegyzet linkek nehezebben kattinthatók.

## Risks / Trade-offs

### R1: Pandoc/LaTeX dependency
[Risk] Az olvasónak/fejlesztőnek telepíteni kell pandoc-ot és texlive-ot a PDF generáláshoz.
→ Mitigation: A `build.sh` ellenőrzi a dependency-ket és hibaüzenetet ad. A generált PDF-et is commitoljuk, szóval a legtöbb esetben nem kell buildeni.

### R2: Külső linkek elavulása
[Risk] Anthropic dokumentáció URL-ek megváltozhatnak.
→ Mitigation: A linkeket a függelékben is összegyűjtjük, és a szöveg érthető a linkek nélkül is.

### R3: Tartalom elavulása
[Risk] Az AI ipar gyorsan változik, a dokumentum 6 hónap múlva részben elavulhat.
→ Mitigation: A VII. fejezet (jövő) explicit módon jelzi hogy előrejelzés, nem tény. A többi fejezet alapvető koncepciókat mutat be amik lassabban avulnak.

### R4: Magyar szaknyelv
[Risk] Sok AI/szoftverfejlesztési fogalomra nincs bevett magyar fordítás.
→ Mitigation: Az angol fogalmak mellé magyar magyarázatot adunk zárójelben, és a szószedet tartalmazza mindkét nyelvet.
