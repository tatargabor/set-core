# Miért van erre szükség?

## A probléma

Az AI-alapú kódfejlesztő eszközök — mint a Claude Code, a Cursor, vagy a GitHub Copilot — forradalmasították az egyéni fejlesztői produktivitást. Egy fejlesztő egy session-ben képes órákon belül komplex feature-öket implementálni.

De mi van, ha a feladat **nem egy feature**, hanem *húsz*?

Egy közepes specifikáció (pl. egy SaaS alkalmazás következő verziója) tipikusan 10-30 önálló fejlesztési feladatot tartalmaz. Ezek között vannak függőségek: az autentikáció kell a profil oldalhoz, az API kell a dashboardhoz, a migrációk kellenek minden adatbázis-művelethez. Ha ezt kézzel menedzseljük:

- Egy-egy feature kész → kézzel merge, kézzel tesztelés
- Merge konfliktusok → kézzel feloldás, ismételt tesztelés
- Egy ágens elakad → kézzel debug, context-váltás, újraindítás
- Specifikáció változik → kézzel újratervezés, átprioritizálás
- Token budget elfogy → kézzel monitorozás, session újraindítás

Mindez **menedzsment overhead**: a fejlesztő idejének jelentős része nem kódolásra megy, hanem pipeline koordinációra.

## A megoldás: autonóm orchestráció

A `set-orchestrate` ezt az overheadet automatizálja. Egyetlen specifikációból kiindulva:

1. **Automatikusan megtervezi** a feladatokat (dekompozíció, DAG)
2. **Párhuzamosan végrehajtja** őket izolált worktree-kben
3. **Folyamatosan ellenőrzi** az ágenseket (15s poll, watchdog)
4. **Automatikusan teszteli és review-zza** a kész munkát (quality gate-ek)
5. **Összefésüli** az eredményt (merge, conflict resolution)
6. **Folytatja** a következő fázissal (auto-replan)

Ez azt jelenti, hogy egy specifikáció átadása után a rendszer akár *órákig* dolgozhat felügyelet nélkül, miközben a fejlesztő más feladatokkal foglalkozik — vagy alszik.

## Kinek szól?

Ez a rendszer **egyéni fejlesztőknek és kis csapatoknak** készült, akik AI ágensekkel dolgoznak. Nem helyettesíti a CI/CD-t (Jenkins, GitHub Actions) — kiegészíti, a *fejlesztési fázisban*, mielőtt a kód egyáltalán a CI pipeline-ba kerülne.

Tipikus felhasználási minta:

```
Reggel:   Spec átadása → set-orchestrate plan → start
Napközben: Más feladatok, meeting-ek, tervezés
Este:     set-orchestrate status → 12/15 change merged, 2 running, 1 failed
          Review → approve → a maradék megy tovább
Másnap:   Minden kész, PR nyitása
```

\begin{fontos}
A cél nem az, hogy az ember "ne kelljen". A cél az, hogy az ember ott kelljen, ahol az ember pótolhatatlan: a specifikáció írásánál, a tervezésnél, és a végső döntéseknél — nem a pipeline babysitting-jénél.
\end{fontos}

## Miben más, mint egy CI/CD rendszer?

| Szempont | CI/CD (pl. GitHub Actions) | set-orchestrate |
|----------|---------------------------|----------------|
| **Mikor fut** | Commit/PR után | Commit *előtt* — a fejlesztés közben |
| **Mit csinál** | Build, test, deploy | Tervezés, implementáció, teszt, merge |
| **Ki dolgozik** | Determinisztikus scriptek | AI ágensek (kreatív, adaptív) |
| **Hiba kezelés** | Fail → piros pipeline | Fail → retry, redispatch, escalate |
| **Párhuzamosság** | Job matrix (fix) | DAG-alapú, dinamikus dispatch |
| **Feedback loop** | Ember javít, újra push | Ágens javít, újra tesztel |

A kettő kiegészíti egymást: a `set-orchestrate` előállítja a kódot, a CI/CD pipeline validálja és deploy-olja.
