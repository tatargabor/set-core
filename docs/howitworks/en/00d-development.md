# Development History

The first commit of `set-core` dates to January 9, 2026 — at that point it lived in a private, internal repository as a simple worktree manager. Public development restarted in February (earlier history isn't visible in the git log due to a force push). In January-February the worktree lifecycle took shape (`set-new`, `set-merge`, `set-close`) along with the Ralph iterative loop. In February it became clear that manual coordination doesn't scale, and the first version of `set-orchestrate` was born: plan generation, DAG, parallel dispatch. Live runs (the sales-raketa project) brought the third chapter: the watchdog system, the verify pipeline, token budget control, and `set-sentinel` crash recovery. By March the spec digest pipeline, requirement coverage tracking, cascade failure handling, and phase-end E2E testing had matured. In the first week the system ran unsupervised for 5 minutes. Two months later it handles 5 hours — overnight, while sleeping, on production codebases.

\begin{keypoint}
The most important lesson: an orchestration system's value is not in handling the "happy path" — anyone can do that. The value is in error handling, recovery, and escalation. 80\% of the system deals with what can go wrong.
\end{keypoint}
