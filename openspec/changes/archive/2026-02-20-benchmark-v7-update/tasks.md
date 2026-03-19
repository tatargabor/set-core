## Tasks

- [x] Enable metrics in init-baseline.sh — After the `wt-deploy-hooks --no-memory .` line, add `mkdir -p "$HOME/.local/share/set-core/metrics" && touch "$HOME/.local/share/set-core/metrics/.enabled"`
- [x] Enable metrics in init-with-memory.sh — After the `wt-deploy-hooks .` line, add the same metrics enablement block
- [x] Strengthen recall-verify in with-memory.md — Replace the "Recall-then-verify" line with stronger wording about memory-induced overconfidence
- [x] Update run-guide.md Current Status to v7 — Replace v6 section, note test fixes done, add metrics integration, add Post-Run Metrics Analysis section
- [x] Enable metrics in synthetic init.sh — For modes b, c, d add metrics enablement after `wt-deploy-hooks` calls
