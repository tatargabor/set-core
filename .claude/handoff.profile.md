# handoff profile — set-core

*A `/handoff` skill projekt-specifikus fele. A skill általános; ez mondja meg, mit jelent
**ebben** a repóban az, hogy „állapot", és mit kell megmérni, mielőtt bárki átveszi a szálat.*

*Írva: 2026-08-17. Minden szám alatt ott a parancs — és minden szám **elavul**: futtasd újra,
ne idézd.*

---

## Mit jelent itt az „állapot"

Ez a repó egy **keretrendszer**, aminek három, egymástól független állapota van, és egy handoff
mindháromról hazudhat, ha csak az elsőt nézi:

1. **A fa** — mi van commitolva, mi nincs. A szokásos git-állapot.
2. **A terv** — mi van OpenSpec-ben leírva, és mi az, ami *csak kódban* létezik. Itt egy
   képesség attól még nem kész, hogy működik: ha nincs spec-je, a következő munkamenet nem
   tudja, hogy szándékos-e.
3. **A futó rendszer** — a `set-web` szolgáltatás, az orchestration, és a gépen dolgozó
   **agent-munkamenetek**. ⚠ *Egy leszállított commit nem futó rendszer:* a szolgáltatás azt a
   kódot tartja, amivel elindult, és itt hetes nagyságrendű uptime a szokásos.

Egy negyedik, ami nem a repóé, de a következő munkamenetet **hamarabb** éri el, mint a handoff:
**a perzisztens memória** (a skill Phase 1b-je). Lásd lent.

---

## Próbák

### Mindig, minden szálhoz

```bash
git status --short                     # nem commitolt ÉS nem követett munka
git worktree list                      # párhuzamos munkafák — ma: 1 (csak a főfa)
```

### A terv épsége — csak ha a szál OpenSpec-et érint

```bash
openspec list                          # mely change-ek élnek, hány taszkkal
openspec validate <change> --strict    # a SAJÁT change-edre
```

⚠ **Ne ijedj meg a nem-validáló change-ektől: ez pre-existing.** Mérve 2026-08-17:
**12 aktív change bukik `--strict`-en** — köztük évek óta nyitottak. Ez a repó ismert
adóssága, nem a te szálad regressziója. Csak arra van dolgod, amit te nyitottál.

```bash
for c in $(ls openspec/changes/ | grep -v archive); do
  openspec validate "$c" --strict >/dev/null 2>&1 || echo "✗ $c"; done | wc -l
#   ha ez a szám NAGYOBB, mint amit a handoff írt, akkor te rontottál el valamit
```

### Tesztek — és a csapda, ami miatt ez a szakasz létezik

Nincs `make test`; a `Makefile` csak képernyőkép-célokat tartalmaz. A tesztek közvetlenül:

```bash
python -m pytest tests/unit -q -p no:randomly
```

⚠ **A darabszám önmagában semmit nem mond** — a repóban ~100 pre-existing bukó teszt van, és a
szám naponta változik. **Regressziót csak halmaz-diffel lehet kimutatni**, és a naiv baseline
**nem működik**: a csomag editable módban van telepítve, így egy `git worktree` alatt futó
baseline is a **munkafa** könyvtárait importálja. A teljes, működő recept — `PYTHONPATH` három
gyökérre és egy session-végi szivárgás-ellenőrzés — a `CLAUDE.md`-ben áll, „Known unrelated
debt" cím alatt. **Ne írd újra fejből: másold onnan.**

### A futó rendszer

```bash
systemctl --user is-active set-web
systemctl --user show -p MainPID -p ActiveEnterTimestamp --value set-web
#   ⚠ az újraindítás megöli a futó sentinel-alfolyamatot — CSAK felhasználói jóváhagyással
```

### Ki dolgozik még ezen a gépen — párhuzamos munkamenetek

A futásidő minden munkamenetről ír egy rekordot; ez a legolcsóbb módja megtudni, hogy nem vagy
egyedül (mérve 2026-08-17: **13 futó munkamenet, 12/12 rekord**):

```bash
python3 -c "
import json,glob,os
for f in glob.glob(os.path.expanduser('~/.claude/sessions/*.json')):
    d=json.load(open(f))
    print(f\"{d.get('pid'):>8} {d.get('status','—'):8} {d.get('entrypoint','?'):8} {d.get('cwd')}\")"
```

