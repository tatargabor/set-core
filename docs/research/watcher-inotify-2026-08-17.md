# A fájlfigyelő két inotify-plafonja — mérés és két javasolt javítás

*2026-08-17. Nem a FleetView része: a FleetView kutatása közben derült ki, önálló, meglévő defekt
ebben a repóban. Minden szám ezen a gépen mért, a parancs mellette áll.*

---

## A tünet, ami most is fennáll

```bash
python3 -c "import ctypes,os;l=ctypes.CDLL('libc.so.6',use_errno=True);fd=l.inotify_init1(0);print(fd, os.strerror(ctypes.get_errno()) if fd<0 else 'ok')"
```

```
-1  Too many open files          ← errno 24, EMFILE
```

**A gépen nincs egyetlen szabad inotify példány sem** (126 / 128). Következmény: minden újonnan
felfegyverzett figyelő — új agent-munkamenet, új fájlfigyelő, bármi — némán visszaesik lassabb
pollra. A meglévők működnek tovább, tehát semmi nem hibázik láthatóan, és **a legfrissebben nyitott
munkamenet az, amelyik veszít**. Ez a legkellemetlenebb hibairány: az újat bünteti, csendben.

## Ki fogyasztja

```bash
for fd in /proc/*/fd/*; do [ "$(readlink $fd 2>/dev/null)" = "anon_inode:inotify" ] && echo "${fd#/proc/}"; done \
  | cut -d/ -f1 | sort | uniq -c | sort -rn | head
```

| tulajdonos | inotify példány | process |
|---|---|---|
| **`set-web` (ez a repó)** | **39** | **1** |
| agent-busz figyelők | 20 | 20 |
| agent-munkamenetek | 11 | 11 |
| rendszer, böngésző, egyéb | 55 | 45 |
| szerkesztő | 1 | 1 |

A legnagyobb egyetlen tétel a saját webszolgáltatásunk, **egyetlen processzben, egyetlen asyncio
event-loopban**, 39 példánnyal — a gép kapacitásának 31%-a. Uptime a mérés idején: 9 nap 23 óra.

## A második plafon, amit előbb senki nem nézett

```bash
grep -c "^inotify " /proc/<pid>/fdinfo/* | ...
```

```
inotify példány    :      39
watch-descriptor   : 178 327          ← ez a szám hiányzott a képből
max_user_watches   : 524 288          (34% egyetlen processzben)
```

**Két külön kernel-plafon van, és nem ugyanaz a javításuk:**

| | most | mi csökkenti | mit NEM old meg |
|---|---|---|---|
| **példány** (`max_user_instances`, 128) | 126 — **ez telített** | kevesebb figyelő-*hívás*, összevonás | a descriptorok szűrése nem érinti |
| **descriptor** (`max_user_watches`, 524 288) | 178 327 | a rekurzió megszüntetése | a példány-plafont nem érinti |

Ez a szétválasztás a legfontosabb rész. Aki csak az egyiket javítja, mérhető javulást lát egy
számban, miközben a rendszer ugyanúgy telített marad a másikon.

## Az ok — egy sor, és egy hiányzó paraméter

`lib/set_orch/watcher.py`, projektenként egy figyelő:

```python
watch_dirs.add(state_dir)
watch_dirs.add(log_dir)
if self.project_path.exists():
    watch_dirs.add(self.project_path)      # "Always watch project root for legacy file creation"
...
async for changes in awatch(*watch_dirs, poll_delay_ms=500):
```

Nincs `recursive=False`, és a watchfiles alapból rekurzív. Vagyis **minden regisztrált projekt
teljes fáját figyeljük** — `node_modules`-tól `.git`-ig — azért, hogy észrevegyük, ha egy fájl
megjelenik a projekt gyökerében.

Mérve, mind a 20 aktív projekt fáján:

```
teljes fa összesen                          119 723 könyvtár
node_modules/.git/.venv/dist nélkül          19 471   (−84%)
nem-rekurzív gyökérrel                          ~ 40   (−99,98%)
```

**A `node_modules` kizárása 84%-os javítás egy problémán, aminek a 99,98%-a egyetlen hiányzó
paraméterből jön.** Ezért a szűrés önmagában rossz válasz: jó számot ad egy rossz megoldásra.

## A két javasolt javítás, külön

