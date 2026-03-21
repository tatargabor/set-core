# Database Type Safety

## NEVER use `any` type on database client parameters

When a database model is missing from the schema (Prisma, Drizzle, TypeORM, etc.), the correct fix is to **add the missing model to the schema** — not to bypass TypeScript with type hacks.

### Forbidden patterns

```typescript
// ALL of these are FORBIDDEN:
prisma: any
prisma as any
(prisma as any).modelName
db: any
```

### Why this matters

Using `any` converts a compile-time error into a runtime error. The build passes, tests pass (because they mock the DB), but the application crashes with 500 errors in production. The verify gate cannot catch what TypeScript cannot see.

### What to do instead

If you encounter a missing model error like `Property 'session' does not exist on type 'PrismaClient'`:

1. Check `prisma/schema.prisma` (or equivalent) for the missing model
2. If the model is missing, **add it** — copy from the feature branch, design doc, or spec
3. Run `npx prisma generate` (or equivalent) to update the client
4. Import and use the typed client normally

### This rule applies to all database ORMs

- Prisma: `prisma: any`, `prisma as any`
- Drizzle: `db: any`, `db as any`
- TypeORM: `connection: any`, `repository: any`
- Sequelize: `sequelize: any`
- Any other ORM where the client type encodes the schema
