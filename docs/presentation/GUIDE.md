# Prezentáció Szerkesztési Útmutató

Ez a guide segít a `set-core-bemutato.md` Marp prezentáció frissítésében és exportálásában.

---

## Gyors referencia

| Feladat | Parancs |
|---------|---------|
| Előnézet böngészőben | `npx @marp-team/marp-cli -p set-core-bemutato.md` |
| Export PDF | `npx @marp-team/marp-cli set-core-bemutato.md -o set-core-bemutato.pdf` |
| Export PPTX | `npx @marp-team/marp-cli set-core-bemutato.md -o set-core-bemutato.pptx` |
| Export HTML | `npx @marp-team/marp-cli set-core-bemutato.md -o set-core-bemutato.html` |
| VS Code előnézet | Telepítsd a "Marp for VS Code" extension-t, majd Ctrl+Shift+V |

### Telepítés (ha még nincs)

```bash
npm install -g @marp-team/marp-cli
# vagy npx-szel futtatod közvetlenül (lásd fent)
```

---

## Fájl struktúra

```
docs/presentation/
├── set-core-bemutato.md    ← A prezentáció (Marp markdown)
├── GUIDE.md                ← Ez a fájl
└── (exportált fájlok ide kerülnek)

docs/images/auto/           ← Screenshotok (relatív útvonallal hivatkozva)
├── web/                    ← Dashboard screenshotok
│   ├── dashboard-overview.png
│   ├── tab-changes.png
│   ├── tab-phases.png
│   ├── tab-tokens.png
│   ├── tab-sessions.png
│   ├── tab-sentinel.png
│   ├── tab-log.png
│   ├── tab-agent.png
│   ├── tab-learnings.png
│   ├── tab-digest.png
│   ├── playwright-report.png
│   ├── battle-view.png
│   ├── manager-project-list.png
│   ├── page-memory.png
│   ├── page-issues.png
│   ├── page-settings.png
│   ├── page-worktrees.png
│   ├── global-issues.png
│   └── agent-session-scroll.gif
├── app/                    ← Alkalmazás screenshotok (MiniShop)
│   ├── home.png
│   ├── products.png
│   ├── product-detail.png
│   ├── cart.png
│   ├── admin-login.png
│   ├── admin-dashboard.png
│   ├── admin-products.png
│   ├── admin-products-new.png
│   ├── admin-register.png
│   ├── admin.png
│   └── orders.png
├── cli/                    ← CLI screenshotok
│   ├── spec-preview.png
│   ├── set-list.png
│   ├── set-status.png
│   └── ...
└── figma/                  ← Figma design screenshotok
    ├── storefront-design.png
    └── product-detail-design.png
```

---

## Szerkesztési útmutató

### Slide elválasztó

Minden `---` egy új slide-ot jelöl. A Marp frontmatter a fájl elején van.

### Képek

Képek relatív útvonallal a `docs/presentation/` könyvtárból:

```markdown
![w:900](../images/auto/web/tab-changes.png)
```

- `w:900` = 900px széles
- `w:480` = fél szélességű (két kép egymás mellett: `![w:480](...) ![w:480](...)`)
- `h:400` = magasság limitálás

### Új screenshot hozzáadása

1. Készítsd el a screenshotot
2. Mentsd a megfelelő könyvtárba:
   - Dashboard → `docs/images/auto/web/`
   - Alkalmazás → `docs/images/auto/app/`
   - CLI → `docs/images/auto/cli/`
   - Figma → `docs/images/auto/figma/`
3. Hivatkozd a prezentációban: `![w:900](../images/auto/<kategória>/<fájlnév>.png)`

### Speaker notes

Minden slide-hoz `<!-- SPEAKER_NOTES: ... -->` komment tartozik. Ezek a presenter view-ban jelennek meg (HTML export + `--notes` flag).

```markdown
<!-- SPEAKER_NOTES:
Itt van a slide magyarázata amit csak az előadó lát.
-->
```

### Speciális slide osztályok

```markdown
<!-- _class: title-slide -->      ← Címoldal (középre igazított, nagy betűk)
<!-- _class: section-divider -->  ← Szekció elválasztó (gradient háttér)
```

