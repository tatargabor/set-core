# FleetView — egy képernyő minden projekt minden agentjéről

*Kutatás, 2026-08-17. Minden szám ebben a dokumentumban ezen a gépen, ezen a napon mért érték,
és a mérőparancs mellette áll — hogy újra lehessen futtatni, ne pedig elhinni.*

---

## 0. A kérés, egy mondatban

Bal oldalt görgethető projektcsempék; jobb oldalt a kiválasztott projekt **agentjei**, egy-egy
csempében, mindegyikben látszik **mit csinál / dolgozik / vár**, megnyitható a **logja**, és
ugyanabban a csempében **be lehet írni neki** — szövegesen vagy diktálva. A subagentek nem
érdekesek; az `claude -p`-vel önmagából indított agent viszont igen.

Az indok nem esztétikai: több ZED-ablakban követni és egyenként gépelni/diktálni nekik már
nem megy, és a fejlődés iránya az automatizált működés, ahol a rendszer maga kérdez vissza.

---

## 1. A legfontosabb megállapítás: ennek a fele már fut, csak nem itt

A képernyő adatgerince **nem zöldmezős**. Három rendszer szolgáltatja, és mindhárom él:

| forrás | mit tud | hol van |
|---|---|---|
| **set-core web** (FastAPI, :7400) | projekt-registry, orchestration state, process-fa, session-JSONL parser, WebSocket stream, chat, **diktálás** | `lib/set_orch/api/`, `web/src/` |
| **set-agent-comm** (`sac`) | **ki az agent, melyik session az, mit deklarált, hogyan lehet neki üzenni és felébreszteni** | `~/.local/share/set-agent-comm/`, `~/code2/set-agent-comm` |
| **Claude Code** | session-JSONL: minden turn, tool-hívás, token, időbélyeg | `~/.claude/projects/<mangled-path>/<session>.jsonl` |

A hiányzó darab nem adat, hanem **összekapcsolás és egy felület**. Ezt a dokumentum §7 részletezi.

### 1.1 Mennyire vak a mai felület — mérve

A `/api/projects` most azt mondja egy projektről, hogy **`Stopped`, „24d ago"**, miközben
ugyanabban a pillanatban **6 élő Claude session** dolgozik benne. Nem hibás a válasz: a mai
felület kizárólag az **orchestration state**-et nézi (`orchestration-state.json` mtime),
és aki ZED-ben ül és dolgozik, az abban nem szerepel.

```bash
curl -s localhost:7400/api/projects | python3 -c "import json,sys;[print(p['name'],p['status'],p['last_updated']) for p in json.load(sys.stdin)]"
pgrep -x claude | while read p; do readlink /proc/$p/cwd; done | sort | uniq -c
```

Ez pontosan a `evidence-discipline.md` **hamis hiány** osztálya: a képernyő olyan nyugalmat
jelent, amit soha nem mért meg. A FleetView első dolga nem új funkció, hanem ennek a
megszüntetése.

---

## 2. Mi egy „agent"? — a mérés szerint

12 élő `claude` process volt a gépen a mérés pillanatában, **7 különböző projektben**, közülük
egy `claude -p` (tehát pontosan az az eset, amit a kérés külön nevesít: az agent által
önmagából indított agent).

```bash
for p in $(pgrep -x claude); do
  echo "$p | $(ps -o etime= -p $p) | $(readlink /proc/$p/cwd) | $(tr '\0' ' ' </proc/$p/cmdline | cut -c1-60)"
done
```

*(A projektneveket `P-A`…`P-E` helyettesíti; `set-core` maga ez a repó. A mérés szempontjából a név lényegtelen — a lelet a `cwd`-ről szól, nem arról, mi van benne.)*

```
11490    4-15:18  /home/…/P-A-reteg     claude --dangerously-skip-permissions
541532      30:58  /home/…/P-A          claude --dangerously-skip-permissions
909226    2:01:23  /home/…/P-A          claude --dangerously-skip-permissions
917772   17:00:43  /home/…/P-B          claude --dangerously-skip-permissions
992658      19:59  /home/…/P-A          claude -p --model opus --output-format stream-json …
996526   2-04:15  /home/…/P-A          claude --dangerously-skip-permissions
1260243   6:33:03  /home/…/P-C          claude --dangerously-skip-permissions
1266258     14:09  /home/…/P-D         claude --dangerously-skip-permissions
1375928     12:30  /home/…/set-core     claude --dangerously-skip-permissions   ← ez a session
1527619  1-01:49  /home/…/P-A          claude --dangerously-skip-permissions
2268597   3:06:00  /home/…/P-A          claude --dangerously-skip-permissions
3386345   4:17:01  /home/…/P-E          claude --dangerously-skip-permissions
```

Két dolog azonnal látszik, és mindkettő tervezési döntést kényszerít:

