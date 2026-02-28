# pm-guide-build Specification

## Purpose
TBD - created by archiving change pm-guide-agentic-development. Update Purpose after archive.
## Requirements
### Requirement: Markdown forrásfájl struktúra
A dokumentum forráskódja Markdown fájlokra SKAL bontva legyen fejeztenként a `docs/pm-guide/` könyvtárban, egy `00-meta.md` (cím, szerző, dátum) és `01-07` fejezeti fájlokkal + `08-appendix.md` függelékkel.

#### Scenario: Fájlstruktúra
- **WHEN** a fejlesztő megnézi a `docs/pm-guide/` könyvtárat
- **THEN** a következő fájlokat találja: `00-meta.md`, `01-ai-fordulopont.md`, `02-claude-code.md`, `03-vibe-vs-spec.md`, `04-openspec.md`, `05-orchestracio.md`, `06-memoria.md`, `07-jovo.md`, `08-appendix.md`

### Requirement: PDF build pipeline
A rendszer SKAL tartalmaznia egy `docs/pm-guide/build.sh` scriptet ami pandoc-kal és LaTeX-el PDF-et generál az összes fejezeti Markdown fájlból.

#### Scenario: PDF generálás
- **WHEN** a felhasználó futtatja a `bash docs/pm-guide/build.sh` parancsot
- **THEN** egy `docs/pm-guide/output/az-agensek-kora.pdf` fájl jön létre az összes fejezetből

#### Scenario: Pandoc nem elérhető
- **WHEN** pandoc nincs telepítve a rendszeren
- **THEN** a script hibaüzenetben jelzi hogy `pandoc` és `texlive` szükséges, és kilép

### Requirement: Magyar nyelvű formázás
A PDF SKAL magyar nyelvi beállításokkal rendelkezzen: magyar fejléc/lábléc, tartalomjegyzék ("Tartalomjegyzék" címmel), magyar tipográfiai konvenciók.

#### Scenario: Tartalomjegyzék
- **WHEN** az olvasó megnyitja a PDF-et
- **THEN** a második oldalon "Tartalomjegyzék" címmel látja az összes fejezetet és alfejezetet oldalszámokkal

#### Scenario: Magyar ékezetes karakterek
- **WHEN** a PDF-ben magyar szöveg jelenik meg
- **THEN** minden ékezetes karakter (á, é, í, ó, ö, ő, ú, ü, ű) helyesen jelenik meg

