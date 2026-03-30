import "dotenv/config";
import { execSync } from "child_process";
import { existsSync, rmSync } from "fs";
import { join } from "path";

async function globalSetup() {
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
