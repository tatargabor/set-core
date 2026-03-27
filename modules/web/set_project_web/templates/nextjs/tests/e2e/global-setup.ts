import { execSync } from "child_process";

async function globalSetup() {
  execSync("npx prisma generate", { stdio: "inherit" });
  execSync("npx prisma db push --force-reset", { stdio: "inherit" });
  execSync("npx prisma db seed", { stdio: "inherit" });
}

export default globalSetup;
