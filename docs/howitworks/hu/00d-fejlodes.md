# Fejlődéstörténet

A `set-core` első commitja 2026. január 9-re datálódik — ekkor még egy belső, privát repóban élt, egyszerű worktree-kezelőként. A publikus fejlesztés februárban indult újra (a korábbi history force push miatt nem látszik a git log-ban). Január-februárban alakult ki a worktree lifecycle (`set-new`, `set-merge`, `set-close`) és a Ralph iteratív loop. Februárban lett nyilvánvaló, hogy a kézi koordináció nem skálázódik, és megszületett a `set-orchestrate` első verziója: plan generálás, DAG, párhuzamos dispatch. Az éles futtatások (sales-raketa projekt) hozták a harmadik fejezetet: a watchdog rendszert, a verify pipeline-t, a token budget kontrollt, és a `set-sentinel` crash recovery-t. Márciusra érett be a spec digest pipeline, a requirement coverage tracking, a cascade failure kezelés, és a phase-end E2E tesztelés. Az első héten a rendszer 5 percig futott felügyelet nélkül. Két hónappal később 5 órát is kibír — éjszaka, alvás közben, production kódbázisokon.

\begin{fontos}
A legfontosabb tanulság: egy orchestrációs rendszer értéke nem a "happy path" kezelésében van — azt bárki megcsinálja. Az érték a hibakezelésben, a recovery-ben, és az eszkalációban van. A rendszer 80\%-a azzal foglalkozik, ami elromolhat.
\end{fontos}