**(a) Az interaktív session parancssora semmit nem mond a projektről.** Csak
`claude --dangerously-skip-permissions`. A projektet egyedül a **`cwd`** azonosítja. A mai
process-felderítés (`actions.py:_build_project_process_tree`, „orphan scan") viszont a
**parancssorban** keres projekt-útvonalat — így ezekre a sessionökre **strukturálisan vak**.
Ez nem hiba a mai céljához képest (orchestrator-gyerekeket keres), de a FleetView nem
építhet rá: **a cwd-t kell olvasni**, `/proc/<pid>/cwd`.

**(b) Egy projektben hat session ül.** A „melyik agent melyik" kérdés tehát nem elkerülhető
mellékszál, hanem a feladat magja — és épp ez az, amiért ZED-ben már nem követhető.

---

## 3. Az azonosítás: miért nem elég a heurisztika (mért 44%)

A csempéhez három dolgot kell összekötni: **process ↔ session-JSONL ↔ agent-identitás**.

A kézenfekvő heurisztika — *„a projekt könyvtárában a legfrissebb `.jsonl` az övé"* —
megmérve, a `sac` registry ismert igazsága ellen (9 pár, ahol a seat `owner` PID-je él):

```
PID    11490 ✓  PID  541532 ✗  PID  909226 ✗  PID  992658 ✓  PID  996526 ✗
PID 1266258 ✓  PID 1527619 ✗  PID 2268597 ✗  PID 3386345 ✓
                                        → 4 találat / 5 hiba
```

**44%**, és a hibák nem véletlenszerűen oszlanak: minden találat olyan projektből jött, ahol
**egy** session fut, minden hiba onnan, ahol **hat**. Vagyis a heurisztika pontosan ott romlik
el, ahol a felület egyedül értelmes. A hibairány pedig a rossz: nem „nem tudom"-ot mond, hanem
magabiztosan **egy másik agent logját** mutatná — egy projektben, ahol hat session ír.

Egy esetben (PID 541532) a valódi session **nem is szerepelt** a könyvtár 497 fájlja között:
a session még egy sort sem írt ki. A „legfrissebb fájl" ott is válaszolt volna.

### 3.1 Ami viszont mérés, nem tipp: a `sac` registry

A `~/.local/share/set-agent-comm/registry.json` seatenként tárolja:

```json
"P-A#f54b3564": { "session": "f54b3564-5e92-…", "owner": 996526, "rooms": [...],
                  "firstSeen": "...", "lastSeen": "..." }
```

`owner` = a Claude process PID-je, `session` = a JSONL fájl neve. Ellenőrizve: a seat
session-azonosítójával a JSONL **létezik** a mangled projekt-könyvtárban.

```bash
ls -la ~/.claude/projects/-home-…/f54b3564-5e92-4a77-a995-e5495af169ef.jsonl   # 2.4 MB
```

Ez a kapcsolat nem levezetés: a hook írja be, a session saját azonosítójából
(`CLAUDE_CODE_SESSION_ID`). **Ezért a `sac` az elsődleges forrás, és a heurisztika csak
jelölt fallback** — soha nem néma.

### 3.2 De a `sac` sem fed le mindent — és ez is mérés

12 élő sessionből **9-nek** van seatje. Háromnak nincs (`P-B`, `P-C`, és ez a set-core session),
mert azokban a projektekben nincs `sac install`. Következmény, és ez a UI egyik alapfogalma:

| | látható | instruálható |
|---|---|---|
| process van, seat van | ✅ | ✅ |
| process van, seat nincs | ✅ (cwd-ből) | ❌ — a csempe ezt **kimondja**, nem hallgatja el |

Egy agent, ami fut, de nem üzenhető, nem „hiányzik" a képernyőről és nem is látszik épnek:
látszik, és rá van írva, hogy miért néma. (`ui-quality.md`: a tömörítés nem rejthet el hibát.)

---

## 4. A beírás: mi lehetséges és mi nem — mérve

Ez a felület legkockázatosabb ígérete, ezért ez a szakasz a legfontosabb.

### 4.1 Ami nem megy: idegen PTY-be írni

Minden létező session egy terminál-PTY-n ül, amit a ZED birtokol:

```bash
readlink /proc/1266258/fd/0     # → /dev/pts/15
```

A klasszikus trükk (TIOCSTI ioctl-lel karaktert tolni egy idegen terminálba) ezen a kernelen
**le van tiltva**:

```bash
sysctl dev.tty.legacy_tiocsti     # → 0        (kernel 6.8.0-136)
```

Tehát **nincs kiskapu**: egy futó, ZED-ben indított sessiont közvetlenül gépelni nem lehet.
Ez nem korlátozás, amit meg lehetne kerülni — ez a rendszer határa, és a terv erre épül.

### 4.2 Ami megy (1): `sac send` — de az ébresztés feltételes

A `sac` a beírás kész útja, és a mechanizmusa a saját forrásában dokumentált
(`hooks/stop.mjs`), két külön esetre:

```
az agent DOLGOZIK  → Stop hook: nem fejezheti be a turnt olvasatlan, neki címzett üzenettel
az agent ÜRESJÁRAT → csak egy futó `sac wait` tud ÚJ turnt indítani
```

Vagyis egy idle session, ami alatt nem fut `sac wait`, **nem ébred fel** — az üzenet ott ül,
amíg valaki kézzel be nem gépel a ZED-be. Megmérve, hány élő sessionnek van saját élő `wait`-je:

```
49 élő `sac wait` process ·  élő claude: 12 ·  saját wait-tel: 4        (~33%)
```

⚠ **A mérés első futása 5-öt mondott, és rossz irányba tévedett.** A számláló python-szkript
saját parancssorában szerepelt a `"sac.mjs wait"` minta, így **önmagát is megtalálta**, és a
saját sessionömet ébreszthetőnek könyvelte. Ez a `evidence-discipline.md`-ben nevesített
*„a mérés a mért korpuszon belül van"* osztály, és pont a kellemetlen irányba hibázik:
optimistább képet fest a lefedettségről, mint a valóság. A javított szám 4/12.

A 49-ből ~30 **árva**: a `wait` fut, de a `claude` gazdája már halott. Ezek se nem ébresztenek,
se nem takarodnak el maguktól.

**Következmény a tervre:** a csempén az „üzenhető" nem bináris, hanem három állapot, és a
különbség a felhasználónak számít:

| állapot | mit jelent | mit írjon a csempe |
|---|---|---|
| **azonnal ébred** | seat + élő `sac wait` | „megkapja most" |
| **turn végén kapja** | seat, de nincs wait; a session dolgozik | „a következő turn végén" |
| **csak ott ül** | seat, nincs wait, a session üresjárat | „nem ébred — kézzel kell felhozni" |

Egy „elküldve" visszajelzés, ami mindhármat ugyanúgy jelenti, hazudik — és a leggyakoribb
esetben hazudik. (A `sac send` maga is ezt csinálja jól: a `wakes` mezőben megmondja, kit
ébresztett fel *ténylegesen*, és a `notice` figyelmeztet, ha senkit.)

### 4.3 Ami megy (2): a FleetView indítja a sessiont — a „saját terminál"

Ha a session a FleetView-ból indul, a PTY **master oldala** a szerveré. Innentől minden adott,
amit a kérés „saját terminálnak" nevez: gépelés, beillesztés, Ctrl-C, méretezés, teljes
scrollback — és a diktálás ugyanide ír.

Ez a rész **zöldmezős**: PTY/tmux infrastruktúra jelenleg nincs a repóban (a `dispatcher.py`
két tmux-említése elavult komment, `tmux ls` → *no server running*), és a web
`package.json`-ban nincs `xterm`.

És pontosan ez az, ami a kimondott célt szolgálja — leválni a ZED-ről: **az új agenteket a
FleetView indítja**, a régiek addig `sac`-on át elérhetők maradnak. Egyik napról a másikra
semmit nem kell átköltöztetni.

---

## 5. Az állapot: „dolgozik" vagy „vár"? — miből olvasható ki

A kérés fő haszna („hol van várakozás") ezen múlik. A jelek, drágaság szerint növekvő sorrendben:

| jel | forrás | mit mond | ára |
|---|---|---|---|
| process él-e | `/proc/<pid>` | fut / halott | ~0 |
| session-JSONL **mtime** | `stat` | mikor mozdult utoljára | 0 ms / 497 fájl (mérve) |
| utolsó bejegyzés + **függő `tool_use`** | JSONL tail 64 KB | tool fut-e, melyik, mióta | 0.1 ms (mérve) |
| `sac focus` | `focus.json` | amit az agent **magáról deklarált** | ~0 |
| `sac inbox` / cursor | store | van-e neki olvasatlan kérdése | ~0 |
| span-elemzés (llm-wait, gap-kategória) | `api/activity_detail.py` | részletes idővonal | teljes parse |

A „függő tool_use" a legbeszédesebb egyetlen jel: az utolsó ~60 bejegyzésben van olyan
`tool_use` id, amire még nem jött `tool_result`. Ha van, az agent **abban a toolban ül** — és a
tool neve az, amit a csempén látni akarunk (`Bash`, `Read`, `Task`…). Ha nincs, és az utolsó
bejegyzés assistant-üzenet, akkor **befejezte a turnt** — vagyis vár.

⚠ Egy figyelmeztetés, amit a `sac` saját kimenete adott: a `sac agents` a projektre azt írta,
**„21m silent"**, miközben a legfrissebb JSONL abban a projektben **abban a percben** íródott.
A registry `lastSeen`-je nem az aktivitás, hanem az **utolsó hook- vagy `sac`-hívás** ideje.
Proxy, nem a dolog maga. A csempe „utoljára mozdult" adata **a JSONL mtime-ból** jöjjön, és
soha a registry `lastSeen`-jéből — különben nyugalmat jelent egy dolgozó agentről.

### 5.1 Teljesítmény: a listanézet soha ne olvasson teljes logot

Mérve a legnagyobb projekt-könyvtáron:

```
497 jsonl · összesen 955 MB
stat mind:            0 ms
legfrissebb (1.5 MB) teljes olvasás: 4 ms
tail 64 KB:           0.1 ms
```

Tehát: **`stat` + `tail` a csempéknek, teljes parse csak megnyitott lognál.** (A mai
`sessions.py` az `_extract_session_change_name`-mel minden fájlt megnyit — ez egy 497 fájlos
könyvtárban nem az az út, amit a FleetView másolhat.)

---

## 6. Adatmodell — mi a „projekt" és mi az „agent"

### 6.1 A bal oldali fa forrása: unió, nem választás

A két registry alig fedi egymást — mérve:

```
set-core registry:  39 bejegyzés, ebből 20 nem archivált
sac registry:       15 agent (12 lokális útvonallal)
metszet:             4
```

8 olyan projektben fut agent, ami a set-core registryben **nincs benne**; 16 regisztrált
projektben viszont nincs agent. Ha a fa csak a set-core registryt mutatná, a felhasználó
pontosan azokat a projekteket nem látná, ahol valaki most dolgozik.

Tehát a fa forrása **három halmaz uniója**, és a csempe megmondja, honnan tud róla:

```
   set-core registry  ∪  sac registry  ∪  élő claude process cwd-je
        (regisztrált)      (bus-tag)          (aki éppen dolgozik)
```

A harmadik tag nélkül egy ZED-ben most indított session projektje nem jelenne meg — pedig épp
az a leggyakoribb eset.

### 6.2 Az agent identitása

```
Agent  := { seat?, pid?, session_file?, project }
```

Egyik mező sem kötelező önmagában, és **melyik hiányzik, az maga is információ**:

| eset | mit lehet vele | példa a mérésből |
|---|---|---|
| seat + pid + jsonl | minden: állapot, log, üzenet | 9 session |
| pid + jsonl (seat nincs) | állapot és log, üzenet nem | 3 session |
| seat + jsonl, pid halott | log, előzmény; nem él | a ~30 árva `wait` gazdái |
| seat + pid, jsonl nincs | él, de még nem írt | PID 541532 (mérve) |

### 6.3 A projekt ≠ a munkakönyvtár — worktree, és egy hiba, amit ez a kutatás elkövetett

**Az első kör ezt elrontotta.** Egy agent, aminek a `cwd`-je `…/projekt-reteg` volt, **külön
projektként** került a listára. Nem az: ugyanannak a repónak egy másik worktree-je. Mérve egy
valós projekten:

```bash
git -C <projekt> worktree list
```

```
…/projekt          dev
…/projekt-hotfix   bugfix/…          ← ugyanaz a repó
…/projekt-reteg    planning/…        ← ugyanaz a repó
/tmp/…/scratch     (detached)  ×2    ← eldobható, agent nélkül nem érdekes
```

**5 worktree, egy projekt.** A visszavezetés egy parancs, és mindhárom valós worktree-n helyesen
válaszolt:

```bash
dirname "$(git -C <cwd> rev-parse --path-format=absolute --git-common-dir)"   # → a fő repó
git -C <cwd> rev-parse --abbrev-ref HEAD                                       # → az ág
```

Tehát: **a `cwd` a projekthez vezet, de csak a git-en keresztül.** A nyers útvonal-egyezés — amit
az első kör csinált — szétszórja egy projekt agentjeit annyi hamis projektre, ahány worktree-je
van, és pont a „hány agent dolgozik ezen a projekten" kérdésre nem ad többé választ.

Ugyanaz az osztály, amit ez a dokumentum végig kerülget: **a proxy helyes, amíg valaki meg nem
kérdezi, mihez tartozik.**

### 6.4 A leszármazás mérhető — nem kell hozzá új mechanizmus

„Melyik agentből ered" kérdésre a **process-szülőlánc** válaszol: felfelé haladva az első
agent-process a szülő. Mérve:

```
PID 355028  claude -p            ← headless
   └─ szülő: bash
        └─ PID 996526  claude    ← interaktív: ez indította
```

A 12 élő agentből **1** volt gyerek — ma még ritka, de pontosan az az eset, amit a felvetés
külön nevesít (az agent, amit egy agent `claude -p`-vel indít önmagából).

Két figyelmeztetés, mindkettő mérésből:

- **A lánc élő.** Két mérés között az egyik headless agent lefutott, és a szülője újat indított
  más PID-del. A csempe tehát a szülő **seatjét** jegyezze meg, ne a PID-et — a PID
  újrahasznosul, a seat nem.
- **A szerep viszont ebből mérés, nem tipp.** Aki gyereket indított, az **irányít**; a gyerek
  **végrehajt**. Ez a különbség ikont érdemel — ellentétben a fázissal, lásd alább.

### 6.5 A fázis nem mérés — és ezt ki kell mondani, mielőtt ikont kap

A felvetés fázis-ikonokat kér („OpenSpec tervez", „végrehajt"). Megmérve, hogy ez kiolvasható-e
a naplóból — **ebben a munkamenetben**, ami végig OpenSpec-munkát végzett:

| jel | találat | mit mond |
|---|---|---|
| `/opsx:*` slash-parancs | **0** | a munka nagy része nem slash-parancsból indul |
| `/set:*` | 0 | ugyanaz |
| `apply-cycle`, `git commit`, teszt-futtatás | 0 | ez a munkamenet nem ért odáig |
| tool-eloszlás | 66 Bash · 9 Write · 7 Read | *mit tesz*, nem *hol tart* |

A nulla a lényeg: a legkézenfekvőbb jel **egyetlen találatot sem adott** egy olyan
munkamenetre, aminek a fázisa egyértelmű volt. Egy tippelt fázis-ikon tehát pont akkor téved,
amikor a helyzet szokatlan — és a szokatlan helyzet az, amiért ezt a képernyőt nézik.

**Javaslat: a fázis deklarált legyen, és ahol nincs deklaráció, ott ne legyen ikon.** Ez
ugyanaz a felállás, mint a keretrendszer minden más pontján: a projekt szolgáltatja az adatot, a
keretrendszer az absztrakciót. Az útvonal-alapú heurisztika (`openspec/` → tervez) ráadásul
domain-tudást vinne a Layer 1-be, amit a modular-architecture szabálya tilt.

### 6.6 Mi van bekötve egy projektbe — az ikonsor forrása

A projektcsempe ikonsora fájlok jelenlétéből mérhető, projekttípus-tudás nélkül:

| ikon | mérés |
|---|---|
| agent-busz | a busz hookja a `.claude/settings.json`-ban + a skill könyvtára |
| OpenSpec | `openspec/` létezik |
| orchestration | orchestration-állapotfájl létezik |
| set-core szabályok | `.claude/rules/` és tartalma |
| MCP | `.mcp.json` `mcpServers` kulcsai |

Két valós projekten lefuttatva mindegyik helyesen válaszolt. **A halvány ikon nem hiba:**
azt jelenti, hogy a képesség bekötHETŐ, de nincs bekötve — ami más állítás, mint hogy nem
létezik. A készlet adatvezérelt legyen, ne beégetett lista: minden új bekötés egy sor.

---

## 6.7 ⚠ HARMADIK KÖR — a §3 és a §4 nagy része ELAVULT

*A felhasználó rákérdezett: „a `claude -p`-vel indított sessionbe bele lehet injektálni, nem?"
Igaza volt, és a nyomon elindulva kiderült, hogy nemcsak a `-p` esetében — a §3 heurisztika-
mérése és a §4 „nem lehet beírni" következtetése is egy **jobb forrás létezésének nem-ismerete**
volt. A régi mérések helyesek; a belőlük levont terv nem.*

### 6.7.1 A Claude Code maga írja ki, amit én kikövetkeztetni próbáltam

Minden futó session regisztrálja magát:

```
~/.claude/sessions/<PID>.json          ← metaadat
/run/user/1000/cc-socks/<PID>.sock     ← lokális unix socket, amin figyel
```

Tartalma (valós példa, mezőnevek változatlanul):

```json
{ "pid": 1266258, "sessionId": "d59deac7-…", "cwd": "/home/…/projekt",
  "kind": "interactive", "peerProtocol": 1, "version": "2.1.233",
  "name": "projekt-eb", "status": "waiting", "waitingFor": "input needed",
  "messagingSocketPath": "/run/user/1000/cc-socks/1266258.sock",
  "startedAt": …, "procStart": …, "statusUpdatedAt": … }
```

**Mérve, mind a 12 futó sessionre:**

| | eredmény |
|---|---|
| futó `claude` process | 12 |
| `sessions/*.json` bejegyzés | 12 — **teljes fedés, szemét nélkül** |
| `sessionId` → létező napló-fájl | **12 / 12** |
| státusz-értékek a mintában | `idle`, `busy`, `shell`, `waiting` |
| `waitingFor` | `"input needed"` — 2 sessionnél |

Vessük össze a §3-mal: ott a „legfrissebb napló" heurisztika **4/9** volt, és a `sac` registry
kellett hozzá, hogy egyáltalán legyen igazság, amihez mérni lehet. Itt **12/12**, natívan, a
`sac` nélkül is.

**Amit ez leír a tervből:**

| §-ban ez állt | most |
|---|---|
| PID→session párosítás 44%, jelölni kell a tippet | `sessionId` pontosan megvan — a heurisztika **fallback**, nem alapeset |
| az identitáshoz kell a `sac` registry | nem kell; a `sac` marad, de más okból (szobák, fókusz, több gép) |
| az állapot a napló tail-jéből derül ki | `status` natívan; a tail a **finomítás**, nem az alap |
| a projekt a `cwd`-ből, `/proc`-ból | `cwd` a JSON-ban |
| 12-ből 3 agent „nem címezhető" (nincs seat) | mind a 12-nek van socketje |

**Két mért figyelmeztetés, amitől ez nem lesz csodaszer:**

- **A headless (`claude -p`) session megjelenik, de a `status` KULCS NINCS OTT.** Külön mérve, egy
  eldobható headless futással: a `<pid>.json` létrejön, de `status = None`, és a `kind` mezője
  **`"interactive"`** — vagyis a `kind` nem különbözteti meg. A megkülönböztető az
  **`entrypoint`**: `cli` az interaktívra, `sdk-cli` a headlessre.

  Ez a mérés egy agent-csatornán oda-vissza ment, és mindkét oldal állítása javult tőle. A másik
  fél először azt mérte, hogy headless session **egyáltalán nem jelenik meg** — az ő mintájában
  ugyanis épp nem futott ilyen, és mivel a `kind` mindenkinél `interactive`, a hiányukat nem
  lehetett megkülönböztetni attól, hogy nem is léteznének. Az én első megfogalmazásom („nem
  frissít státuszt") viszont azt sugallta, hogy a mező ott van, csak elavult.

  **A pontos alak, és ez a fontos rész:** a kulcs *hiányzik*. Aki `record.status === "waiting"`-et
  ír, az **hamis nemlegeset** kap egy valóban emberre váró headless futásra — ami rosszabb, mint
  ha a rekord se lenne meg, mert egy hiányzó rekord láthatóan hiányzik, egy hamis nemleges pedig
  megkülönböztethetetlen attól, hogy „itt nincs teendő". Ez a *hamis hiány* osztály, és pontosan
  ezért van a specben az a követelmény, hogy amit a keretrendszer nem tud eldönteni, azt
  **ismeretlennek** kell jelentenie, soha nem üresjáratnak. Most mért esete is van.
- **A `statusUpdatedAt` elavul.** Mértem 55 órás „idle"-t. Logikus — egy idle sessionnek nincs
  mit frissítenie —, de ebből következik, hogy **a „mikor mozdult utoljára" továbbra is a napló
  mtime-jából jön** (§5). A `status` azt mondja, *mit csinál*; az mtime azt, *mikor mozdult*.
  Ez a kettő nem ugyanaz, és a `status` egyedül nyugalmat jelentene egy leállt sessionről is.

### 6.7.2 A beírás: a peer-csatorna működik — élő bizonyítékkal

A §4.1 („idegen PTY-ba nem lehet írni, `dev.tty.legacy_tiocsti = 0`") **igaz marad**, de rossz
rétegre nézett. A PTY alatt van egy magasabb csatorna: a sessionök unix socketje.

A bizonyíték nem szintetikus. **E kutatás írása közben egy másik projekt futó Claude sessionje
üzenetet küldött ebbe a sessionbe** ezen a csatornán — kérdésekkel a készülő felületről. Vagyis
a „futó, más által indított sessionbe kívülről be lehet szólni" nem terv, hanem megtörtént.

**Ami ebből még NINCS mérve, és ez a terv legfontosabb nyitott kérdése:** a peer-üzenetküldést
egy *Claude Code session* végezte. Hogy egy **külső program** (a FleetView Python-szervere)
tud-e ugyanezen a socketen beszélni, nem tudom — a protokoll nem publikus. A `peerProtocol: 1`
mező arra utal, hogy verziózott és szándékos felület, de ez következtetés, nem mérés. Három
kimenet lehetséges, és a terv mérete múlik rajta:
1. a socket protokollja használható kívülről → a beírás triviális, minden futó agentre;
2. nem, de a FleetView indíthat egy Claude Code-ot proxynak → körülményes, de működik;
3. egyik sem → marad a `sac` busz és a `-p` csatorna (lásd alább), ami a mai állapot.

### 6.7.3 A `-p` csatorna: mérve, és jobb, mint a PTY

Ha a FleetView indítja az agentet, `--input-format stream-json`-nal **nem kell PTY**:

```
1. üzenet  → válasz     (a session elindul)
2. üzenet UGYANABBA a processbe → válasz
ugyanaz a session-azonosító: IGEN · a process a 2. válasz után is él: IGEN
```

**Költség — élő process vs. `--resume` (amit a repo `chat.py`-ja már ma is csinál):**

| | friss input | cache-ből | falióra |
|---|---|---|---|
| élő process, 2. üzenet | 10 | 25 811 | **2.1 s** |
| `--resume`, új process | 10 | 25 994 | **5.1 s** |
| `--resume` 6,7 perc várakozás után | 10 | 26 272 | **4.5 s** |

**A tokenkülönbség gyakorlatilag nincs** — mindkettő ~10 friss tokent fizet, a többit a
prompt-cache viszi. A `--resume` ára **idő** (~3 mp), nem token. A „sok megszakított resume
drága?" kérdésre tehát mérve: **nem**, a cache-ablakon belül. *Nem mértem* egy óránál hosszabb
szünet utáni resume-ot; ott a cache lejárhat, és akkor a teljes kontextus friss inputként
számítana — ez a tokenaggodalom egyetlen valós formája.

**Közbeírás egy DOLGOZÓ agentbe — mérve:** hosszú feladat közben beküldött második üzenet
**sorba állt**. Az első feladat végigfutott (`result: success`), a második külön turnként
lefutott utána, a process élt tovább. Nem szakít meg, nem hibázik, nem vész el. A megszakítás
egyébként sem követelmény — az a cél, hogy az automaták lefussanak.

**A PTY-út ára viszont mérve nem nulla:** egy PTY-ban indított *interaktív* session először egy
bizalmi kérdést tesz fel („Is this a project you created or one you trust?"), és amíg nem
válaszol rá senki, **nem is regisztrálja magát** a `sessions/` könyvtárba (60 s alatt nem
jelent meg). Aki interaktív sessiont indít programból, annak ezt kezelnie kell.

### 6.7.4 Miért nem ért célba a wake-upok fele — egy második ok, amit nem én találtam

A §4.2 azt mérte, hogy 12 élő sessionből 4 alatt fut ébresztő, és a busz saját statisztikája is
azt mondta, hogy a wake-upok jelentős része „reached no session". Egy másik projekt copilotja a
saját oldalán találta meg a **második** okot, és ez a mérés ellenőrizve:

```
fs.inotify max_user_instances : 128
használatban                  : 126        ← két szabad hely
élő `sac wait` process        : 50
```

Két szabad példány mellett bármelyik új `fs.watch` **EMFILE-lel elhasal**, és a figyelő némán
visszaesik egy lassabb pollra. Vagyis egy ébresztő létezhet és mégsem ébreszt időben — ami a
mérésben „nincs alatta ébresztő"-nek látszik.

**Az attribúció két kört vett igénybe, és a második az érdekesebb.** Az eredeti állítás az volt,
hogy az árva figyelők eszik el a limitet — ez tipp volt, mérésnek öltözve. Az én ellenőrzésem
viszont **hibás mérés** lett, ami magabiztosabban hangzott, tehát rosszabb fajta. A valóság,
process-azonosítóval és teljes parancssorral:

| tulajdonos | inotify fd | process |
|---|---|---|
| **`set-web` (ez a repó)** | **39** | **1** |
| `sac wait` | 20 | 20 |
| claude session | 11 | 11 |
| systemd, böngésző, egyéb | 55 | 45 |
| szerkesztő | **1** | 1 |

**Az én első mérésem „szerkesztő 41"-et mondott, és az osztályozóm volt a hibás:**

```python
elif "code" in cmd or "zed" in cmd.lower(): key = "szerkesztő"   # ← ez a hiba
```

A projektek `~/code2/…` alatt vannak, tehát a minta a **saját webszerverünket**, a busz figyelőit
és a gui-t is „szerkesztőnek" vette — összesen 61 fd-t. Ez a `evidence-discipline.md`-ben
nevesített *bare substring check*, elkövetve épp egy másik mérés javítása közben.

**Amit a helyes mérés mutat, az a repóra nézve fontosabb, mint a wake-up rés.** A legnagyobb
fogyasztó a saját webszerverünk, egyetlen processben, 39 példánnyal — a gép kapacitásának 31%-a.
Utánamérve nem lyuk, hanem tervezett fogyasztás: **20 regisztrált projekt**, mindegyikre egy
figyelő, projektenként 1–3 könyvtárral (állapot, napló, projektgyökér) → 20 × ~2 ≈ 39. Uptime
9 nap 23 óra.

De ez azt is jelenti, hogy **a fogyasztásunk a regisztrált projektek számával nő**: ~40 projektnél
a webszerver egymaga elvinné a 128-as limitet. Ez a FleetView-tól független, meglévő skálázódási
korlát ebben a repóban.

**A mechanizmus pontos alakja, és ez a fontos rész:** nem a régi figyelők romlanak el, hanem
telítettségnél **minden ÚJONNAN felfegyverzett figyelő hasal el**. Vagyis a legfrissebben nyitott
session — amit valaki épp most indított — az, amelyik lassabb pollra esik vissza. Ez rosszabb
irányú, mint az „árvák elfogyasztják" magyarázat, és konzisztens a §4.2 4/12-es lefedettségével.

**Tervezési korlát, ami ebből következik:** a FleetView **nem indíthat per-agent figyelőt**. Egy
figyelő a session-könyvtárra elég, a naplókra igény szerinti olvasás.

**A korlát indoklása viszont futtatókörnyezet-függő, és ez egy negyedik kört vett igénybe.** A
másik oldal mérte, hogy a libuv (Node) **processzenként egyetlen** inotify példányt nyit, és
könyvtáranként csak egy watch-descriptort tesz bele — a `sac wait` processeken ez látszik is
(2 szoba → 1 példány). Ebből az következne, hogy a figyelők száma nem is számít, csak a
processzeké.

**Ránk ez nem áll, és egyetlen szám mondja ki:** a `set-web` **egy process, egy asyncio
event-loop**, és **39** példányt tart. Ha processzenként egy lenne, ez 1 lenne. A Python/watchfiles
út tehát hívásonként fogyaszt. *Amit viszont nem mértem: hogy a 39-et konkrétan a watchfiles
nyitotta-e — csak azt tudom, hogy a set-web process tartja őket.*

**És a mérés, amivel ezt ellenőrizni akartam, maga is áldozatul esett a mért jelenségnek.** Egy
tesztben nyitottam egy `awatch`-ot hat könyvtárral, majd hatot egyesével — mindkettő **0 inotify
fd**-t mutatott. Nem azért, mert olcsó, hanem mert nem tudott nyitni:

```python
inotify_init()  →  errno 24 (EMFILE), NULLA sikeres nyitás után
```

A gépen **nincs egyetlen szabad példány sem**, tehát a watchfiles pontosan úgy esett némán pollra,
ahogy a busz figyelői. Ez egyben a telítettségi mechanizmus legerősebb bizonyítéka: nem
rekonstruált eset, hanem a mérőeszközön mutatkozott meg.

*A tanulság a negyedik körből: mindkét oldal olyan környezetről általánosított, amit csak a saját
oldalán lát — Node-ot mérni és Pythonra következtetni ugyanaz a lépés, mint fordítva. Amikor a
következtetés átlép a másik oldalra, ott kell újramérni.*

*Ez a harmadik kör ezen a csatornán, ahol a **mérés helyes volt és az általánosítás nem**: előbb a
headless session `kind` mezőjénél, aztán az én „nem frissít státuszt" megfogalmazásomnál, most az
attribúciónál — ahol viszont már nem az általánosítás, hanem maga a mérőeszköz volt rossz.*

### 6.7.5 A közvetlen socket: csengő, nem postaláda

Kísértés volt a socketet kézbesítésre használni, mert az a mért rést közvetlenül zárná. A másik
oldal ellenérve döntötte el, és erősebb, mint amit én terveztem: egy socketre tett üzenet
**fire-and-forget** — nincs napló, nincs olvasási kurzor, és a „ki van lemaradva" nézet vakon marad
rá. Egy felület, aminek az alapszabálya, hogy semmit nem rejt el, nem kézbesíthet olyan csatornán,
ami nem hagy nyomot.

Ezért: **az üzenetet a tartós út viszi** (fájl, címzés, kurzor), és ha a küldés válasza szerint
senkit nem ébresztett fel, akkor a FleetView a socketen **odabök**, hogy nézzen postaládát. Ez
bezárja a rést, és ha a socket kívülről mégsem használható, a rendszer pontosan a mai módon
működik tovább — csak lassabban ér célba az üzenet. Egy nem dokumentált felületre építve ez a
visszaesési út nem opcionális.

### 6.7.6 Mit jelent ez a terv méretére

- A **felderítés és az állapot** rétege jóval kisebb: egy könyvtár olvasása, nem process-scan
  plusz registry-összefésülés plusz heurisztika. A `/proc` és a `sac` **fallback és kiegészítés**
  marad (több gép, szobák, fókusz), nem alap.
- A **PTY-terminál mint külön nagy szakasz elesik.** Amit a §11 „második körnek" nevezett, azt a
  `-p` stream-json csatorna olcsóbban adja, és a repóban már van rá kód (`chat.py`).
- A **„nem címezhető agent" kategória összezsugorodik** — a mockup ezt 12-ből 3 esetre mutatta.
- **A kockázat viszont új:** a `sessions/*.json` és a socket nem dokumentált felület. Verzióváltás
  eltörheti. A mintában **két különböző Claude-verzió** futott egyszerre (2.1.229 és 2.1.233),
  mindkettő `peerProtocol: 1`-gyel — ez jó jel, de a felület olvasásakor a `peerProtocol` és a
  `version` mezőt ellenőrizni kell, és hiányuk esetén a régi úton (process + napló) kell tudni
  működni.

---

## 7. Mi hiányzik ténylegesen — a munka listája

| # | darab | van már? |
|---|---|---|
| 1 | **agent-felderítés**: cwd-alapú process-scan + `sac` registry összefésülése | ❌ új (a process-fa létezik, de parancssorban keres) |
| 2 | **agent-állapot**: mtime + függő tool_use + focus + inbox → egy állapotszó | ❌ új (a parser létezik: `activity_detail.py`) |
| 3 | **FleetView API**: `/api/fleet` (projektek+agentek), `/api/fleet/<agent>/log`, `…/send` | ❌ új |
| 4 | **élő stream** per agent | ⚠ minta megvan (`/ws/{project}/stream`), per-agent új |
| 5 | **UI**: kétpaneles elrendezés, projektcsempék, agent-csempe-rács | ❌ új |
| 6 | **log-nézet** a csempében | ⚠ `LogPanel`/`ActivityView` létezik, csempe-méretre nem |
| 7 | **beírás** `sac send`-en át, háromállapotú visszajelzéssel | ⚠ `sac` kész, kötés nincs |
| 8 | **diktálás** | ✅ `VoiceInput.tsx` + `/api/soniox-key` — bekötendő |
| 9 | **PTY-terminál** (FleetView által indított session) | ❌ új, és ez a legnagyobb darab |
| 10 | árva `sac wait` processek takarítása | ❌ új (mérve: ~30 db) |
| 11 | **worktree → projekt visszavezetés** és ág-jelölés a csempén | ❌ új, de egy `git` hívás (§6.3) |
| 12 | **leszármazás**: szülő-agent felderítése a process-fából | ❌ új, de a process-fa már megvan (§6.4) |
| 13 | **projekt-képességek** ikonsora (mi van bekötve) | ❌ új, fájl-jelenlét vizsgálat (§6.6) |
| 14 | **nézetállapot projektenként** (nagyítás, sűrűség, piszkozat) | ❌ új, kliens-oldali |
| 15 | **fázis-deklaráció** — az agent mondja meg, hol tart | ❌ új, és **nem** a keretrendszer találgatja (§6.5) |

**Ebből 13 kicsi és egy nagy.** A PTY-terminál (9) önmagában akkora, mint a többi együtt — és
a többi nélküle is teljes értékű felületet ad. Ez a természetes vágás a szakaszok között.

A 11–15 a második kör visszajelzéséből jött. Négy közülük mérésre épül és emiatt olcsó; a
15. az egyetlen, ami **új megállapodást** kíván a projektek felé — és épp ezért az, amit nem
szabad heurisztikával kiváltani.

---

## 8. Kockázatok, amiket a terv nem kerülhet meg

1. **A „elküldve" hazudhat.** §4.2 — a mai telepítésen az esetek kétharmadában nem ér célba
   azonnal. A visszajelzésnek a `sac send` `wakes`/`notice` mezőit kell tükröznie, nem egy
   pipát.
2. **Rossz agent logja.** §3 — a heurisztikus párosítás 44%. Jelöletlenül átvéve ez
   magabiztosan téves logot mutat. A jelöletlen párosítás tilos.
3. **Bizalmasság.** A logcsempe és a fókusz-sor **consumer-tartalmat** jelenít meg. Futásidőben
   ez rendben van (`CLAUDE.md`, External Project Confidentiality: a határ a *megőrzés*), de
   semmi nem kerülhet cache-be, logba, memóriába vagy hibaüzenetbe. A képernyőterv és minden
   teszt-fixture semleges nevekkel dolgozik.
4. **A képernyő tömörítése elrejthet egy elakadt agentet.** Ha sok agent van és a rács kicsi
   csempékre esik, a „vár emberi válaszra" állapotnak a **projektcsempén is** látszania kell —
   különben a bal oldal nyugodt, miközben jobbra valaki órák óta áll (`ui-quality.md`).
5. **A PTY-út új felelősség**: a szerver processeket indít és tart életben. Ez egy sokat futó
   szolgáltatás (a jelenlegi `set-web` uptime-ja mérve **1 hét 2 nap**) — ami azt is jelenti,
   hogy egy leszállított javítás nem attól fut, hogy be van commitolva.

---

## 9. Amit ez a kutatás nem mért meg

- **Több gép.** A `sac` tud relay-t; a `/proc`-alapú felderítés nem. A távoli agent
  megjeleníthető a registryből, de az állapota nem mérhető ugyanígy. A terv egygépes.
- **Windows/macOS.** A `/proc/<pid>/cwd` Linux-specifikus. A `psutil` már függőség és
  hordozható — de ezt nem mértem le máshol.
- **A ZED-ből indított sessionök átvétele.** §4.1 szerint nem lehetséges; hogy egy session
  „átköltöztethető-e" FleetView-PTY alá `--resume`-mal, nyitott kérdés — a session-fájl adott,
  tehát valószínűleg igen, de **nem mértem**.
- **A dashboard `web/` build-produktumának izoláltsága** (`CLAUDE.md` említi mint nem mért
  területet) — ez a munka is oda épül.

---

## 10. Az egy mondat, ami a felületet elfogadja

> Ránézek, és látom, hogy melyik agent dolgozik, melyik vár rám, és a rám várónak beírok —
> anélkül, hogy ZED-et váltanék.

Nem az, hogy az API helyes JSON-t ad. A `ui-quality.md` szerint az utolsó lépés az, hogy
**ránézünk** — szerkezeti számok (hány csempe renderelődött, nulla JS-hiba) ezt nem mérik.
