import "dotenv/config";
import { execSync, spawnSync } from "child_process";
import { createHash } from "crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "fs";
import { join, dirname } from "path";

const PROJECT_ROOT = join(__dirname, "..", "..");
const NEXT_DIR = join(PROJECT_ROOT, ".next");
const BUILD_COMMIT_PATH = join(NEXT_DIR, "BUILD_COMMIT");
const LEGACY_BUILD_ID_PATH = join(NEXT_DIR, "BUILD_ID");

function log(msg: string): void {
  console.log(`[global-setup] ${msg}`);
}

function warn(msg: string): void {
  console.warn(`[global-setup] ${msg}`);
}

/**
 * Kill any process bound to PW_PORT. A zombie `next start` left over from a
 * previous crashed gate run would otherwise bind the port and cause Playwright's
 * webServer to fail with "port already in use" — then the test suite hangs
 * waiting on a server that never comes up, burning the whole gate budget.
 */
function killStaleProcessOnPort(port: number): void {
  if (!port || !Number.isFinite(port)) return;
  if (process.platform !== "linux" && process.platform !== "darwin") {
    log(`platform ${process.platform} — skipping stale-process kill`);
    return;
  }
  const lsof = spawnSync("lsof", ["-ti", `:${port}`], { encoding: "utf8" });
  if (lsof.status === null || !lsof.stdout) return;
  const pids = lsof.stdout
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .filter((s) => /^\d+$/.test(s));
  if (pids.length === 0) return;
  warn(`killing ${pids.length} stale process(es) on port ${port}: ${pids.join(", ")}`);
  for (const pid of pids) {
    try {
      process.kill(Number(pid), "SIGKILL");
    } catch (err) {
      warn(`kill ${pid} failed: ${(err as Error).message}`);
    }
  }
}

/**
 * Validate .next/BUILD_COMMIT against the current git HEAD. When the SHA
 * mismatches (or when only the legacy .next/BUILD_ID marker is present),
 * remove .next/ so the webServer rebuilds against current source. This kills
 * the "stale clientReferenceManifest / wrong ISR manifest" class of bug that
 * otherwise appears as flaky hydration errors in unrelated e2e tests.
 */
function invalidateStaleBuild(): string | null {
  let headSha: string | null = null;
  try {
    headSha = execSync("git rev-parse HEAD", { cwd: PROJECT_ROOT, encoding: "utf8" })
      .trim()
      .slice(0, 40);
  } catch (err) {
    warn(`git rev-parse HEAD failed — skipping BUILD_COMMIT check: ${(err as Error).message}`);
    return null;
  }

  if (!existsSync(NEXT_DIR)) {
    return headSha;
  }

  const hasNewMarker = existsSync(BUILD_COMMIT_PATH);
  const hasLegacyMarker = existsSync(LEGACY_BUILD_ID_PATH);

  let invalidateReason: string | null = null;
  if (!hasNewMarker && hasLegacyMarker) {
    invalidateReason = `only legacy .next/BUILD_ID present (no BUILD_COMMIT for HEAD ${headSha.slice(0, 8)})`;
  } else if (!hasNewMarker) {
    invalidateReason = `no .next/BUILD_COMMIT marker (HEAD is ${headSha.slice(0, 8)})`;
  } else {
    try {
      const cachedSha = readFileSync(BUILD_COMMIT_PATH, "utf8").trim();
      if (cachedSha !== headSha) {
        invalidateReason = `.next/BUILD_COMMIT=${cachedSha.slice(0, 8)} mismatches HEAD=${headSha.slice(0, 8)}`;
      }
    } catch (err) {
      invalidateReason = `failed to read BUILD_COMMIT: ${(err as Error).message}`;
    }
  }

  if (invalidateReason) {
    warn(`invalidating .next/: ${invalidateReason}`);
    rmSync(NEXT_DIR, { recursive: true, force: true });
  } else {
    log(`.next/BUILD_COMMIT matches HEAD ${headSha.slice(0, 8)} — keeping build cache`);
  }

  return headSha;
}

