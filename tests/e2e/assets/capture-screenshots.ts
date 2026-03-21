import { chromium } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

// Standalone screenshot capture for the E2E benchmark report.
// NOT a Playwright test — run via: npx tsx tests/e2e/capture-screenshots.ts
//
// Requires a running dev/production server. Port from PW_PORT env (default 3000).

const PORT = process.env.PW_PORT || "3000";
const BASE = `http://localhost:${PORT}`;
const OUT_DIR = "e2e-screenshots";

const pages = [
  { name: "products", path: "/products" },
  { name: "product-detail", path: "/products" }, // will click first product
  { name: "cart", path: "/cart" },
  { name: "admin-login", path: "/admin/login" },
  { name: "admin-dashboard", path: "/admin" },
  { name: "admin-products", path: "/admin/products" },
];

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });

  for (const { name, path: pagePath } of pages) {
    try {
      const page = await context.newPage();

      // Admin pages need login first
      if (name.startsWith("admin-") && name !== "admin-login") {
        await page.goto(`${BASE}/admin/login`, { waitUntil: "networkidle", timeout: 10000 });
        // Try to register+login (idempotent)
        const emailInput = page.locator('input[type="email"], input[name="email"]');
        if (await emailInput.isVisible({ timeout: 2000 }).catch(() => false)) {
          await emailInput.fill("admin@test.com");
          const pwInput = page.locator('input[type="password"]');
          await pwInput.fill("admin123");
          const submitBtn = page.locator('button[type="submit"]');
          await submitBtn.click();
          await page.waitForTimeout(1000);
        }
      }

      if (name === "product-detail") {
        // Navigate to products then click first product
        await page.goto(`${BASE}/products`, { waitUntil: "networkidle", timeout: 10000 });
        const firstProduct = page.locator("a[href*='/products/']").first();
        if (await firstProduct.isVisible({ timeout: 3000 }).catch(() => false)) {
          await firstProduct.click();
          await page.waitForLoadState("networkidle");
        }
      } else {
        await page.goto(`${BASE}${pagePath}`, { waitUntil: "networkidle", timeout: 10000 });
      }

      await page.screenshot({
        path: path.join(OUT_DIR, `${name}.png`),
        fullPage: true,
      });
      console.log(`Captured: ${name}.png`);
      await page.close();
    } catch (err) {
      console.error(`Failed: ${name}.png — ${(err as Error).message}`);
    }
  }

  await browser.close();
}

main().catch(console.error);
