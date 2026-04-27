# set-core Makefile
#
# Screenshot pipeline for documentation

.PHONY: screenshots screenshots-web screenshots-cli screenshots-app screenshots-design screenshots-figma help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Screenshot pipeline ──

screenshots: screenshots-web screenshots-cli screenshots-app screenshots-design ## Regenerate all documentation screenshots

screenshots-web: ## Web dashboard screenshots (requires running set-web on :7400)
	@echo "=== Web Dashboard Screenshots ==="
	@eval $$(scripts/detect-e2e-project.sh) && cd web && pnpm screenshot:docs

screenshots-cli: ## CLI output screenshots (requires set-core tools in PATH)
	@echo "=== CLI Screenshots ==="
	@python3 scripts/capture-cli-screenshots.py

screenshots-app: ## Consumer app screenshots (auto-detects latest done project; APP_PROJECT=<name> overrides)
	@echo "=== Consumer App Screenshots ==="
	@./scripts/capture-app-screenshots.sh $(APP_PROJECT)

screenshots-design: ## v0.app design source screenshots (auto-detects latest done v0-export; DESIGN_PROJECT=<name> overrides)
	@echo "=== v0 Design Source Screenshots ==="
	@./scripts/capture-design-screenshots.sh $(DESIGN_PROJECT)

screenshots-figma: ## DEPRECATED — superseded by screenshots-design (v0 export). Kept only for historical regen.
	@echo "=== Figma Design Screenshots (DEPRECATED) ==="
	@echo "  The Figma design pipeline was removed in v0-only-design-pipeline."
	@echo "  Use 'make screenshots-design' to capture v0.app exports instead."
	@echo "  This target remains so historical figma images can be regenerated"
	@echo "  if a Figma URL is still configured. Skipping."
	@exit 0
