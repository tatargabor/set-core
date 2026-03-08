# MiniShop API

Minimal Express.js webshop API.

## Tech Stack

- **Runtime:** Node.js
- **Framework:** Express.js
- **Database:** better-sqlite3 (SQLite, local file)
- **Testing:** Jest + supertest
- **Auth:** jsonwebtoken + bcryptjs (used in change 4)

## Commands

- `npm test` — run all tests
- `npm start` — start the server

## File Conventions

- **Routes:** `src/routes/<feature>.js` — export an Express Router
- **Tests:** `tests/<feature>.test.js` — use supertest for HTTP assertions
- **Middleware:** `src/middleware/<name>.js` — export a middleware function

## Database Access

- Import directly: `const db = require('../db')`
- Inline SQL in route handlers — no service layer, no ORM
- Database path from `DATABASE_PATH` env var (default: `./minishop.db`)
- For tests, set `DATABASE_PATH=:memory:` or truncate tables in `beforeEach`
- `PRAGMA foreign_keys = ON` is set globally — FK constraints are enforced

## Error Handling

- Use `try/catch` in async route handlers
- Call `next(err)` to pass errors to the global error handler
- The global error handler at `src/middleware/errors.js` returns `{"error": "message"}` with status 500
- Do NOT use inline `res.status(500)` — always use `next(err)`

## Session / Cookie

- `cookie-parser` middleware is mounted globally
- Session ID comes from the `session_id` cookie
- If no `session_id` cookie exists, generate a UUID and set it: `res.cookie('session_id', uuid, { httpOnly: true })`
- Use `const { v4: uuidv4 } = require('uuid')` for UUID generation

## Environment Variables

- `PORT` — server port (default: 3000)
- `JWT_SECRET` — required for auth (default: none, must be set)
- `DATABASE_PATH` — SQLite file path (default: `./minishop.db`)

See `.env.example` for all variables.

## Future: Auth (change 4)

> **Do NOT implement auth until the auth change runs.** This section describes conventions for when that change is implemented.

- JWT token in `Authorization: Bearer <token>` header
- Auth middleware at `src/middleware/auth.js`, export `authMiddleware`
- Protected routes use `router.use(authMiddleware)` for POST/PUT/DELETE
- GET endpoints remain public (no auth required)
- `POST /api/register` — create user, return JWT
- `POST /api/login` — validate credentials, return JWT
- The `users` table already exists in the database schema — do NOT recreate it
