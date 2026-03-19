## 1. Update Playwright planning template

- [x] 1.1 In `lib/set_orch/templates.py`, update the Playwright E2E planning instruction (line ~297) to include `screenshot: 'on'` in the `playwright.config.ts` requirements. Change from: `Create playwright.config.ts with PW_PORT env var support and webServer auto-start` to: `Create playwright.config.ts with PW_PORT env var support, webServer auto-start, and screenshot: 'on' in the use section (without this, Playwright writes error-context.md text files instead of PNG screenshots)`
