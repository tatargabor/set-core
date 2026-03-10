# Merge és Delivery

## Merge Queue

Amikor egy change sikeresen átmegy minden minőségi kapun, a merge queue-ba kerül. A queue feldolgozása a `merge_policy` direktíva szerint történik.

![A merge pipeline és post-merge folyamat](diagrams/rendered/08-merge-pipeline.png){width=90%}

## Merge Policy

Három merge policy létezik:

### eager

A change azonnal merge-elődik, amint a verify pipeline végére ér.

```yaml
merge_policy: eager
```

Előny: gyors delivery, a többi worktree hamarabb kap friss main-t.
Hátrány: nincs lehetőség csoportos áttekintésre.

### checkpoint (alapértelmezett)

N db change után a rendszer megáll és emberi jóváhagyást kér.

```yaml
merge_policy: checkpoint
checkpoint_every: 3
```

Folyamat:

1. A 3. change befejeződik → checkpoint aktiválódik
2. Az orchestrátor megáll (status: `checkpoint`)
3. Az ember áttekinti a merge queue-t
4. `wt-orchestrate approve --merge` → merge + folytatás

### manual

Minden merge emberi jóváhagyást igényel.

```yaml
merge_policy: manual
```

## A merge folyamat

A `merge_change()` három esetet kezel:

### Eset 1: Branch már nem létezik

Ha a `change/<name>` branch már nem létezik (valaki kézzel mergelte és törölte):

- Státusz → `merged`
- Worktree cleanup
- Change archiválás

### Eset 2: Branch már be van mergelve

Ha a branch létezik, de már a HEAD őse:

- Státusz → `merged`
- Cleanup

### Eset 3: Normál merge (a gyakori)

A `wt-merge` parancs végzi a tényleges merge-t:

```bash
wt-merge <change-name> --no-push --llm-resolve
```

## 3-rétegű Conflict Resolution

Merge konfliktus esetén három szinten próbál a rendszer feloldást:

### 1. réteg: Generált fájlok (automatikus)

A `sync_worktree_with_main()` és a merge logika automatikusan kezeli a generált fájlok konfliktusait:

- `package-lock.json`
- `yarn.lock`, `pnpm-lock.yaml`
- `*.tsbuildinfo`

Ezeket `--ours` stratégiával oldja fel (a worktree verziója nyer).

### 2. réteg: LLM merge (`--llm-resolve`)

Ha valódi kód konfliktus van, a `wt-merge --llm-resolve` egy Claude ágenst hív:

1. A conflicted fájlok átadása az LLM-nek
2. Az LLM megérti mindkét oldal szándékát
3. Az LLM össze merge-li a változtatásokat
4. Az eredmény commit-olódik

### 3. réteg: Emberi beavatkozás

Ha az LLM sem tudja feloldani a konfliktust:

- A change `merge_blocked` státuszba kerül
- Notification küldése
- Az ember kézi merge-t végez
- Az orchestrátor a következő poll-ban észleli az új állapotot

## Post-Merge Pipeline

Sikeres merge után a következő lépések futnak:

### 1. Futó worktree-k szinkronizálása

A `_sync_running_worktrees()` biztosítja, hogy a többi aktív worktree megkapja a friss main-t:

```
main ← merge(auth-system)
  ↓ sync
  worktree/user-profile ← git merge main
  worktree/api-endpoints ← git merge main
```

Ez megakadályozza, hogy a többi ágens elavult kódra építsen.

### 2. Base build ellenőrzés

A merge után a base build cache érvénytelenítődik (`BASE_BUILD_STATUS=""`), és a következő verify gate újraellenőrzi, hogy a main branch buildelhető-e.

### 3. Post-merge command

Ha van `post_merge_command` konfigurálva:

```yaml
post_merge_command: "pnpm db:generate"
```

Ez a parancs a merge után fut le a projekt gyökerében. Tipikus használat:

- Adatbázis migráció generálás (`prisma generate`, `drizzle-kit generate`)
- Build artifact frissítés
- Cache invalidálás

### 4. Change archiválás

A `archive_change()` az OpenSpec change könyvtárat az archívumba mozgatja:

```
openspec/changes/auth-system/
  → openspec/changes/archive/2026-03-10-auth-system/
```

### 5. Post-merge hook

Ha van `hook_post_merge` konfigurálva, az lefut a change nevével mint argumentum.

### 6. Coverage frissítés

A `update_coverage_status()` frissíti a requirement lefedettséget: a change-hez rendelt REQ-XXX azonosítók `merged` státuszba kerülnek.

## Checkpoint és Approval

### Checkpoint aktiválás

Checkpoint az alábbi esetekben aktiválódik:

| Trigger | Leírás |
|---------|--------|
| `checkpoint_every: N` | N merge után |
| `token_hard_limit` | Token hard limit elérése |
| Manuális | `wt-orchestrate pause --all` |

### Approval folyamat

```bash
wt-orchestrate approve            # jóváhagyás, folytatás
wt-orchestrate approve --merge    # jóváhagyás + azonnali merge flush
```

A `--merge` flag a merge queue-ban várakozó change-eket azonnal merge-li.

### Auto-approve (E2E futtatásokhoz)

```yaml
checkpoint_auto_approve: true
```

Ez felügyelet nélküli futtatásokhoz használatos (pl. CI/CD, E2E tesztelés).

\begin{fontos}
A merge policy a projekthez és a csapat igényeihez igazítandó. Kis projekteknél az eager policy a leghatékonyabb. Nagyobb projekteknél a checkpoint policy biztosítja, hogy az ember lássa az eredményt, mielőtt túl sok change merge-elődne.
\end{fontos}

## Merge retry intelligencia

Ha egy merge sikertelen (pl. build hiba merge után), a rendszer:

1. A build kimenetet menti (`build_output`)
2. A change-et `merge_blocked` státuszba rakja
3. A következő poll-ban újrapróbálja
4. Ha a `fix_base_build_with_llm()` elérhető, LLM-mel próbálja javítani a hibát
