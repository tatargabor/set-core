#!/usr/bin/env tsx
/**
 * i18n completeness check — ensures every `useTranslations('ns')` + `t('ns.key')`
 * referenced in src/ has a matching entry in messages/<locale>.json for every
 * locale. Exits non-zero on missing keys with a structured report.
 *
 * Run from project root:
 *   npx tsx scripts/check-i18n-completeness.ts
 *   SET_I18N_CHECK_ROOT=/path/to/project npx tsx scripts/check-i18n-completeness.ts
 *
 * Flags env:
 *   SET_I18N_CHECK_SRC    — comma-separated source globs (default: "src")
 *   SET_I18N_CHECK_MSGS   — messages dir (default: "messages")
 *   SET_I18N_CHECK_LOCALES— comma-separated locales (default: all *.json files)
 */

import * as fs from "node:fs";
import * as path from "node:path";

type LocaleData = Record<string, unknown>;
type Missing = { locale: string; key: string; file: string; line: number };

const ROOT = process.env.SET_I18N_CHECK_ROOT || process.cwd();
const SRC_DIRS = (process.env.SET_I18N_CHECK_SRC || "src").split(",");
const MSGS_DIR = process.env.SET_I18N_CHECK_MSGS || "messages";

function walk(dir: string, acc: string[] = []): string[] {
  if (!fs.existsSync(dir)) return acc;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
      walk(p, acc);
    } else if (/\.(tsx?|jsx?|mjs|cjs)$/.test(entry.name)) {
      acc.push(p);
    }
  }
  return acc;
}

function loadLocales(): Record<string, LocaleData> {
  const absMsgs = path.join(ROOT, MSGS_DIR);
  if (!fs.existsSync(absMsgs)) {
    console.error(`[i18n-check] messages dir not found: ${absMsgs}`);
    process.exit(2);
  }
  const specified = process.env.SET_I18N_CHECK_LOCALES;
  const files = specified
    ? specified.split(",").map((l) => `${l.trim()}.json`)
    : fs
        .readdirSync(absMsgs)
        .filter((f) => /^[a-z]{2}(-[A-Z]{2})?\.json$/.test(f));

  const out: Record<string, LocaleData> = {};
  for (const f of files) {
    const locale = f.replace(/\.json$/, "");
    try {
      out[locale] = JSON.parse(fs.readFileSync(path.join(absMsgs, f), "utf8"));
    } catch (err) {
      console.error(`[i18n-check] failed to parse ${f}: ${(err as Error).message}`);
      process.exit(2);
    }
  }
  return out;
}

function hasKey(obj: unknown, dotted: string): boolean {
  const parts = dotted.split(".");
  let cur: unknown = obj;
  for (const p of parts) {
    if (typeof cur !== "object" || cur === null) return false;
    if (!(p in (cur as Record<string, unknown>))) return false;
    cur = (cur as Record<string, unknown>)[p];
  }
  return true;
}

// Capture: `const <var> = useTranslations('ns')` / `getTranslations('ns')` /
//          `getTranslations({ namespace: 'ns' })` / `await getTranslations(...)`
const RE_VAR_BINDING = /(?:const|let|var)\s+(\w+)\s*=\s*(?:await\s+)?(?:useTranslations|getTranslations)\(\s*(?:{[^}]*namespace:\s*)?['"`]([^'"`]+)['"`]/g;
// Any `t(` / `<var>(` call with a string-literal first argument.
const RE_VAR_CALL = /\b(\w+)\(\s*['"`]([^'"`${}]+)['"`]/g;

type Reference = { file: string; line: number; namespace: string; key: string };

function extractRefs(file: string): Reference[] {
  const source = fs.readFileSync(file, "utf8");
  const lines = source.split("\n");
  const refs: Reference[] = [];

  // Map of <variable> → <namespace>. Populated by scanning for
  // `const X = useTranslations('ns')` / `getTranslations('ns')` bindings.
  // When we see a call `X('key')`, the full key is `<ns>.<key>`.
  const varToNs = new Map<string, string>();
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    RE_VAR_BINDING.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = RE_VAR_BINDING.exec(line)) !== null) {
      varToNs.set(m[1], m[2]);
    }
  }

  if (varToNs.size === 0) return refs;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    RE_VAR_CALL.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = RE_VAR_CALL.exec(line)) !== null) {
      const varName = m[1];
      const rawKey = m[2];
      const ns = varToNs.get(varName);
      if (!ns) continue; // not a translation call — skip
      if (rawKey.includes("${") || rawKey.includes("{")) continue;
      const key = `${ns}.${rawKey}`;
      refs.push({ file, line: i + 1, namespace: ns, key });
    }
  }
  return refs;
}

function main(): void {
  const locales = loadLocales();
  const localeNames = Object.keys(locales);
  if (localeNames.length === 0) {
    console.error(`[i18n-check] no locale files found in ${MSGS_DIR}/`);
    process.exit(2);
  }

  const files: string[] = [];
  for (const d of SRC_DIRS) walk(path.join(ROOT, d), files);

  const allRefs: Reference[] = [];
  for (const f of files) {
    try {
      allRefs.push(...extractRefs(f));
    } catch (err) {
      console.error(`[i18n-check] skipping ${f}: ${(err as Error).message}`);
    }
  }

  // Deduplicate refs by (key) — same key referenced many times only reported once.
  const seen = new Map<string, Reference>();
  for (const r of allRefs) {
    if (!seen.has(r.key)) seen.set(r.key, r);
  }
  const uniqueRefs = [...seen.values()];

  const missing: Missing[] = [];
  for (const ref of uniqueRefs) {
    for (const locale of localeNames) {
      if (!hasKey(locales[locale], ref.key)) {
        missing.push({ locale, key: ref.key, file: path.relative(ROOT, ref.file), line: ref.line });
      }
    }
  }

  console.log(
    `[i18n-check] scanned ${files.length} files, ${uniqueRefs.length} unique keys, ${localeNames.length} locales: ${localeNames.join(", ")}`
  );

  if (missing.length === 0) {
    console.log(`[i18n-check] OK — all translation keys present in all locales`);
    process.exit(0);
  }

  const byLocale = new Map<string, Missing[]>();
  for (const m of missing) {
    if (!byLocale.has(m.locale)) byLocale.set(m.locale, []);
    byLocale.get(m.locale)!.push(m);
  }

  console.error(`\n[i18n-check] FAIL — ${missing.length} missing translation(s):\n`);
  for (const [locale, list] of byLocale) {
    console.error(`  ${locale}.json is missing ${list.length} key(s):`);
    for (const m of list.slice(0, 50)) {
      console.error(`    - ${m.key}    (used at ${m.file}:${m.line})`);
    }
    if (list.length > 50) {
      console.error(`    ... and ${list.length - 50} more`);
    }
    console.error("");
  }
  console.error(
    `Fix: add the missing keys to messages/<locale>.json, mirroring the key set across locales.\n`
  );
  process.exit(1);
}

main();
