# set-core Makefile
#
# Screenshot pipeline for documentation

.PHONY: screenshots screenshots-web screenshots-cli screenshots-app screenshots-figma help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Screenshot pipeline ──

screenshots: screenshots-web screenshots-cli screenshots-app screenshots-figma ## Regenerate all documentation screenshots

screenshots-web: ## Web dashboard screenshots (requires running set-web on :7400)
	@echo "=== Web Dashboard Screenshots ==="
	@eval $$(scripts/detect-e2e-project.sh) && cd web && pnpm screenshot:docs

screenshots-cli: ## CLI output screenshots (requires set-core tools in PATH)
	@echo "=== CLI Screenshots ==="
	@python3 scripts/capture-cli-screenshots.py

screenshots-app: ## Consumer app screenshots (auto-detects latest done project)
	@echo "=== Consumer App Screenshots ==="
	@./scripts/capture-app-screenshots.sh $(APP_PROJECT)

screenshots-figma: ## Figma design preview screenshots
	@echo "=== Figma Design Screenshots ==="
	@python3 scripts/capture-figma-screenshots.py
