import "dotenv/config";
import { execSync } from "child_process";
import { existsSync, rmSync } from "fs";
import { join } from "path";

async function globalSetup() {
  // E2E secret check — generate a deterministic test secret if missing.
  // We do NOT fall back silently in playwright.config.ts to keep production
  // safety; instead, we set it here in the test bootstrap so the dev server
  // child process inherits it via process.env.
  if (!process.env.NEXTAUTH_SECRET) {
    process.env.NEXTAUTH_SECRET =
      "e2e-test-secret-do-not-use-in-production-32-chars-long";
  }

  // Clean stale .next cache — prevents clientReferenceManifest errors after merges
  const nextDir = join(__dirname, "../../.next");
  if (existsSync(nextDir)) {
    rmSync(nextDir, { recursive: true });
  }

  execSync("npx prisma generate", { stdio: "inherit" });
  execSync("npx prisma db push --force-reset", { stdio: "inherit" });
  execSync("npx prisma db seed", { stdio: "inherit" });
}

export default globalSetup;