⚠ Két buktató, mindkettő mérve: a `status` **kulcs hiányzik** a headless futásoknál (nem üres —
`rekord['status']` `KeyError`, `rekord.get('status')=='waiting'` pedig **hamis nemleges**), és a
`kind` mező **mindig** `interactive`; a megkülönböztető az `entrypoint` (`cli` / `sdk-cli`).
Részletek: `docs/research/fleet-view-2026-08-17.md` §6.7.

---

## Soha ne veszítsd el

**Tiltott takarítás, amíg nem commitolt munka van a fában.** `git reset --hard` és `git clean`
egyaránt **némán** viszi el az alábbiakat. Célzott visszavonás: `git restore -- <path>`;
ideiglenes commit eldobása: `git reset --soft`.

| mi | miért tűnne el némán |
|---|---|
| `.set/` (teljes) | gitignore-olt (`.gitignore:89`) — benne a **handoff fájlok**, az issue-registry, az agent-állapot |
| `.claude/settings.local.json`, `.env`, `.mcp.json` | gitignore-olt **konfiguráció** — újragépelni fájdalmas, és nincs róla másolat |
| `.claude/sentinel.pid`, `loop-state.json`, `logs/` | futó rendszer állapota — egy törlés után az orchestration árván maradt folyamatokat hagy |
| `/tmp/claude-1000/<projekt>/<session-id>/scratchpad/` | **munkamenet-specifikus**: a `/clear` után nem található meg. Ha mérőszkript vagy vázlat van benne, amit érdemes megtartani, a handoff **nevezze meg**, vagy tedd tartós helyre |

**Perzisztens memória** — a könyvtár neve a repó *abszolút* útvonalából képződik, ezért ne írd
ki: derítsd ki (`ls -d ~/.claude/projects/*set-core*/memory/`). Indexe: `MEMORY.md`.
Nem vész el, de **elavul**, és a következő munkamenetbe magától betöltődik. A skill Phase 1b-je
kötelezővé teszi az átnézését; ebben a repóban ez nem formalitás: 2026-08-17-én egy reggel írt
memória **ugyanaznap megdőlt**, és a handoff attól még helyes volt — vagyis a hibát semmi más nem
fogta volna meg.

---

## Párhuzamos munkamenetek

**A főfa megosztott.** Mérve: ma egy worktree van (`git worktree list`), de **13 agent-munkamenet
fut a gépen**, több projektben. A repón belül a párhuzamosság jellemzően nem worktree-ből jön,
hanem abból, hogy több munkamenet ugyanabban a fában dolgozik.

Ezért a handoff **§6-ja itt nem elhagyható**. Amit meg kell nézni, mielőtt bármihez hozzányúlsz:

- `openspec/changes/<valami>/` könyvtárak, amiket **nem te hoztál létre** — mindegyik egy másik
  szál. A `git status` nem mondja meg, ki írta; a `ls -lt` és a saját emlékezeted igen. Ha nem
  tudod, **hagyd békén, és írd bele a handoffba idegenként**.
- `.set/handoff/*.md` — más szálak handoff-fájljai. Egy szál = egy fájl = egy író; **soha ne írj
  bele másik ID fájljába.**
- A `set-web` és az orchestration folyamatai közösek. Az újraindításuk **más** munkamenet munkáját
  szakítja meg, nem a tiédet.

---

## Sablon-kiegészítések

A skeleton fölé, a §0 elé, egy sor — mert ez a repó három állapotot hordoz, és a handoff
alapértelmezésben csak az elsőt méri:

```markdown
**Állapot-fedezet:** fa ☐ · terv (OpenSpec) ☐ · futó rendszer ☐ · memória ☐
<amelyiket nem mérted, hagyd üresen — az üres kockát a következő munkamenet meg tudja mérni,
 egy hiányzó sort nem tud>
```

A §1 táblázatához egy oszlop, mert itt egy szál akkor is „nyitott", ha a kód kész:

| oszlop | mit írj bele |
|---|---|
| **spec?** | `van` / `nincs` / `nem kell` — egy leszállított képesség spec nélkül itt **nyitott munka**, nem kész munka |
