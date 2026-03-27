import { chromium } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

/**
 * Standalone screenshot capture for consumer app documentation.
 * NOT a Playwright test — run via: npx tsx capture-screenshots.ts
 *
 * Features:
 * - Auto-discovers Next.js App Router pages from src/app/
 * - Falls back to hardcoded routes for known scaffolds
 * - Handles admin login for protected pages
 * - Outputs PNGs to specified directory
 *
 * Environment variables:
 *   PW_PORT       — Dev server port (default: 3000)
 *   APP_OUT_DIR   — Output directory (default: e2e-screenshots)
 *   PROJECT_DIR   — Project root for route auto-discovery (default: cwd)
 */

const PORT = process.env.PW_PORT || "3000";
const BASE = `http://localhost:${PORT}`;
const OUT_DIR = process.env.APP_OUT_DIR || "e2e-screenshots";
const PROJECT_DIR = process.env.PROJECT_DIR || process.cwd();

interface PageDef {
  name: string;
  path: string;
  /** If true, click the first link matching a[href*='/products/'] after navigating */
  clickFirstLink?: boolean;
  /** If true, requires admin login before navigation */
  requiresAuth?: boolean;
}

/** Known fallback routes for common scaffolds */
const FALLBACK_ROUTES: PageDef[] = [
  { name: "home", path: "/" },
  { name: "products", path: "/products" },
  { name: "product-detail", path: "/products", clickFirstLink: true },
  { name: "cart", path: "/cart" },
  { name: "admin-login", path: "/admin/login" },
  { name: "admin-dashboard", path: "/admin", requiresAuth: true },
  { name: "admin-products", path: "/admin/products", requiresAuth: true },
];

/**
 * Auto-discover static routes from Next.js App Router (src/app/).
 * Skips dynamic routes ([param]) and API routes.
 */
function discoverRoutes(projectDir: string): PageDef[] {
  const appDir = path.join(projectDir, "src", "app");
  if (!fs.existsSync(appDir)) return [];

  const routes: PageDef[] = [];

  function walk(dir: string, prefix: string) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) {
        if (entry.name === "page.tsx" || entry.name === "page.js") {
          // Skip dynamic routes and API routes
          if (prefix.includes("[") || prefix.includes("/api")) continue;
          const routePath = prefix || "/";
          const name = routePath === "/" ? "home" : routePath.slice(1).replace(/\//g, "-");
          routes.push({
            name,
            path: routePath,
            requiresAuth: routePath.startsWith("/admin") && routePath !== "/admin/login" && routePath !== "/admin/register",
          });
        }
        continue;
      }
      const dirName = entry.name;
      // Skip dynamic segments, API dirs, and internal dirs
      if (dirName.startsWith("[") || dirName === "api" || dirName.startsWith("_")) continue;
      // Next.js route groups — strip parens from path
      const segment = dirName.startsWith("(") && dirName.endsWith(")") ? "" : `/${dirName}`;
      walk(path.join(dir, dirName), prefix + segment);
    }
  }

  walk(appDir, "");

  // Deduplicate by path
  const seen = new Set<string>();
  return routes.filter((r) => {
    if (seen.has(r.path)) return false;
    seen.add(r.path);
    return true;
  });
}

async function main() {
  // Try auto-discovery first, fall back to known routes
  let pages = discoverRoutes(PROJECT_DIR);
  if (pages.length === 0) {
    console.log("No src/app/ found, using fallback routes");
    pages = FALLBACK_ROUTES;
  } else {
    console.log(`Auto-discovered ${pages.length} routes from ${PROJECT_DIR}/src/app/`);
    // Add product-detail click-through if products page exists
    if (pages.some((p) => p.path === "/products")) {
      pages.push({ name: "product-detail", path: "/products", clickFirstLink: true });
    }
  }

  fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  let loggedIn = false;

  for (const pageDef of pages) {
    try {
      const page = await context.newPage();

      // Admin pages need login first
      if (pageDef.requiresAuth && !loggedIn) {
        await page.goto(`${BASE}/admin/login`, { waitUntil: "networkidle", timeout: 10000 });
        const emailInput = page.locator('input[type="email"], input[name="email"]');
        if (await emailInput.isVisible({ timeout: 2000 }).catch(() => false)) {
          await emailInput.fill("admin@test.com");
          const pwInput = page.locator('input[type="password"]');
          await pwInput.fill("admin123");
          const submitBtn = page.locator('button[type="submit"]');
          await submitBtn.click();
          await page.waitForTimeout(1000);
          loggedIn = true;
        }
      }

      if (pageDef.clickFirstLink) {
        await page.goto(`${BASE}${pageDef.path}`, { waitUntil: "networkidle", timeout: 10000 });
        const firstLink = page.locator("a[href*='/products/']").first();
        if (await firstLink.isVisible({ timeout: 3000 }).catch(() => false)) {
          await firstLink.click();
          await page.waitForLoadState("networkidle");
        }
      } else {
        await page.goto(`${BASE}${pageDef.path}`, { waitUntil: "networkidle", timeout: 10000 });
      }

      await page.screenshot({
        path: path.join(OUT_DIR, `${pageDef.name}.png`),
        fullPage: true,
      });
      console.log(`  Captured: ${pageDef.name}.png`);
      await page.close();
    } catch (err) {
      console.error(`  Failed: ${pageDef.name}.png — ${(err as Error).message}`);
    }
  }

  await browser.close();
  console.log(`\nDone. ${pages.length} screenshots in ${OUT_DIR}/`);
}

main().catch(console.error);