1. **A gyökér ne legyen rekurzívan figyelve.** Amit a kód el akar kapni, az egy fájl *megjelenése*
   a gyökérben; ehhez nem kell a teljes fa. → 178 327 descriptor helyett ~40.
2. **A 20 külön `awatch`-hívás összevonása.** → 39 példány helyett ~1–3, ami a most telített
   plafont oldja.

Egyik sem helyettesíti a másikat.

## Nem szivárgás — mérve, három mintavétellel

Ez a dokumentum előbb nyitva hagyta, hogy a szám nő-e. Lezárva:

| mintavétel | fd | descriptor | a legnagyobb fd |
|---|---|---|---|
| T1 | 39 | 176 123 | 40 315 |
| T2 | 39 | **178 327** (+2 204) | 42 519 |
| T3 | 39 | **178 327** (változatlan) | 42 519 |

**A teljes növekmény egyetlen figyelőben jelentkezett**, a többi négy legnagyobb bájtra azonos
maradt, és új fd nem keletkezett. Egy szivárgás vagy több figyelőben mutatkozna, vagy új
fd-kben. Ami történt: **egy figyelt projekt könyvtárfája nőtt a lemezen** (épp automatizált
futás zajlott benne), és a figyelő ezt helyesen követte. A T3-ra a szám megállt.

**Két következménye van, és ellentétes irányúak:**

- **A sürgősség lefelé.** Nincs olyan óra, amikorra a szám magától elvinné a plafont, tehát a
  szolgáltatás újraindítását nem kell futó munka elé sorolni.
- **A szűréssel szembeni érv viszont erősödik.** A descriptor-szám nem attól függ, amit ez a repó
  csinál, hanem attól, amit a *figyelt projektekben mások* csinálnak: egy csomagtelepítés egy nagy
  fában egy lépésben hozzáadhat tízezret, előjelzés nélkül. A 178 ezer ma bőven fér az 524 288-ba,
  de **a fejtér nem ennek a repónak a kezében van.** A nem-rekurzív gyökér ezt kizárja; a
  `node_modules`-szűrés csak eltolja, mert a következő nagy fa amúgy is beleszámol.

## Amit NEM mértem — nyitott
- **A kernel-memória ára.** Descriptoronként néhány száz bájt nem kilapozható memória az irodalmi
  érték; 178 ezernél ez nagyságrendileg száz megabájt lenne. **Ezen a gépen nem ellenőriztem** — a
  szolgáltatás 530 MB-os RSS-e nem igazolja és nem cáfolja, mert az felhasználói memória, a
  descriptorok pedig kernel-oldalon vannak.
- **Hogy a 39 példányt konkrétan a watchfiles nyitja-e.** A kód és a szám egybevág, de a
  hozzárendelést process-szinten mértem, nem hívás-szinten.

## Hogyan derült ki — módszertani megjegyzés

Két agent négy körön át javította egymást, és **minden körben a mérés volt helyes és az
általánosítás hibás**:

1. „a headless munkamenetek nem jelennek meg" — de a mintában épp nem futott ilyen;
2. „nem frissítenek státuszt" — valójában a kulcs *hiányzik*, ami hamis nemlegest okoz;
3. „az árva figyelők eszik el a limitet" — attribúció mérés nélkül;
4. „processzenként egy példány" — a Node futtatókörnyezetre igaz, a Pythonra nem.

És egy ötödik, a sajátom, ami a legrosszabb fajta volt: **hibás mérés, magabiztosan előadva.** Egy
`"code" in cmd` substring-illesztés a saját webszerverünket „szerkesztőnek" sorolta be, mert a
projektek `~/code2/…` alatt vannak — 61 fd tévesen. A repó szabálykönyve épp ezt az osztályt
nevesíti.

A közös ok nem figyelmetlenség: **mindkét fél arról a futtatókörnyezetről általánosított, amit csak
a saját oldalán lát.** Amikor a következtetés átlép a másik oldalra, ott újra kell mérni.

Egy utolsó, amit érdemes megjegyezni: **a mérőeszköz maga is áldozatul esett a mért jelenségnek.**
Egy teszt, ami azt akarta megmérni, hány példányt nyit a watchfiles, minden változatra `0`-t adott
— nem azért, mert olcsó, hanem mert nem tudott nyitni. A nulla itt nem adat volt, hanem a hiba
maga.
