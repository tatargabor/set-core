import "dotenv/config";
import { execSync } from "child_process";
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
 * Validate that DATABASE_URL matches the provider declared in
 * `prisma/schema.prisma`. The orchestrator bootstraps `.env` from
 * `set/orchestration/config.yaml.env_vars` at worktree dispatch — if the
 * schema's `provider` is later changed (e.g. SQLite → PostgreSQL) the stale
 * `.env` carries the wrong URL forward and `npx prisma db push` crashes
 * deep inside Prisma with no Playwright-parseable failure list. Catch the
 * mismatch up front with a clear, actionable error instead.
 *
 * Recovery: when `.env` carries a wrong provider URL (e.g. the orchestrator
 * reset it from a stale template), attempt to self-heal from
 * `set/orchestration/config.yaml env_vars.DATABASE_URL` before throwing.
 *
 * Belt-and-suspenders: the gate-runner Python side has a parallel self-heal
 * (`_self_heal_db_env_drift` in `modules/web/set_project_web/gates.py`) that
 * fires when this pre-flight is absent or could not recover. The TS pre-flight
 * is the cheaper path — it runs in the same process as Prisma init so it
 * catches the bad state before any DB command touches the wrong URL.
 */
function validateDatabaseUrl(): void {
  const schemaPath = join(PROJECT_ROOT, "prisma", "schema.prisma");
  if (!existsSync(schemaPath)) return;

  const schema = readFileSync(schemaPath, "utf8");
  const providerMatch = schema.match(
    // [^}]*? + 's' flag would be cleaner but requires ES2018; the negated
    // class works on older targets and is sufficient for `datasource X { ... }`
    /datasource\s+\w+\s*\{[^}]*provider\s*=\s*"([^"]+)"/,
  );
  if (!providerMatch) return;
  const provider = providerMatch[1];

  const expected: Record<string, RegExp> = {
    postgresql: /^postgres(ql)?:\/\//i,
    mysql: /^mysql:\/\//i,
    sqlite: /^file:/i,
    sqlserver: /^sqlserver:\/\//i,
  };
  const matcher = expected[provider];

  let url = process.env.DATABASE_URL;

  // If the URL is missing or mismatches the schema provider, try to recover
  // from set/orchestration/config.yaml before failing. The orchestrator may
  // have reset .env from a stale template that still points at the old provider.
  if (!url || (matcher && !matcher.test(url))) {
    const configPath = join(PROJECT_ROOT, "set", "orchestration", "config.yaml");
    if (existsSync(configPath)) {
      try {
        const configText = readFileSync(configPath, "utf8");
        // Simple line-by-line extraction — avoids a YAML parser dependency.
        // Matches: `  DATABASE_URL: "postgresql://..."` or `  DATABASE_URL: postgresql://...`
        const match = configText.match(
          /^\s*DATABASE_URL:\s*["']?([^\s"'\n]+)["']?\s*$/m,
        );
        if (match) {
          const configUrl = match[1];
          if (!matcher || matcher.test(configUrl)) {
            warn(
              `DATABASE_URL in .env ("${(url ?? "").replace(/:[^:@]*@/, ":****@")}") ` +
                `does not match schema provider="${provider}". ` +
                `Auto-correcting from set/orchestration/config.yaml.`,
            );
            process.env.DATABASE_URL = configUrl;
            url = configUrl;
          }
        }
      } catch (err) {
        warn(
          `failed to read set/orchestration/config.yaml for DATABASE_URL recovery: ${(err as Error).message}`,
        );
      }
    }
  }

  if (!url) {
    throw new Error(
      `[global-setup] DATABASE_URL is not set. ` +
        `prisma/schema.prisma declares provider="${provider}" — ` +
        `set DATABASE_URL in .env or via set/orchestration/config.yaml env_vars.`,
    );
  }

  if (matcher && !matcher.test(url)) {
    throw new Error(
      `[global-setup] DATABASE_URL/schema provider mismatch — ` +
        `schema.prisma provider="${provider}" but DATABASE_URL="${url.replace(/:[^:@]*@/, ":****@")}". ` +
        `Update .env (or set/orchestration/config.yaml env_vars.DATABASE_URL) to match the schema provider.`,
    );
  }
  log(`DATABASE_URL provider OK (schema="${provider}")`);
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
  //
  // Zombie port cleanup lives in the orchestrator gate-runner (Python side)
  // because globalSetup runs AFTER Playwright's webServer has already bound
  // the port — killing anything listening here would kill our own server.

  // Fail fast on DATABASE_URL/schema-provider mismatch. Prevents the silent
  // crash where `prisma db push --force-reset` dies deep with no Playwright-
  // parseable failure list (root cause when .env carries a stale provider URL
  // from worktree bootstrap that no longer matches schema.prisma).
  // Recovers from set/orchestration/config.yaml.env_vars.DATABASE_URL when
  // possible; throws an actionable error otherwise.
  validateDatabaseUrl();

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
