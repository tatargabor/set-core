---
paths:
  - "Dockerfile"
  - "docker-compose*"
  - ".github/**"
  - "next.config*"
---
# Deployment Conventions

## Migration-First Deploy
- Migrations run BEFORE the new application version starts
- Deploy sequence: migrate → build → start
- Never rely on `prisma db push` in production — always use migrations

## Health Check
- Provide `/api/health` endpoint returning `{ status: "ok" }`
- Use for readiness probes in Docker/Kubernetes/platform

## Environment Variables
- `.env.example` — all variables with placeholder values, committed
- `.env` — actual values, gitignored
- Secrets MUST use platform secret management in production
- Never commit actual secrets — use placeholders in examples
- When adding a new env var: ALWAYS add it to `.env.example` with a placeholder value and a comment explaining its purpose
- Group env vars by service (DATABASE, AUTH, STRIPE, EMAIL, etc.) in `.env.example`

## Build & Test
- `pnpm build` must succeed before deploy
- `pnpm test` must pass before merge
- Smoke test after deploy to verify basic functionality
