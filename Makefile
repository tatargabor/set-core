# set-core Makefile
#
# Screenshot pipeline for documentation

.PHONY: screenshots screenshots-web screenshots-cli screenshots-app help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Screenshot pipeline ──

screenshots: screenshots-web screenshots-cli screenshots-app ## Regenerate all documentation screenshots

screenshots-web: ## Web dashboard screenshots (requires running set-web on :7400)
	@echo "=== Web Dashboard Screenshots ==="
	@if [ -z "$$E2E_PROJECT" ]; then \
		E2E_PROJECT=$$(curl -sf http://localhost:7400/api/projects | python3 -c "\
import sys, json; \
ps = json.load(sys.stdin); \
done = [p for p in ps if p.get('status') == 'done' and p.get('changes_merged', 0) > 0]; \
done.sort(key=lambda p: p.get('last_updated', ''), reverse=True); \
print(done[0]['name'] if done else '')" 2>/dev/null); \
		if [ -z "$$E2E_PROJECT" ]; then echo "ERROR: No done project found. Set E2E_PROJECT."; exit 1; fi; \
		echo "Auto-detected project: $$E2E_PROJECT"; \
		cd web && E2E_PROJECT=$$E2E_PROJECT pnpm screenshot:docs; \
	else \
		cd web && pnpm screenshot:docs; \
	fi

screenshots-cli: ## CLI output screenshots (requires set-core tools in PATH)
	@echo "=== CLI Screenshots ==="
	python3 scripts/capture-cli-screenshots.py

screenshots-app: ## Consumer app screenshots (auto-detects latest done project)
	@echo "=== Consumer App Screenshots ==="
	./scripts/capture-app-screenshots.sh $(APP_PROJECT)