/**
 * Persist the current HEAD SHA as the marker for the .next build that
 * Playwright's webServer is about to produce. Called after Prisma setup so
 * Next.js has a chance to rebuild when invalidateStaleBuild() removed .next/.
 */
function writeBuildCommitMarker(headSha: string | null): void {
  if (!headSha) return;
  try {
    mkdirSync(dirname(BUILD_COMMIT_PATH), { recursive: true });
    writeFileSync(BUILD_COMMIT_PATH, headSha, "utf8");
    log(`wrote .next/BUILD_COMMIT=${headSha.slice(0, 8)}`);
  } catch (err) {
    warn(`failed to write BUILD_COMMIT marker: ${(err as Error).message}`);
  }
}

async function globalSetup() {
  // NEXTAUTH_SECRET is generated at the top of playwright.config.ts so the
  // webServer child process inherits it via the `...process.env` spread.
  // globalSetup runs AFTER webServer is spawned and cannot influence its env.

  // Kill any zombie process on our assigned port BEFORE Next.js tries to bind.
  const port = Number(process.env.PW_PORT || process.env.PORT || 0);
  killStaleProcessOnPort(port);

  // Stale .next cache causes clientReferenceManifest errors after merges.
  // The BUILD_COMMIT marker replaces the previous "always rm -rf" behavior
  // with conditional invalidation — saves ~30s on unchanged worktrees.
  const headSha = invalidateStaleBuild();

  // Prisma 7+ blocks destructive operations when invoked by AI agents.
  // E2E tests always run against dev/test databases, so consent is implicit.
  const env = { ...process.env, PRISMA_USER_CONSENT_FOR_DANGEROUS_AI_ACTION: "true" };
  execSync("npx prisma generate", { stdio: "inherit", env });

  // Schema-hash cache — skip `db push --force-reset` when prisma/schema.prisma
  // is byte-identical to the previous run. `db push --force-reset` takes ~30s
  // on realistic schemas and runs on every worktree e2e gate; skipping it when
  // nothing changed saves substantial wall-clock on feature iterations that
  // don't touch the schema. Opt-out via PRISMA_FORCE_RESEED=1.
  const schemaPath = join(PROJECT_ROOT, "prisma", "schema.prisma");
  const cacheDir = join(PROJECT_ROOT, ".set");
  const cachePath = join(cacheDir, "seed-schema-hash");

  let schemaHash: string | null = null;
  if (existsSync(schemaPath)) {
    schemaHash = createHash("sha256")
      .update(readFileSync(schemaPath))
      .digest("hex");
  }

  let skipReset = false;
  if (
    !process.env.PRISMA_FORCE_RESEED &&
    schemaHash &&
    existsSync(cachePath)
  ) {
    try {
      const cachedHash = readFileSync(cachePath, "utf8").trim();
      if (cachedHash === schemaHash) {
        skipReset = true;
        log(`prisma schema unchanged (${schemaHash.slice(0, 8)}) — skipping db push --force-reset`);
      }
    } catch (err) {
      warn(`failed to read seed-schema-hash: ${(err as Error).message}`);
    }
  }

  if (!skipReset) {
    execSync("npx prisma db push --force-reset", { stdio: "inherit", env });
    if (schemaHash) {
      try {
        mkdirSync(cacheDir, { recursive: true });
        writeFileSync(cachePath, schemaHash, "utf8");
        log(`wrote seed-schema-hash=${schemaHash.slice(0, 8)}`);
      } catch (err) {
        warn(`failed to persist seed-schema-hash: ${(err as Error).message}`);
      }
    }
  }

  execSync("npx prisma db seed", { stdio: "inherit", env });

  writeBuildCommitMarker(headSha);
}

export default globalSetup;
