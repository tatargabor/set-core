# Design: web-template-test-configs

## Decision 1: Vitest over Jest

**Choice**: Replace `jest.config.ts` with `vitest.config.ts`.

**Rationale**: Next.js 14+ projects predominantly use Vitest. In 3 E2E runs (craftbrew, minishop, micro-web), agents always created `vitest.config.ts` and ignored the template's `jest.config.ts`. The template should match reality.

**Config**:
```ts
import { defineConfig } from "vitest/config";
export default defineConfig({
  test: {
    exclude: ["tests/e2e/**", "node_modules/**"],
  },
});
```

The `exclude` for `tests/e2e/**` prevents Vitest from running Playwright tests (those run via `npx playwright test`).

## Decision 2: Playwright config with PW_PORT

**Choice**: Ship `playwright.config.ts` that reads `PW_PORT` env var.

**Rationale**: The integration gate sets `PW_PORT` per worktree (via `profile.e2e_gate_env(port)`). Without this in the Playwright config, all parallel agents use port 3000 → `ERR_SOCKET_NOT_CONNECTED`.

**Config**: Uses `process.env.PW_PORT || 3000` for `webServer.port` and `baseURL`. Screenshot `on`, chromium only, `webServer` starts `next dev`.

## Decision 3: Remove tailwind.config.ts

**Choice**: Remove from template entirely.

**Rationale**: Tailwind CSS v4 uses CSS-based configuration (`@theme` directive in CSS files). The JS config file is a v3 artifact. Agents in recent runs don't reference it.

## Decision 4: Discord in orchestration config

**Choice**: Add commented-out Discord section to the orchestration config template.

**Rationale**: E2E runners manually inject Discord config. The template should have it as a commented example so users know it's available.

## Decision 5: Keep components.json

**Choice**: Keep `components.json` (shadcn/ui) in template.

**Rationale**: Most web projects use shadcn/ui. It's a small file and agents reference it for component installation.

## File Layout After Change

```
modules/web/set_project_web/templates/nextjs/
├── manifest.yaml              (UPDATED — vitest, playwright, no tailwind)
├── vitest.config.ts           (NEW — replaces jest.config.ts)
├── playwright.config.ts       (NEW — with PW_PORT)
├── tsconfig.json              (unchanged)
├── postcss.config.mjs         (unchanged)
├── next.config.js             (unchanged)
├── components.json            (unchanged)
├── project-knowledge.yaml     (unchanged)
├── rules/                     (unchanged)
└── framework-rules/           (unchanged)
```

Removed: `jest.config.ts`, `tailwind.config.ts`