### Szín séma

| Szín | Hex | Használat |
|------|-----|-----------|
| Háttér | `#0f172a` | Slide háttér |
| Szöveg | `#e2e8f0` | Alap szöveg |
| Címsor | `#38bdf8` | H1 fejlécek |
| Alcímsor | `#7dd3fc` | H2 fejlécek |
| Kiemelés | `#fbbf24` | Bold szöveg, fontos számok |
| Kód háttér | `#1e293b` | Kód blokkok |
| Kód szöveg | `#a5f3fc` | Inline kód |

---

## Tartalom frissítése

### Számok/metrikák frissítése

A prezentáció fix számokat tartalmaz. Ha új benchmark fut, frissítsd:

1. **MiniShop számok** (slide: "A számok") — `docs/learn/benchmarks.md`-ből
2. **Token táblázat** (slide: "Token felhasználás") — ugyanonnan
3. **Gate timing** (slide: "Quality Gates") — gate átlagok
4. **Konvergencia score** (slide: "Konvergencia") — `tests/e2e/runs/minishop/run-*-vs-*.md`
5. **Skálázás táblázat** (slide: "MiniShop vs CraftBrew") — `docs/learn/benchmarks.md`
6. **Projekt méret** (slide: "Projekt méret") — `cloc` vagy hasonló
7. **Roadmap** (slide: "Fejlesztési irányok") — `docs/roadmap.md` + README

### Új szekció hozzáadása

```markdown
---

<!-- _class: section-divider -->

# Szekció címe

*Alcím*

---

# Első slide a szekcióban

Tartalom...

<!-- SPEAKER_NOTES:
Megjegyzések az előadónak.
-->
```

### Slide törlése

Töröld a `---` elválasztók közötti tartalmat (az előző `---`-tól a következőig).

---

## Export opciók

### PDF (nyomtatáshoz, megosztáshoz)

```bash
cd docs/presentation/
npx @marp-team/marp-cli set-core-bemutato.md -o set-core-bemutato.pdf --allow-local-files
```

A `--allow-local-files` flag kell a lokális képek betöltéséhez.

### PPTX (PowerPoint szerkesztéshez)

```bash
npx @marp-team/marp-cli set-core-bemutato.md -o set-core-bemutato.pptx --allow-local-files
```

Figyelem: a PPTX export után a formázás kisebb módosításokat igényelhet PowerPoint-ban.

### HTML (böngészőben prezentálás)

```bash
npx @marp-team/marp-cli set-core-bemutato.md -o set-core-bemutato.html --allow-local-files
```

Ez a legjobb megjelenés -- böngészőben nyitod meg, nyilakkal navigálsz.

### HTML presenter mode-dal

```bash
npx @marp-team/marp-cli set-core-bemutato.md -o set-core-bemutato.html --allow-local-files
# Megnyitás után: böngészőben nyomd meg a "p" billentyűt a presenter view-hoz
```

---

## Ellenőrzőlista frissítés előtt

- [ ] Screenshotok naprakészek? (dashboard frissült-e az utolsó screenshot óta?)
- [ ] Benchmark számok egyeznek `docs/learn/benchmarks.md`-vel?
- [ ] Roadmap aktuális? (befejezett irányok kiszedve, újak hozzáadva?)
- [ ] Speaker notes frissítve az új tartalomhoz?
- [ ] Export tesztelve (legalább HTML + PDF)?
- [ ] Képek betöltődnek? (`--allow-local-files` flag)

---

## Tippek az előadáshoz

1. **HTML exportot** használd prezentáláshoz -- a legjobb megjelenés
2. **"p" billentyű** a böngészőben = presenter view (speaker notes + következő slide)
3. **Nyilak** vagy **Space** a navigációhoz
4. **"f" billentyű** = teljes képernyő
5. A sötét téma jól mutat kivetítőn -- ha világos teremben vagy, emeld a fényerőt
6. Az E2E demo résznél érdemes **a dashboardot is megnyitni** élőben ha van futó projekt
