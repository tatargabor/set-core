/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    // Defaults chosen for dev + E2E test runs:
    //
    // - `unoptimized: true` bypasses the Next.js image optimization pipeline
    //   entirely, so any remote host (including placehold.co used in seed
    //   fixtures) works without a `remotePatterns` allowlist.
    //
    // - `dangerouslyAllowSVG: true` is required because seed data + examples
    //   commonly reference placehold.co which serves SVG, not PNG. Without
    //   this, Next.js <Image> rejects SVG sources with the error
    //   "type image/svg+xml but dangerouslyAllowSVG is disabled".
    //
    // - `contentSecurityPolicy` neutralises the SVG-as-script risk that
    //   `dangerouslyAllowSVG` would otherwise enable. Blocks scripts,
    //   sandboxes the image context.
    //
    // If you add `remotePatterns` for a production CDN, DO NOT simultaneously
    // remove `unoptimized` AND `dangerouslyAllowSVG`/`contentSecurityPolicy` —
    // that breaks the placehold.co fallback used by seeded data. Either keep
    // the SVG settings, or replace ALL placehold.co references in
    // prisma/seed.ts + fixtures with real PNG/JPG CDN URLs.
    unoptimized: true,
    dangerouslyAllowSVG: true,
    contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
  },
};

module.exports = nextConfig;
